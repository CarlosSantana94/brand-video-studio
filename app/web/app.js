"use strict";
const $ = (s, el = document) => el.querySelector(s);
const main = $("#main");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STYLES = [["pop-bounce", "Pop bounce", "st1"], ["editorial-clean", "Editorial clean", "st2"], ["kinetic-bold", "Kinetic bold", "st3"],
  ["tech-glitch", "Tech dry", "st4"], ["cinematic-minimal", "Cinematic minimal", "st5"], ["scrapbook", "Scrapbook", "st6"]];
const ROLES = ["ink", "ink_dark", "bg", "light", "accent", "highlight"];
const DEFAULT_COLORS = { ink: "#123C3A", ink_dark: "#0A2221", bg: "#F2E6C9", light: "#FBF7EC", accent: "#F2A541", highlight: "#FFD27F" };
const STYLE_LOOK = { "pop-bounce": ["card", "hard", "d-blobs", "color"], "editorial-clean": ["card", "", "", "none"], "kinetic-bold": ["full", "", "", "box", "upper"], "tech-glitch": ["card", "hard", "d-grid", "color"], "cinematic-minimal": ["full", "", "", "none", "upper"], "scrapbook": ["card", "hard", "d-dots", "box", "", "tilt"] };
const TAPES = ["#FF5A36", "#FFC933", "#2BD9A8", "#FF6FB5", "#5CC8FF", "#B48CFF", "#F2F2F2", "#9BE564"];

let lang = "en";
try { lang = localStorage.getItem("bvs-lang") || ""; } catch {}
if (!STRINGS[lang]) lang = (navigator.language || "en").startsWith("es") ? "es" : "en";
const t = (key) => STRINGS[lang][key] ?? STRINGS.en[key] ?? key;

async function api(path, options = {}) {
  const res = await fetch(path, { ...options, headers: { "Content-Type": "application/json", "X-Studio": "1", ...(options.headers || {}) } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
const post = (path, body = {}) => api(path, { method: "POST", body: JSON.stringify(body) });

function toast(text) {
  const el = $("#toast");
  el.textContent = text;
  el.classList.add("on");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("on"), 4000);
}
const guard = (fn) => async (...args) => { try { await fn(...args); } catch (e) { toast(e.message); } };

function upload(path, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `${path}/${encodeURIComponent(file.name)}`);
    xhr.setRequestHeader("X-Studio", "1");
    xhr.upload.onprogress = (e) => onProgress && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      const data = JSON.parse(xhr.responseText || "{}");
      xhr.status < 300 ? resolve(data) : reject(new Error(data.error || "Upload failed"));
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(file);
  });
}

function shell() {
  const here = location.hash.startsWith("#/brand") ? "brands" : "projects";
  $("#nav").innerHTML = `<a href="#/" ${here === "projects" ? 'aria-current="page"' : ""}>${t("projects")}</a>
    <a href="#/brands" ${here === "brands" ? 'aria-current="page"' : ""}>${t("brands")}</a>`;
  $("#lang").textContent = t("language");
  document.documentElement.lang = lang;
}

