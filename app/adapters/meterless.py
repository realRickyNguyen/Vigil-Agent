"""Meterless Nightshift adapter, the app's only model provider.
OpenAI-compatible POST {METERLESS_BASE_URL}/chat/completions with the Runtime token, the meterless-app
header and a fresh meterless-scope on every call, which keeps Nightshift's H-MEM out (see _post).
The NVIDIA key stays inside Nightshift."""
import hashlib
import http.client
import json
import logging
import re
import time
import urllib.error
import urllib.request
import uuid

from app.config import Settings
from app.tracing import Timer, Tracer

log = logging.getLogger(__name__)


class MeterlessError(RuntimeError):
    pass


class MeterlessUnauthorized(MeterlessError):
    pass


# Error codes in a streamed error frame that a retry cannot fix (Nightshift's proxy.js, statusForCode).
NOT_RETRYABLE = {"no_provider_configured", "model_disabled_by_operator", "runtime_model_missing",
                 "runtime_model_unknown", "unknown_decision_id", "unhandled_endpoint"}


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
    The app keeps H-MEM out with a fresh scope per call (see NightshiftClient._post), and every call records what
    the receipt says, so a run shows that no memory was injected."""
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


def setup_problems(requested: str, served_by: str | None, steps: dict | None) -> list[str]:
    """Signs that Nightshift is not set up as the README's "Run it" section says. Nightshift 1.2.1 ignores the
    model an app asks for and routes each call by its own mode, so on a default install calls can go to other
    models, and its quality lane answers some of them unstreamed and cuts them off at 45 s."""
    problems = []
    if served_by and served_by != requested:
        problems.append(f"Nightshift served {served_by} instead of the requested {requested}. Set up its lanes as "
                        "the README's Run it section says, with only that model's lane running.")
    if steps and steps.get("scaffold_active"):
        problems.append("Nightshift added its reasoning scaffold, so its Quality track is not set up as the README's "
                        "Run it section says. With the quality race on, about half of the calls are answered "
                        "unstreamed and cut off at 45 s.")
    return problems


def read_sse(lines) -> dict:
    """Assemble Nightshift's SSE frames into the shape of a buffered reply, so chat() reads both the same way.
    Nightshift has already sent 200 when a stream fails, so the failure arrives as an error frame instead.
    Its message is generic, so the error keeps the code and Nightshift's detail (for example provider_deadline)."""
    content, reasoning, reply = [], [], {"model": None, "usage": None, "meterless": None}
    finished = False
    for raw in lines:
        line = raw.decode("utf-8", errors="replace").strip() if isinstance(raw, bytes) else raw.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            finished = True
            break
        frame = json.loads(data)
        if frame.get("error"):
            err = frame["error"] if isinstance(frame["error"], dict) else {"message": str(frame["error"])}
            e = MeterlessError(f"{err.get('code', 'error')}: {err.get('meterless_detail') or err.get('message')}"[:300])
            e.retryable = err.get("code") not in NOT_RETRYABLE
            raise e
        reply["model"] = frame.get("model") or reply["model"]
        reply["usage"] = frame.get("usage") or reply["usage"]
        reply["meterless"] = frame.get("meterless") or reply["meterless"]
        for choice in frame.get("choices") or []:
            delta = choice.get("delta") or {}
            content.append(delta.get("content") or "")
            reasoning.append(delta.get("reasoning_content") or "")
            finished = finished or bool(choice.get("finish_reason"))
    if not finished:
        # The connection closed cleanly mid-answer. Returning the partial text would look like a bad reply.
        raise MeterlessError("stream ended before the reply finished")
    message = {"role": "assistant", "content": "".join(content)}
    if any(reasoning):
        message["reasoning_content"] = "".join(reasoning)
    return {**reply, "choices": [{"message": message}]}


