"""What this project has learned about what you keep.

Every Keep and every Drop is already recorded, with the prompt that produced it.
Until now that history only decided what shipped. Here it starts steering what
gets made: the prompts you kept become examples, the ones you dropped become
warnings, and the next brief is expanded with both in view.

Two deliberate limits.

It learns per *kind*: a voice line you liked says nothing about what makes a good
engraving, and mixing them would produce guidance that reads like noise.

It weighs recent judgements over old ones. A project's look drifts, and taste
that cannot change is not taste — it is a rule.
"""
from dataclasses import dataclass, field

#: How many judgements of each sort reach the model. Enough to show a pattern,
#: few enough that the guidance stays shorter than the brief it serves.
DEFAULT_LIMIT = 6

#: States that mean a human said yes. `published` is `approved` that shipped.
_KEPT = ("approved", "published")


@dataclass(frozen=True)
class Taste:
    kept: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

    @property
    def informed(self) -> bool:
        return bool(self.kept or self.dropped)

    @property
    def summary(self) -> str:
        """One line for the interface, so the influence is never invisible."""
        if not self.informed:
            return ""
        return f"informed by {len(self.kept)} kept, {len(self.dropped)} dropped"

    @classmethod
    def from_entries(cls, entries: list[dict], kind: str, limit: int = DEFAULT_LIMIT) -> "Taste":
        kept: list[str] = []
        dropped: list[str] = []

        for entry in entries:
            if entry.get("kind") != kind:
                continue
            prompt = (entry.get("prompt") or "").strip()
            if not prompt:
                continue
            if entry.get("state") in _KEPT:
                kept.append(prompt)
            elif entry.get("state") == "rejected":
                dropped.append(prompt)

        # entries arrive oldest-first, so the tail is the most recent opinion
        return cls(kept=kept[-limit:], dropped=dropped[-limit:])


def guidance_from(taste: Taste) -> str:
    """Turn a taste into a paragraph a model can act on.

    Phrased as observation rather than instruction. "These were kept" invites a
    model to infer what they share; "always use fog" would have it copy a word.
    """
    if not taste.informed:
        return ""

    parts: list[str] = []
    if taste.kept:
        examples = "; ".join(f'"{p}"' for p in taste.kept)
        parts.append(
            f"Earlier briefs on this project that were kept: {examples}. "
            "Infer what they have in common and stay within it."
        )
    if taste.dropped:
        examples = "; ".join(f'"{p}"' for p in taste.dropped)
        # With no kept examples there is nothing to contrast against, so asking
        # for the difference would be asking about a set that does not exist.
        contrast = (
            "Avoid whatever distinguishes those from the ones above."
            if taste.kept
            else "Steer away from what those have in common."
        )
        parts.append(f"Briefs that were rejected: {examples}. {contrast}")
    return " ".join(parts)
