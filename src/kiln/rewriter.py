"""Rewrite a brief in the light of what this project has kept.

The loop this closes: you judge assets, and your judgements come back as better
briefs. Without it, Keep and Drop only decide what ships, and the library
collects opinions it never uses.

Three properties it has to hold, in order of how badly their absence would hurt:

**It must not break the cache.** Generation is keyed on the prompt, so a rewrite
that varies run to run would miss its own cache forever and the project's whole
premise would quietly stop working. The rewrite is therefore cached in the
bucket under the brief *and* a fingerprint of the taste that shaped it. Same
brief, same taste, same prompts, down to the byte. Change your mind and you get
a fresh rewrite, which is what changing your mind ought to mean.

**It must not be able to break generation.** A model that is slow, down or
talkative falls back to the plain expansion. The feature can fail; the product
cannot.

**It must be visible.** The interface says what it learned from, because
something steering your prompts without saying so is not a feature.
"""
import hashlib
import json
import logging
import re

from kiln.blobs import Blobs
from kiln.taste import Taste, guidance_from

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"

_INSTRUCTION = """You write prompts for a generative media pipeline.

{guidance}

Write exactly {count} prompt(s) for this brief: "{brief}"

Rules:
- One prompt per line. No numbering, no quotes, no commentary, no preamble.
- Each prompt must stand alone and describe one asset.
- Keep the brief's subject. Let the kept examples guide style, not subject.
"""

#: leading "1.", "2)", "- ", "* " that small models add despite instructions
_ORNAMENT = re.compile(r"^\s*(?:\d+\s*[.)]|[-*•])\s*")


def _clean(line: str) -> str:
    return _ORNAMENT.sub("", line).strip().strip('"').strip()


def _looks_like_commentary(line: str) -> bool:
    """A line that talks *about* the prompts rather than being one."""
    lowered = line.lower()
    return lowered.endswith(":") or lowered.startswith(("here are", "here is", "sure", "certainly"))


def plain_expand(description: str, count: int) -> list[str]:
    """The expansion used when there is no taste, or when the model fails."""
    if count == 1:
        return [description]
    return [f"{description} (variant {i + 1} of {count})" for i in range(count)]


def nvidia_chat(api_key: str, model: str = DEFAULT_MODEL):
    """A one-argument chat callable, or None when there is no key.

    Returning None rather than a failing stub is deliberate: the rewriter skips
    the model entirely when it has none, so a deployment without an LLM key
    never pays a call to discover it cannot make one.
    """
    if not api_key:
        return None

    def chat(prompt: str) -> str:
        import genblaze_nvidia as gn

        return gn.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            max_tokens=400,
        ).text

    return chat


class TasteRewriter:
    def __init__(self, blobs: Blobs, chat=None, model: str = DEFAULT_MODEL) -> None:
        self._blobs = blobs
        self._chat = chat
        self._model = model

    # ---- storage -----------------------------------------------------
    def _key(self, project: str, kind: str, brief: str, count: int, taste: Taste) -> str:
        fingerprint = json.dumps(
            {"kind": kind, "brief": brief, "count": count,
             "kept": taste.kept, "dropped": taste.dropped},
            sort_keys=True, ensure_ascii=False,
        )
        digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
        return f"{project}/taste/{digest}.json"

    # ---- the call ----------------------------------------------------
    def _ask(self, guidance: str, brief: str, count: int) -> list[str]:
        prompt = _INSTRUCTION.format(guidance=guidance, brief=brief, count=count)
        raw = self._chat(prompt)
        lines = [_clean(line) for line in str(raw).splitlines()]
        return [line for line in lines if line and not _looks_like_commentary(line)]

    def prompts(self, project: str, kind: str, brief: str, count: int, taste: Taste) -> list[str]:
        fallback = plain_expand(brief, count)
        if not taste.informed or self._chat is None:
            return fallback

        key = self._key(project, kind, brief, count, taste)
        cached = self._blobs.get(key)
        if cached is not None:
            try:
                return json.loads(cached.decode("utf-8"))["prompts"]
            except Exception:
                logger.warning("Taste rewrite unreadable; asking again")

        try:
            written = self._ask(guidance_from(taste), brief, count)
        except Exception as exc:
            # the feature may fail; generation may not
            logger.warning("Taste rewrite failed, using the plain expansion: %s", exc)
            return fallback

        if not written:
            return fallback

        # a model that under-delivers must not shrink the batch the user asked for
        prompts = (written + fallback[len(written):])[:count]

        self._blobs.put(
            key,
            json.dumps({"brief": brief, "kind": kind, "count": count,
                        "kept": taste.kept, "dropped": taste.dropped,
                        "model": self._model, "prompts": prompts},
                       indent=2, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )
        return prompts
