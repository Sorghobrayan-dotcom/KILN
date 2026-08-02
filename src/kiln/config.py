"""Settings from the environment: credentials, and nothing else.

Which provider serves which asset, and under which model id, lives in
:mod:`kiln.kinds` — one place, keyed by the credential each needs. An earlier
version also carried a ``KILN_PROVIDER`` switch here; it survived the move to
kinds as dead configuration, which is worse than no configuration, because it
looks like it does something.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    b2_key_id: str
    b2_app_key: str
    b2_bucket: str
    b2_endpoint: str
    nvidia_api_key: str
    gemini_api_key: str
    gmi_api_key: str
    elevenlabs_api_key: str
    kiln_token: str
    eval_threshold: int
    max_iterations: int


def settings() -> Settings:
    return Settings(
        b2_key_id=os.getenv("B2_KEY_ID", ""),
        b2_app_key=os.getenv("B2_APP_KEY", ""),
        b2_bucket=os.getenv("B2_BUCKET", "kiln-assets"),
        b2_endpoint=os.getenv("B2_ENDPOINT", "https://s3.us-west-004.backblazeb2.com"),
        nvidia_api_key=os.getenv("NVIDIA_API_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gmi_api_key=os.getenv("GMI_API_KEY", ""),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        kiln_token=os.getenv("KILN_TOKEN", "dev"),
        eval_threshold=int(os.getenv("KILN_EVAL_THRESHOLD", "7")),
        max_iterations=int(os.getenv("KILN_MAX_ITERATIONS", "2")),
    )
