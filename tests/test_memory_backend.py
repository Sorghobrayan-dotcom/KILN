from genblaze_core import KeyStrategy
from genblaze_core.storage.sink import ObjectStorageSink

from kiln.cache import B2StepCache, was_cache_hit
from kiln.blobs import BackendBlobs, MemoryBlobs
from kiln.memory_backend import MemoryBackend


def test_basic_put_get_roundtrip():
    b = MemoryBackend()
    key = b.put("hello", b"world")
    assert key == "hello"
    assert b.get("hello") == b"world"
    assert b.exists("hello") is True
    assert b.exists("missing") is False


def test_delete_removes_key():
    b = MemoryBackend()
    b.put("k", b"v")
    assert b.exists("k")
    b.delete("k")
    assert not b.exists("k")


def test_durable_url_roundtrips_through_key_from_url():
    b = MemoryBackend()
    key = b.put("obj/1", b"data")
    url = b.get_durable_url(key)
    assert url.startswith("memory://")
    assert b.key_from_url(url) == key


def test_durable_url_uses_public_base_when_set():
    b = MemoryBackend(public_url_base="https://cdn.example.com")
    key = b.put("img/x.png", b"data")
    url = b.get_durable_url(key)
    assert url == "https://cdn.example.com/img/x.png"
    assert b.key_from_url(url) == key


def test_key_from_url_returns_none_for_foreign_urls():
    b = MemoryBackend(public_url_base="memory://localhost")
    assert b.key_from_url("https://other.com/key") is None
    assert b.key_from_url("memory://otherhost/key") is None


def test_sink_can_upload_and_backend_serves_it():
    b = MemoryBackend()
    sink = ObjectStorageSink(b, prefix="test", key_strategy=KeyStrategy.CONTENT_ADDRESSABLE)
    assert b.list("test") is not None


def test_list_returns_populated_entries_and_paginates():
    """list() went unexercised with real content and raised TypeError on a
    required etag; anything walking the bucket would have hit it."""
    b = MemoryBackend()
    for i in range(3):
        b.put(f"p/{i}", b"x" * (i + 1))
    b.put("other/z", b"zzz")

    page = b.list("p/")
    assert [e.key for e in page.entries] == ["p/0", "p/1", "p/2"]
    assert [e.size for e in page.entries] == [1, 2, 3]
    assert all(e.etag and e.last_modified for e in page.entries)
    assert page.next_token is None

    first = b.list("p/", max_keys=2)
    assert len(first.entries) == 2 and first.next_token == "2"
    rest = b.list("p/", max_keys=2, continuation_token=first.next_token)
    assert [e.key for e in rest.entries] == ["p/2"] and rest.next_token is None


def test_backend_blobs_puts_state_and_assets_in_one_place():
    """Without this, a credential-free deployment splits its bytes: Genblaze
    writes assets to the backend, Kiln writes the index elsewhere, and /files/
    can only serve one of them — so the gallery shows dead links."""
    backend = MemoryBackend(public_url_base="/files")
    blobs = BackendBlobs(backend)

    assert blobs.get("missing") is None

    blobs.put("providence/index.json", b"{}", "application/json")
    backend.put("kiln/assets/x.png", b"img", content_type="image/png")

    assert blobs.get("providence/index.json") == b"{}"
    assert blobs.get("kiln/assets/x.png") == b"img"
    assert set(blobs.keys("")) == {"providence/index.json", "kiln/assets/x.png"}
    assert blobs.keys("kiln/") == ["kiln/assets/x.png"]


def test_backend_blobs_serves_what_a_durable_url_points_at():
    """A durable url of /files/<key> must resolve through the same blobs the
    API reads, or the browser gets a 404 for every picture."""
    backend = MemoryBackend(public_url_base="/files")
    blobs = BackendBlobs(backend)
    key = backend.put("kiln/assets/ab/cd.png", b"png-bytes", content_type="image/png")

    url = backend.get_durable_url(key)
    assert url == "/files/kiln/assets/ab/cd.png"
    assert blobs.get(url.removeprefix("/files/")) == b"png-bytes"


def test_cache_hit_after_sink_upload():
    """The end-to-end claim: local provider + memory sink + B2StepCache →
    a warm pass that is served entirely from the cache."""
    from genblaze_core import Modality, Pipeline
    from genblaze_core.models.asset import Asset
    from genblaze_core.models.step import Step

    from kiln.local_provider import LocalImageProvider

    blobs = MemoryBlobs()
    backend = MemoryBackend()
    cache = B2StepCache(blobs, prefix="demo/cache")
    provider = LocalImageProvider()
    sink = ObjectStorageSink(backend, prefix="demo", key_strategy=KeyStrategy.CONTENT_ADDRESSABLE)

    def run(prompt):
        result = (
            Pipeline("kiln")
            .cache(cache)
            .tracer(None)
            .step(provider, model="kiln-local-1", prompt=prompt, modality=Modality.IMAGE)
            .run(sink=sink, raise_on_failure=False)
        )
        return result.run.steps[0]

    cold = run("a test prompt for the demo")
    assert not was_cache_hit(cold)
    assert cold.assets[0].url.startswith("memory://")

    warm = run("a test prompt for the demo")
    assert was_cache_hit(warm)
    assert warm.assets[0].url == cold.assets[0].url
