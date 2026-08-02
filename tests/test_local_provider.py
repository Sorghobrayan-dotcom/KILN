import io

from PIL import Image

from kiln.local_provider import LocalImageProvider, render


def test_render_is_deterministic():
    assert render("a knight") == render("a knight")


def test_different_prompts_render_differently():
    assert render("a knight") != render("a queen")


def test_render_is_a_valid_png():
    im = Image.open(io.BytesIO(render("a knight")))
    assert im.format == "PNG"
    assert im.size == (512, 512)


def test_provider_attaches_an_asset(tmp_path):
    from genblaze_core import Modality
    from genblaze_core.models.step import Step

    provider = LocalImageProvider(output_dir=tmp_path)
    step = Step(provider="kiln-local", model="kiln-local-1",
                prompt="a plumb line", modality=Modality.IMAGE)

    out = provider.generate(step)

    assert len(out.assets) == 1
    asset = out.assets[0]
    assert asset.media_type == "image/png"
    assert asset.url.startswith("file://")
    written = list(tmp_path.glob("*.png"))
    assert len(written) == 1
    assert written[0].read_bytes() == render("a plumb line")