// The whole interface takes the brand's colors, opening out from where you clicked.
const BASE = { "--paper": "#F3F1FF", "--ink": "#1E1A4D", "--soft": "#5C5888", "--line": "#DCD8F5", "--primary": "#5B45F5", "--on-primary": "#FFFFFF", "--edge": "#3F2CC4", "--tint": "#E7E2FF", "--pop": "#FFD24D" };
function themeFrom(c) {
  const paper = mix(c.bg, "#FFFFFF", 0.4);
  const ink = contrast(c.ink, paper) >= 4.5 ? c.ink : contrast(c.ink_dark, paper) >= 4.5 ? c.ink_dark : "#1A1A2E";
  const primary = contrast(c.accent, "#FFFFFF") >= 2 && saturation(c.accent) > 40 ? c.accent : ink;
  const onPrimary = contrast("#FFFFFF", primary) >= 3.2 ? "#FFFFFF" : ink;
  return { "--paper": paper, "--ink": ink, "--soft": mix(ink, paper, 0.28), "--line": mix(ink, paper, 0.82), "--primary": primary, "--on-primary": onPrimary,
    "--edge": mix(primary, "#000000", 0.28), "--tint": mix(primary, "#FFFFFF", 0.84), "--pop": c.highlight };
}
function paintTheme(vars) {
  const root = document.documentElement;
  Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v));
}
function setTheme(colors, event) {
  const vars = colors ? themeFrom(colors) : BASE;
  if (!event || !document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return paintTheme(vars);
  const box = event.currentTarget?.getBoundingClientRect?.();
  const x = box ? box.left + box.width / 2 : innerWidth / 2;
  const y = box ? box.top + box.height / 2 : innerHeight / 2;
  const far = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  const change = document.startViewTransition(() => paintTheme(vars));
  change.ready.then(() => document.documentElement.animate(
    { clipPath: [`circle(0 at ${x}px ${y}px)`, `circle(${far}px at ${x}px ${y}px)`] },
    { duration: 650, easing: "cubic-bezier(.65,0,.2,1)", pseudoElement: "::view-transition-new(root)" })).catch(() => {});
}

const STAGE = { draft: "you", proposal: "you", first: "you", working: "work", done: "done", failed: "bad", limited: "bad", stopped: "you" };
function statusPill(stage) {
  return `<span class="status ${STAGE[stage] || ""}">${stage === "working" ? '<i class="pulse"></i>' : ""}${t("s_" + stage)}</span>`;
}

async function viewProjects() {
  setTheme(null);
  const [projects, brands] = await Promise.all([api("/api/projects"), api("/api/brands")]);
  const action = `<a class="btn go big" href="${brands.length ? "#/new" : "#/brand/new"}">${t(brands.length ? "createVideos" : "addBrand")}</a>`;
  main.innerHTML = `<div class="page"><div class="head"><div><h1>${t("projects")}</h1><p class="sub">${t("startHere")}</p></div>${projects.length ? action : ""}</div>
    <div id="health"></div>
    ${projects.length ? `<div class="cards">${projects.map((p) => `<a class="slate" href="#/p/${esc(p.id)}">
      <h3>${esc(p.name)}</h3><small>${esc(p.brand_name)} · ${esc(p.format)}</small><div>${statusPill(p.stage)}</div></a>`).join("")}</div>`
      : `<div class="empty"><h2>${t("noProjects")}</h2><p class="sub">${t("noProjectsHint")}</p>${action}</div>`}</div>`;
  health();
}

async function health() {
  const h = await api("/api/health");
  const notes = [];
  if (!h.claude) notes.push(t("noClaude"));
  if (h.api_key) notes.push(t("apiKeyOn"));
  if (h.missing.length) notes.push(`${t("missing")} ${h.missing.map((m) => m.split(" ")[1]).join(", ")}`);
  const el = $("#health");
  if (el) el.innerHTML = notes.map((n) => `<p class="notice" style="margin-bottom:16px">${esc(n)}</p>`).join("");
}

async function viewBrands() {
  setTheme(null);
  const brands = await api("/api/brands");
  const add = `<span class="row"><button type="button" class="btn go" id="import">${t("importBrand")}</button><a class="btn" href="#/brand/new">${t("newBrand")}</a></span>`;
  main.innerHTML = `<div class="page"><div class="head"><div><h1>${t("brands")}</h1><p class="sub">${t("brandsHint")}</p></div>${brands.length ? add : ""}</div>
  ${brands.length ? `<div class="cards">${brands.map((b) => `<a class="slate" href="#/brand/${esc(b.id)}"><h3>${esc(b.name)}</h3>
    <div class="tagline"><span class="swatches">${ROLES.map((r) => `<i style="background:${esc(b.colors[r])}"></i>`).join("")}</span></div>
    <small>${b.importing ? t("importing") : esc(STYLES.find((s) => s[0] === b.style)?.[1] || b.style)}</small></a>`).join("")}</div>`
    : `<div class="empty"><h2>${t("noBrands")}</h2><p class="sub">${t("noBrandsHint")}</p>${add}</div>`}</div>`;
  $("#import").onclick = guard(async () => {
    const out = await post("/api/pick-folder");
    const folder = out.path || (out.typed ? prompt(t("typePath")) : null);
    if (!folder) return;
    const brand = await post("/api/brands-import", { folder });
    location.hash = `#/brand/${brand.id}`;
  });
}

const hex = (v) => [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16));
function luminance(v) {
  const [r, g, b] = hex(v).map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
}
function saturation(v) { const c = hex(v); return Math.max(...c) - Math.min(...c); }
function mix(a, b, amount) {
  const [x, y] = [hex(a), hex(b)];
  return "#" + x.map((c, i) => Math.round(c + (y[i] - c) * amount).toString(16).padStart(2, "0")).join("").toUpperCase();
}
function rolesFrom(palette) {
  const list = palette.map((p) => p.hex).filter((c) => luminance(c) < 0.95 || saturation(c) > 20);
  if (!list.length) return null;
  const darkest = [...list].sort((a, b) => luminance(a) - luminance(b))[0];
  const vivid = [...list].sort((a, b) => saturation(b) - saturation(a))[0];
  const ink = luminance(darkest) < 0.18 ? darkest : mix(darkest, "#000000", 0.55);
  return { ink, ink_dark: mix(ink, "#000000", 0.45), bg: mix(vivid, "#FFFFFF", 0.82), light: mix(vivid, "#FFFFFF", 0.94),
    accent: vivid, highlight: mix(vivid, "#FFFFFF", 0.4) };
}