class NightshiftClient:
    def __init__(self, settings: Settings, tracer: Tracer):
        if not settings.meterless_token:
            raise MeterlessError("METERLESS_RUNTIME_TOKEN is not set")
        self.s = settings
        self.tracer = tracer
        self._warned: set[str] = set()

    def _warn_setup(self, agent: str, model: str, served_by: str | None, steps: dict | None) -> None:
        """Warn once per problem, at the first call that shows it, rather than leave a run of quiet timeouts."""
        for problem in setup_problems(model, served_by, steps):
            if problem not in self._warned:
                self._warned.add(problem)
                self.tracer.event(agent, "nightshift_warning", warning=problem)
                log.warning(problem)

    def _post(self, body: dict) -> dict:
        # A fresh scope per call keeps Nightshift's H-MEM out. Its memory is walled by scope, and under the
        # shared "user" scope it fed each call up to 3 earlier answers as vetted evidence, which replayed one
        # wrong 22 Oct answer into every later montelukast run. The World Model is the app's memory instead.
        headers = {"Content-Type": "application/json",
                   "Authorization": "Bearer " + self.s.meterless_token,
                   "meterless-app": self.s.meterless_app,
                   "meterless-scope": "call-" + uuid.uuid4().hex,
                   # Nightshift ignores our model pin because the app has a mode policy, so it may split a prompt
                   # into a buffered planning phase (still cut at 45 s) with a "write a plan" or "show the diff"
                   # system prompt that fights our JSON contract. One phase keeps the call as we wrote it.
                   "meterless-tier-split": "off"}
        if self.s.model_stream:
            # Nightshift aborts its NVIDIA fetch if no response headers arrive within 45 s (providers.js,
            # CLOUD_FETCH_DEADLINE_MS). A buffered call gets no headers until the whole answer is written, so
            # any reply that takes Ultra over 45 s failed with provider_deadline. Streaming gets headers at once.
            # The trace header makes the final frame carry the full receipt, as the buffered reply does.
            body = {**body, "stream": True, "stream_options": {"include_usage": True}}
            headers["meterless-trace"] = "on"
        req = urllib.request.Request(self.s.meterless_url + "/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers)
        # With streaming the socket timeout is a gap between chunks, not a cap on the whole reply.
        try:
            with urllib.request.urlopen(req, timeout=self.s.model_timeout) as r:
                return read_sse(r) if self.s.model_stream else json.loads(r.read())
        except (ValueError, http.client.HTTPException) as e:
            # A connection dropped mid-frame leaves half a JSON line, which would otherwise crash the run.
            raise MeterlessError(f"broken reply: {type(e).__name__}: {e}"[:300]) from e

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
                steps = nightshift_steps(j)
                self.tracer.event(agent, "llm_call", provider="meterless-nightshift", model=model,
                                  served_by=j.get("model"), prompt_sha=prompt_sha,
                                  prompt_chars=sum(len(m["content"]) for m in messages),
                                  reply_chars=len(content), usage=j.get("usage"), ms=t.ms, attempt=attempt,
                                  messages=messages, reply=content, nightshift=steps,
                                  **({"reasoning": msg["reasoning_content"]} if msg.get("reasoning_content") else {}))
                self._warn_setup(agent, model, j.get("model"), steps)
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
            # RemoteDisconnected), which on 22 Oct crashed a whole run at the Analyst's first call.
            except (urllib.error.URLError, TimeoutError, ConnectionError, MeterlessError, KeyError) as e:
                last = f"{type(e).__name__}: {e}"
                if not getattr(e, "retryable", True):
                    self.tracer.event(agent, "llm_error", model=model, error=last)
                    break
            self.tracer.event(agent, "llm_retry", model=model, attempt=attempt, error=last)
            # NVIDIA trial lanes have a per-minute cap, so a 429 waits out most of the minute.
            time.sleep(30 if "429" in (last or "") else 5 * (attempt + 1))
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
            again = self.chat(agent, model, repair, **kw)
            try:
                return extract_json(again)
            except ValueError as e2:
                # Raised as a model failure, so the agents' smaller-call fallbacks apply instead of a crash.
                self.tracer.event(agent, "llm_bad_json", error=str(e2), reply_head=again[:300], repair=True)
                raise MeterlessError(f"no valid JSON after a repair attempt: {e2}") from e2
