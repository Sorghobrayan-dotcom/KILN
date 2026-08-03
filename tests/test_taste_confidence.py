"""Below a handful of judgements there is no pattern, only coincidence.

Claiming to have learned from one kept prompt is the kind of thing that makes a
feature feel like a toy the first time a user notices.
"""
from kiln.taste import MIN_TO_LEARN, Taste, guidance_from


def test_a_single_judgement_is_not_a_taste():
    t = Taste(kept=["a knight"], dropped=[])
    assert not t.informed
    assert guidance_from(t) == ""


def test_learning_starts_at_the_threshold():
    below = Taste(kept=["a"] * (MIN_TO_LEARN - 1), dropped=[])
    at = Taste(kept=["a"] * MIN_TO_LEARN, dropped=[])
    assert not below.informed
    assert at.informed


def test_kept_and_dropped_count_together_towards_the_threshold():
    t = Taste(kept=["a"], dropped=["b", "c"])
    assert t.judged == 3
    assert t.informed is (3 >= MIN_TO_LEARN)


def test_progress_is_reported_while_still_learning():
    t = Taste(kept=["a"], dropped=[])
    assert t.summary == f"still learning, 1 of {MIN_TO_LEARN} judgements so far"


def test_summary_reports_the_split_once_it_has_enough():
    t = Taste(kept=["a", "b"], dropped=["c"])
    assert t.summary == "informed by 2 kept, 1 dropped"


def test_nothing_judged_says_nothing():
    assert Taste([], []).summary == ""


def test_thin_evidence_is_hedged_in_the_guidance():
    """With few examples a model should be told they may be coincidence, or it
    will latch onto a shared word and call it a style."""
    thin = guidance_from(Taste(kept=["a", "b"], dropped=["c"]))
    assert "few" in thin.lower() or "may" in thin.lower()

    thick = guidance_from(Taste(kept=["a", "b", "c", "d"], dropped=["e", "f"]))
    assert "few" not in thick.lower()