async function viewBrand(id) {
  const brand = id === "new" ? { name: "", style: "pop-bounce", colors: { ...DEFAULT_COLORS } } : await api("/api/brands").then((l) => l.find((b) => b.id === id));
  if (!brand) { location.hash = "#/brands"; return; }
  if (brand.importing) {
    main.innerHTML = `<div class="page"><div class="empty"><div class="spinner" aria-hidden="true"></div><h2>${t("importing")}</h2>
      <p class="sub">${t("importingHint")}</p><p class="hint">${esc(brand.source || "")}</p></div></div>`;
    clearTimeout(page.timer);
    page.timer = setTimeout(() => { if (location.hash === `#/brand/${id}`) viewBrand(id); }, 3000);
    return;
  }
  const logoUrl = () => brand.logo ? `/files/brand/${esc(brand.id)}/${esc(brand.logo)}?${Date.now()}` : "";
  main.innerHTML = `<div class="page"><div class="head"><h1>${brand.id ? esc(brand.name) : t("newBrand")}</h1></div>
  <form class="brand-edit" id="f"><div class="panel stack">
    ${brand.import_note ? `<p class="notice bad">${esc(brand.import_note)}</p>` : brand.source ? `<p class="notice">${t("importedFrom")} <b>${esc(brand.source)}</b>${brand.fonts ? ` · ${esc(brand.fonts.display.family)} + ${esc(brand.fonts.body.family)}` : ""}</p>` : ""}
    <div class="grid2">
      <label class="field">${t("brandName")}<input type="text" name="name" value="${esc(brand.name)}" required></label>
      <label class="field">${t("handle")}<input type="text" name="handle" value="${esc(brand.handle)}" placeholder="@brand"></label>
      <label class="field">${t("website")}<input type="text" name="url" value="${esc(brand.url)}"></label>
      <label class="field">${t("cta")}<input type="text" name="cta" value="${esc(brand.cta)}"><span class="hint">${t("ctaHint")}</span></label>
    </div>
    <div class="stack" style="gap:8px"><h3>${t("logo")}</h3><div class="logo-row">
      <img id="logo" alt="" ${brand.logo ? `src="${logoUrl()}"` : "hidden"}>
      <label class="btn">${t("chooseLogo")}<input type="file" id="logofile" accept="image/*" hidden></label>
      <button type="button" class="btn" id="fromlogo" ${brand.logo ? "" : "hidden"}>${t("useLogoColors")}</button></div></div>
    <div class="stack" style="gap:8px"><h3>${t("colors")}</h3><div class="colors">${ROLES.map((r) => `<label class="color"><input type="color" name="c_${r}" value="${esc(brand.colors[r])}">${t("c_" + r)}</label>`).join("")}</div>
      <p class="notice" id="contrast" hidden>${t("lowContrast")}</p></div>
    <div class="stack" style="gap:8px"><h3>${t("style")}</h3><input type="hidden" name="style" value="${esc(brand.style)}"><div class="tiles">${STYLES.map(([v, n, k]) => `<button type="button" class="tile st" data-v="${v}" aria-pressed="${brand.style === v}"><b>${n}</b><small>${t(k)}</small></button>`).join("")}</div></div>
    <label class="field">${t("voice")}<span class="hint">${t("voiceHint")}</span><textarea name="notes">${esc(brand.notes)}</textarea></label>
    <div><button class="btn go">${t("saveBrand")}</button></div>
  </div>
  <div class="stage">${phoneHtml()}</div></form></div>`;
  const form = $("#f");
  const paint = () => {
    const c = Object.fromEntries(ROLES.map((r) => [r, form[`c_${r}`].value]));
    updatePhone({ colors: c, style: form.style.value });
    setTheme(c);
    $("#contrast").hidden = contrast(c.ink, c.bg) >= 4.5;
    return c;
  };
  main.querySelectorAll(".tile.st").forEach((b) => { b.onclick = () => {
    form.style.value = b.dataset.v;
    main.querySelectorAll(".tile.st").forEach((x) => x.setAttribute("aria-pressed", x === b));
    paint();
  }; });
  paint();
  form.addEventListener("input", paint);
  const save = async () => {
    const d = new FormData(form);
    const body = { name: d.get("name"), handle: d.get("handle"), url: d.get("url"), cta: d.get("cta"), style: d.get("style"), notes: d.get("notes"), colors: paint() };
    const out = await post(brand.id ? `/api/brands/${brand.id}` : "/api/brands", body);
    Object.assign(brand, out);
    return out;
  };
  form.onsubmit = guard(async (e) => {
    e.preventDefault();
    await save();
    toast(t("saved"));
    location.hash = "#/brands";
  });
  $("#logofile").onchange = guard(async (e) => {
    if (!form.reportValidity()) return;
    await save();
    Object.assign(brand, await upload(`/api/brands/${brand.id}/logo`, e.target.files[0]));
    const el = $("#logo");
    el.src = logoUrl();
    el.hidden = false;
    $("#fromlogo").hidden = brand.logo.endsWith(".svg");
    if (location.hash === "#/brand/new") history.replaceState(null, "", `#/brand/${brand.id}`);
  });
  $("#fromlogo").onclick = guard(async () => {
    const roles = rolesFrom(await post(`/api/brands/${brand.id}/palette`));
    if (roles) ROLES.forEach((r) => { form[`c_${r}`].value = roles[r]; });
    paint();
  });
}

