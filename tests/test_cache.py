from genblaze_core import Modality
from genblaze_core.models.step import Step

from kiln.blobs import MemoryBlobs
from kiln.cache import B2StepCache, was_cache_hit


def a_step(prompt="a knight"):
    return Step(provider="nvidia", model="sdxl", prompt=prompt, modality=Modality.IMAGE)


def test_miss_then_hit_roundtrip():
    c = B2StepCache(MemoryBlobs(), prefix="demo/cache")
    step = a_step()
    assert c.get(step) is None
    c.put(step, step)
    got = c.get(step)
    assert got is not None and got.prompt == "a knight"


def test_different_prompts_do_not_collide():
    c = B2StepCache(MemoryBlobs(), prefix="demo/cache")
    c.put(a_step("a knight"), a_step("a knight"))
    assert c.get(a_step("a queen")) is None


def test_tenant_partitions_the_cache():
    c = B2StepCache(MemoryBlobs(), prefix="demo/cache")
    step = a_step()
    c.put(step, step, tenant_id="alice")
    assert c.get(step, tenant_id="bob") is None
    assert c.get(step, tenant_id="alice") is not None


def test_survives_a_new_instance_same_bucket():
    blobs = MemoryBlobs()
    B2StepCache(blobs, prefix="demo/cache").put(a_step(), a_step())
    # a fresh process against the same bucket — this is the whole point
    assert B2StepCache(blobs, prefix="demo/cache").get(a_step()) is not None


def test_a_hit_is_marked_because_genblaze_returns_it_unflagged():
    c = B2StepCache(MemoryBlobs(), prefix="demo/cache")
    step = a_step()
    assert not was_cache_hit(step)
    c.put(step, step)
    hit = c.get(step)
    assert was_cache_hit(hit), "a caller cannot otherwise tell a hit from a fresh run"


def test_marking_a_hit_preserves_existing_metadata():
    c = B2StepCache(MemoryBlobs(), prefix="demo/cache")
    step = a_step()
    step.metadata = {"project": "providence"}
    c.put(step, step)
    hit = c.get(step)
    assert hit.metadata["project"] == "providence"
    assert was_cache_hit(hit)


def test_hits_and_misses_are_counted():
    c = B2StepCache(MemoryBlobs(), prefix="demo/cache")
    step = a_step()
    c.get(step)
    c.put(step, step)
    c.get(step)
    c.get(step)
    assert (c.misses, c.hits) == (1, 2)


def test_corrupt_entry_is_a_miss_not_a_crash():
    blobs = MemoryBlobs()
    c = B2StepCache(blobs, prefix="demo/cache")
    c.put(a_step(), a_step())
    key = next(iter(blobs.keys()))
    blobs.put(key, b"{not json", "application/json")
    assert c.get(a_step()) is None
    assert c.corruption_count == 1
