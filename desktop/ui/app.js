// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
"use strict";

const invoke = (command, args = {}) => window.__TAURI__.core.invoke(command, args);
const $ = id => document.getElementById(id);
const state = {
  language: localStorage.getItem("language") || "en",
  page: "compose", media: [], cover: null, options: null,
  history: [], selected: -1, busy: false, receipt: null
};
const text = (en, es) => state.language === "es" ? es : en;
const labels = {
  subtitle: ["Compose, choose delivery, then review", "Redacta, elige destinos y revisa"],
  help: ["Help", "Ayuda"], reconnect: ["Retry connection", "Volver a conectar"], workspace: ["Project folder…", "Carpeta del proyecto…"],
  "add-media": ["Choose files…", "Elegir archivos…"], "clear-media": ["Clear files", "Quitar archivos"],
  "to-delivery": ["Choose delivery →", "Elegir destinos →"], "back-compose": ["← Compose", "← Redactar"],
  bake: ["👨‍🍳 Bake and review", "👨‍🍳 Hornea y revisa"],
  "cover-image": ["Choose cover image…", "Elegir portada…"], "cover-clear": ["Clear cover", "Quitar portada"],
  "select-all": ["Select all supported", "Elegir todos los compatibles"],
  "edit-inputs": ["Edit inputs", "Editar opciones"], another: ["Try Another Caption", "Probar otro texto"],
  "edit-caption": ["Edit caption", "Editar texto"], "save-caption": ["Apply caption", "Aplicar texto"],
  "cancel-edit": ["Cancel", "Cancelar"], create: ["Create Drafts", "Crear borradores"],
  schedule: ["Schedule directly…", "Programar directamente…"],
  calendar: ["Open Postiz Calendar", "Abrir calendario de Postiz"],
  "new-plan": ["New post", "Nueva publicación"],
  "approve-status": ["Approve WhatsApp Status…", "Aprobar Estado de WhatsApp…"],
  new: ["Clear composer", "Limpiar formulario"],
  cleanup: ["Manage drafts & queue…", "Gestionar borradores y cola…"],
  "telegram-info": ["Telegram setup", "Configurar Telegram"]
};

function localize() {
  document.documentElement.lang = state.language === "es" ? "es-EC" : "en";
  $("language").value = state.language;
  document.querySelectorAll("[data-en]").forEach(node => node.textContent = node.dataset[state.language]);
  Object.entries(labels).forEach(([id, values]) => $(id).textContent = values[state.language === "es" ? 1 : 0]);
  $("body-label").textContent = text("Your message or idea", "Tu mensaje o idea");
  $("body").placeholder = text("What would you like to share?", "¿Qué quieres compartir?");
  $("drop-label").textContent = text("Choose files or drop them here. You can also continue with text only.", "Elige archivos o arrástralos aquí. También puedes continuar solo con texto.");
  $("text-warning").textContent = text(
    "Text-only announcement. Facebook posts, Threads posts and WhatsApp Status accept text. The other placements need media.",
    "Anuncio solo de texto. Las publicaciones de Facebook, Threads y los Estados de WhatsApp admiten texto. Los otros formatos requieren archivos.");
  $("final-tag").placeholder = text("#MyBusiness", "#MiNegocio");
  $("previous").setAttribute("aria-label", text("Previous caption", "Texto anterior"));
  $("next").setAttribute("aria-label", text("Next caption", "Texto siguiente"));
  updateModeHint();
  renderMedia();
  renderSteps();
  renderDestinations();
  if (state.selected >= 0) renderReview();
}

function updateModeHint() {
  const exact = document.querySelector('input[name="mode"]:checked').value === "exact";
  $("mode-hint").textContent = exact
    ? text("Your wording is preserved. A configured business hashtag is added at the end.", "Se conserva tu redacción. La etiqueta del negocio se añade al final si está configurada.")
    : text("Give the facts and tone you want. Destinations and time are chosen separately.", "Indica los datos y el tono que buscas. Los destinos y la hora se eligen aparte.");
}