// Project page. It rebuilds only when its state changes, so polling never wipes what you are typing.
const page = { id: null, key: "", seen: 0, timer: null, picks: new Set() };
const clock = (s) => { s = Math.round(s); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const stepOf = (p) => ({ draft: 0, proposal: 1, first: 2, done: 3 }[p.stage] ?? (p.videos.length ? (p.approved?.length > 1 ? 3 : 2) : p.proposal ? 1 : p.job === "propose" ? 1 : 0));

function steps(p) {
  const on = stepOf(p);
  return `<ol class="steps">${["stepFootage", "stepProposal", "stepFirst", "stepAll"].map((k, i) =>
    `<li class="${i === on ? "on" : i < on ? "past" : ""}" ${i === on ? 'aria-current="step"' : ""}><b>${i + 1}</b>${t(k)}</li>`).join("")}</ol>`;
}

function footagePanel(p) {
  const ready = p.footage.length && p.request;
  return `<section class="panel stack"><h2>${t("footage")}</h2>
    <label class="drop" id="drop"><strong>${t("dropFootage")}</strong><span class="sub">${t("dropHint")}</span>
      <input type="file" id="files" accept="video/*,.mkv" multiple hidden></label>
    <ul class="files" id="filelist">${p.footage.map((f) => `<li><span>${esc(f)}</span><span>${t("uploaded")}</span></li>`).join("")}</ul>
    <label class="field">${t("whatDoYouWant")}<textarea id="request">${esc(p.request)}</textarea></label>
    <div class="row"><button class="btn go" id="propose" ${ready ? "" : "disabled"}>${t("askProposal")}</button>
    ${ready ? "" : `<span class="hint">${t("needFootage")}</span>`}</div></section>`;
}

function strip(p) {
  const videos = p.proposal.videos;
  const fallback = p.sources[0]?.id;
  return `<div class="strip-wrap" id="strip">${p.sources.map((s) => `<div class="strip-row">
    <div class="strip-label"><span>${esc(s.id)}</span><span>${clock(s.duration)}</span></div>
    <div class="strip">${videos.flatMap((v, i) => (v.ranges || []).filter((r) => (r[2] || fallback) === s.id).map((r) =>
      `<i class="cut" data-v="${i}" title="${esc(v.title)}" style="--tape:${TAPES[i % TAPES.length]};left:${(r[0] / s.duration) * 100}%;width:${((r[1] - r[0]) / s.duration) * 100}%"></i>`)).join("")}</div></div>`).join("")}</div>`;
}

function proposalPanel(p) {
  const v = p.proposal;
  if (!page.picks.size || ![...page.picks].every((n) => v.videos.some((x) => x.name === n))) page.picks = new Set(v.videos.map((x) => x.name));
  return `<section class="stack"><div class="panel stack"><h2>${t("proposalTitle")}</h2><p>${esc(v.summary)}</p>
    ${(v.questions || []).length ? `<div class="notice"><h3>${t("questions")}</h3><ul>${v.questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul><label class="field">${t("answersLabel")}<textarea id="answers" placeholder="${esc(t("answersExample"))}"></textarea></label></div>` : ""}
    ${p.sources.length ? `<div class="stack" style="gap:10px"><h3>${t("whereFrom")}</h3>${strip(p)}</div>` : ""}</div>
    <div class="reels">${v.videos.map((x, i) => `<label class="reel" data-v="${i}" style="--tape:${TAPES[i % TAPES.length]}">
      <input type="checkbox" value="${esc(x.name)}" checked>
      <div><h3>${esc(x.title)}</h3><q>${esc(x.hook)}</q><p>${esc(x.why)}</p></div>
      <span class="time">${x.duration ? `${clock(x.duration)}` : ""}${x.type ? ` · ${esc(x.type)}` : ""}</span></label>`).join("")}</div>
    <div class="panel stack"><div class="row"><button class="btn go" id="build">${t("makeFirst")}</button><span class="hint" id="count"></span></div>
      <p class="hint">${t("firstHint")}</p>
      <label class="field">${t("changesLabel")}<span class="hint">${t("changesHint")}</span><textarea id="changes" placeholder="${esc(t("changesExample"))}"></textarea></label>
      <div><button class="btn" id="rewrite">${t("askChanges")}</button></div></div></section>`;
}

function resultCard(p, v) {
  const url = `/files/project/${esc(p.id)}/renders/${esc(v.name)}.mp4`;
  const idle = p.stage !== "working";
  return `<article class="result"><h3>${esc(v.title || v.name)}</h3>
    ${v.render ? `<video controls preload="metadata" src="${url}?v=${v.state}"></video>` : `<div class="waiting">${t("notReady")}</div>`}
    <div class="row"><span class="status">${t("st_" + v.state)}</span>${v.render ? `<a class="link" href="${url}" download>${t("download")}</a>` : ""}</div>
    ${v.render && idle ? `<details><summary>${t("changeVideo")}</summary><div class="stack" style="gap:8px;margin-top:8px">
      <textarea class="note" data-name="${esc(v.name)}" placeholder="${esc(t("changeExample"))}"></textarea>
      <div><button class="btn send" data-name="${esc(v.name)}">${t("sendChange")}</button></div></div></details>` : ""}</article>`;
}

function outcome(p) {
  const pending = (p.approved || []).filter((n) => !p.videos.some((v) => v.name === n && ["reviewed", "rendered"].includes(v.state)));
  return `${p.videos.length ? `<section class="panel stack"><h2>${t("videosTitle")}</h2><div class="result-grid">${p.videos.map((v) => resultCard(p, v)).join("")}</div>
    ${p.stage === "first" && pending.length ? `<div class="row"><button class="btn go" id="rest">${t("makeRest")} (${pending.length})</button></div>` : ""}</section>` : ""}
    ${p.copy ? `<section class="panel stack"><div class="row" style="justify-content:space-between"><h2>${t("copyTitle")}</h2><button class="btn" id="copy">${t("copyAll")}</button></div><div class="copy" id="copytext">${esc(p.copy)}</div></section>` : ""}`;
}

function logPanel() {
  return `<section class="panel stack"><h2>${t("activity")}</h2><div class="log" id="log" aria-live="polite"><p class="sub">${t("noActivity")}</p></div></section>`;
}

function renderProject(p) {
  page.key = keyOf(p);
  page.seen = 0;
  const busy = p.stage === "working";
  const notice = p.stage === "limited" ? t("limitedHint") : p.stage === "stopped" ? t("stoppedHint") : p.stage === "failed" ? p.note : busy && p.queued ? t("queuedHint") : "";
  const again = ["limited", "stopped", "failed"].includes(p.stage);
  main.innerHTML = `<div class="page"><div class="head"><div><h1>${esc(p.name)}</h1><p class="sub">${esc(p.brand_name)} · ${esc(p.format)}</p></div>
      <div class="row">${statusPill(p.stage)}${busy ? `<button class="btn" id="stop">${t("stop")}</button>` : ""}</div></div>
    ${steps(p)}
    <div class="stack">
      ${notice || again ? `<div class="notice ${p.stage === "failed" ? "bad" : ""}"><p>${esc(notice)}</p>${again ? `<p style="margin-top:8px"><button class="btn go" id="resume">${t(p.stage === "failed" ? "tryAgain" : "resume")}</button></p>` : ""}</div>` : ""}
      ${p.stage === "draft" ? footagePanel(p) : ""}
      ${p.stage === "proposal" && p.proposal ? proposalPanel(p) : ""}
      ${["first", "done", "working", "limited", "stopped", "failed"].includes(p.stage) ? outcome(p) : ""}
      ${p.stage !== "draft" && p.stage !== "proposal" ? logPanel() : ""}
      ${p.tokens ? `<div class="meter" id="meter"></div>` : ""}
    </div></div>`;
  bindProject(p);
  meter(p);
}

function meter(p) {
  const el = $("#meter");
  if (el) el.innerHTML = `<span>${t("usage")}</span><span>${Math.round(p.tokens).toLocaleString()} ${t("tokens")}</span><span>${(p.seconds / 60).toFixed(1)} ${t("minutes")}</span><span>$${(p.cost || 0).toFixed(2)} ${t("equiv")}</span>`;
}

const keyOf = (p) => [p.stage, p.queued > 0, p.videos.map((v) => v.name + v.state + v.render).join(), !!p.proposal, !!p.copy, p.footage.length, p.lang].join("|");

function act(p, action, body) {
  return guard(async () => { apply(await post(`/api/projects/${p.id}/${action}`, body)); })();
}
function apply(p) {
  if (page.id !== p.id) return;
  if (keyOf(p) !== page.key) renderProject(p);
}

function bindProject(p) {
  const on = (sel, fn) => { const el = $(sel); if (el) el.onclick = fn; };
  on("#stop", () => act(p, "stop"));
  on("#resume", () => act(p, "resume"));
  on("#rest", () => act(p, "rest"));
  on("#copy", guard(async () => { await navigator.clipboard.writeText(p.copy); toast(t("copied")); }));
  main.querySelectorAll(".send").forEach((b) => { b.onclick = () => {
    const note = main.querySelector(`.note[data-name="${CSS.escape(b.dataset.name)}"]`).value;
    act(p, "revise", { name: b.dataset.name, note });
  }; });
  if (p.stage === "draft") bindDraft(p);
  if (p.stage === "proposal" && p.proposal) bindProposal(p);
}

function bindDraft(p) {
  const drop = $("#drop");
  const list = $("#filelist");
  const send = guard(async (files) => {
    for (const file of files) {
      const row = document.createElement("li");
      row.innerHTML = `<span>${esc(file.name)}</span><progress max="1" value="0" aria-label="${esc(t("uploading"))}"></progress>`;
      list.append(row);
      await upload(`/api/projects/${p.id}/footage`, file, (v) => { row.querySelector("progress").value = v; });
      row.lastChild.replaceWith(Object.assign(document.createElement("span"), { textContent: t("uploaded") }));
    }
    refreshDraft();
  });
  const refreshDraft = () => {
    const ok = list.children.length && $("#request").value.trim();
    $("#propose").disabled = !ok;
  };
  ["dragenter", "dragover"].forEach((n) => drop.addEventListener(n, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((n) => drop.addEventListener(n, () => drop.classList.remove("over")));
  drop.addEventListener("drop", (e) => { e.preventDefault(); send([...e.dataTransfer.files]); });
  $("#files").onchange = (e) => send([...e.target.files]);
  $("#request").oninput = refreshDraft;
  $("#propose").onclick = guard(async () => {
    await post(`/api/projects/${p.id}/edit`, { request: $("#request").value, format: p.format, count: p.count });
    await act(p, "propose");
  });
}

function bindProposal(p) {
  const wrap = $("#strip");
  const count = () => { $("#count").textContent = `${page.picks.size} ${t("selected")}`; $("#build").disabled = !page.picks.size; };
  main.querySelectorAll(".reel").forEach((card) => {
    const box = $("input", card);
    box.onchange = () => {
      box.checked ? page.picks.add(box.value) : page.picks.delete(box.value);
      card.classList.toggle("off", !box.checked);
      count();
    };
    const focus = (lit) => {
      if (!wrap) return;
      wrap.toggleAttribute("data-focus", lit);
      wrap.querySelectorAll(".cut").forEach((c) => c.classList.toggle("lit", lit && c.dataset.v === card.dataset.v));
    };
    card.onmouseenter = () => focus(true);
    card.onmouseleave = () => focus(false);
    box.onfocus = () => focus(true);
    box.onblur = () => focus(false);
  });
  count();
  $("#build").onclick = () => act(p, "build", { names: [...page.picks], first_only: true, answers: $("#answers")?.value.trim() || "" });
  $("#rewrite").onclick = () => { const changes = $("#changes").value.trim(); if (changes) act(p, "propose", { changes }); else $("#changes").focus(); };
}

function addLog(items) {
  const log = $("#log");
  if (!log || !items.length) return;
  $(".sub", log)?.remove();
  const near = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
  for (const a of items) {
    const row = document.createElement("div");
    const when = new Date(a.t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    row.innerHTML = `<time>${when}</time><span class="${esc(a.kind)}">${esc(a.text)}</span>`;
    log.append(row);
  }
  if (near) log.scrollTop = log.scrollHeight;
}

async function tick(id) {
  if (page.id !== id) return;
  try {
    const p = await api(`/api/projects/${id}?after=${page.seen}`);
    if (page.id !== id) return;
    if (keyOf(p) !== page.key) { page.seen = 0; renderProject(p); const all = await api(`/api/projects/${id}?after=0`); addLog(all.activity); page.seen = all.activity.length; }
    else { addLog(p.activity); page.seen += p.activity.length; meter(p); }
    page.timer = setTimeout(() => tick(id), p.stage === "working" ? 1500 : 5000);
  } catch (e) { toast(e.message); }
}

async function viewProject(id) {
  const p = await api(`/api/projects/${id}`);
  const brand = (await api("/api/brands")).find((b) => b.id === p.brand);
  setTheme(brand?.colors);
  page.id = id;
  page.picks = new Set();
  renderProject(p);
  addLog(p.activity);
  page.seen = p.activity.length;
  page.timer = setTimeout(() => tick(id), 1500);
}

async function route() {
  clearTimeout(page.timer);
  page.id = null;
  shell();
  const [, name, id] = location.hash.split("/");
  try {
    if (name === "new") await viewCreator();
    else if (name === "brands") await viewBrands();
    else if (name === "brand") await viewBrand(id);
    else if (name === "p") await viewProject(id);
    else await viewProjects();
    main.focus({ preventScroll: true });
  } catch (e) {
    main.innerHTML = `<div class="page"><div class="empty"><h2>${esc(e.message)}</h2><a class="btn" href="#/">${t("projects")}</a></div></div>`;
  }
}

$("#lang").onclick = () => {
  lang = lang === "en" ? "es" : "en";
  try { localStorage.setItem("bvs-lang", lang); } catch {}
  route();
};
addEventListener("hashchange", route);
