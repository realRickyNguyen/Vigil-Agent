"""Meterless Nightshift adapter, the app's only model provider.
OpenAI-compatible POST {METERLESS_BASE_URL}/chat/completions with the Runtime token, the meterless-app
header and a fresh meterless-scope on every call, which keeps Nightshift's H-MEM out (see _post).
The NVIDIA key stays inside Nightshift."""
import hashlib
import http.client
import json
import logging
import re
import threading
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


class MeterlessDeadline(MeterlessError):
    """Nightshift ended the provider call at its deadline. Retrying the same prompt mostly hits it again."""


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


RATE_LIMIT_RETRIES = 3  # NVIDIA 429s clear with time, unlike the provider deadline
RATE_LIMIT_PAUSE = 15  # seconds, times the number of 429s in a row
# Seconds a slot must stay free, with no main call waiting, before a low-priority call takes it. A Reviewer worker
# asks for its next slot within this time of giving one back, so a low-priority call takes only slots the main
# calls are not using.
LOW_PRIORITY_GRACE = 0.25


class Slots:
    """MODEL_PARALLEL model-call slots shared by every thread of a run, with main calls first: a low-priority call
    (the Skeptic's challenge reviews) gets a slot only when one has stayed free for LOW_PRIORITY_GRACE seconds with
    no main call (the Reviewer's rounds, the Analyst's revisions) waiting. Main calls can still wait behind a
    low-priority call already in flight, at most one call's length."""

    def __init__(self, n: int):
        self.free, self.main_waiting, self.cond = n, 0, threading.Condition()

    def acquire(self, low: bool = False, until: float | None = None) -> bool:
        """Take a slot. A low-priority call with `until` (time.monotonic()) gives up at that time and returns False."""
        with self.cond:
            if not low:
                self.main_waiting += 1
                try:
                    while self.free == 0:
                        self.cond.wait()
                finally:
                    self.main_waiting -= 1
            else:
                while True:
                    while self.free == 0 or self.main_waiting:
                        if not self._wait(until):
                            return False
                    # A slot must stay free, with no main call asking, for the whole grace; the wait starts over if
                    # the free slots run out or a main call asks for one in the meantime.
                    grace = time.monotonic() + LOW_PRIORITY_GRACE
                    while self.free and not self.main_waiting and (wait := grace - time.monotonic()) > 0:
                        self.cond.wait(wait)
                    if self.free and not self.main_waiting:
                        break
                    if until is not None and time.monotonic() >= until:
                        return False
            self.free -= 1
            return True

    def _wait(self, until: float | None) -> bool:
        """Wait for a change, until `until` at most; False once it has passed (the lock is held)."""
        if until is None:
            self.cond.wait()
            return True
        wait = until - time.monotonic()
        return wait > 0 and (self.cond.wait(wait) or time.monotonic() < until)

    def free_before(self, until: float) -> bool:
        """Whether a low-priority call could get a slot before `until`, without keeping it."""
        if not self.acquire(low=True, until=until):
            return False
        self.release()
        return True

    def release(self) -> None:
        with self.cond:
            self.free += 1
            self.cond.notify_all()


class LowPriority:
    """The client as the Skeptic's challenge reviews use it: every call takes a low-priority slot. Everything else,
    including the shared cool-down and the cancel flag, is the same client's."""

    def __init__(self, client: "NightshiftClient"):
        self._client = client

    def __getattr__(self, name):
        return getattr(self._client, name)

    def chat(self, *a, **kw) -> str:
        return self._client.chat(*a, low_priority=True, **kw)

    def chat_json(self, *a, **kw) -> dict:
        return self._client.chat_json(*a, low_priority=True, **kw)


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


