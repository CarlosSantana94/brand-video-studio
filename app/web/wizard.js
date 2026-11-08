"use strict";
// The creator: one question per screen, with a live reel beside it.
const FLOW = ["brand", "videos", "context", "style", "graphics", "captions", "energy", "platforms", "sound", "ready"];
const PLATFORMS = [["tiktok", "TikTok", "🎵", "9:16"], ["reels", "Instagram Reels", "📸", "9:16"], ["shorts", "YouTube Shorts", "▶️", "9:16"], ["youtube", "YouTube", "📺", "16:9"], ["facebook", "Facebook", "👍", "1:1"], ["linkedin", "LinkedIn", "💼", "1:1"]];
const FORMATS = [["9:16", "f_v", 18, 32], ["16:9", "f_h", 32, 18], ["1:1", "f_s", 24, 24]];
const ENERGY_ICON = ["🧘", "🙂", "⚡", "🔥"];
const TEMPO = [950, 620, 380, 230];
const fresh = () => ({ step: 0, brand: null, brands: [], source: "folder", folder: null, listing: null, files: [], request: "", single: false, style: "pop-bounce", motion: "medium",
  captions: { on: true, type: "color", upper: false, scale: 1 }, energy: 2, count: 5, auto: false, length: "len_mid", platforms: ["tiktok", "reels", "shorts"], formats: ["9:16"],
  sfx_folder: null, music_folder: null, name: "", direction: "" });
let W = fresh();
let capTimer;

function phoneHtml() {
  return `<div class="prev" id="prev"><div class="prev-decor"></div>
    <div class="prev-frame" id="prev-frame"><div class="scene"><i class="sun"></i><i class="hill"></i><i class="hill two"></i></div></div>
    <div class="prev-hook"><b>${t("sampleHook")}</b><span class="prev-pill">${t("samplePill")}</span></div>
    <div class="prev-stat">$102</div><div class="prev-list">${t("sampleList")}</div>
    <div class="prev-cap" id="prev-cap">${t("sampleCap").split(" ").map((w) => `<span>${esc(w)}</span>`).join(" ")}</div></div>`;
}

function updatePhone(o) {
  const el = $("#prev");
  if (!el) return;
  const s = { style: "pop-bounce", motion: "medium", captions: { on: true, type: "", upper: false, scale: 1 }, energy: 2, format: "9:16", ...o };
  const [layout, shadow, decor, mode, upper, tilt] = STYLE_LOOK[s.style];
  const type = s.captions.type || mode;
  el.className = ["prev", layout, shadow, decor, upper, tilt, `cap-${type}`, s.captions.on ? "" : "capoff", s.captions.upper ? "capup" : ""].filter(Boolean).join(" ");
  if (s.motion === "none") el.classList.add("bare");
  el.dataset.motion = s.motion;
  const [w, h] = s.format.split(":").map(Number);
  el.style.setProperty("--ratio", h / w);
  el.style.setProperty("--w", w > h ? "312px" : w === h ? "290px" : "268px");
  const tempo = TEMPO[s.energy - 1];
  el.style.setProperty("--tempo", `${tempo}ms`);
  el.style.setProperty("--cap", s.captions.scale);
  if (s.colors) {
    const map = { "--b-bg": "bg", "--b-ink": "ink", "--b-accent": "accent", "--b-light": "light", "--b-high": "highlight", "--b-dark": "ink_dark" };
    Object.entries(map).forEach(([k, r]) => el.style.setProperty(k, s.colors[r]));
  }
  clearInterval(capTimer);
  const words = [...el.querySelectorAll(".prev-cap span")];
  let i = 0;
  capTimer = setInterval(() => {
    if (!document.body.contains(el)) return clearInterval(capTimer);
    words.forEach((n, k) => n.classList.toggle("on", k === i));
    i = (i + 1) % words.length;
  }, tempo);
}

function syncPhone() {
  updatePhone({ colors: W.brand?.colors || DEFAULT_COLORS, style: W.style, motion: W.motion, captions: W.captions, energy: W.energy, format: W.formats[0] || "9:16" });
  const frame = $("#prev-frame");
  if (frame && W.files[0] && !$("video", frame)) {
    frame.innerHTML = `<video muted autoplay loop playsinline src="${URL.createObjectURL(W.files[0])}"></video>`;
  }
}

