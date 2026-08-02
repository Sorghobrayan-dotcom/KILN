import json

from kiln.blobs import MemoryBlobs
from kiln.rewriter import TasteRewriter
from kiln.taste import Taste

BRIEF = "a watchtower on a ridge"
TASTE = Taste(kept=["a gate in fog, engraving"], dropped=["a gate, neon"])


def rewriter(blobs=None, chat=None, **kw):
    return TasteRewriter(blobs or MemoryBlobs(), chat=chat, **kw)


def scripted(*lines, calls=None):
    def chat(prompt: str) -> str:
        if calls is not None:
            calls.append(prompt)
        return "\n".join(lines)
    return chat


def test_without_taste_it_does_not_call_the_model_at_all():
    calls = []
    out = rewriter(chat=scripted("x", calls=calls)).prompts("p", "art", BRIEF, 2, Taste([], []))
    assert calls == []
    assert out == [f"{BRIEF} — variant 1 of 2", f"{BRIEF} — variant 2 of 2"]


def test_with_taste_it_returns_the_models_lines():
    out = rewriter(chat=scripted("tower in fog, engraving", "tower at dusk, engraving")).prompts(
        "p", "art", BRIEF, 2, TASTE)
    assert out == ["tower in fog, engraving", "tower at dusk, engraving"]


def test_the_guidance_reaches_the_model():
    calls = []
    rewriter(chat=scripted("a", "b", calls=calls)).prompts("p", "art", BRIEF, 2, TASTE)
    sent = calls[0]
    assert "a gate in fog, engraving" in sent
    assert "a gate, neon" in sent
    assert BRIEF in sent


def test_a_second_identical_brief_is_served_from_storage():
    blobs, calls = MemoryBlobs(), []
    first = rewriter(blobs, scripted("a", "b", calls=calls)).prompts("p", "art", BRIEF, 2, TASTE)
    second = rewriter(blobs, scripted("DIFFERENT", "LINES", calls=calls)).prompts(
        "p", "art", BRIEF, 2, TASTE)
    assert second == first
    assert len(calls) == 1, "the model must be asked once, not once per run"


def test_changed_taste_earns_a_fresh_rewrite():
    """Dropping something new is a change of mind; the cache must not hide it."""
    blobs = MemoryBlobs()
    rewriter(blobs, scripted("old-a", "old-b")).prompts("p", "art", BRIEF, 2, TASTE)
    moved_on = Taste(kept=TASTE.kept, dropped=[*TASTE.dropped, "a gate, chrome"])
    out = rewriter(blobs, scripted("new-a", "new-b")).prompts("p", "art", BRIEF, 2, moved_on)
    assert out == ["new-a", "new-b"]


def test_a_model_failure_falls_back_to_the_plain_expansion():
    def boom(prompt):
        raise RuntimeError("provider down")

    out = rewriter(chat=boom).prompts("p", "art", BRIEF, 2, TASTE)
    assert out == [f"{BRIEF} — variant 1 of 2", f"{BRIEF} — variant 2 of 2"]


def test_a_short_reply_is_padded_and_a_long_one_trimmed():
    short = rewriter(chat=scripted("only one")).prompts("p", "art", BRIEF, 3, TASTE)
    assert len(short) == 3

    long = rewriter(chat=scripted("a", "b", "c", "d", "e")).prompts("p", "art", BRIEF, 2, TASTE)
    assert long == ["a", "b"]


def test_numbering_and_blank_lines_are_stripped():
    out = rewriter(chat=scripted("1. tower in fog", "", "2) tower at dusk", "   ")).prompts(
        "p", "art", BRIEF, 2, TASTE)
    assert out == ["tower in fog", "tower at dusk"]


def test_a_refusal_or_preamble_does_not_become_a_prompt():
    """Small models like to explain themselves. That text is not an asset brief."""
    out = rewriter(chat=scripted("Here are the prompts:", "tower in fog", "tower at dusk")).prompts(
        "p", "art", BRIEF, 2, TASTE)
    assert out == ["tower in fog", "tower at dusk"]


def test_what_is_cached_is_readable_not_opaque():
    blobs = MemoryBlobs()
    rewriter(blobs, scripted("a", "b")).prompts("p", "art", BRIEF, 2, TASTE)
    key = next(k for k in blobs.keys("p/taste/"))
    stored = json.loads(blobs.get(key))
    assert stored["prompts"] == ["a", "b"]
    assert stored["brief"] == BRIEF
