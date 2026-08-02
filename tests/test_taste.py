from kiln.taste import Taste, guidance_from


def entry(asset, prompt, state, kind="art", **extra):
    return {"asset": asset, "prompt": prompt, "state": state, "kind": kind, **extra}


def test_taste_is_empty_when_nothing_was_judged():
    t = Taste.from_entries([entry("a", "a knight", "staged")], kind="art")
    assert t.kept == [] and t.dropped == []
    assert not t.informed


def test_taste_separates_kept_from_dropped():
    t = Taste.from_entries([
        entry("a", "a knight in fog", "approved"),
        entry("b", "a knight, neon", "rejected"),
        entry("c", "a queen in fog", "published"),
        entry("d", "undecided", "staged"),
    ], kind="art")
    assert t.kept == ["a knight in fog", "a queen in fog"]   # published counts as kept
    assert t.dropped == ["a knight, neon"]
    assert t.informed


def test_taste_only_learns_from_the_same_kind():
    """A voice line says nothing about what makes a good engraving."""
    t = Taste.from_entries([
        entry("a", "a knight", "approved", kind="art"),
        entry("b", "gate creaking", "approved", kind="sfx"),
    ], kind="art")
    assert t.kept == ["a knight"]


def test_recent_judgements_win_when_there_are_many():
    entries = [entry(str(i), f"prompt {i}", "approved") for i in range(20)]
    t = Taste.from_entries(entries, kind="art", limit=5)
    assert t.kept == [f"prompt {i}" for i in range(15, 20)]


def test_guidance_is_empty_without_judgements():
    assert guidance_from(Taste([], [])) == ""


def test_guidance_names_both_sides():
    text = guidance_from(Taste(kept=["a knight in fog"], dropped=["a knight, neon"]))
    assert "a knight in fog" in text
    assert "a knight, neon" in text
    assert "kept" in text.lower() and "rejected" in text.lower()


def test_guidance_survives_one_sided_history():
    only_kept = guidance_from(Taste(kept=["a knight"], dropped=[]))
    only_dropped = guidance_from(Taste(kept=[], dropped=["neon"]))
    assert "a knight" in only_kept and "rejected" not in only_kept.lower()
    assert "neon" in only_dropped and "kept" not in only_dropped.lower()


def test_summary_reports_what_it_learned_from():
    t = Taste(kept=["a", "b"], dropped=["c"])
    assert t.summary == "informed by 2 kept, 1 dropped"
    assert Taste([], []).summary == ""