async function viewCreator() {
  W = fresh();
  W.brands = await api("/api/brands");
  if (!W.brands.length) { location.hash = "#/brand/new"; return; }
  if (W.brands.length === 1) pickBrand(W.brands[0]);
  setTheme(W.brand?.colors);
  main.innerHTML = `<div class="wiz"><div class="bar" id="bar"></div><div class="wiz-main"><div id="step"></div>
    <div class="wiz-foot"><button class="btn" id="back">${t("back")}</button><button class="btn go big" id="next"></button></div></div>
    <div class="stage">${phoneHtml()}<p class="stage-note">${t("previewNote")}</p></div></div>`;
  $("#back").onclick = () => go(W.step - 1);
  $("#next").onclick = () => (W.step === FLOW.length - 1 ? launch() : go(W.step + 1));
  drawStep();
}

function pickBrand(brand) {
  W.brand = brand;
  const memory = brand.app || {};
  W.style = memory.style || brand.style || W.style;
  for (const key of ["motion", "energy", "sfx_folder", "music_folder"]) if (memory[key]) W[key] = memory[key];
  if (memory.captions) W.captions = memory.captions;
  if (memory.formats?.length) W.formats = memory.formats;
  if (memory.platform_ids?.length) W.platforms = memory.platform_ids;
}

function ready(step) {
  if (step === "brand") return !!W.brand;
  if (step === "videos") return W.source === "folder" ? W.listing?.count > 0 : W.files.length > 0;
  if (step === "context") return W.request.trim().length > 0;
  if (step === "platforms") return W.formats.length > 0;
  return true;
}

function go(to) {
  if (to < 0) { location.hash = "#/"; return; }
  W.direction = to < W.step ? "back" : "";
  W.step = to;
  drawStep();
  scrollTo({ top: 0, behavior: "smooth" });
}

function refreshFoot() {
  const name = FLOW[W.step];
  $("#next").disabled = !ready(name);
  $("#next").textContent = name === "ready" ? t("create") : t("next");
  $("#back").textContent = W.step ? t("back") : t("projects");
}

function drawBar() {
  $("#bar").innerHTML = FLOW.map((name, i) => {
    const open = FLOW.slice(0, i).every(ready);
    return `<button class="${i === W.step ? "on" : i < W.step ? "past" : ""}" data-i="${i}" title="${t("w_" + name)}" aria-label="${t("w_" + name)}" ${open ? "" : "disabled"}></button>`;
  }).join("");
  $("#bar").querySelectorAll("button").forEach((b) => { b.onclick = () => go(Number(b.dataset.i)); });
}

function drawStep() {
  const name = FLOW[W.step];
  $("#step").innerHTML = `<section class="wiz-step ${W.direction}"><h1 class="wiz-q" tabindex="-1"><small>${t("stepOf")} ${W.step + 1} ${t("of")} ${FLOW.length}</small>${t("q_" + name)}</h1>${STEPS[name]()}</section>`;
  BIND[name]?.();
  bindTiles();
  drawBar();
  refreshFoot();
  syncPhone();
}

const tile = (group, value, label, hint = "", icon = "", pressed = false) => `<button type="button" class="tile" data-group="${group}" data-value="${esc(value)}" aria-pressed="${pressed}">${icon ? `<span class="ico" aria-hidden="true">${icon}</span>` : ""}<b>${label}</b>${hint ? `<small>${hint}</small>` : ""}</button>`;

function bindTiles() {
  main.querySelectorAll(".tile[data-group]").forEach((b) => { b.onclick = (e) => {
    choose(b.dataset.group, b.dataset.value, e);
    if (!["platform", "format"].includes(b.dataset.group)) main.querySelectorAll(`.tile[data-group="${b.dataset.group}"]`).forEach((x) => x.setAttribute("aria-pressed", x === b));
    refreshFoot();
    drawBar();
    syncPhone();
  }; });
}

function choose(group, value, event) {
  if (group === "brand") { pickBrand(W.brands.find((b) => b.id === value)); setTheme(W.brand.colors, event); }
  if (group === "source") { W.source = value; drawStep(); }
  if (group === "mode") { W.single = value === "one"; }
  if (group === "style") {
    W.style = value;
    W.captions.type = STYLE_LOOK[value][3];
    W.captions.upper = STYLE_LOOK[value][4] === "upper";
  }
  if (group === "motion") W.motion = value;
  if (group === "capon") { W.captions.on = value === "on"; drawStep(); }
  if (group === "captype") W.captions.type = value;
  if (group === "capsize") W.captions.scale = Number(value);
  if (group === "length") W.length = value;
  if (group === "platform") togglePlatform(value);
  if (group === "format") toggleFormat(value);
}