function renderSteps() {
  $("steps").replaceChildren();
  const steps = [
    ["compose", text("1 · Compose", "1 · Redacta")],
    ["delivery", text("2 · Delivery", "2 · Destinos")],
    ["review", text("3 · Review & finish", "3 · Revisa y termina")]
  ];
  for (const [id, label] of steps) {
    const button = document.createElement("button");
    button.textContent = label;
    button.classList.toggle("active", state.page === id);
    button.disabled = state.busy || (id === "review" && state.selected < 0)
      || (id === "delivery" && !$("body").value.trim());
    button.onclick = () => id === "delivery" ? delivery() : showPage(id);
    $("steps").append(button);
  }
}

function showPage(page) {
  state.page = page;
  document.querySelectorAll(".page").forEach(node => node.hidden = node.id !== page);
  renderSteps();
}

function notice(message = "", busy = false) {
  $("notice").textContent = message;
  $("notice").hidden = !message;
  $("notice").classList.toggle("busy", busy);
}

async function engine(operation, payload = {}) {
  return invoke("engine", { operation, payload });
}

async function work(message, action) {
  if (state.busy) return;
  state.busy = true;
  renderSteps();
  const controls = document.querySelectorAll("main button, main input, main textarea, main select, header button, header select, footer button");
  controls.forEach(node => node.disabled = true);
  notice(message, true);
  try {
    await action();
    notice();
  } catch (error) {
    notice(text("Please review this before continuing.\n", "Revisa esto antes de continuar.\n") + String(error));
  } finally {
    state.busy = false;
    controls.forEach(node => node.disabled = false);
    $("placement").disabled = state.media.length === 0;
    renderDestinations();
    renderSteps();
    if (state.selected >= 0) updateVersionControls();
  }
}

function invalidate() {
  state.history = [];
  state.selected = -1;
  state.receipt = null;
  renderSteps();
}

function renderMedia() {
  $("media-list").replaceChildren();
  for (const path of state.media) {
    const row = document.createElement("li");
    row.textContent = path.split(/[\\/]/).pop();
    $("media-list").append(row);
  }
  $("clear-media").hidden = state.media.length === 0;
  $("cover-options").hidden = !state.media.some(path => /\.(mp4|mov|m4v|webm|mkv|avi|3gp)$/i.test(path));
  $("cover-name").textContent = state.cover?.split(/[\\/]/).pop() || "";
}

async function addMedia() {
  const paths = await invoke("choose_files", { imagesOnly: false });
  if (!paths.length) return;
  if (state.media.length + paths.length > 10) {
    notice(text("Choose up to ten files.", "Elige hasta diez archivos."));
    return;
  }
  state.media = [...new Set([...state.media, ...paths])];
  invalidate();
  renderMedia();
}

function delivery() {
  if (!$("body").value.trim()) {
    notice(text("Write your message or idea first.", "Primero escribe tu mensaje o idea."));
    return;
  }
  if (!state.options) {
    notice(text("Connect your PostForge folder and start its services first.", "Conecta la carpeta de PostForge y enciende sus servicios."));
    return;
  }
  $("text-warning").hidden = state.media.length > 0;
  $("placement").disabled = state.media.length === 0;
  renderDestinations();
  showPage("delivery");
}

function renderDestinations() {
  if (!state.options) return;
  const previous = new Set([...$("destinations").querySelectorAll("input:checked")].map(input => input.value));
  const first = $("destinations").childElementCount === 0;
  $("destinations").replaceChildren();
  for (const network of state.options.networks) {
    const blocked = state.media.length === 0 && !network.text;
    const label = document.createElement("label");
    label.className = "destination";
    label.classList.toggle("disabled", blocked);
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = network.id;
    input.disabled = blocked;
    input.checked = !blocked && (first || previous.has(network.id));
    input.onchange = invalidate;
    const description = document.createElement("span");
    description.textContent = network.id === "whatsapp" ? text("WhatsApp Status", "Estado de WhatsApp") : network.name;
    const sub = document.createElement("small");
    sub.textContent = blocked ? text("Photo or video required", "Requiere foto o video") : network.accounts.join(" · ");
    description.append(sub);
    label.append(input, description);
    $("destinations").append(label);
  }
}

