"""Settings from environment variables, with .env in the project root as a fallback.
Secrets are read here and passed to adapters; nothing in this module prints them."""
import os
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


@dataclass(frozen=True)
class Settings:
    zetaris_url: str
    zetaris_key: str
    zetaris_org: str
    meterless_url: str
    meterless_token: str
    meterless_app: str
    hunter_model: str
    judge_model: str
    source_timeout: int
    model_timeout: int
    max_retries: int
    judge_rounds: int
    parallel: int
    sample_mode: bool
    logs_dir: Path


def get_settings() -> Settings:
    load_dotenv()
    e = os.environ.get
    return Settings(
        zetaris_url=e("ZETARIS_REST_URL", "http://localhost:8888/api/v1.0").rstrip("/"),
        zetaris_key=e("ZETARIS_API_KEY", ""),
        zetaris_org=e("ZETARIS_ORG_ID", "1"),
        meterless_url=e("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1").rstrip("/"),
        meterless_token=e("METERLESS_RUNTIME_TOKEN", ""),
        meterless_app=e("METERLESS_APP", "black-box"),
        # Pinned Nemotron lanes, so the award evidence does not depend on meterless/auto routing.
        # Ultra by default. On 22 Oct, Super returned NVIDIA 404s for this account, and racing Ultra against
        # Lightning failed whenever Lightning returned empty first. Ultra alone, race width 1: 5 of 6 classify
        # calls succeeded with better classifications. The trace records which model actually served each call.
        hunter_model=e("HUNTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
        judge_model=e("JUDGE_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
        source_timeout=int(e("SOURCE_TIMEOUT_SECONDS", "20")),
        model_timeout=int(e("MODEL_TIMEOUT_SECONDS", "180")),
        max_retries=int(e("MAX_RETRIES", "2")),
        judge_rounds=int(e("JUDGE_ROUNDS", "2")),
        # Concurrent model calls. The NVIDIA trial lanes have a per-minute cap, so keep this small.
        parallel=max(1, int(e("MODEL_PARALLEL", "2"))),
        sample_mode=e("SAMPLE_MODE", "false").lower() == "true",
        logs_dir=ROOT / "logs",
    )