function togglePlatform(id) {
  W.platforms = W.platforms.includes(id) ? W.platforms.filter((p) => p !== id) : [...W.platforms, id];
  const wanted = [...new Set(W.platforms.map((p) => PLATFORMS.find((x) => x[0] === p)[3]))];
  if (wanted.length) W.formats = wanted;
  drawStep();
}
function toggleFormat(id) {
  W.formats = W.formats.includes(id) ? W.formats.filter((f) => f !== id) : [...W.formats, id];
  drawStep();
}

async function pickFolderInto(key, kind) {
  const out = await post("/api/pick-folder");
  const path = out.path || (out.typed ? prompt(t("typePath")) : null);
  if (!path) return;
  const listing = await post("/api/folder", { path, kind });
  if (key === "folder") { W.folder = listing.path; W.listing = listing; if (!W.name) W.name = listing.path.split("/").pop(); }
  else W[key] = listing.path;
  drawStep();
}

const STEPS = {
  brand: () => `<div class="tiles">${W.brands.map((b) => `<button type="button" class="tile" data-group="brand" data-value="${esc(b.id)}" aria-pressed="${W.brand?.id === b.id}">
      ${b.logo ? `<img class="logo" alt="" src="/files/brand/${esc(b.id)}/${esc(b.logo)}">` : ""}<b>${esc(b.name)}</b>
      <span class="swatches">${ROLES.map((r) => `<i style="background:${esc(b.colors[r])}"></i>`).join("")}</span></button>`).join("")}</div>
    <div><a class="btn" href="#/brand/new">${t("newBrand")}</a></div>`,
  videos: () => `<div class="tiles">${tile("source", "folder", t("fromFolder"), t("fromFolderHint"), "📁", W.source === "folder")}${tile("source", "upload", t("fromUpload"), t("fromUploadHint"), "🎬", W.source === "upload")}</div>
    ${W.source === "folder" ? `<div class="folder"><div class="row"><button class="btn go" id="pick">${t(W.folder ? "changeFolder" : "chooseFolder")}</button>${W.folder ? `<code>${esc(W.folder)}</code>` : ""}</div>
      ${W.listing ? (W.listing.count ? `<strong>${W.listing.count} ${t("found")}</strong><ul class="files">${W.listing.files.slice(0, 40).map((f) => `<li><span>${esc(f.name)}</span><span>${f.mb} MB</span></li>`).join("")}</ul>` : `<p class="notice">${t("noVideosHere")}</p>`) : ""}</div>`
    : `<label class="drop" id="drop"><span class="big-emoji" aria-hidden="true">🎞️</span><strong>${t("dropFootage")}</strong><span class="sub">${t("dropHint")}</span><input type="file" id="files" accept="video/*,.mkv" multiple hidden></label>
      ${W.files.length ? `<ul class="files">${W.files.map((f) => `<li><span>${esc(f.name)}</span><span>${(f.size / 1e6).toFixed(1)} MB</span></li>`).join("")}</ul>` : ""}`}`,
  context: () => `<div class="tiles">${tile("mode", "many", t("manyReels"), t("manyReelsHint"), "🎬", !W.single)}${tile("mode", "one", t("oneVideo"), t("oneVideoHint"), "🧩", W.single)}</div>
    <label class="field">${t("whatHint")}<textarea id="request" placeholder="${esc(t("wantExample"))}">${esc(W.request)}</textarea></label>
    <div class="chips">${[1, 2, 3, 4, 5].map((n) => `<button type="button" class="btn chip" data-chip="${esc(t("ch" + n))}">+ ${t("ch" + n)}</button>`).join("")}</div>`,
  style: () => `<div class="tiles">${STYLES.map(([v, n, k]) => tile("style", v, n, t(k), "", W.style === v)).join("")}</div>`,
  graphics: () => `<div class="tiles">${[["none", "▫️"], ["light", "✨"], ["medium", "🎯"], ["heavy", "🎆"]].map(([v, i]) => tile("motion", v, t("m_" + v), t(`m_${v}Hint`), i, W.motion === v)).join("")}</div>`,
  captions: () => `<div class="tiles">${tile("capon", "on", t("capOn"), "", "💬", W.captions.on)}${tile("capon", "off", t("capOff"), "", "🔇", !W.captions.on)}</div>
    ${W.captions.on ? `<p class="seg-title">${t("capType")}</p><div class="tiles small">${["color", "box", "none"].map((v) => tile("captype", v, t("cap_" + v), "", "", W.captions.type === v)).join("")}</div>
      <p class="seg-title">${t("capSize")}</p><div class="tiles small">${[["0.85", "size_s"], ["1", "size_m"], ["1.2", "size_l"]].map(([v, k]) => tile("capsize", v, t(k), "", "", Number(v) === W.captions.scale)).join("")}</div>
      <label class="row"><input type="checkbox" id="upper" ${W.captions.upper ? "checked" : ""} style="width:24px;height:24px;accent-color:var(--primary)"><b style="font-weight:600">${t("capUpper")}</b></label>` : ""}`,
  energy: () => `<div class="energy-read"><span class="big-emoji" id="e-ico" aria-hidden="true">${ENERGY_ICON[W.energy - 1]}</span><div><h2 id="e-name">${t("e" + W.energy)}</h2><p class="sub" id="e-hint">${t(`e${W.energy}h`)}</p></div></div>
    <input type="range" id="energy" min="1" max="4" step="1" value="${W.energy}" aria-label="${t("w_energy")}">
    ${W.single ? "" : `<p class="seg-title">${t("howManyQ")}</p><div class="row"><div class="stepper"><button type="button" class="btn" id="minus" aria-label="-">−</button><output id="n">${W.count}</output><button type="button" class="btn" id="plus" aria-label="+">+</button></div>
      <label class="row"><input type="checkbox" id="auto" ${W.auto ? "checked" : ""} style="width:24px;height:24px;accent-color:var(--primary)">${t("claudeDecides")}</label></div>`}
    <p class="seg-title">${t("length")}</p><div class="tiles small">${["len_short", "len_mid", "len_long"].map((v) => tile("length", v, t(v), "", "", W.length === v)).join("")}</div>`,
  platforms: () => `<div class="tiles small">${PLATFORMS.map(([id, label, icon]) => tile("platform", id, label, "", icon, W.platforms.includes(id))).join("")}</div>
    <p class="seg-title">${t("formats")}</p><div class="tiles small">${FORMATS.map(([id, k, w, h]) => `<button type="button" class="tile" data-group="format" data-value="${id}" aria-pressed="${W.formats.includes(id)}"><span class="shape" style="width:${w}px;height:${h}px"></span><b>${t(k)}</b><small>${id}</small></button>`).join("")}</div>`,
  sound: () => [["sfx_folder", "sfxFolder", "sfxHint", "🔊"], ["music_folder", "musicFolder", "musicHint", "🎵"]].map(([key, title, hint, icon]) => `<div class="folder"><h2>${icon} ${t(title)}</h2><p class="hint">${t(hint)}</p>
      <div class="row"><button class="btn" data-pick="${key}">${t(W[key] ? "changeFolder" : "chooseFolder")}</button>${W[key] ? `<code>${esc(W[key])}</code><button class="link" data-clear="${key}">${t("removeFolder")}</button>` : `<span class="hint">${t("noFolder")}</span>`}</div></div>`).join(""),
  ready: () => {
    const row = (key, value) => `<div><span>${t("w_" + key)}</span><b style="font-weight:500">${esc(value)}</b><button class="link" data-jump="${FLOW.indexOf(key)}">${t("edit")}</button></div>`;
    const count = W.single ? t("oneVideo") : W.auto ? t("claudeDecides") : `${W.count} ${t("videosWord")}`;
    const caps = W.captions.on ? t("cap_" + W.captions.type) : t("capOff");
    const shots = W.source === "folder" ? `${W.listing?.count || 0} ${t("found")}` : `${W.files.length} ${t("videosWord")}`;
    return `<label class="field">${t("r_project")}<input type="text" id="pname" value="${esc(W.name || t("defaultName"))}"></label>
    <div class="recap">${row("brand", W.brand?.name)}${row("videos", shots)}${row("context", W.request)}${row("style", STYLES.find((s) => s[0] === W.style)[1])}${row("graphics", t("m_" + W.motion))}${row("captions", caps)}${row("energy", `${t("e" + W.energy)} · ${count}`)}${row("platforms", `${W.platforms.map((p) => PLATFORMS.find((x) => x[0] === p)[1]).join(", ")} · ${W.formats.join(", ")}`)}</div>`;
  },
};

