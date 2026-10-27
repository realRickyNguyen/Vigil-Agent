"""Offline checks of streamed Nightshift calls. Run: python -I -m pytest tests"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters import meterless  # noqa: E402
from app.adapters.meterless import MeterlessDeadline, MeterlessError, nightshift_steps, read_sse  # noqa: E402


class FakeTracer:
    def __init__(self):
        self.events = []

    def check(self):  # the run was not stopped
        pass

    def event(self, agent, kind, **data):
        self.events.append((agent, kind, data))


def sse(*frames):
    return [("data: " + (f if isinstance(f, str) else json.dumps(f))).encode() for f in frames]


OK = sse({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}, "[DONE]")


def test_read_sse_assembles_a_streamed_reply_like_a_buffered_one():
    # Frame shapes from Nightshift's streamChat (openai.mjs): role, content deltas, trace frames we ignore,
    # the terminal frame with the receipt, then usage and [DONE].
    frames = [{"model": "m", "choices": [{"delta": {"role": "assistant"}}]},
              {"model": "m", "choices": [{"delta": {"content": "thinking...</think>"}}]},
              {"meterless_trace": {"lanes": []}, "choices": []},
              {"model": "m", "choices": [{"delta": {"content": '{"ok": 1}'}}]},
              {"model": "served", "choices": [{"delta": {}, "finish_reason": "stop"}],
               "meterless": {"receipt": {"receipt_id": "r1", "phases": [{"phase": "final"}]}}},
              {"model": "served", "choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 7}}]
    lines = [("data: " + json.dumps(f)).encode() for f in frames] + [b"", b"data: [DONE]"]
    reply = read_sse(lines)
    assert reply["choices"][0]["message"]["content"] == 'thinking...</think>{"ok": 1}'
    assert reply["model"] == "served" and reply["usage"]["completion_tokens"] == 7
    assert nightshift_steps(reply)["receipt_id"] == "r1"


def test_read_sse_keeps_nightshifts_detail_from_an_error_frame():
    # Real shape (proxy.js openAIError): a generic message, the cause only in meterless_detail.
    lines = sse({"choices": [{"delta": {"role": "assistant"}}]},
                {"error": {"message": "Meterless provider request failed.", "type": "api_error",
                           "code": "provider_error", "meterless_detail": "provider_deadline"}}, "[DONE]")
    with pytest.raises(MeterlessError, match="provider_error: provider_deadline") as e:
        read_sse(lines)
    assert e.value.retryable and e.value.detail == "provider_deadline"


def test_read_sse_rejects_a_stream_that_stops_mid_answer():
    with pytest.raises(MeterlessError, match="before the reply finished"):
        read_sse(sse({"choices": [{"delta": {"content": "half an ans"}}]}))


def test_chat_retries_a_streamed_failure_but_not_a_missing_provider(monkeypatch):
    monkeypatch.setattr(meterless.time, "sleep", lambda s: None)
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", max_retries=2), FakeTracer())
    frames = {"provider_error": sse({"error": {"code": "provider_error", "meterless_detail": "provider_deadline"}}),
              "ok": OK, "none": sse({"error": {"code": "no_provider_configured", "message": "No provider"}})}
    replies = ["provider_error", "ok"]
    monkeypatch.setattr(client, "_post", lambda body: read_sse(frames[replies.pop(0)]))
    assert client.chat("analyst", "m", [{"role": "user", "content": "hi"}]) == "ok"
    replies = ["none", "ok"]
    with pytest.raises(MeterlessError, match="no_provider_configured"):
        client.chat("analyst", "m", [{"role": "user", "content": "hi"}])
    assert replies == ["ok"]  # not retried


def test_a_streamed_rate_limit_starts_the_shared_cool_down(monkeypatch):
    """A streamed call reports NVIDIA's 429 inside the stream, so it must start the same cool-down as an HTTP 429."""
    monkeypatch.setattr(meterless.time, "sleep", lambda s: None)
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", max_retries=1), FakeTracer())
    limited = sse({"error": {"code": "provider_error", "meterless_detail": 'nvidia_429: {"status":429}'}})
    replies = [limited, OK]
    monkeypatch.setattr(client, "_post", lambda body: read_sse(replies.pop(0)))
    assert client.chat("analyst", "m", [{"role": "user", "content": "hi"}]) == "ok"
    retries = [d for _, kind, d in client.tracer.events if kind == "llm_retry"]
    assert len(retries) == 1 and retries[0]["reason"] == "rate_limited" and retries[0]["wait_s"] > 0


def test_a_streamed_deadline_splits_the_batch_when_asked(monkeypatch):
    """With fail_fast a deadline inside the stream raises at once, so the caller splits the batch."""
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", max_retries=1), FakeTracer())
    timed_out = sse({"error": {"code": "provider_error",
                               "meterless_detail": "ttfb_timeout:nvidia/nemotron-3-ultra-550b-a55b"}})
    monkeypatch.setattr(client, "_post", lambda body: read_sse(timed_out))
    with pytest.raises(MeterlessDeadline):
        client.chat("analyst", "m", [{"role": "user", "content": "hi"}], fail_fast=True)


def test_post_turns_a_half_written_frame_into_a_retryable_error(monkeypatch):
    class Resp:
        def __enter__(self):
            return iter([b'data: {"choices": [{"delta": {"content": "hal'])

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(meterless.urllib.request, "urlopen", lambda req, timeout: Resp())
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", meterless_url="http://x",
                                                        meterless_app="a", model_timeout=1, model_stream=True),
                                        FakeTracer())
    with pytest.raises(MeterlessError, match="broken reply"):
        client._post({"model": "m"})


def test_post_streams_by_default(monkeypatch):
    sent = {}

    class Resp:
        def __enter__(self):
            return iter(sse({"model": "m", "choices": [{"delta": {"content": "hi"}}]}, "[DONE]"))

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout):
        sent["body"], sent["headers"] = json.loads(req.data), dict(req.header_items())
        return Resp()
    monkeypatch.setattr(meterless.urllib.request, "urlopen", urlopen)
    client = meterless.NightshiftClient(SimpleNamespace(meterless_token="t", meterless_url="http://x",
                                                        meterless_app="a", model_timeout=1, model_stream=True),
                                        FakeTracer())
    assert client._post({"model": "m"})["choices"][0]["message"]["content"] == "hi"
    assert sent["body"]["stream"] is True and sent["headers"]["Meterless-trace"] == "on"
    assert sent["headers"]["Meterless-tier-split"] == "off"
