# Deploying Kiln

**One server, one port, one origin.** The landing page, the tool and the API are
served by the same FastAPI process, and every link between them is relative.
There is no second deployment to keep in sync, no CORS, and no way for the
showcase to describe a version of the app that is not the one running.

```
/            the showcase, what Kiln is, in ten seconds
/app/        the tool, brief, judge, seal
/api/…       the API the tool calls, same origin
/files/…     assets, when no bucket is configured
/health      readiness, savings counter, kind roster
```

---

## Hugging Face Spaces

**Create the Space** (manual, needs your account):

1. <https://huggingface.co/new-space>
2. Name `kiln`, SDK **Docker**, hardware **CPU basic (free)**, visibility **Public**.

**Set the secrets**, Space → *Settings* → *Variables and secrets* → *New secret*:

| Name | Value |
|---|---|
| `B2_KEY_ID` | your Backblaze application key id |
| `B2_APP_KEY` | your Backblaze application key |
| `B2_BUCKET` | `kiln-assets` |
| `B2_ENDPOINT` | `https://s3.eu-central-003.backblazeb2.com` |
| `ELEVENLABS_API_KEY` | unlocks `voice` and `sfx` |
| `KILN_TOKEN` | `kiln-demo-2026`, published as the test credential |

Without the B2 secrets the Space still runs and still generates real media, but
state resets on every restart, which defeats the point of the project.

**Push the code:**

```bash
git remote add space https://huggingface.co/spaces/<your-user>/kiln
git push space master:main
```

First build takes a few minutes. Afterwards the dependency layer is cached and a
code change redeploys in seconds.

## Before submitting

- [ ] Replace the two `TODO` links in [`static/index.html`](static/index.html)
      the YouTube URL and the GitHub URL.
- [ ] Check from a **logged-out** browser, on a phone:
      `/` loads, `/app/` works, a brief generates, the same brief comes back
      *served from B2*, Trace shows the Genblaze manifest.
- [ ] `GET /health` returns `{"ok": true, …}`.

Cold start is import time only, about 1.6 s locally, because nothing contacts
a provider or a bucket before uvicorn binds. A Space that has gone to sleep still
takes longer to wake; the landing page is deliberately static and light so the
first paint is immediate once it does.

## What goes in the Devpost submission

| Field | Value |
|---|---|
| App URL | the Space URL, it opens on the showcase, one click from the tool |
| Repository | the GitHub repo, public, MIT visible in *About* |
| Video | the YouTube link, public, under 3 minutes |
| Test credential | `kiln-demo-2026`, the rules require it for authenticated apps |
| Providers and models | Pollinations `sana`; ElevenLabs `eleven_flash_v2_5`, `eleven_text_to_sound_v2`; GMI Cloud `Veo3-Fast`, `reve-remix-20250915` (wired, unfunded) |
