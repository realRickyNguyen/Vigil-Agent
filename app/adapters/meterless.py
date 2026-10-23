"""Meterless Nightshift adapter, the app's only model provider.
OpenAI-compatible POST {METERLESS_BASE_URL}/chat/completions with the Runtime token,
the meterless-app header and meterless-scope: user. The NVIDIA key stays inside Nightshift."""
import hashlib
import json
import re
import time
import urllib.error
import urllib.request

from app.config import Settings
from app.tracing import Timer, Tracer


class MeterlessError(RuntimeError):
    pass


class MeterlessUnauthorized(MeterlessError):
    pass


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


class NightshiftClient:
    def __init__(self, settings: Settings, tracer: Tracer):
        if not settings.meterless_token:
            raise MeterlessError("METERLESS_RUNTIME_TOKEN is not set")
        self.s = settings
        self.tracer = tracer

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
             temperature: float = 0.2) -> str:
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        prompt_sha = hashlib.sha256(json.dumps(messages).encode()).hexdigest()[:12]
        last = None
        # On 22 Oct about half of Nightshift's Lightning calls returned "empty_response" or hit the
        # provider deadline. The agents fall back to smaller calls when all attempts fail.
        for attempt in range(self.s.max_retries + 1):
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
                                  messages=messages, reply=content,
                                  **({"reasoning": msg["reasoning_content"]} if msg.get("reasoning_content") else {}))
                if not content.strip():
                    raise MeterlessError("empty reply")
                return content
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code in (401, 403):
                    self.tracer.event(agent, "llm_error", model=model, error=f"unauthorized ({e.code})")
                    raise MeterlessUnauthorized(f"Nightshift rejected the Runtime token ({e.code})")
                last = f"HTTP {e.code}: {detail}"
                if e.code not in (408, 429) and e.code < 500:
                    break
            # ConnectionError covers Nightshift closing the socket mid-request (ConnectionResetError,
            # RemoteDisconnected), which on 22 Oct crashed a whole run at the Hunter's first call.
            except (urllib.error.URLError, TimeoutError, ConnectionError, MeterlessError, KeyError) as e:
                last = f"{type(e).__name__}: {e}"
            self.tracer.event(agent, "llm_retry", model=model, attempt=attempt, error=last)
            time.sleep(5 * (attempt + 1))  # NVIDIA trial lanes have a per-minute cap
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
