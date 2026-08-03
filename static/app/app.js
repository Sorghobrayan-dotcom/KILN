const $ = (id) => document.getElementById(id);
const project = () => $("project").value.trim();
const headers = () => ({
  "X-Kiln-Token": $("token").value,
  "Content-Type": "application/json",
});

function say(text, kind = "") {
  const el = $("status");
  el.textContent = text;
  el.className = `status ${kind}`;
}

function showTaste(text) {
  const el = $("taste");
  el.textContent = text ? `Prompts on this project are ${text}.` : "";
  el.hidden = !text;
}

function showSavings(savings) {
  if (!savings || savings.generations_avoided === 0) {
    $("savings").textContent = "";
    return;
  }
  const { generations_avoided: avoided, generations_paid_for: paid, hit_rate: rate } = savings;
  $("savings").textContent =
    `This library has skipped ${avoided} generation(s). ` +
    `${paid} were paid for, ${Math.round(rate * 100)}% came from the bucket.`;
}

async function loadKinds() {
  const { kinds } = await (await fetch("/api/kinds")).json();
  const select = $("kind");
  select.replaceChildren();
  for (const k of kinds) {
    const option = document.createElement("option");
    option.value = k.key;
    option.textContent = k.enabled ? k.label : `${k.label} (unavailable)`;
    option.disabled = !k.enabled;
    option.title = k.hint;
    select.append(option);
  }
  const firstEnabled = kinds.find((k) => k.enabled);
  if (firstEnabled) select.value = firstEnabled.key;
}

$("brief-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("go").disabled = true;
  say("Working…");
  try {
    const res = await fetch("/api/briefs", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        project: project(),
        description: $("description").value,
        count: Number($("count").value),
        kind: $("kind").value,
      }),
    });
    const body = await res.json();
    if (!res.ok) {
      const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      say(`Error: ${detail ?? res.status}`, "err");
      return;
    }
    say(body.summary, body.served_from_cache > 0 ? "hit" : "");
    showSavings(body.savings);
    showTaste(body.taste);
    await refresh();
  } catch (err) {
    say(`Error: ${err.message}`, "err");
  } finally {
    $("go").disabled = false;
  }
});

// Dropping an asset takes it out of the grid but leaves it in the ledger.
// Nothing here throws a decision away, so we hide it and keep a count.
let showDropped = false;

let assets = [];

async function refresh() {
  if (!project()) return;
  const res = await fetch(`/api/projects/${encodeURIComponent(project())}/staging`);
  assets = (await res.json()).assets;
  render();
}

function render() {
  const dropped = assets.filter((a) => a.state === "rejected");
  const visible = showDropped ? assets : assets.filter((a) => a.state !== "rejected");

  const toggle = $("dropped");
  if (dropped.length === 0) {
    toggle.hidden = true;
  } else {
    toggle.hidden = false;
    toggle.textContent = showDropped
      ? `Hide ${dropped.length} dropped`
      : `Show ${dropped.length} dropped`;
  }

  $("empty").hidden = visible.length > 0;
  const grid = $("grid");
  grid.replaceChildren();

  for (const asset of visible) {
    const card = document.createElement("div");
    card.className = `card state-${asset.state}`;
    card.append(preview(asset));

    const meta = document.createElement("div");
    meta.className = "meta";
    const bits = [asset.state];
    if (asset.kind) bits.push(asset.kind);
    if (asset.score != null) bits.push(`${asset.score}/10`);
    meta.textContent = bits.join(" · ");
    meta.title = asset.prompt ?? "";
    card.append(meta);

    const acts = document.createElement("div");
    acts.className = "acts";
    acts.append(
      button("Keep", () => decide(asset.asset, "approve")),
      button("Drop", () => decide(asset.asset, "reject")),
      button("Trace", () => showProvenance(asset)),
    );
    card.append(acts);
    grid.append(card);
  }
}

