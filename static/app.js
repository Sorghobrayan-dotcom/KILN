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
      }),
    });
    const body = await res.json();
    if (!res.ok) {
      say(body.detail ? `Error: ${JSON.stringify(body.detail)}` : `Error ${res.status}`, "err");
      return;
    }
    say(body.summary, body.served_from_cache > 0 ? "hit" : "");
    await refresh();
  } catch (err) {
    say(`Error: ${err.message}`, "err");
  } finally {
    $("go").disabled = false;
  }
});

async function refresh() {
  if (!project()) return;
  const res = await fetch(`/api/projects/${encodeURIComponent(project())}/staging`);
  const { assets } = await res.json();

  $("empty").hidden = assets.length > 0;
  const grid = $("grid");
  grid.replaceChildren();

  for (const asset of assets) {
    const card = document.createElement("div");
    card.className = `card state-${asset.state}`;

    const img = document.createElement("img");
    img.src = asset.url;
    img.alt = asset.prompt ?? "";
    img.loading = "lazy";
    card.append(img);

    const meta = document.createElement("div");
    meta.className = "meta";
    const score = asset.score != null ? ` · ${asset.score}/10` : "";
    meta.textContent = `${asset.state}${score}`;
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

function button(label, onClick) {
  const b = document.createElement("button");
  b.className = "ghost";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

async function decide(asset, action) {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(project())}/assets/${encodeURIComponent(asset)}/${action}`,
    { method: "POST", headers: headers() },
  );
  if (!res.ok) {
    say(res.status === 401 ? "Wrong token — mutations are protected." : `Error ${res.status}`, "err");
    return;
  }
  await refresh();
}

function showProvenance(asset) {
  const dl = $("prov-body");
  dl.replaceChildren();
  const rows = {
    prompt: asset.prompt,
    provider: asset.provider,
    model: asset.model,
    "sha-256": asset.sha256,
    score: asset.score,
    verdict: asset.reasons,
    state: asset.state,
    version: asset.version ?? "not sealed yet",
  };
  for (const [key, value] of Object.entries(rows)) {
    if (value == null || value === "") continue;
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    dl.append(dt, dd);
  }
  $("prov").showModal();
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
    `Sealed v${body.version}: ${body.assets.length} asset(s) → ` +
    `${project()}/v${body.version}/manifest.json in B2. That version can never change.`,
  );
  await refresh();
});

refresh();
