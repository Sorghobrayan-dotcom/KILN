import pytest

from kiln.forge import ForgeError, harvest, region_of


class FakeAsset:
    def __init__(self, sha="aa", url="https://b2/aa.png"):
        self.sha256 = sha
        self.url = url


class FakeStep:
    def __init__(self, assets=(), error=None, status="succeeded", model="flux.1-schnell", cached=False):
        self.assets = list(assets)
        self.error = error
        self.status = status
        self.model = model
        self.cached = cached


class FakeRun:
    def __init__(self, steps):
        self.steps = list(steps)
        self.run_id = "run-123"


class FakeManifest:
    manifest_uri = "b2://kiln-assets/manifest.json"


class FakeResult:
    def __init__(self, steps):
        self.run = FakeRun(steps)
        self.manifest = FakeManifest()


def test_region_is_derived_from_the_endpoint():
    assert region_of("https://s3.eu-central-003.backblazeb2.com") == "eu-central-003"
    assert region_of("https://s3.us-west-004.backblazeb2.com/") == "us-west-004"
    assert region_of("https://example.com") is None


def test_successful_run_is_flattened():
    got = harvest(FakeResult([FakeStep(assets=[FakeAsset()])]), "a knight", "nvidia-image")
    assert got.sha256 == "aa"
    assert got.model == "flux.1-schnell"
    assert got.manifest_uri == "b2://kiln-assets/manifest.json"
    assert got.cached is False


def test_failed_step_raises_with_the_provider_reason_not_an_indexerror():
    result = FakeResult([FakeStep(error="NVIDIA submit failed (transport): read timed out", status="failed")])
    with pytest.raises(ForgeError) as exc:
        harvest(result, "a knight", "nvidia-image")
    assert "read timed out" in str(exc.value)
    assert exc.value.run_id == "run-123"
    assert exc.value.model == "flux.1-schnell"


def test_succeeded_but_empty_run_still_explains_itself():
    with pytest.raises(ForgeError, match="succeeded with no asset"):
        harvest(FakeResult([FakeStep(assets=[], status="succeeded")]), "a knight", "nvidia-image")


def test_run_with_no_steps_is_named_as_such():
    with pytest.raises(ForgeError, match="no steps at all"):
        harvest(FakeResult([]), "a knight", "nvidia-image")


def test_cache_hit_is_reported():
    got = harvest(FakeResult([FakeStep(assets=[FakeAsset()], cached=True)]), "k", "nvidia-image")
    assert got.cached is True