function form() {
  return {
    body: $("body").value,
    mode: document.querySelector('input[name="mode"]:checked').value,
    networks: [...$("destinations").querySelectorAll("input:checked")].map(input => input.value),
    post_at: $("post-at").value,
    media: state.media,
    placement: $("placement").value,
    cover_image: state.cover,
    cover_second: $("cover-second").value || null,
    final_tag: $("final-tag").value,
    language: state.language,
    text_confirmed: state.media.length === 0
  };
}

function current() { return state.history[state.selected]; }

function remember(result) {
  state.history.push(result);
  if (state.history.length > 8) state.history.shift();
  state.selected = state.history.length - 1;
}

function renderReview() {
  const result = current();
  if (!result) return;
  const plan = result.plan;
  $("plan-meta").replaceChildren();
  const when = document.createElement("p");
  when.textContent = new Intl.DateTimeFormat(state.language === "es" ? "es-EC" : "en", {
    dateStyle: "medium", timeStyle: "short", timeZone: state.options.timezone
  }).format(new Date(plan.when_utc)) + " · " + state.options.timezone;
  const destinations = document.createElement("ul");
  for (const target of plan.targets) {
    const item = document.createElement("li");
    const network = target.network === "whatsapp" ? text("WhatsApp Status", "Estado de WhatsApp")
      : state.options.networks.find(item => item.id === target.network)?.name || target.network;
    const placement = target.placement === "story" ? text(" · Story", " · Historia")
      : target.placement === "feed" ? text(" · Post", " · Publicación") : "";
    item.textContent = network + (target.network === "whatsapp" ? "" : " · " + target.channel + placement);
    destinations.append(item);
  }
  $("plan-meta").append(when, destinations);
  $("warnings").textContent = [...(plan.notes || []), ...(plan.warnings || [])].join("\n\n");
  renderCopy();
  updateVersionControls();
}

function renderCopy() {
  const plan = current().plan;
  $("copy").replaceChildren();
  const main = document.createElement("div");
  main.textContent = plan.caption;
  $("copy").append(main);
  const extra = [
    ["youtube_title", text("YouTube title", "Título de YouTube")],
    ["threads_caption", text("Threads caption", "Texto para Threads")]
  ];
  for (const [key, title] of extra) {
    if (!plan[key]) continue;
    const heading = document.createElement("h3");
    heading.textContent = title;
    const value = document.createElement("div");
    value.textContent = plan[key];
    $("copy").append(heading, value);
  }
}

function updateVersionControls() {
  $("previous").disabled = state.busy || state.selected <= 0;
  $("next").disabled = state.busy || state.selected >= state.history.length - 1;
  $("version").textContent = (state.selected + 1) + text(" of ", " de ") + state.history.length;
  $("schedule").disabled = state.busy || !current()?.plan.direct_schedule_available;
  $("create").disabled = state.busy || state.selected < 0;
}

function navigateVersion(offset) {
  const next = state.selected + offset;
  if (next < 0 || next >= state.history.length) return;
  state.selected = next;
  renderCopy();
  updateVersionControls();
}

function modal(title, content, confirmLabel = text("Continue", "Continuar")) {
  return new Promise(resolve => {
    $("modal-title").textContent = title;
    $("modal-body").replaceChildren();
    if (typeof content === "string") {
      const paragraph = document.createElement("p");
      paragraph.textContent = content;
      $("modal-body").append(paragraph);
    } else {
      $("modal-body").append(content);
    }
    $("modal-cancel").textContent = text("Cancel", "Cancelar");
    $("modal-confirm").textContent = confirmLabel;
    $("modal-confirm").onclick = () => { $("modal").close(); resolve(true); };
    $("modal-cancel").onclick = () => { $("modal").close(); resolve(false); };
    $("modal").oncancel = () => resolve(false);
    $("modal").showModal();
  });
}

