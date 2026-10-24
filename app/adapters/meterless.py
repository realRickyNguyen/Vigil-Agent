"""Meterless Nightshift adapter, the app's only model provider.
OpenAI-compatible POST {METERLESS_BASE_URL}/chat/completions with the Runtime token,
the meterless-app header and meterless-scope: user. The NVIDIA key stays inside Nightshift."""
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request

from app.config import Settings
from app.tracing import Timer, Tracer


class MeterlessError(RuntimeError):
    pass


class MeterlessUnauthorized(MeterlessError):
    pass


class MeterlessDeadline(MeterlessError):
    """Nightshift ended the provider call at its deadline. Retrying the same prompt mostly hits it again."""


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a model reply, ignoring <think> blocks and code fences.
    Nemotron Ultra (via Nightshift) returns its reasoning inline, ending in </think> with no opening tag."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start:end + 1])


def nightshift_steps(response: dict) -> dict | None:
    """What Nightshift did to one call, from the compute receipt it returns inline (response["meterless"]
    ["receipt"]). Nightshift can add its own steps: H-MEM injects earlier answers into the prompt after our app
    sends it, so the injected text never appears in our trace, and the reasoning scaffold can add a planning call.
    On 23 Oct memory was injected into 32 of 34 calls and we found no switch for it, so every call records it."""
    receipt = (response.get("meterless") or {}).get("receipt")
    if not receipt:
        return None  # not served by Nightshift, or an older Nightshift without inline receipts
    hmem = receipt.get("hmem") or {}
    scaffold = receipt.get("reasoning_scaffold") or {}
    return {"receipt_id": receipt.get("receipt_id"),
            "hmem_injected": hmem.get("injected", 0), "hmem_ids": hmem.get("ids", []),
            "scaffold_active": bool(scaffold.get("active")), "scaffold_variant": scaffold.get("variant"),
            "phases": [p.get("phase") for p in receipt.get("phases") or []],
            "context_sources": ((receipt.get("egress") or {}).get("sent") or {}).get("context_sources", []),
            "mode": receipt.get("mode")}


RATE_LIMIT_RETRIES = 3  # NVIDIA 429s clear with time, unlike the provider deadline
RATE_LIMIT_PAUSE = 15  # seconds, times the number of 429s in a row


