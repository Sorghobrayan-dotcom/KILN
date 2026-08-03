"""Seed the two demo projects in the real bucket, and seal a v1 for each.

- providence      the game: NPC voice lines + engraved concept art
- midnight-radio  the podcast: intro voice + jingle + cover art

Two projects, two audiences, one instance. The podcast is the proof that
nothing in Kiln knows what a game is. Idempotent: the step cache makes a
second run cost nothing, and publish() only seals what is approved and
unshipped.
"""
import _env

_env.load()

from kiln.blobs import B2Blobs  # noqa: E402
from kiln.config import settings  # noqa: E402
from kiln.forge import b2_sink  # noqa: E402
from kiln.library import Library  # noqa: E402
from kiln.service import Forge  # noqa: E402

st = settings()
blobs = B2Blobs(st.b2_bucket, st.b2_key_id, st.b2_app_key, st.b2_endpoint)
forge = Forge(blobs, st, sink=b2_sink(st))

BRIEFS = {
    "providence": [
        ("voice", "It is written. You will not pass this gate tonight.", 2),
        ("sfx", "heavy wooden gate creaking shut, stone hall reverb", 1),
        ("art", "weathered stone gate of a hill fort at dusk, monochrome engraving, high contrast woodcut", 2),
    ],
    "midnight-radio": [
        ("voice", "Welcome back to Midnight Radio, the show that keeps the lights on after everyone else has gone home.", 1),
        ("sfx", "warm radio jingle sting, three notes, vinyl crackle", 1),
        ("art", "art deco radio microphone under a single spotlight, deep blue and gold, podcast cover", 1),
    ],
}


for project, briefs in BRIEFS.items():
    print(f"\n=== {project} ===")
    library = Library(blobs, project)

    for kind, description, count in briefs:
        results = forge.generate(project, description, count, kind)
        for r in results:
            state = "cache" if r["cached"] else ("FAILED" if r.get("failed") else "new")
            print(f"  [{state:6s}] {kind:5s} {r['asset_id'][:16]}")
            if not r.get("failed"):
                library.record(
                    r["asset_id"],
                    prompt=r["prompt"], model=r["model"], provider=r["provider"],
                    url=r["url"], sha256=r["sha256"],
                    kind=r.get("kind"), modality=r.get("modality"),
                    manifest_uri=r.get("manifest_uri"),
                    score=r.get("score"), reasons=r.get("reasons"),
                )

    # approve everything staged that generated cleanly, then seal
    staged = [a for a in library.staging() if a["state"] == "staged" and a.get("sha256")]
    for asset in staged:
        library.approve(asset["asset"])
    manifest = library.publish()
    print(f"  sealed v{manifest['version']} with {len(manifest['assets'])} asset(s)")
    print(f"  manifest: {st.b2_endpoint}/{st.b2_bucket}/{project}/v{manifest['version']}/manifest.json")

print(f"\nsavings: {forge.savings}")