async function bake() {
  const data = form();
  if (!data.networks.length) {
    notice(text("Choose at least one destination.", "Elige al menos un destino."));
    return;
  }
  if (!data.post_at) {
    notice(text("Choose a future date and time.", "Elige una fecha y hora futuras."));
    return;
  }
  const hasVideo = data.media.some(path => /\.(mp4|mov|m4v|webm|mkv)$/i.test(path));
  if (hasVideo && !data.cover_image && data.cover_second === null) {
    const proceed = await modal(text("Continue without a selected cover?", "¿Continuar sin elegir portada?"),
      text("You can go back and choose an image or a frame. Supported platforms use their default cover if you continue.",
           "Puedes volver y elegir una imagen o un fotograma. Si continúas, las plataformas compatibles usarán su portada predeterminada."));
    if (!proceed) return;
  }
  await work(text("Baking your plan… ✦", "Horneando tu plan… ✦"), async () => {
    const result = await engine("preview", data);
    state.history = [];
    remember(result);
    renderReview();
    showPage("review");
  });
}

async function revise(edited) {
  const id = current()?.review_id;
  if (!id) return;
  await work(text("Preparing another caption…", "Preparando otro texto…"), async () => {
    const payload = { review_id: id };
    if (edited !== undefined) payload.edited = edited;
    remember(await engine("revise", payload));
    renderCopy();
    $("caption-editor").hidden = true;
    $("copy").hidden = false;
  });
}

async function submit(mode) {
  const result = current();
  if (!result) return;
  const prompt = mode === "schedule"
    ? text("These social posts will publish automatically at the reviewed time. WhatsApp Status requires separate approval.",
           "Las publicaciones de redes saldrán automáticamente a la hora revisada. El Estado de WhatsApp requiere aprobación aparte.")
    : text("Create this plan as Postiz drafts for later approval?", "¿Crear este plan como borradores de Postiz para aprobar después?");
  const confirm = mode === "schedule" ? text("Schedule posts", "Programar publicaciones") : labels.create[state.language === "es" ? 1 : 0];
  if (!await modal(text("Confirm this plan", "Confirma este plan"), prompt, confirm)) return;
  await work(text("Submitting the reviewed plan…", "Enviando el plan revisado…"), async () => {
    state.receipt = await engine("submit", { review_id: result.review_id, mode });
    $("receipt-title").textContent = mode === "schedule" ? text("Posts scheduled", "Publicaciones programadas") : text("Drafts prepared", "Borradores preparados");
    $("receipt-content").textContent = text("Postiz entries: ", "Elementos de Postiz: ")
      + (state.receipt.drafts || []).filter(item => item.post_id).length
      + (state.receipt.whatsapp_pending_id ? text("\nWhatsApp Status is waiting for separate approval.", "\nEl Estado de WhatsApp espera su aprobación por separado.") : "");
    $("approve-status").hidden = !state.receipt.whatsapp_pending_id;
    showPage("receipt");
  });
}

async function approveStatus() {
  if (!await modal(text("Approve this WhatsApp Status?", "¿Aprobar este Estado de WhatsApp?"),
      text("It will go to the configured Status audience at the reviewed time, or soon if that time passed.",
           "Se enviará al público de Estados configurado a la hora revisada o cuanto antes si esa hora ya pasó."),
      text("Approve Status", "Aprobar Estado"))) return;
  await work(text("Approving Status…", "Aprobando Estado…"), async () => {
    await engine("approve_status", { id: state.receipt.whatsapp_pending_id });
    $("approve-status").hidden = true;
  });
}

