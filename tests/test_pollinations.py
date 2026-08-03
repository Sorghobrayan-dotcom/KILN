import urllib.parse
from pathlib import Path

import httpx
import pytest
from genblaze_core import Modality
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.step import Step

from kiln.pollinations import PollinationsImageProvider, build_url, seed_for


def a_step(prompt="a plumb line", model="sana", **kw):
    return Step(provider="pollinations", model=model, prompt=prompt,
                modality=Modality.IMAGE, **kw)


def transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


def ok(request):
    return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})


def test_seed_is_stable_for_a_prompt():
    assert seed_for("a knight") == seed_for("a knight")
    assert seed_for("a knight") != seed_for("a queen")
    assert 0 <= seed_for("x") <= 0x7FFFFFFF


def test_url_carries_the_prompt_and_the_derived_seed():
    url = build_url("a knight", "sana", 512, 512)
    assert url.startswith("https://image.pollinations.ai/prompt/")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert query["seed"] == [str(seed_for("a knight"))]
    assert query["width"] == ["512"] and query["model"] == ["sana"]
    assert query["nologo"] == ["true"]


def test_slashes_in_a_prompt_do_not_escape_the_path():
    url = build_url("a knight / a queen", "sana", 512, 512)
    assert "/prompt/a%20knight%20%2F%20a%20queen?" in url


def test_generate_attaches_the_image_and_its_hash(tmp_path):
    provider = PollinationsImageProvider(output_dir=tmp_path, client=transport(ok))
    out = provider.generate(a_step())

    assert len(out.assets) == 1
    asset = out.assets[0]
    assert asset.media_type == "image/jpeg"
    assert asset.sha256 and len(asset.sha256) == 64
    written = list(tmp_path.glob("*.jpg"))
    assert len(written) == 1 and written[0].read_bytes() == JPEG


def test_an_http_error_is_a_provider_error_not_a_stray_exception(tmp_path):
    def boom(request):
        return httpx.Response(503, text="upstream busy")

    provider = PollinationsImageProvider(output_dir=tmp_path, client=transport(boom))
    with pytest.raises(ProviderError, match="503"):
        provider.generate(a_step())


def test_a_text_body_dressed_as_200_is_rejected(tmp_path):
    def html(request):
        return httpx.Response(200, text="<html>rate limited</html>",
                              headers={"content-type": "text/html"})

    provider = PollinationsImageProvider(output_dir=tmp_path, client=transport(html))
    with pytest.raises(ProviderError, match="not an image"):
        provider.generate(a_step())


def test_a_transport_failure_is_reported_as_unreachable(tmp_path):
    def dead(request):
        raise httpx.ConnectError("no route")

    provider = PollinationsImageProvider(output_dir=tmp_path, client=transport(dead))
    with pytest.raises(ProviderError, match="unreachable"):
        provider.generate(a_step())


def test_without_an_output_dir_the_file_lands_in_temp():
    """Genblaze's sink refuses to upload a file from an arbitrary path. It has
    to sit under temp or a declared output_dir. Defaulting elsewhere silently
    breaks every transfer, which is how this was found."""
    import tempfile
    from urllib.parse import unquote, urlparse

    provider = PollinationsImageProvider(client=transport(ok))
    out = provider.generate(a_step())

    path = Path(unquote(urlparse(out.assets[0].url).path).lstrip("/"))
    assert Path(tempfile.gettempdir()).resolve() in path.resolve().parents


def test_an_explicit_seed_overrides_the_derived_one(tmp_path):
    seen = {}

    def capture(request):
        seen["url"] = str(request.url)
        return ok(request)

    provider = PollinationsImageProvider(output_dir=tmp_path, client=transport(capture))
    provider.generate(a_step(seed=42))
    assert "seed=42" in seen["url"]
