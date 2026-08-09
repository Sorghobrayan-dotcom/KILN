from kiln.blobs import MemoryBlobs
from kiln.library import Library


def lib():
    return Library(MemoryBlobs(), "providence")


def test_record_then_list_staging():
    L = lib()
    L.record("aa", prompt="knight", model="sdxl", provider="nvidia",
             url="https://b2/aa.png", sha256="aa", score=8, reasons="on style")
    items = L.staging()
    assert len(items) == 1
    assert items[0]["sha256"] == "aa" and items[0]["state"] == "staged"


def test_approve_and_reject_move_state():
    L = lib()
    L.record("aa", prompt="k", model="m", provider="p", url="u", sha256="aa")
    L.record("bb", prompt="q", model="m", provider="p", url="u2", sha256="bb")
    L.approve("aa")
    L.reject("bb")
    states = {i["asset"]: i["state"] for i in L.staging()}
    assert states == {"aa": "approved", "bb": "rejected"}


def test_publish_seals_an_immutable_version():
    L = lib()
    L.record("aa", prompt="k", model="m", provider="p", url="u", sha256="aa")
    L.approve("aa")
    m1 = L.publish()
    assert m1["version"] == 1
    assert [a["asset"] for a in m1["assets"]] == ["aa"]
    assert L.manifest(1) == m1
    # published assets leave staging; publishing again ships nothing new
    assert L.publish()["assets"] == []
    assert L.publish()["version"] == 3


def test_rejected_assets_never_ship():
    L = lib()
    L.record("aa", prompt="k", model="m", provider="p", url="u", sha256="aa")
    L.record("bb", prompt="q", model="m", provider="p", url="u2", sha256="bb")
    L.approve("aa")
    L.reject("bb")
    assert [a["asset"] for a in L.publish()["assets"]] == ["aa"]


def test_state_survives_a_new_instance():
    blobs = MemoryBlobs()
    Library(blobs, "p").record("aa", prompt="k", model="m", provider="p", url="u", sha256="aa")
    assert len(Library(blobs, "p").staging()) == 1


def test_recording_the_same_asset_twice_updates_not_duplicates():
    L = lib()
    L.record("aa", prompt="k", model="m", provider="p", url="u", sha256="aa", score=3)
    L.record("aa", prompt="k", model="m", provider="p", url="u2", sha256="aa", score=9)
    items = L.staging()
    assert len(items) == 1 and items[0]["score"] == 9 and items[0]["url"] == "u2"


def test_a_sealed_asset_is_still_findable():
    """staging() hides published assets, so looking provenance up there gave a
    404 for every asset that had shipped. That is the one you most want to
    read."""
    L = lib()
    L.record("aa", prompt="k", model="m", provider="p", url="u", sha256="aa")
    L.approve("aa")
    L.publish()

    assert L.staging() == []
    found = L.entry("aa")
    assert found is not None
    assert found["state"] == "published" and found["prompt"] == "k"


def test_entry_returns_none_for_an_asset_that_never_existed():
    assert lib().entry("nope") is None