function preview(asset) {
  // a failed asset has no bytes, so say that rather than draw a broken box
  if (!asset.url) {
    const dead = document.createElement("div");
    dead.className = "dead";
    dead.textContent = asset.reasons ?? "no asset";
    return dead;
  }
  if (asset.modality === "audio") {
    const audio = document.createElement("audio");
    audio.src = asset.url;
    audio.controls = true;
    audio.preload = "none";
    return audio;
  }
  if (asset.modality === "video") {
    const video = document.createElement("video");
    video.src = asset.url;
    video.controls = true;
    video.preload = "metadata";
    return video;
  }
  const img = document.createElement("img");
  img.src = asset.url;
  img.alt = asset.prompt ?? "";
  img.loading = "lazy";
  return img;
}

function button(label, onClick) {
  const b = document.createElement("button");
  b.className = "ghost";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

async function decide(asset, action) {
  // The decision is already made: it was the click. Waiting three round trips
  // to Frankfurt before showing it makes the app feel broken, so we show it at
  // once and put it back if the write refuses.
  const entry = assets.find((a) => a.asset === asset);
  const previous = entry?.state;
  if (entry) {
    entry.state = action === "approve" ? "approved" : "rejected";
    render();
  }

  const res = await fetch(
    `/api/projects/${encodeURIComponent(project())}/assets/${encodeURIComponent(asset)}/${action}`,
    { method: "POST", headers: headers() },
  );

  if (!res.ok) {
    if (entry) {
      entry.state = previous;
      render();
    }
    say(res.status === 401 ? "Wrong token. Changes are protected." : `Error ${res.status}`, "err");
  }
}

function rows(target, pairs) {
  for (const [key, value] of Object.entries(pairs)) {
    if (value == null || value === "") continue;
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    target.append(dt, dd);
  }
}

function section(title) {
  const h = document.createElement("h3");
  h.textContent = title;
  return h;
}

async function showProvenance(asset) {
  const body = $("prov-body");
  body.replaceChildren();
  $("prov").showModal();

  const kiln = document.createElement("dl");
  rows(kiln, {
    prompt: asset.prompt,
    kind: asset.kind,
    modality: asset.modality,
    state: asset.state,
    version: asset.version ?? "not sealed yet",
    verdict: asset.reasons,
  });
  body.append(section("What a human decided"), kiln);

  const loading = document.createElement("p");
  loading.className = "muted";
  loading.textContent = "Reading the Genblaze manifest from storage…";
  body.append(loading);

  let payload;
  try {
    const res = await fetch(
      `/api/projects/${encodeURIComponent(project())}/assets/${encodeURIComponent(asset.asset)}/provenance`,
    );
    payload = await res.json();
  } catch (err) {
    loading.textContent = `Could not read the manifest: ${err.message}`;
    return;
  }
  loading.remove();

  const gb = document.createElement("dl");
  const manifest = payload.manifest;
  const step = manifest?.run?.steps?.[0] ?? {};

  rows(gb, {
    provider: step.provider ?? asset.provider,
    model: step.model ?? asset.model,
    "sha-256": asset.sha256,
    "canonical hash": manifest?.canonical_hash,
    "schema version": manifest?.schema_version,
    "run id": manifest?.run?.run_id,
    started: step.started_at,
    completed: step.completed_at,
    "cost (usd)": step.cost_usd,
    retries: step.retries,
    "manifest uri": manifest?.manifest_uri ?? asset.manifest_uri,
    signature: manifest?.signature ? "present" : undefined,
  });
  body.append(section("How Genblaze made it"), gb);

  if (payload.manifest_note) {
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = payload.manifest_note;
    body.append(note);
  }

  if (manifest) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Raw manifest";
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(manifest, null, 2);
    details.append(summary, pre);
    body.append(details);
  }
}

$("refresh").addEventListener("click", refresh);

$("publish").addEventListener("click", async () => {
  const res = await fetch(`/api/projects/${encodeURIComponent(project())}/publish`, {
    method: "POST",
    headers: headers(),
  });
  const body = await res.json();
  if (!res.ok) {
    say(res.status === 401 ? "Wrong token." : `Error ${res.status}`, "err");
    return;
  }
  say(
    `Sealed v${body.version} with ${body.assets.length} asset(s), written to ` +
    `${project()}/v${body.version}/manifest.json in B2. Nothing can change it now.`,
  );
  await refresh();
});

$("dropped").addEventListener("click", () => {
  // purely a filter over what we already hold, so no round trip
  showDropped = !showDropped;
  render();
});

loadKinds().then(refresh);