async function cleanup() {
  const choices = document.createElement("select");
  for (const [value, label] of [
    ["drafts", text("Drafts and failed posts", "Borradores y publicaciones fallidas")],
    ["queue", text("Queue and pending WhatsApp Status", "Cola y Estados pendientes de WhatsApp")],
    ["all", text("All unpublished Postiz work and pending Status", "Todo lo pendiente de Postiz y Estados")]
  ]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    choices.append(option);
  }
  if (!await modal(text("Choose cleanup scope", "Elige qué limpiar"), choices)) return;
  await work(text("Reading unpublished work…", "Leyendo los elementos pendientes…"), async () => {
    const snapshot = await engine("cleanup_preview", { scope: choices.value });
    const prompt = snapshot.post_count + text(" Postiz entries and ", " elementos de Postiz y ")
      + snapshot.whatsapp_count + text(" WhatsApp Status items. A send already underway may finish. Media follows its retention setting.",
                                       " Estados de WhatsApp. Un envío que ya empezó podría completarse. Los archivos siguen su retención.");
    if (!await modal(text("Confirm cleanup", "Confirma la limpieza"), prompt, text("Clear selected work", "Eliminar elementos seleccionados"))) return;
    const result = await engine("cleanup", snapshot);
    if (result.errors?.length) throw new Error(text("Some entries could not be cancelled. Review Postiz.", "No se pudieron cancelar algunos elementos. Revisa Postiz."));
    await modal(text("Cleanup finished", "Limpieza terminada"),
      result.deleted + text(" Postiz entries cleared. ", " elementos eliminados de Postiz. ") + result.cancelled_whatsapp + text(" Status items cancelled.", " Estados cancelados."),
      text("Done", "Listo"));
  });
}

async function reset() {
  if (($("body").value || state.history.length) && !await modal(text("Clear this composer?", "¿Limpiar este formulario?"),
      text("Saved Postiz drafts and queue are managed separately.", "Los borradores guardados y la cola se gestionan por separado."))) return;
  $("body").value = "";
  state.media = [];
  state.cover = null;
  $("cover-second").value = "";
  invalidate();
  renderMedia();
  showPage("compose");
  notice();
}