def read_sse(lines, deadline: float | None = None) -> dict:
    """Assemble Nightshift's SSE frames into the shape of a buffered reply, so chat() reads both the same way.
    Nightshift has already sent 200 when a stream fails, so the failure arrives as an error frame instead.
    Its message is generic, so the error keeps the code and Nightshift's detail (for example provider_deadline).
    deadline (time.monotonic()): a stream that keeps sending past it is cut, so a call stays within the
    organisers' 30 to 90 s even though the socket timeout only bounds the gap between chunks."""
    content, reasoning, reply = [], [], {"model": None, "usage": None, "meterless": None}
    finished = False
    for raw in lines:
        if deadline is not None and time.monotonic() > deadline:
            raise MeterlessError("call_time_limit: the streamed reply ran past MODEL_TIMEOUT_SECONDS")
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
            detail = str(err.get("meterless_detail") or err.get("message") or "")
            e = MeterlessError(f"{err.get('code', 'error')}: {detail}"[:300])
            e.detail = detail  # chat() reads it the way it reads an HTTP error's detail
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
        # Shared by every worker thread: after a 429, all calls wait until the cool-down ends. On 24 Oct a third
        # back-to-back run with four parallel calls got 33 NVIDIA 429s; each retry 5 s later hit the cap again.
        self._lock = threading.Lock()
        self._cooldown_until = 0.0
        self._rate_limited = 0
        # Set by the pipeline while the Skeptic's challenge reviews make model calls alongside the Reviewer's first
        # round and the revision round: each attempt holds one of its slots, so together they stay within
        # MODEL_PARALLEL, and the Reviewer's rounds come first (see Slots). A slot is not held during a retry
        # pause. A call that got its slot while a cool-down started waits that cool-down out before posting.
        self.slots: Slots | None = None
        # Set when the run stops on an error (by the pipeline, or here on a rejected token), so a challenge review
        # still running in its own thread makes no further calls.
        self.cancelled: threading.Event | None = None

    def low_priority(self) -> LowPriority:
        return LowPriority(self)

    def _check_cancelled(self) -> None:
        if self.cancelled is not None and self.cancelled.is_set():
            e = MeterlessError("run cancelled: the run stopped on an error")
            e.retryable = False  # chat() gives up at once instead of retrying
            raise e

    def _wait_for_cooldown(self) -> None:
        # Check again after sleeping, because another thread's 429 may have extended the cool-down meanwhile.
        # Sleep again only for an extension, not for a deadline already waited out.
        waited_until = 0.0
        while True:
            with self._lock:
                until = self._cooldown_until
            wait = until - time.monotonic()
            if wait <= 0 or until <= waited_until:
                return
            time.sleep(wait)
            waited_until = until

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

    def _warn_setup(self, agent: str, model: str, served_by: str | None, steps: dict | None) -> None:
        """Warn once per problem, at the first call that shows it, rather than leave a run of quiet timeouts."""
        for problem in setup_problems(model, served_by, steps):
            with self._lock:  # worker threads share the set, so two calls cannot both warn
                if problem in self._warned:
                    continue
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
        self.tracer.check()  # a run a person stopped sends no more calls
        req = urllib.request.Request(self.s.meterless_url + "/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers)
        # With streaming the socket timeout is a gap between chunks, so read_sse also stops at the whole-call limit.
        try:
            with urllib.request.urlopen(req, timeout=self.s.model_timeout) as r:
                if self.s.model_stream:
                    return read_sse(r, deadline=time.monotonic() + self.s.model_timeout)
                return json.loads(r.read())
        except (ValueError, http.client.HTTPException) as e:
            # A connection dropped mid-frame leaves half a JSON line, which would otherwise crash the run.
            raise MeterlessError(f"broken reply: {type(e).__name__}: {e}"[:300]) from e

    def chat(self, agent: str, model: str, messages: list[dict], max_tokens: int = 8000,
             temperature: float = 0.2, fail_fast: bool = False, low_priority: bool = False) -> str:
        """fail_fast: on Nightshift's provider deadline, raise MeterlessDeadline at once instead of retrying,
        so a caller that can split the work does so. On 23 Oct the atorvastatin run had 43 failed attempts,
        all provider_deadline 502s at about 50 s each, with the same batch retried up to three times.
        low_priority: take a low-priority slot (the Skeptic's challenge reviews), when slots are set."""
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        prompt_sha = hashlib.sha256(json.dumps(messages).encode()).hexdigest()[:12]
        last, attempt, limited = None, 0, 0
        # On 22 Oct about half of Nightshift's Lightning calls returned "empty_response" or hit the
        # provider deadline. The agents fall back to smaller calls when all attempts fail.
        while True:
            self._wait_for_cooldown()
            rate_limited = False
            self._check_cancelled()
            try:
                slots, waited = self.slots, None  # read once, so the release matches the acquire
                if slots is not None:
                    with Timer() as w:
                        slots.acquire(low=low_priority)
                    waited = w.ms
                try:
                    if slots is not None:
                        self._wait_for_cooldown()  # a 429 elsewhere may have started one while this call queued
                        self._check_cancelled()
                    with Timer() as t:
                        j = self._post(body)
                finally:
                    if slots is not None:
                        slots.release()
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
                                  **({"slot_wait_ms": waited} if waited is not None else {}),
                                  **({"reasoning": msg["reasoning_content"]} if msg.get("reasoning_content") else {}))
                self._warn_setup(agent, model, j.get("model"), steps)
                if not content.strip():
                    raise MeterlessError("empty reply")
                self._rate_ok()
                return content
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code in (401, 403):
                    self.tracer.event(agent, "llm_error", model=model, error=f"unauthorized ({e.code})")
                    if self.cancelled is not None:
                        self.cancelled.set()  # every other call of this run would fail the same way, so stop them now
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
                if not getattr(e, "retryable", True):
                    self.tracer.event(agent, "llm_error", model=model, error=last)
                    break
                # A streamed call has already had its 200, so a 429 or a provider time limit arrives as an error
                # frame whose detail names it: nvidia_429, provider_deadline, or ttfb_timeout when Nightshift's
                # learned first-byte budget runs out (33 of 237 calls in the 24 Oct evening evaluation).
                detail = getattr(e, "detail", "")
                rate_limited = "_429" in detail
                if fail_fast and ("provider_deadline" in detail or "ttfb_timeout" in detail):
                    self.tracer.event(agent, "llm_deadline", model=model, attempt=attempt, error=last,
                                      action="split the batch")
                    raise MeterlessDeadline(last) from e
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
            # A first-byte cut means no reply had started, so the retry goes out at once. Over 18 runs on 24 and
            # 25 Oct there were 58 such cuts, about 3 a run, each followed by a 5 s wait.
            if "ttfb_timeout" not in last:
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
            again = self.chat(agent, model, repair, **kw)
            try:
                return extract_json(again)
            except ValueError as e2:
                # Raised as a model failure, so the agents' smaller-call fallbacks apply instead of a crash.
                self.tracer.event(agent, "llm_bad_json", error=str(e2), reply_head=again[:300], repair=True)
                raise MeterlessError(f"no valid JSON after a repair attempt: {e2}") from e2