class NightshiftClient:
    def __init__(self, settings: Settings, tracer: Tracer):
        if not settings.meterless_token:
            raise MeterlessError("METERLESS_RUNTIME_TOKEN is not set")
        self.s = settings
        self.tracer = tracer
        # Shared by every worker thread: after a 429, all calls wait until the cool-down ends. On 24 Oct a third
        # back-to-back run with four parallel calls got 33 NVIDIA 429s; each retry 5 s later hit the cap again.
        self._lock = threading.Lock()
        self._cooldown_until = 0.0
        self._rate_limited = 0

    def _wait_for_cooldown(self) -> None:
        with self._lock:
            wait = self._cooldown_until - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def _rate_limited_now(self) -> float:
        """Start or extend the shared cool-down; returns its length in seconds."""
        with self._lock:
            self._rate_limited += 1
            pause = RATE_LIMIT_PAUSE * min(self._rate_limited, 3)
            self._cooldown_until = max(self._cooldown_until, time.monotonic() + pause)
            return pause

    def _rate_ok(self) -> None:
        with self._lock:
            self._rate_limited = 0

    def _post(self, body: dict) -> dict:
        headers = {"Content-Type": "application/json",
                   "Authorization": "Bearer " + self.s.meterless_token,
                   "meterless-app": self.s.meterless_app,
                   "meterless-scope": "user"}
        req = urllib.request.Request(self.s.meterless_url + "/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=self.s.model_timeout) as r:
            return json.loads(r.read())

    def chat(self, agent: str, model: str, messages: list[dict], max_tokens: int = 8000,
             temperature: float = 0.2, fail_fast: bool = False) -> str:
        """fail_fast: on Nightshift's provider deadline, raise MeterlessDeadline at once instead of retrying,
        so a caller that can split the work does so. On 23 Oct the atorvastatin run had 43 failed attempts,
        all provider_deadline 502s at about 50 s each, with the same batch retried up to three times."""
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        prompt_sha = hashlib.sha256(json.dumps(messages).encode()).hexdigest()[:12]
        last, attempt, limited = None, 0, 0
        # On 22 Oct about half of Nightshift's Lightning calls returned "empty_response" or hit the
        # provider deadline. The agents fall back to smaller calls when all attempts fail.
        while True:
            self._wait_for_cooldown()
            rate_limited = False
            try:
                with Timer() as t:
                    j = self._post(body)
                msg = j["choices"][0]["message"]
                content = msg.get("content") or ""
                # The full messages and reply go into the trace so a reader can see exactly what each agent
                # was shown and what it answered, including Ultra's inline reasoning. Nothing secret is in
                # them: the token travels only in the request headers, and all data is public openFDA.
                self.tracer.event(agent, "llm_call", provider="meterless-nightshift", model=model,
                                  served_by=j.get("model"), prompt_sha=prompt_sha,
                                  prompt_chars=sum(len(m["content"]) for m in messages),
                                  reply_chars=len(content), usage=j.get("usage"), ms=t.ms, attempt=attempt,
                                  messages=messages, reply=content, nightshift=nightshift_steps(j),
                                  **({"reasoning": msg["reasoning_content"]} if msg.get("reasoning_content") else {}))
                if not content.strip():
                    raise MeterlessError("empty reply")
                self._rate_ok()
                return content
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code in (401, 403):
                    self.tracer.event(agent, "llm_error", model=model, error=f"unauthorized ({e.code})")
                    raise MeterlessUnauthorized(f"Nightshift rejected the Runtime token ({e.code})")
                last = f"HTTP {e.code}: {detail}"
                # Nightshift passes NVIDIA's 429 on as a 502 with meterless_detail "nvidia_429".
                rate_limited = e.code == 429 or "nvidia_429" in detail
                if fail_fast and "provider_deadline" in detail:
                    self.tracer.event(agent, "llm_deadline", model=model, attempt=attempt, error=last,
                                      action="split the batch")
                    raise MeterlessDeadline(last)
                if not rate_limited and e.code != 408 and e.code < 500:
                    break
            # ConnectionError covers Nightshift closing the socket mid-request (ConnectionResetError,
            # RemoteDisconnected), which on 22 Oct crashed a whole run at the Analyst's first call.
            except (urllib.error.URLError, TimeoutError, ConnectionError, MeterlessError, KeyError) as e:
                last = f"{type(e).__name__}: {e}"
            if rate_limited:
                limited += 1
                if limited > RATE_LIMIT_RETRIES:
                    break
                pause = self._rate_limited_now()
                self.tracer.event(agent, "llm_retry", model=model, attempt=attempt, error=last,
                                  reason="rate_limited", wait_s=pause)
                continue
            self.tracer.event(agent, "llm_retry", model=model, attempt=attempt, error=last)
            attempt += 1
            if attempt > self.s.max_retries:
                break
            time.sleep(5 * attempt)
        raise MeterlessError(last)

    def chat_json(self, agent: str, model: str, messages: list[dict], **kw) -> dict:
        """chat() that must return a JSON object. One repair attempt if the reply does not parse."""
        reply = self.chat(agent, model, messages, **kw)
        try:
            return extract_json(reply)
        except ValueError as e:
            self.tracer.event(agent, "llm_bad_json", error=str(e), reply_head=reply[:300])
            repair = messages + [{"role": "assistant", "content": reply},
                                 {"role": "user", "content": "That was not a valid JSON object. "
                                  "Reply again with only the JSON object, no other text."}]
            return extract_json(self.chat(agent, model, repair, **kw))