async function help() {
  const choices = document.createElement("select");
  for (const [value, label] of [["quick", text("Quick guide", "Guía rápida")],
                                 ["technical", text("Technical guide", "Guía técnica")]]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    choices.append(option);
  }
  if (!await modal(text("PostForge Help", "Ayuda de PostForge"), choices)) return;
  const result = await engine("help", { language: state.language, technical: choices.value === "technical" });
  const content = document.createElement("div");
  content.className = "help-document";
  let code = false;
  let pre = null;
  let paragraph = [];
  let list = null;
  const clean = value => value.replace(/\*\*/g, "").replace(/`([^`]+)`/g, "$1");
  const flush = () => {
    if (paragraph.length) {
      const element = document.createElement("p");
      element.textContent = clean(paragraph.join(" "));
      content.append(element);
      paragraph = [];
    }
  };
  for (const line of result.markdown.split("\n")) {
    if (line.startsWith(String.fromCharCode(96).repeat(3))) {
      flush(); list = null; code = !code;
      if (code) { pre = document.createElement("pre"); content.append(pre); }
      continue;
    }
    if (code) { pre.textContent += line + "\n"; continue; }
    const heading = line.match(/^(#{1,3}) (.+)/);
    const item = line.match(/^(- |\d+\. )(.+)/);
    if (!line.trim() || heading || item) flush();
    if (heading) {
      list = null;
      const element = document.createElement("h" + heading[1].length);
      element.textContent = clean(heading[2]);
      content.append(element);
    } else if (item) {
      const kind = item[1] === "- " ? "UL" : "OL";
      if (!list || list.tagName !== kind) { list = document.createElement(kind); content.append(list); }
      const element = document.createElement("li");
      element.textContent = clean(item[2]);
      list.append(element);
    } else if (line.trim()) {
      if (list && /^\s+/.test(line)) list.lastElementChild.textContent += " " + clean(line.trim());
      else { list = null; paragraph.push(line.trim()); }
    } else { list = null; }
  }
  flush();
  await modal(text("PostForge Help", "Ayuda de PostForge"), content, text("Close", "Cerrar"));
}

async function loadOptions() {
  try {
    state.options = await engine("options");
    $("workspace-status").textContent = state.options.workspace;
    $("zone").textContent = state.options.timezone;
    $("final-tag").value = state.options.final_tag;
    const tomorrow = new Date(Date.now() + 86400000);
    const pieces = new Intl.DateTimeFormat("sv-SE", {
      timeZone: state.options.timezone, year: "numeric", month: "2-digit", day: "2-digit"
    }).format(tomorrow);
    $("post-at").value = pieces + "T09:00";
    renderDestinations();
    notice();
  } catch (error) {
    state.options = null;
    notice(text("Postiz is unavailable. Start PostForge services, then choose Retry connection. Use Project folder if this installation is elsewhere.", "Postiz no está disponible. Enciende los servicios de PostForge y pulsa Volver a conectar. Usa Carpeta del proyecto si esta instalación está en otro lugar."));
  }
}

function bind(id, action) {
  $(id).onclick = () => Promise.resolve().then(action).catch(error => notice(String(error)));
}

$("language").onchange = () => {
  state.language = $("language").value;
  localStorage.setItem("language", state.language);
  localize();
  notice();
  if (!state.options) loadOptions();
};
bind("reconnect", loadOptions);
bind("workspace", async () => { if (await invoke("choose_workspace")) await loadOptions(); });
$("body").oninput = () => {
  invalidate();
  $("body").style.height = "auto";
  $("body").style.height = Math.min(300, $("body").scrollHeight) + "px";
};
document.querySelectorAll('input[name="mode"]').forEach(input => input.onchange = () => { invalidate(); updateModeHint(); });
for (const id of ["post-at", "placement", "final-tag", "cover-second"]) {
  $(id).onchange = () => { if (id === "cover-second") state.cover = null; invalidate(); };
}
bind("add-media", addMedia);
bind("clear-media", () => { state.media = []; state.cover = null; invalidate(); renderMedia(); });
bind("cover-image", async () => {
  const selected = await invoke("choose_files", { imagesOnly: true });
  if (selected.length) { state.cover = selected[0]; $("cover-second").value = ""; invalidate(); renderMedia(); }
});
bind("cover-clear", () => { state.cover = null; $("cover-second").value = ""; invalidate(); renderMedia(); });
bind("select-all", () => {
  $("destinations").querySelectorAll("input:not(:disabled)").forEach(input => input.checked = true);
  invalidate();
});
bind("to-delivery", delivery);
bind("back-compose", () => showPage("compose"));
bind("edit-inputs", () => showPage("delivery"));
bind("bake", bake);
bind("previous", () => navigateVersion(-1));
bind("next", () => navigateVersion(1));
bind("another", () => revise());
bind("edit-caption", () => { $("edited").value = current().plan.caption; $("copy").hidden = true; $("caption-editor").hidden = false; });
bind("save-caption", () => revise($("edited").value));
bind("cancel-edit", () => { $("copy").hidden = false; $("caption-editor").hidden = true; });
bind("create", () => submit("draft"));
bind("schedule", () => submit("schedule"));
bind("calendar", () => invoke("open_calendar"));
bind("approve-status", approveStatus);
bind("new-plan", reset);
bind("new", reset);
bind("cleanup", cleanup);
bind("help", help);
bind("telegram-info", () => modal(text("Telegram setup", "Configurar Telegram"),
  text("Create a private bot with @BotFather. In the PostForge folder run:\npython3 v2/telegram_setup.py\nThen start the local agent:\npython3 scripts/host_agent.py start\nEnter the token only in the local setup prompt.",
       "Crea un bot privado con @BotFather. En la carpeta de PostForge ejecuta:\npython3 v2/telegram_setup.py\nLuego inicia el agente local:\npython3 scripts/host_agent.py start\nIngresa el token solo en el formulario local."), text("Done", "Listo")));
document.addEventListener("keydown", event => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && !state.busy) {
    event.preventDefault();
    if (state.page === "compose") delivery();
    else if (state.page === "delivery") bake();
  }
});
if (window.__TAURI__?.event) {
  window.__TAURI__.event.listen("tauri://drag-drop", event => {
    if (state.busy) return;
    if (state.media.length + event.payload.paths.length > 10) return;
    state.media = [...new Set([...state.media, ...event.payload.paths])];
    invalidate();
    renderMedia();
  });
}
localize();
loadOptions();