const BIND = {
  videos() {
    const pick = $("#pick");
    if (pick) pick.onclick = guard(() => pickFolderInto("folder", "video"));
    const drop = $("#drop");
    if (!drop) return;
    const take = (files) => { W.files.push(...files); if (!W.name) W.name = files[0].name.replace(/\.[^.]+$/, ""); drawStep(); };
    ["dragenter", "dragover"].forEach((n) => drop.addEventListener(n, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((n) => drop.addEventListener(n, () => drop.classList.remove("over")));
    drop.addEventListener("drop", (e) => { e.preventDefault(); take([...e.dataTransfer.files]); });
    $("#files").onchange = (e) => take([...e.target.files]);
  },
  context() {
    const box = $("#request");
    box.oninput = () => { W.request = box.value; refreshFoot(); drawBar(); };
    main.querySelectorAll("[data-chip]").forEach((b) => { b.onclick = () => {
      box.value = box.value.trim() ? `${box.value.trim()} ${b.dataset.chip}.` : `${b.dataset.chip}.`;
      box.oninput();
      box.focus();
    }; });
  },
  captions() {
    const box = $("#upper");
    if (box) box.onchange = () => { W.captions.upper = box.checked; syncPhone(); };
  },
  energy() {
    const range = $("#energy");
    range.oninput = () => {
      W.energy = Number(range.value);
      $("#e-ico").textContent = ENERGY_ICON[W.energy - 1];
      $("#e-name").textContent = t("e" + W.energy);
      $("#e-hint").textContent = t(`e${W.energy}h`);
      syncPhone();
    };
    if (W.single) return;
    const set = (n) => { W.count = Math.max(1, Math.min(50, n)); $("#n").textContent = W.count; };
    $("#minus").onclick = () => set(W.count - 1);
    $("#plus").onclick = () => set(W.count + 1);
    $("#auto").onchange = (e) => { W.auto = e.target.checked; };
  },
  sound() {
    main.querySelectorAll("[data-pick]").forEach((b) => { b.onclick = guard(() => pickFolderInto(b.dataset.pick, "audio")); });
    main.querySelectorAll("[data-clear]").forEach((b) => { b.onclick = () => { W[b.dataset.clear] = null; drawStep(); }; });
  },
  ready() {
    $("#pname").oninput = (e) => { W.name = e.target.value; };
    main.querySelectorAll("[data-jump]").forEach((b) => { b.onclick = () => go(Number(b.dataset.jump)); });
  },
};

function briefOf() {
  const seconds = { len_short: "15 to 30", len_mid: "30 to 60", len_long: "60 to 90" };
  return { style: W.style, motion: W.motion, energy: W.energy, captions: W.captions, length: seconds[W.length], single: W.single,
    platforms: W.platforms.map((p) => PLATFORMS.find((x) => x[0] === p)[1]), platform_ids: W.platforms, formats: W.formats, sfx_folder: W.sfx_folder, music_folder: W.music_folder };
}

const launch = guard(async () => {
  const name = $("#pname")?.value.trim() || t("defaultName");
  const cover = document.createElement("div");
  cover.className = "launch";
  cover.innerHTML = `<div class="box"><span class="big-emoji" aria-hidden="true">🎬</span><h1>${t("launching")}</h1><p class="sub" id="l-file"></p><progress id="l-bar" max="1" value="0" hidden></progress></div>`;
  document.body.append(cover);
  try {
    const project = await post("/api/projects", { name, brand: W.brand.id, request: W.request, folder: W.source === "folder" ? W.folder : null,
      count: W.single || W.auto ? null : W.count, brief: briefOf() });
    if (W.source === "upload") {
      const bar = $("#l-bar");
      bar.hidden = false;
      for (const file of W.files) {
        $("#l-file").textContent = file.name;
        await upload(`/api/projects/${project.id}/footage`, file, (v) => { bar.value = v; });
      }
    }
    await post(`/api/projects/${project.id}/propose`);
    location.hash = `#/p/${project.id}`;
  } finally {
    cover.remove();
  }
});
