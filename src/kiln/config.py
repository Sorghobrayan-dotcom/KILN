"""Settings from the environment.

Model ids are configuration, never code: they were verified against
``NvidiaImageProvider.models_default().known()`` on 2026-08-01, but a provider
can rename a slug any morning, and that must be a one-line env change rather
than a deploy.
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
    kiln_token: str
    provider: str
    image_model: str
    fallback_models: list[str]
    vision_model: str
    tts_model: str
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
        kiln_token=os.getenv("KILN_TOKEN", "dev"),
        # google by default: NVIDIA's free image endpoint returned 504 after
        # 303s on 2026-08-02 — their gateway gave up, not our network.
        provider=os.getenv("KILN_PROVIDER", "google"),
        image_model=os.getenv("KILN_IMAGE_MODEL", "gemini-2.5-flash-image"),
        # a slug going dark mid-demo degrades instead of failing
        fallback_models=[
            m.strip()
            for m in os.getenv("KILN_FALLBACK_MODELS", "gemini-3.1-flash-image").split(",")
            if m.strip()
        ],
        vision_model=os.getenv("KILN_VISION_MODEL", "meta/llama-3.2-90b-vision-instruct"),
        tts_model=os.getenv("KILN_TTS_MODEL", "nvidia/magpie-tts-multilingual"),
        eval_threshold=int(os.getenv("KILN_EVAL_THRESHOLD", "7")),
        max_iterations=int(os.getenv("KILN_MAX_ITERATIONS", "2")),
    )
