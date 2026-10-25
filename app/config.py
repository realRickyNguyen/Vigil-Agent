"""Settings from environment variables, with .env in the project root as a fallback.
Secrets are read here and passed to adapters; nothing in this module prints them."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


LOOPBACK = re.compile(r"^(https?://)(localhost|127\.0\.0\.1)(?=[:/]|$)")


def in_container() -> bool:
    return Path("/.dockerenv").exists()


def host_url(url: str) -> str:
    """Inside a Docker container, localhost is the container itself; Zetaris and Nightshift run on the host,
    which Docker Desktop names host.docker.internal. So the .env written for running on the machine also works
    with `docker run --env-file .env`. Set DOCKER_HOST_REWRITE=false to keep the addresses as given."""
    if in_container() and os.environ.get("DOCKER_HOST_REWRITE", "true").lower() != "false":
        return LOOPBACK.sub(r"\1host.docker.internal", url)
    return url


@dataclass(frozen=True)
class Settings:
    zetaris_url: str
    zetaris_key: str
    zetaris_org: str
    meterless_url: str
    meterless_token: str
    meterless_app: str
    analyst_model: str
    reviewer_model: str
    source_timeout: int
    model_timeout: int
    model_stream: bool
    max_retries: int
    reviewer_rounds: int
    parallel: int
    run_budget: int
    sample_mode: bool
    logs_dir: Path
    world_path: Path
    analyst_top: int = 15
    analyst_extra: int = 5
    skeptic_items: int = 3
    skeptic_co_drugs: int = 3
    source_items: int = 10


def env_value(value: str | None) -> str | None:
    """`docker run --env-file` keeps everything after the = sign, so drop an inline comment and matching quotes
    the way load_dotenv does for a .env read from disk."""
    if value is None:
        return None
    value = re.sub(r"\s+#.*$", "", value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def get_settings() -> Settings:
    load_dotenv()
    e = lambda key, default=None: env_value(os.environ.get(key, default))  # noqa: E731
    return Settings(
        zetaris_url=host_url(e("ZETARIS_REST_URL", "http://localhost:8888/api/v1.0").rstrip("/")),
        zetaris_key=e("ZETARIS_API_KEY", ""),
        zetaris_org=e("ZETARIS_ORG_ID", "1"),
        meterless_url=host_url(e("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1").rstrip("/")),
        meterless_token=e("METERLESS_RUNTIME_TOKEN", ""),
        meterless_app=e("METERLESS_APP", "vigil"),
        # Pinned Nemotron lanes, so the award evidence does not depend on meterless/auto routing.
        # Ultra by default. On 22 Oct, Super returned NVIDIA 404s for this account, and racing Ultra against
        # Lightning failed whenever Lightning returned empty first. Ultra alone, race width 1: 5 of 6 classify
        # calls succeeded with better classifications. The trace records which model actually served each call.
        # The pre-rename names (HUNTER_MODEL, JUDGE_MODEL, JUDGE_ROUNDS) still work in an older .env.
        analyst_model=e("ANALYST_MODEL", e("HUNTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")),
        reviewer_model=e("REVIEWER_MODEL", e("JUDGE_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")),
        source_timeout=int(e("SOURCE_TIMEOUT_SECONDS", "20")),
        # Whole-call limit (organisers' guide: model calls bounded at 30 to 90 s). A streamed call is cut when it
        # runs past it; the same value is the socket timeout, which for a stream bounds the gap between chunks.
        # One retry: on 23 Oct 125 of 132 failed attempts were Nightshift's 45 s provider deadline on buffered
        # calls, and retrying the same prompt mostly hit it again.
        model_timeout=int(e("MODEL_TIMEOUT_SECONDS", "90")),
        # Stream model replies. Off brings back the buffered calls that Nightshift cut at 45 s.
        model_stream=e("MODEL_STREAM", "true").lower() not in ("false", "0", "no", "off"),
        max_retries=int(e("MAX_RETRIES", "1")),
        # One revision round: on 24 Oct a second round rarely changed an answer (a repeated dispute closes as
        # unresolved anyway) and cost about two minutes that the Skeptic needed.
        reviewer_rounds=int(e("REVIEWER_ROUNDS", e("JUDGE_ROUNDS", "1"))),
        # Concurrent model calls. On 23 Oct two concurrent Ultra calls each took as long as one alone, and the
        # NVIDIA trial cap (7 of 132 failures were 429s) leaves room for four one-reaction calls of 20 to 40 s.
        parallel=max(1, int(e("MODEL_PARALLEL", "4"))),
        # Wall-clock budget for one run (organisers' target: 5 to 10 minutes). When too little is left, the
        # revision round and the Skeptic are skipped and their items say so, instead of the run running long.
        run_budget=int(e("RUN_BUDGET_SECONDS", "600")),
        sample_mode=e("SAMPLE_MODE", "false").lower() == "true",
        logs_dir=ROOT / "logs",
        # The World Model persists across runs (unlike logs/, which is per-run evidence), so a later run can
        # reopen verdicts that an earlier run's label version supported. Relative paths are from the repo root.
        world_path=ROOT / e("WORLD_MODEL_PATH", "state/world-model.json"),
        # The Skeptic checks the top review_next items against their most co-reported drugs. Each co-drug
        # costs four openFDA calls (no-key limit: about 1,000 a day per IP), so both are kept small.
        # The Analyst always assesses the strongest rows by chi2 and may add a few more of its own choice.
        analyst_top=max(1, int(e("ANALYST_TOP", "15"))),
        analyst_extra=max(0, int(e("ANALYST_EXTRA", "5"))),
        skeptic_items=max(0, int(e("SKEPTIC_ITEMS", "3"))),
        skeptic_co_drugs=max(1, int(e("SKEPTIC_CO_DRUGS", "3"))),
        # Review-next items whose report sources (country, reporter type) are checked. Each costs two openFDA calls,
        # and each run two more for the drug's usual mix.
        source_items=max(0, int(e("SOURCE_ITEMS", "10"))),
    )
