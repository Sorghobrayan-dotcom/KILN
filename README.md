---
title: Kiln
emoji: 🏺
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: A curated, versioned asset library on Genblaze and Backblaze B2
---

# Kiln — assets with a memory

> Built for a game studio because that's where I hit the problem. The loop — generate, judge, seal, never pay twice — belongs to any team producing media at volume.

A curation layer over [Genblaze](https://github.com/backblaze-labs/genblaze) that ships generated media to [Backblaze B2](https://www.backblaze.com/cloud-storage) and adds human approval, versioned manifests, and — most importantly — a **durable step cache that lives in B2** so you never pay for the same generation twice, even across deploys.

## The problem it solves

Every hosted AI tier rate-limits or 504s. When that happens, your pipeline retries — and pays again for a PNG it already produced. Worse, Genblaze's built-in step cache is disk-backed: it dies with the container, so every redeploy regenerates everything.

Kiln implements the same `StepCache` contract against B2 instead of disk. The cache is shared, durable, and survives any restart. The second time you request the same prompt, Genblaze returns the cached step instantly — zero API calls, zero cost.

## The hosted demo

- **App:** *(deployed URL)*
- **Test credential:** paste `kiln-demo-2026` into the Token field. Reads need
  nothing at all, so the staging area, every provenance panel and every sealed
  manifest are browsable without it.

## Run it yourself — one command, no API key

```bash
git clone https://github.com/<your-user>/kiln && cd kiln
python scripts/setup.py                     # venv, deps, tests, and what it can make
.venv/Scripts/python scripts/dev.py         # http://127.0.0.1:8000
```

`setup.py` asks for no credentials. With an empty `.env` you still get **real**
AI generation — the `art` kind uses Pollinations, which needs none — plus the
offline sketch provider.

Send a brief. Then send **the same brief again**: it is served from storage and
costs nothing. That is the whole product in one gesture.

Add keys to `.env` to unlock the rest; see [`.env.example`](.env.example). The
B2 bucket must be **public** — Genblaze hands out credential-free asset URLs, and
a private bucket makes every picture in the gallery a dead link.

## Verify the whole pipeline offline

```bash
.venv/Scripts/python scripts/demo_local.py
```

Real Genblaze `Pipeline`, real `ObjectStorageSink`, real `B2StepCache` — over an
in-memory `StorageBackend` so the credential-free path runs the *same* transfer
and URL-rewriting code as production instead of skipping it. Prints 3/3 cache
hits on the warm pass and seals v1 with only the approved assets.

## How it uses B2 and Genblaze

**Genblaze** — orchestration framework: `Pipeline`, `Step`, `SyncProvider`, `ObjectStorageSink`, `StepCache` contract.

**Backblaze B2** — three distinct surfaces:

| What | How | File |
|---|---|---|
| Generated assets | `ObjectStorageSink` with `S3StorageBackend.for_backblaze` | `assets/{sha256}.ext` |
| Durable step cache | `B2StepCache` implementing Genblaze's `StepCache` | `{project}/cache/{key}.json` |
| App state & manifests | `B2Blobs` direct writes | `{project}/index.json`, `{project}/v{N}/manifest.json` |

All under `KeyStrategy.CONTENT_ADDRESSABLE` — identical bytes share one key, no matter how many runs produced them.

`MemoryBackend` implements the same `StorageBackend` contract in memory, so the
credential-free path exercises the real sink rather than skipping it.

### Three things we found by using Genblaze

All three are defended against in this repository, and all three are worth
reporting upstream:

- **A cache hit is invisible to the caller.** Genblaze returns the cached `Step`
  verbatim — no flag, no tracer event — so an application cannot distinguish a
  hit from a fresh run, and cannot tell its user what was just saved.
  `B2StepCache` stamps `Step.metadata` and counts hits, misses and stale entries.
  That counter is what the UI's savings line reads.
- **A step is cached before its assets are uploaded.** A failed transfer leaves
  an entry pointing at a temp file the next process cannot read, so that prompt
  breaks *permanently* — the failure replays forever. The cache now discards
  entries whose files have vanished.
- **Providers must write under temp or a declared `output_dir`.** The sink
  rejects anything else as path traversal, which is correct, and is not obvious
  until a transfer fails citing allowed directories.

## Architecture

```
brief → Pipeline → [StepCache (B2)] → provider → [Sink (B2)]
                                             ↓
                                    Library → staging → approve → publish (v1, v2, ...)
```

- `api.py` — stateless FastAPI surface; reads/writes go to B2 through `B2Blobs`
- `service.py` — wires briefs to pipelines to the library
- `forge.py` — single entry point to Genblaze: builds pipeline, runs, harvests results
- `cache.py` — `B2StepCache`, the durable cache
- `library.py` — per-project curation: staging, approval, immutable versioned manifests
- `kinds.py` — modality registry with credential gating
- `memory_backend.py` — in-memory `StorageBackend` for offline demos
- `pollinations.py` — a Genblaze `SyncProvider` the SDK does not ship

## API

| Method | Path | Auth | |
|---|---|---|---|
| `GET` | `/health` | — | savings counter and kind roster |
| `GET` | `/api/kinds` | — | what this deployment can make, and why not |
| `POST` | `/api/briefs` | token | `{project, description, count, kind}` |
| `GET` | `/api/projects/{p}/staging` | — | everything awaiting a decision |
| `POST` | `/api/projects/{p}/assets/{a}/approve` | token | |
| `POST` | `/api/projects/{p}/assets/{a}/reject` | token | |
| `GET` | `/api/projects/{p}/assets/{a}/provenance` | — | Kiln's record **and** the Genblaze manifest |
| `POST` | `/api/projects/{p}/publish` | token | seals the next version |
| `GET` | `/api/projects/{p}/versions/{n}/manifest` | — | what a build reads |

Reads are open on purpose: a judge should be able to inspect provenance and
sealed manifests without holding a credential.

## Providers and models

| Kind | Modality | Model | Credential |
|---|---|---|---|
| voice | audio | `eleven_flash_v2_5` | ElevenLabs API key |
| sfx | audio | `eleven_text_to_sound_v2` | ElevenLabs API key |
| art | image | `sana` | free (Pollinations) |
| video | video | `Veo3-Fast` | GMI Cloud API key |
| image | image | `reve-remix-20250915` | GMI Cloud API key |
| sketch | image | `kiln-local-1` | none (deterministic offline) |

A kind is offered when its credential is present; `GET /api/kinds` says why each
missing one is missing, and asking for one returns `400` naming the variable to
set rather than `500`. Nothing contacts a provider at start-up — booting must not
depend on somebody else's uptime.

`sketch` draws locally from the prompt hash. It is deliberately **not** presented
as AI generation: it exists so a fresh clone is never dead on arrival, and so the
tests exercise real Genblaze machinery rather than a stand-in.

## Tests

```bash
python -m pytest tests/ -q
```

68 tests cover the cache contract, failure paths, curation workflow, and provider
integrations — all without a network. Live checks are scripts rather than tests,
because a test that needs somebody else's uptime is not a test:

```bash
python scripts/demo_local.py    # the whole product, no network, 3/3 cache hits
python scripts/smoke_b2.py      # B2 and the durable cache
python scripts/smoke_art.py     # Pollinations -> B2, cold then warm
python scripts/smoke_audio.py   # ElevenLabs voice + sfx -> B2
```

## The story behind this project

Three days before starting this, I shipped a narrative game that needed 24 NPC
portraits. Nothing in that pipeline remembered anything: which prompt made which
portrait, which ones I had accepted, whether a regeneration was a new idea or the
same one paid for twice.

Then, building Kiln, the point made itself again. On 2 August 2026, hunting for a
free image provider:

- NVIDIA validated my request and its own gateway returned **504 after 303
  seconds** with zero bytes. Twice, on two different keys.
- Google returned **429 with `limit: 0`** on all six of its image models — not
  rate-limited, quota zero.
- A failed upload then poisoned the step cache with a path to a temp file that no
  longer existed, and the same prompt failed **three runs in a row** before I
  understood why.

Kiln does not guess at better prompts. It makes sure you never pay twice for the
ones that worked, and that six months from now you can still say where an asset
came from.
