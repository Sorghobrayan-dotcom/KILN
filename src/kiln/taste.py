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

#: Below this, there is no pattern — only coincidence. Two prompts sharing a
#: word say nothing, and a model asked to generalise from them will seize that
#: word and call it a style. Better to say "still learning" than to invent.
MIN_TO_LEARN = 3

#: Above this, the evidence is thick enough to state plainly rather than hedge.
CONFIDENT_AT = 6


@dataclass(frozen=True)
class Taste:
    kept: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

    @property
    def judged(self) -> int:
        return len(self.kept) + len(self.dropped)

    @property
    def informed(self) -> bool:
        """Whether there is enough here to steer anything."""
        return self.judged >= MIN_TO_LEARN

    @property
    def confident(self) -> bool:
        return self.judged >= CONFIDENT_AT

    @property
    def summary(self) -> str:
        """One line for the interface, so the influence is never invisible —
        including when there is not yet any influence to report."""
        if self.judged == 0:
            return ""
        if not self.informed:
            return f"still learning, {self.judged} of {MIN_TO_LEARN} judgements so far"
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
    if not taste.confident:
        # said out loud, because a model given three examples will otherwise
        # treat a shared adjective as a rule
        parts.append(
            "These are few examples and what they share may be coincidence. "
            "Follow the pattern only where it is clear."
        )
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
