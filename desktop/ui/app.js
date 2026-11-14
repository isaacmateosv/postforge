// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
"use strict";

const invoke = (command, args = {}) => window.__TAURI__.core.invoke(command, args);
const $ = id => document.getElementById(id);
const state = {
  language: localStorage.getItem("language") || "en",
  page: "home", media: [], cover: null, options: null,
  history: [], selected: -1, busy: false, receipt: null
};
const text = (en, es) => state.language === "es" ? es : en;
let feedbackTimeout;
function selectionFeedback({state:result,message}) {
  clearTimeout(feedbackTimeout);
  const box=$("selection-feedback");box.textContent=message;box.dataset.state=result;box.hidden=false;
  feedbackTimeout=setTimeout(()=>{box.hidden=true;},4500);
}
const receiptReturn=window.PostForgeCompletionTimer.create({
  isActive:()=>state.page==="receipt" && !document.hidden && document.hasFocus() && !document.querySelector("dialog[open]"),
  onTick:seconds=>{
    $("receipt-countdown").textContent=text("Returning to Dashboard in ","Volverás al inicio en ")+seconds+text(" seconds"," segundos");
    $("receipt-progress").value=seconds;
  },
  onDone:()=>showPage("home")
});
function stopReceiptReturn(){receiptReturn.stop();$("receipt-return").hidden=true;}
function renderActionDock(){
  const page=state.page;$("workflow-actions").hidden=!["compose","delivery","review"].includes(page);
  for(const name of ["compose","delivery","review"])$(name+"-actions").hidden=name!==page;
  $("workflow-next-title").textContent=page==="compose"?text("Next: choose where and when","Siguiente: elige dónde y cuándo"):page==="delivery"?text("Next: bake and review your plan","Siguiente: hornea y revisa tu plan"):text("Ready to save or schedule?","¿Listo para guardar o programar?");
  $("workflow-next-detail").textContent=page==="delivery"?text("⌘ / Ctrl + Enter · nothing is published yet","⌘ / Ctrl + Enter · aún no se publica nada"):page==="review"?text("Drafts for later approval, or schedule the reviewed plan","Guarda borradores para aprobar después o programa el plan revisado"):text("Your caption and media stay with you","Se conservan tu texto y tus archivos");
}
const labels = {
  subtitle: ["Compose, choose delivery, then review", "Redacta, elige destinos y revisa"],
  help: ["Help", "Ayuda"], reconnect: ["Refresh status", "Actualizar estado"], workspace: ["Locate recovered installation", "Localizar instalación recuperada"],
  "add-media": ["Choose files", "Elegir archivos"], "clear-media": ["Clear files", "Quitar archivos"],
  "to-delivery": ["Choose delivery →", "Elegir destinos →"], "back-compose": ["← Compose", "← Redactar"],
  bake: ["👨‍🍳 Bake and review", "👨‍🍳 Hornea y revisa"],
  "cover-image": ["Choose cover image", "Elegir portada"], "cover-clear": ["Clear cover", "Quitar portada"],
  "select-all": ["Select all supported", "Elegir todos los compatibles"],
  "edit-inputs": ["Edit inputs", "Editar opciones"], another: ["Try Another Caption", "Probar otro texto"],
  "edit-caption": ["Edit caption", "Editar texto"], "save-caption": ["Apply caption", "Aplicar texto"],
  "cancel-edit": ["Cancel", "Cancelar"], create: ["Create Drafts", "Crear borradores"],
  schedule: ["Schedule directly", "Programar directamente"],
  calendar: ["Open Postiz Calendar", "Abrir calendario de Postiz"],
  "new-plan": ["New post", "Nueva publicación"],
  "approve-status": ["Approve WhatsApp Status", "Aprobar Estado de WhatsApp"],
  new: ["Clear composer", "Limpiar formulario"],
  cleanup: ["Remove posts", "Eliminar publicaciones"]
};

function localize() {
  document.documentElement.lang = state.language === "es" ? "es-EC" : "en";
  $("language").value = state.language;
  $("language").setAttribute("aria-label", text("Language", "Idioma"));
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
  $("telegram-owners").setAttribute("aria-label", text("Detected private accounts", "Cuentas privadas encontradas"));
  $("wa-receipts").textContent=$("wa-receipt-history").hidden?text("View delivery receipts","Ver recibos de entrega"):text("Hide delivery receipts","Ocultar recibos de entrega");
  updateModeHint();
  renderMedia();
  renderSteps();
  renderDestinations();
  if (state.selected >= 0) renderReview();
  $("workspace-status").textContent = text("Private data · on your device", "Datos privados · en tu equipo");
  if (state.dashboard) renderDashboard();
}

function updateModeHint() {
  const exact = document.querySelector('input[name="mode"]:checked').value === "exact";
  $("mode-hint").textContent = exact
    ? text("Your wording is preserved. A configured business hashtag is added at the end.", "Se conserva tu redacción. La etiqueta del negocio se añade al final si está configurada.")
    : text("Give the facts and tone you want. Destinations and time are chosen separately.", "Indica los datos y el tono que buscas. Los destinos y la hora se eligen aparte.");
}

function renderSteps() {
  renderActionDock();
  $("steps").replaceChildren();
  const steps = [
    ["compose", text("1 · Compose", "1 · Redacta")],
    ["delivery", text("2 · Delivery", "2 · Destinos")],
    ["review", text("3 · Review & finish", "3 · Revisa y termina")]
  ];
  for (const [id, label] of steps) {
    const button = document.createElement("button");
    const done = id === "compose" ? !!$("body").value.trim() : id === "delivery" ? state.selected >= 0 : !!state.receipt;
    button.textContent = done ? "✓ " + label : label;
    button.classList.toggle("complete", done);
    button.classList.toggle("active", state.page === id);
    button.disabled = state.busy || (id === "review" && state.selected < 0)
      || (id === "delivery" && !$("body").value.trim());
    button.onclick = () => id === "delivery" ? delivery() : showPage(id);
    $("steps").append(button);
  }
}

function showPage(page) {
  window.PostForgeMedia.pause();
  if(page!=="receipt")stopReceiptReturn();
  state.page = page;
  document.querySelector("main").scrollTop = 0;
  $("steps").hidden = page === "home";
  if (page === "home") refreshDashboard(true);
  document.querySelectorAll(".page").forEach(node => node.hidden = node.id !== page);
  renderSteps();
  $("new").hidden = !["compose","delivery","review"].includes(page);
}

const openDialog = id => window.PostForgeDialogs.open(id);

function notice(message = "", busy = false) {
  $("notice").textContent = message;
  $("notice").hidden = !message;
  $("notice").classList.toggle("busy", busy);
}

async function engine(operation, payload = {}) {
  return invoke("engine", { operation, payload });
}

async function work(message, action, baking=false) {
  if (state.busy) return;
  state.busy = true;
  updateTray();
  renderSteps();
  const controls = document.querySelectorAll("main button, main input, main textarea, main select, header button, header select, footer button, #workflow-actions button, #telegram-settings button, #telegram-settings input, #telegram-settings select");
  controls.forEach(node => node.disabled = true);
  notice(baking ? "" : message, true);
  $("baking-visual").hidden = !baking;
  try {
    await action();
    notice();
  } catch (error) {
    notice(text("Please review this before continuing.\n", "Revisa esto antes de continuar.\n") + friendlyError(error));
  } finally {
    $("baking-visual").hidden = true;
    state.busy = false;
    updateTray();
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
  window.PostForgeMedia.update(state.media,state.cover,$("cover-second").value || null,state.language);
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
    notice(text("Start local services first. Settings includes advanced recovery.", "Primero enciende los servicios locales. Ajustes incluye la recuperación avanzada."));
    return;
  }
  $("text-warning").hidden = state.media.length > 0;
  $("placement").disabled = state.media.length === 0;
  $("wa-text-options").hidden = state.media.length > 0;
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
    input.onchange = () => { invalidate(); updateNetworkOptions(); };
    const description = document.createElement("span");
    description.textContent = network.id === "whatsapp" ? text("WhatsApp Status", "Estado de WhatsApp") : network.name;
    const sub = document.createElement("small");
    sub.textContent = network.id === "whatsapp" && !state.dashboard?.whatsapp?.connected ? text("Link WhatsApp before approving Status", "Vincula WhatsApp antes de aprobar el Estado") : blocked ? text("Photo or video required", "Requiere foto o video") : network.accounts.join(" · ");
    description.append(sub);
    label.append(input, description);
    $("destinations").append(label);
  }
  updateNetworkOptions();
}

function updateNetworkOptions() {
  const selected = new Set([...$("destinations").querySelectorAll("input:checked")].map(input => input.value));
  $("youtube-options").hidden = !selected.has("youtube");
  $("wa-text-options").hidden = state.media.length > 0 || !selected.has("whatsapp");
  renderYouTubeRoute();
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
    youtube_mode: $("youtube-mode").value,
    whatsapp_background: $("wa-background").value,
    text_confirmed: state.media.length === 0
  };
}

function current() { return state.history[state.selected]; }

function remember(result) {
  const same = state.history.findIndex(item => item.plan.caption === result.plan.caption && item.plan.threads_caption === result.plan.threads_caption);
  if (same >= 0) { state.history[same] = result; state.selected = same; return; }
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
    const placement = target.network === "youtube" ? (plan.short ? " · Short" : text(" · Video", " · Video")) : target.placement === "story" ? text(" · Story", " · Historia")
      : target.placement === "feed" ? text(" · Post", " · Publicación") : "";
    item.textContent = network + (target.network === "whatsapp" ? "" : " · " + target.channel + placement)
      + (target.parts > 1 ? text(" · ", " · ") + target.parts + text(" segments / drafts", " segmentos / borradores") : "")
      + (target.cover ? text(" · ✓ Selected cover", " · ✓ Portada elegida") : "");
    destinations.append(item);
  }
  $("plan-meta").append(when, destinations);
  $("review-post-at").value = new Intl.DateTimeFormat("sv-SE", {timeZone:state.options.timezone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(plan.when_utc)).replace(" ","T");
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
  main.className = "copy-primary";
  if (plan.youtube_title) {
    const section = document.createElement("div"); section.className = "platform-copy";
    const heading = document.createElement("h3"); heading.textContent = text("YouTube title", "Título de YouTube");
    const value = document.createElement("p"); value.textContent = plan.youtube_title;
    const button = document.createElement("button"); button.textContent = text("Edit title", "Editar título");
    button.onclick = editYoutubeTitle;
    const retry = document.createElement("button"); retry.textContent = text("Try another title", "Probar otro título");
    retry.onclick = async () => { await work(text("Preparing another title", "Preparando otro título"), async () => {
      state.history[state.selected] = await engine("revise", {review_id:current().review_id, regenerate_title:true});
      renderCopy();
    }); };
    const actions = document.createElement("div"); actions.className = "actions wrap"; actions.append(button,retry);
    section.append(heading,value,actions); $("copy").append(section);
  }
  if(plan.youtube_caption && plan.youtube_caption!==plan.caption){
    const section=document.createElement("div");section.className="platform-copy";
    const heading=document.createElement("h3");heading.textContent=text("YouTube description","Descripción de YouTube");
    const body=document.createElement("p");body.textContent=plan.youtube_caption;section.append(heading,body);$("copy").append(section);
  }
  if (plan.threads_caption) {
    const details = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = text("Threads adaptation · same idea, shorter", "Adaptación para Threads · misma idea, más corta");
    const value = document.createElement("p"); value.textContent = plan.threads_caption;
    details.append(summary,value); $("copy").append(details);
  }

}

function reviewNeedsNetworkRefresh(plan,network) {
  return !!(plan?.public_origin && network?.url && plan.public_origin!==network.url);
}
function updateVersionControls() {
  $("previous").disabled = state.busy || state.selected <= 0;
  $("next").disabled = state.busy || state.selected >= state.history.length - 1;
  $("version").textContent = (state.selected + 1) + text(" of ", " de ") + state.history.length;
  const stale=reviewNeedsNetworkRefresh(current()?.plan,state.network);
  $("schedule").disabled = state.busy || stale || !current()?.plan.direct_schedule_available;
  $("create").disabled = state.busy || stale || state.selected < 0;
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
    openDialog("modal");
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
  await work(text("Baking your plan ✦", "Horneando tu plan ✦"), async () => {
    const result = await engine("preview", data);
    state.history = [];
    remember(result);
    renderReview();
    showPage("review");
  }, true);
}

async function revise(edited) {
  const id = current()?.review_id;
  if (!id) return;
  await work(text("Preparing another caption", "Preparando otro texto"), async () => {
    const payload = { review_id: id };
    if (edited !== undefined) payload.edited = edited;
    const revised = await engine("revise", payload);
    if (edited !== undefined) state.history[state.selected] = revised;
    else remember(revised);
    renderCopy();
    $("caption-editor").hidden = true;
    $("copy").hidden = false;
  });
}

async function submit(mode) {
  if (!current() || state.busy) return;
  if ($("review-post-at").value !== new Intl.DateTimeFormat("sv-SE", {timeZone:state.options.timezone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(current().plan.when_utc)).replace(" ","T")) { if (!await rescheduleReview()) return; }
  const result = current();
  if (!result) return;
  const prompt = mode === "schedule"
    ? text("All selected destinations, including WhatsApp Status, will publish at the reviewed time. This also approves delivery to your configured WhatsApp audience.",
           "Todos los destinos seleccionados, incluido el Estado de WhatsApp, se publicarán a la hora revisada. Esto también aprueba el envío al público de WhatsApp configurado.")
    : text("Create this plan as Postiz drafts for later approval?", "¿Crear este plan como borradores de Postiz para aprobar después?");
  const confirm = mode === "schedule" ? text("Schedule posts", "Programar publicaciones") : labels.create[state.language === "es" ? 1 : 0];
  if (!await modal(text("Confirm this plan", "Confirma este plan"), prompt, confirm)) return;
  await work(text("Submitting the reviewed plan", "Enviando el plan revisado"), async () => {
    state.receipt = await engine("submit", { review_id: result.review_id, mode });
    refreshDashboard(true);
    $("receipt-title").textContent = mode === "schedule" ? text("Posts scheduled", "Publicaciones programadas") : text("Drafts prepared", "Borradores preparados");
    $("receipt-content").textContent = text("Postiz entries: ", "Elementos de Postiz: ")
      + (state.receipt.drafts || []).filter(item => item.post_id).length
      + (state.receipt.whatsapp_scheduled ? text("\nWhatsApp Status is approved and scheduled.", "\nEl Estado de WhatsApp está aprobado y programado.") : state.receipt.whatsapp_pending_id ? text("\nWhatsApp Status is waiting for separate approval.", "\nEl Estado de WhatsApp espera su aprobación por separado.") : "");
    $("approve-status").hidden = !state.receipt.whatsapp_pending_id || state.receipt.whatsapp_scheduled;
    showPage("receipt");
    $("receipt-title").focus({preventScroll:true});
    if(mode==="schedule") {$("receipt-return").hidden=false;receiptReturn.start(8);}
  });
}

async function approveStatus() {
  if (!await modal(text("Approve this WhatsApp Status?", "¿Aprobar este Estado de WhatsApp?"),
      text("It will go to the configured Status audience at the reviewed time, or soon if that time passed.",
           "Se enviará al público de Estados configurado a la hora revisada o cuanto antes si esa hora ya pasó."),
      text("Approve Status", "Aprobar Estado"))) return;
  await work(text("Approving Status", "Aprobando Estado"), async () => {
    await engine("approve_status", { id: state.receipt.whatsapp_pending_id });
    $("approve-status").hidden = true;
  });
}

async function cleanup() {
  const choices = document.createElement("select");
  for (const [value, label] of [
    ["drafts", text("Unpublished drafts (including failed attempts)", "Borradores sin publicar (incluye intentos fallidos)")],
    ["queue", text("Cancel scheduled posts and pending WhatsApp Status", "Cancelar publicaciones programadas y Estados pendientes")],
    ["all", text("Both drafts and scheduled posts", "Ambos: borradores y publicaciones programadas")]
  ]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    choices.append(option);
  }
  if (!await modal(text("What would you like to remove?", "¿Qué publicaciones quieres eliminar?"), choices)) return;
  await work(text("Reading unpublished work", "Leyendo los elementos pendientes"), async () => {
    const snapshot = await engine("cleanup_preview", { scope: choices.value });
    const prompt = snapshot.post_count + text(" Postiz entries and ", " elementos de Postiz y ")
      + snapshot.whatsapp_count + text(" WhatsApp Status items. A send already underway may finish. Media follows its retention setting.",
                                       " Estados de WhatsApp. Un envío que ya empezó podría completarse. Los archivos siguen su retención.");
    if (!await modal(text("Review before removing", "Revisa antes de eliminar"), prompt, text("Clear selected work", "Eliminar elementos seleccionados"))) return;
    const result = await engine("cleanup", snapshot);
    await refreshDashboard(true);
    if (result.errors?.length) throw new Error(text("Some entries could not be cancelled. Review Postiz.", "No se pudieron cancelar algunos elementos. Revisa Postiz."));
    await modal(text("Cleanup finished", "Limpieza terminada"),
      result.deleted + text(" Postiz entries cleared. ", " elementos eliminados de Postiz. ") + result.cancelled_whatsapp + text(" Status items cancelled.", " Estados cancelados."),
      text("Done", "Listo"));
  });
}

async function reset(force=false) {
  if (!force && ($("body").value || state.history.length) && !await modal(text("Clear this composer?", "¿Limpiar este formulario?"),
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

function momentLabel(value) {
  if (!value) return text("Nothing scheduled", "Nada programado");
  const normalized = /(?:Z|[+-]\d\d:?\d\d)$/.test(value) ? value : value + "Z";
  return new Intl.DateTimeFormat(state.language === "es" ? "es-EC" : "en", {
    dateStyle: "medium", timeStyle: "short", timeZone: state.options?.timezone || "America/Guayaquil"
  }).format(new Date(normalized));
}

function renderDashboard() {
  const data = state.dashboard;
  if (!data) return;
  $("start-post").textContent = $("body").value.trim() && !state.receipt ? text("Continue your post →", "Continúa tu publicación →") : text("＋ New post", "＋ Nueva publicación");
  $("dash-drafts").textContent = data.available ? data.drafts : "—";
  $("dash-queue").textContent = data.available ? data.queue : "—";
  $("dash-next").textContent = data.available ? momentLabel(data.next) : text("Services offline", "Servicios apagados");
  $("dash-updated").textContent = text("Updated ", "Actualizado ") + new Date().toLocaleTimeString(state.language === "es" ? "es-EC" : "en", {hour:"2-digit",minute:"2-digit"});
  $("whatsapp-open").textContent = (data.whatsapp?.connected ? "✓ " : "○ ") + "WhatsApp";
  $("whatsapp-open").classList.toggle("ready", !!data.whatsapp?.connected);
  $("telegram-open").textContent = (data.telegram?.running ? "✓ " : "○ ") + "Telegram";
  $("telegram-open").classList.toggle("ready", !!data.telegram?.running);
  $("health").replaceChildren();
  for (const [label, ready, configured, action] of [
    ["Postiz", data.postiz_online, data.available, () => invoke("open_calendar")]
  ]) {
    const button = document.createElement("span");
    button.className = "health-pill " + (ready ? "ready" : "waiting");
    button.textContent = (ready ? "✓ " : "○ ") + label + " · " + (ready ? text("Connected", "Conectado")
      : configured ? text("Paused", "En pausa") : text("Set up", "Configurar"));
    $("health").append(button);
  }
  const statusItems = data.status_items || [];
  $("status-card").hidden = false;
  const sending=statusItems.filter(item=>item.status==="sending").length;
  $("status-count").textContent = " · " + statusItems.length + text(" items", " estados")+(sending?" · "+sending+text(" sending"," en envío"):"");
  $("dashboard-status").replaceChildren();
  for (const item of statusItems) {
    const row = document.createElement("article"); row.className = "post-row";
    const content = document.createElement("div");
    const title = document.createElement("strong"); title.textContent = item.caption.slice(0,120) || text("Media Status", "Estado con archivos");
    const note = document.createElement("p"); note.textContent = momentLabel(item.when) + " · " + (item.status === "needs_review"
      ? text("Delivery needs review · automatic retry is held", "Revisa la entrega · el reintento automático está detenido")
      : item.status === "sending" ? (item.delivery_parts ? text("Sending part ","Enviando parte ")+item.delivery_part+text(" of "," de ")+item.delivery_parts : text("Sending to audience","Enviando a la audiencia"))+text(" · large audiences can take several minutes"," · las audiencias grandes pueden tardar varios minutos") : item.approved ? text("Approved · waiting for delivery", "Aprobado · esperando el envío") : text("Awaiting your approval", "Espera tu aprobación"));
    const audience=document.createElement("small");audience.textContent=item.audience==="test" ? text("Selected contacts: ","Contactos seleccionados: ")+item.recipient_count : text("Audience: all contacts","Audiencia: todos los contactos");
    content.append(title,note,audience); row.append(content);
    if (item.status === "pending" && !item.approved) {
      const approve = document.createElement("button"); approve.textContent = text("Review Status", "Revisar Estado");
      approve.onclick = async () => {
        const note = item.caption + "\n\n" + momentLabel(item.when) + "\n" + item.media.join("\n") + "\n" + text("Text background: ", "Fondo del texto: ") + item.background
          + text("\nIf the time has passed, approval sends it now.", "\nSi la hora ya pasó, aprobarlo lo enviará ahora.");
        if (!await modal(text("Approve this WhatsApp Status?", "¿Aprobar este Estado de WhatsApp?"), note, text("Approve Status", "Aprobar Estado"))) return;
        await work(text("Approving Status", "Aprobando Estado"), async () => { await engine("approve_status",{id:item.id}); await refreshDashboard(true); });
      };
      row.append(approve);
    }
    $("dashboard-status").append(row);
  }
  $("dashboard-posts").replaceChildren();
  const list = (data.posts || []).filter(post => !state.dashFilter || post.state === state.dashFilter);
  if (!list.length) {
    const empty = document.createElement("p");
    empty.className = "dashboard-empty";
    empty.textContent = data.available ? text("A little room for your next idea. Your recent drafts and scheduled posts appear here.",
      "Aquí hay espacio para tu próxima idea. Tus borradores y publicaciones programadas aparecerán aquí.")
      : text("Start your local services, then refresh to see saved posts.", "Enciende los servicios locales y actualiza para ver tus publicaciones.");
    $("dashboard-posts").append(empty);
  }
  for (const post of list) {
    const row = document.createElement("article"); row.className = "post-row";
    const badge = document.createElement("span"); badge.className = "post-badge " + post.state.toLowerCase();
    badge.textContent = post.state === "DRAFT" ? text("Draft", "Borrador") : post.state === "QUEUE" ? text("Scheduled", "Programada") : text("Needs review", "Por revisar");
    const content = document.createElement("div");
    const heading = document.createElement("strong");
    const names = {facebook:"Facebook",instagram:"Instagram","instagram-standalone":"Instagram",threads:"Threads",youtube:"YouTube",tiktok:"TikTok"};
    heading.textContent = (names[post.network] || post.network) + " · " + post.channel;
    const caption = document.createElement("p"); caption.textContent = post.text || text("Media post", "Publicación con archivos");
    const date = document.createElement("small"); date.textContent = momentLabel(post.at);
    content.append(heading,caption,date); row.append(badge,content); $("dashboard-posts").append(row);
  }
}

async function refreshDashboard(force=false) {
  if (state.dashboardPending || (!force && Date.now() - (state.dashboardAt || 0) < 20000)) return;
  state.dashboardPending = true;
  try {
    const data = await engine("dashboard");
    const changed = JSON.stringify(data) !== JSON.stringify(state.dashboard);
    state.dashboard = data; state.dashboardAt = Date.now();
    showConnections();
    checkPublicAccess();
    updateTray();
    if (changed || force) renderDashboard();
  }
  catch (error) { $("dashboard-posts").textContent = text("Local services are unavailable. Open Settings for recovery.", "Los servicios locales no están disponibles. Abre Ajustes para recuperarlos."); }
  finally { state.dashboardPending = false; }
}

function soon() {
  const date = new Date(Date.now() + 10 * 60000);
  $("post-at").value = new Intl.DateTimeFormat("sv-SE", {timeZone:state.options?.timezone || "America/Guayaquil",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(date).replace(" ", "T");
  invalidate();
}

let waTimer = null;
let waChecking = false;
let waHadQR = false;
function waClose() {
  clearInterval(waTimer); waTimer = null;
  $("wa-qr").removeAttribute("src"); $("wa-qr").hidden = true;
}
async function waState() {
  if (waChecking || !$("whatsapp-settings").open) return;
  waChecking = true;
  try {
    const result = await engine("whatsapp_state");
    $("wa-state").textContent = result.connected ? text("✓ WhatsApp connected", "✓ WhatsApp conectado") : text("○ Waiting for the phone", "○ Esperando al teléfono");
    $("wa-state").classList.toggle("connected", result.connected);
    $("wa-refresh").hidden = result.connected;
    if (result.connected) {
      waClose();
      if (waHadQR) {
        waHadQR = false;
        const finish = await engine("whatsapp_finish");
        if (!finish.receipts_ready) $("wa-feedback").textContent = text("Linked. Status receipt setup still needs review.", "Vinculado. Falta revisar la configuración de los recibos de Estado.");
      }
      await refreshDashboard(true);
    }
  } catch (error) { $("wa-feedback").textContent = friendlyError(error); }
  finally { waChecking = false; }
}
async function whatsappSettings() {
  waClose(); waHadQR = false;
  $("wa-feedback").textContent = "";
  $("wa-state").textContent = text("Checking connection", "Comprobando conexión");
  $("wa-refresh").hidden = false;
  openDialog("whatsapp-settings");
  await readAudience();
  await waState();
  if ($("whatsapp-settings").open && !$("wa-refresh").hidden) waTimer = setInterval(waState, 4000);
}

async function editYoutubeTitle() {
  const input = document.createElement("textarea"); input.rows = 3; input.maxLength = 100;
  input.value = current().plan.youtube_title || "";
  input.setAttribute("aria-label", text("YouTube title · up to 100 characters", "Título de YouTube · hasta 100 caracteres"));
  if (!await modal(text("Edit YouTube title · 100 characters", "Editar título de YouTube · 100 caracteres"), input, text("Save title", "Guardar título"))) return;
  await work(text("Saving title", "Guardando título"), async () => {
    state.history[state.selected] = await engine("revise", {review_id:current().review_id, youtube_title:input.value});
    renderCopy();
  });
}

function friendlyError(error) {
  const parts = String(error).split(" / ");
  return parts.length === 2 ? parts[state.language === "es" ? 1 : 0] : String(error);
}

function renderTelegramStatus(config) {
  $("telegram-open").textContent = "Telegram";
  $("telegram-enabled").checked = config.enabled && !config.migration_hold;
  $("telegram-owner").value = config.owner_id;
  $("telegram-language").value = config.language;
  $("telegram-heartbeat").value = config.heartbeat;
  $("telegram-owners").hidden = true;
  $("telegram-summary").textContent = (config.username ? "@" + config.username + " · " : "") + (config.migration_hold
    ? text("Restored settings · paused. Stop the old host, then enable this one.", "Ajustes restaurados · en pausa. Detén el equipo anterior y activa este.")
    : config.running ? text("Connected · owner ", "Conectado · cuenta ") + config.owner_id
    : config.configured ? text("Configured · paused", "Configurado · en pausa")
    : text("Not configured · bring your own bot", "Sin configurar · usa tu propio bot"));
  $("telegram-token").placeholder = config.has_token
    ? text("Saved token · leave empty to keep", "Token guardado · deja vacío para conservarlo")
    : text("Paste the token from BotFather", "Pega el token de BotFather");
}

async function telegramSettings() {
  $("telegram-token").value = "";
  $("telegram-feedback").textContent = "";
  renderTelegramStatus(await engine("telegram_status"));
  openDialog("telegram-settings");
  $("telegram-settings").querySelector(".telegram-body").scrollTop = 0;
}

async function telegramAction(action) {
  const buttons = $("telegram-settings").querySelectorAll("button, input, select");
  buttons.forEach(node => node.disabled = true);
  try { await action(); }
  catch (error) { $("telegram-feedback").textContent = friendlyError(error); }
  finally { buttons.forEach(node => node.disabled = false); }
}

let helpRequest=0;
async function help(technical=state.helpTechnical || false) {
  state.helpTechnical=technical;
  const request=++helpRequest;
  openDialog("help-dialog");
  $("help-feedback").textContent=text("Opening guide…","Abriendo guía…");$("help-retry").hidden=true;
  $("help-body").replaceChildren();$("help-body").setAttribute("aria-busy","true");
  $("help-quick").setAttribute("aria-pressed",String(!technical));$("help-technical").setAttribute("aria-pressed",String(technical));
  try {
    const result=await engine("help",{language:state.language,technical});
    if(request!==helpRequest || !$("help-dialog").open) return;
    $("help-body").append(renderHelpDocument(result.markdown));
    $("help-feedback").textContent="";
  } catch(error) {
    if(request!==helpRequest || !$("help-dialog").open) return;
    $("help-feedback").textContent=text("Could not open the guide. ","No se pudo abrir la guía. ")+friendlyError(error);$("help-retry").hidden=false;
  } finally { if(request===helpRequest) $("help-body").setAttribute("aria-busy","false"); }
}
function renderHelpDocument(markdown) {
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
  for (const line of markdown.split("\n")) {
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
  return content;
}
bind("help-quick",()=>help(false));bind("help-technical",()=>help(true));
bind("help-retry",()=>help());bind("help-close",()=>{$("help-dialog").close();++helpRequest;});
$("help-dialog").addEventListener("cancel",()=>{++helpRequest;});

async function loadOptions() {
  try {
    state.options = await engine("options");
    $("storage-location").textContent = state.options.workspace;
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
    notice(text("Postiz is unavailable. Start local services and refresh. Settings includes advanced recovery if needed.", "Postiz no está disponible. Enciende los servicios locales y actualiza. Ajustes incluye la recuperación avanzada si la necesitas."));
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
bind("reconnect", async () => { await loadOptions(); await refreshDashboard(true); });
bind("workspace", async () => { if (await invoke("choose_workspace")) { await loadOptions(); await refreshDashboard(true); } });
$("body").oninput = () => {
  invalidate();
  $("body").style.height = "auto";
  $("body").style.height = Math.min(300, $("body").scrollHeight) + "px";
};
document.querySelectorAll('input[name="mode"]').forEach(input => input.onchange = () => { invalidate(); updateModeHint(); });
for (const id of ["post-at", "placement", "final-tag", "cover-second", "youtube-mode", "wa-background"]) {
  $(id).onchange = () => { if (id === "cover-second") { state.cover = null; renderMedia(); } invalidate(); if(id==="youtube-mode")renderYouTubeRoute(); };
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
  updateNetworkOptions();
});
bind("go-home", () => showPage("home"));
bind("start-post", async () => { if (state.receipt) await reset(true); else showPage("compose"); });
bind("home-calendar", () => invoke("open_calendar"));
bind("show-drafts", () => { state.dashFilter = state.dashFilter === "DRAFT" ? null : "DRAFT"; renderDashboard(); });
bind("show-queue", () => { state.dashFilter = state.dashFilter === "QUEUE" ? null : "QUEUE"; renderDashboard(); });
bind("asap", soon);
bind("settings-open", () => openDialog("app-settings"));
bind("settings-close", () => $("app-settings").close());
bind("whatsapp-open", whatsappSettings);
bind("wa-close", () => { waClose(); $("whatsapp-settings").close(); });
$("whatsapp-settings").oncancel = waClose;
bind("wa-refresh", async () => {
  $("wa-refresh").disabled = true;
  try {
    const result = await engine("whatsapp_connect");
    if (result.qr) { $("wa-qr").src = result.qr; $("wa-qr").hidden = false; waHadQR = true; }
    else await waState();
  } catch (error) { $("wa-feedback").textContent = friendlyError(error); }
  finally { $("wa-refresh").disabled = false; }
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
bind("cleanup", () => fromSettings(cleanup));
bind("help", help);

bind("telegram-open", telegramSettings);
bind("telegram-inspect", () => telegramAction(async () => {
  const bot = await engine("telegram_inspect", { token: $("telegram-token").value });
  $("telegram-feedback").textContent = text("Validated bot: @", "Bot validado: @") + bot.username;
}));
bind("telegram-detect", () => telegramAction(async () => {
  const result = await engine("telegram_detect", { token: $("telegram-token").value });
  const choices = $("telegram-owners");
  choices.replaceChildren();
  if (result.owners.length > 1) {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = text("Choose your account", "Elige tu cuenta");
    choices.append(placeholder);
  }
  for (const owner of result.owners) {
    const option = document.createElement("option");
    option.value = owner.id;
    option.textContent = owner.name + (owner.username ? " · @" + owner.username : "") + " · " + owner.id;
    choices.append(option);
  }
  choices.hidden = result.owners.length === 0;
  if (result.owners.length === 1) $("telegram-owner").value = result.owners[0].id;
  else $("telegram-owner").value = "";
  $("telegram-feedback").textContent = result.owners.length
    ? text("Choose your account and review its ID before saving.", "Elige tu cuenta y revisa su ID antes de guardar.")
    : text("No private /start found. Send /start to your bot, then try again.", "No se encontró un /start privado. Envía /start a tu bot y vuelve a intentar.");
}));
$("telegram-owners").onchange = () => { $("telegram-owner").value = $("telegram-owners").value; };
bind("telegram-close", () => { $("telegram-token").value = ""; $("telegram-settings").close(); });
$("telegram-settings").oncancel = () => { $("telegram-token").value = ""; };
bind("telegram-save", async () => {
  const payload = { token: $("telegram-token").value, owner_id: $("telegram-owner").value,
    enabled: $("telegram-enabled").checked, language: $("telegram-language").value,
    heartbeat: $("telegram-heartbeat").value };
  let bot = null;
  if (payload.enabled) {
    try { bot = await engine("telegram_inspect", { token: payload.token }); }
    catch (error) { $("telegram-feedback").textContent = friendlyError(error); return; }
  }
  const message = payload.enabled
    ? text("Enable @", "¿Activar @") + bot.username + text(" for private owner ", " para la cuenta privada ") + payload.owner_id
      + text("? Ensure the previous receiver is stopped. New bot/owner or migrated setups ignore messages sent before activation. Heartbeat: ",
             "? Confirma que el receptor anterior esté detenido. Al cambiar el bot o propietario, o al migrar, se omiten los mensajes anteriores a la activación. Aviso de actividad: ")
      + payload.heartbeat + text(" minutes (0 = off).", " minutos (0 = apagado).")
    : text("Disable Telegram on this computer? Your saved credentials and preferences are kept.",
           "¿Desactivar Telegram en este equipo? Se conservan tus credenciales y preferencias guardadas.");
  if (!await modal(text("Confirm Telegram settings", "Confirma los ajustes de Telegram"), message, text("Save", "Guardar"))) return;
  await telegramAction(async () => {
    const saved = await engine("telegram_save", payload);
    $("telegram-token").value = "";
    renderTelegramStatus(saved);
    $("telegram-feedback").textContent = text("Settings saved. ", "Ajustes guardados. ") + (saved.running
      ? text("Your bot is ready for /new.", "Tu bot está listo para /new.")
      : text("Telegram is paused on this computer.", "Telegram está en pausa en este equipo."));
  });
});
document.addEventListener("keydown", event => {
  if (!document.querySelector("dialog[open]") && (event.metaKey || event.ctrlKey) && event.key === "Enter" && !state.busy) {
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
function renderYouTubeRoute() {
  const info=state.mediaInfo;
  let message=text("YouTube classifies the upload by its dimensions and duration.","YouTube clasifica el archivo según sus dimensiones y duración.");
  if(info?.video){
    const vertical=info.height>=info.width;const mode=$("youtube-mode").value;
    message=mode==="auto" ? (vertical ? text("Shorts · vertical or square. A separate 2:59 copy is made if needed.","Shorts · vertical o cuadrado. Se crea una copia de 2:59 si hace falta.") : text("Regular video · horizontal, full duration.","Video normal · horizontal, duración completa.")) :
      mode==="regular" && vertical && info.duration<=180 ? text("YouTube will classify this file as a Short. Choose a horizontal version for a regular video.","YouTube clasificará este archivo como Short. Elige una versión horizontal para un video normal.") :
      mode==="shorts" && !vertical ? text("Shorts need a vertical or square version; this horizontal file will not be cropped automatically.","Shorts necesita una versión vertical o cuadrada; este archivo horizontal no se recorta automáticamente.") : message;
  }
  $("youtube-route-hint").textContent=message;
}
window.PostForgeMedia.configure({onCover:selectionFeedback,onInfo:info=>{state.mediaInfo=info;renderYouTubeRoute();},onFrame:second=>{
  state.cover=null;$("cover-second").value=String(second);invalidate();renderMedia();
}});
localize();
showPage("home");
loadOptions();
setInterval(() => { if (!state.busy && state.page === "home" && document.visibilityState === "visible" && document.hasFocus()) refreshDashboard(); }, 30000);
window.addEventListener("focus", () => { if (state.page === "home") refreshDashboard(); });
engine("telegram_resume").catch(() => {
  $("telegram-open").textContent = text("Telegram · paused", "Telegram · en pausa");
});

// Native tray mirrors the same window workflows, without creating a second app.
function updateTray() {
  invoke("tray_state", { language:state.language, drafts:state.dashboard?.drafts || 0,
    queued:state.dashboard?.queue || 0, busy:Number(!!state.busy)+Number(!!state.backupBusy)+(state.dashboard?.status_items || []).filter(item=>item.status==="sending").length, update:!!state.updateAvailable }).catch(() => {});
}
async function requirementsOpen(automatic=false) {
  try {
    if(!automatic) {openDialog("requirements-dialog");$("requirements-feedback").textContent=text("Checking installed tools…","Revisando las herramientas instaladas…");}
    const result=await engine("requirements");
    if(automatic && (result.configured || document.querySelector("dialog[open]"))) return;
    if(automatic) openDialog("requirements-dialog");
    $("requirements-list").replaceChildren();
    for(const item of result.items) {
      const row=document.createElement("p");
      const status=item.ready ? "✓ " : item.stopped ? text("Start Docker · ","Inicia Docker · ") : item.optional ? text("Optional · ","Opcional · ") : text("Missing · ","Falta · ");
      const label=document.createElement("strong");label.textContent=status+item.name;
      const link=document.createElement("a");link.textContent=text(" Official download / instructions"," Descarga oficial / instrucciones");link.href=item.url;link.target="_blank";link.rel="noreferrer noopener";link.onclick=event=>{event.preventDefault();invoke("open_requirement",{key:item.key}).catch(error=>{$("requirements-feedback").textContent=friendlyError(error);});};
      row.append(label,link);$("requirements-list").append(row);
    }
    $("requirements-feedback").textContent=result.ready_for_restore ? text("Ready to inspect and restore your backup.","Listo para revisar y restaurar tu respaldo.") : result.ready_for_inspection ? text("You can inspect a backup. Complete the requirements below before restoring.","Puedes revisar un respaldo. Completa los requisitos de abajo antes de restaurar.") : text("Complete Python/OpenSSL setup before opening a backup.","Completa la instalación de Python/OpenSSL antes de abrir un respaldo.");
    if(result.runtime_error) $("requirements-feedback").textContent=friendlyError(result.runtime_error);
    $("requirements-restore").disabled=!result.ready_for_inspection;
  } catch(error) {if(!automatic) $("requirements-feedback").textContent=friendlyError(error);else notice(friendlyError(error));}
}
bind("requirements-open",()=>fromSettings(()=>requirementsOpen()));bind("requirements-retry",()=>requirementsOpen());
bind("requirements-close",()=>$("requirements-dialog").close());
bind("requirements-restore",async()=>{$("requirements-dialog").close();await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));backupOpen("inspect");});
requirementsOpen(true);
let updateCheckTask=null,updateDialogRequest=0;
async function updateResult(components) {
  if(updateCheckTask) {
    const active=updateCheckTask;
    if(!components || active.components) return active.promise;
    try {await active.promise;} catch(_) {}
    return updateResult(components);
  }
  const task={components};updateCheckTask=task;state.updateChecking=true;updateTray();
  task.promise=Promise.resolve().then(()=>engine("updates",{components})).finally(()=>{
    if(updateCheckTask===task){updateCheckTask=null;state.updateChecking=false;updateTray();}
  });
  return task.promise;
}
async function checkUpdates(manual=false) {
  const request=manual ? ++updateDialogRequest : 0;
  if(manual) {
    openDialog("updates-dialog");$("updates-feedback").textContent=text("Checking the app and services…","Buscando actualizaciones de la app y los servicios…");
    $("updates-progress").hidden=false;$("updates-install").hidden=true;$("updates-retry").disabled=true;
  }
  try {
    const result=await updateResult(manual);
    state.updateAvailable=result.available || !!(result.services?.updates_available || result.services?.evolution?.update_available);
    $("updates-open").textContent=state.updateAvailable ? text("Updates Available","Actualizaciones disponibles") : text("Check for Updates","Buscar actualizaciones");
    if(manual && request===updateDialogRequest && $("updates-dialog").open) {
      $("updates-feedback").textContent=text("Desktop installed: ","App instalada: ")+result.installed+"\n"+
        (!result.checked ? text("The check could not finish. Try again.","La consulta no pudo completarse. Vuelve a intentar.") : result.available ? text("Available: ","Disponible: ")+result.latest : text("Your desktop app is up to date.","Tu app está actualizada."))+
        (result.services ? "\n"+text("Services: ","Servicios: ")+((result.services.updates_available || result.services.evolution?.update_available) ? text("updates available.","hay actualizaciones disponibles.") : result.services.check_complete ? text("current.","actualizados.") : text("some checks could not finish.","algunas consultas no pudieron completarse.")) : "");
      $("updates-install").hidden=!result.available;
    }
  } catch(error) {
    if(manual && request===updateDialogRequest && $("updates-dialog").open) $("updates-feedback").textContent=friendlyError(error);
  } finally {
    if(manual && request===updateDialogRequest){$("updates-progress").hidden=true;$("updates-retry").disabled=false;}
    updateTray();
  }
}
async function installAvailableUpdate() {
  if(state.updateInstalling)return;
  state.updateInstalling=true;$("updates-install").disabled=true;$("updates-retry").disabled=true;$("updates-progress").hidden=false;
  $("updates-feedback").textContent=text("Downloading and verifying. PostForge will restart and refresh its services. Wait until publishing has finished before updating.","Descargando y verificando. PostForge se reiniciará y actualizará sus servicios. Espera a que termine cualquier publicación antes de actualizar.");
  try {await invoke("install_update");}
  catch(error){$("updates-feedback").textContent=friendlyError(error);}
  finally {state.updateInstalling=false;$("updates-install").disabled=false;$("updates-retry").disabled=false;$("updates-progress").hidden=true;}
}
bind("updates-retry",()=>checkUpdates(true));bind("updates-install",installAvailableUpdate);
bind("updates-close",()=>{$("updates-dialog").close();++updateDialogRequest;});
$("updates-dialog").addEventListener("cancel",()=>{++updateDialogRequest;});
// Let WebKit finish removing the old modal from the top layer before opening
// another. Otherwise the new dialog can remain absent from the accessibility tree.
async function fromSettings(action) {
  if ($("app-settings").open) {
    $("app-settings").close();
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }
  return action();
}
function backupSetMode(mode) {
  if (state.backupBusy) return;
  $("backup-mode").value=mode;
  backupClearInspection();state.backupPath=null;
  ["backup-path","backup-stage","backup-result","backup-password","backup-confirm"].forEach(id=>{$(id).textContent="";if("value" in $(id)) $(id).value="";});
  $("backup-stage").dataset.error="false";$("backup-progress").hidden=true;$("backup-progress").value=0;
  const exporting=mode==="export";
  $("backup-confirm-row").hidden=!exporting;
  $("backup-pick").textContent=exporting ? text("Choose destination folder","Elegir carpeta de destino") : text("Choose backup file","Elegir archivo de respaldo");
  $("backup-start").textContent=exporting ? text("Create backup","Crear respaldo") : text("Inspect backup","Revisar respaldo");
  $("backup-instructions").textContent=exporting ? text("Choose a folder. The encrypted file includes all retained media, so videos can make it large.","Elige una carpeta. El archivo cifrado incluye todos los archivos conservados; los videos pueden hacerlo grande.") : text("Choose your .pfbackup file and enter its passphrase. Inspecting it does not replace data or stop services. Restore on the destination computer after inspection.","Elige tu archivo .pfbackup e ingresa su contraseña. Revisarlo no reemplaza datos ni detiene servicios. Restáuralo en el equipo de destino después de la revisión.");
  for (const name of ["export","inspect"]) $("backup-"+name+"-mode").setAttribute("aria-pressed",String(name===mode));
}
function backupOpen(mode) {
  if (!state.backupBusy && (mode || !$("backup-instructions").textContent)) backupSetMode(mode || "export");
  openDialog("backup-dialog");
}
function backupClearInspection() {
  state.backupInspection=null;
  ["backup-restore","backup-replace-row","backup-old-host-row"].forEach(id=>$(id).hidden=true);
  $("backup-old-host").checked=false;$("backup-replace").checked=false;
}
function backupClose() {
  $("backup-password").value="";$("backup-confirm").value="";backupClearInspection();$("backup-dialog").close();
}
async function backupRun(action) {
  if (state.backupBusy) return;
  const password=$("backup-password").value;
  if (!state.backupPath || password.length<12) {$("backup-stage").textContent=text("Choose a location and a passphrase of at least 12 characters.","Elige una ubicación y una contraseña de al menos 12 caracteres.");return;}
  if (action==="export" && password!==$("backup-confirm").value) {$("backup-stage").textContent=text("Passphrases do not match.","Las contraseñas no coinciden.");return;}
  const payload={action,password};
  if (action==="export") payload.folder=state.backupPath;else payload.file=state.backupPath;
  if (action==="restore") {
    if (!state.backupInspection || !$("backup-old-host").checked) {$("backup-stage").textContent=text("Confirm that the previous host is stopped.","Confirma que el equipo anterior esté detenido.");return;}
    if (!await modal(text("Restore local data?","¿Restaurar los datos locales?"),text("Local publishing services will stop. Verify restored channels before starting them again. Telegram stays paused.","Los servicios locales de publicación se detendrán. Verifica los canales restaurados antes de iniciarlos otra vez. Telegram queda en pausa."),text("Restore","Restaurar"))) return;
    Object.assign(payload,{confirmed:true,fingerprint:state.backupInspection.fingerprint,replace:$("backup-replace").checked});
  }
  state.backupBusy=true;updateTray();$("backup-progress").hidden=false;$("backup-progress").value=0;
  $("backup-stage").dataset.error="false";$("backup-stage").textContent=text("Starting…","Iniciando…");$("backup-result").textContent="";
  document.querySelectorAll("#backup-dialog input,#backup-dialog select,#backup-pick,#backup-start,#backup-restore,#backup-export-mode,#backup-inspect-mode").forEach(node=>node.disabled=true);
  try {
    const job=await engine("backup_start",payload);
    $("backup-password").value="";$("backup-confirm").value="";
    let result;
    do {
      await new Promise(resolve=>setTimeout(resolve,1000));
      result=await engine("backup_status",{id:job.id});
      $("backup-progress").value=result.percent || 0;
      $("backup-stage").textContent=result.stage ? friendlyError(result.stage) : "";
    } while (result.state==="running");
    if (result.state!=="done") throw new Error(result.error);
    const data=result.result;
    if (action==="inspect") {
      state.backupInspection=data;
      $("backup-result").textContent=text("Verified backup", "Respaldo verificado")+"\n"+data.rows+text(" database rows · "," registros · ")+data.media_files+text(" media files", " archivos")+"\n"+text("Gateway: ","Acceso seguro: ")+(data.gateway ? "✓" : "—")+text(" · Telegram: "," · Telegram: ")+(data.telegram ? "✓" : "—");
      ["backup-restore","backup-replace-row","backup-old-host-row"].forEach(id=>$(id).hidden=false);
      $("backup-stage").textContent=text("Enter the passphrase again when ready to restore.","Ingresa otra vez la contraseña cuando vayas a restaurarlo.");
    } else if (action==="export") {
      $("backup-result").textContent=text("Verified encrypted backup saved:\n", "Respaldo cifrado y verificado guardado:\n")+data.file+"\nSHA-256: "+data.sha256;
      $("backup-stage").textContent=text("Complete", "Completado");
    } else {
      backupClearInspection();$("backup-result").textContent=text("Restored. Services remain stopped. Before starting: verify the public URL, gateway login, channels and schedules. Check WhatsApp linking. Enable Telegram only after the previous host is stopped.","Restaurado. Los servicios siguen detenidos. Antes de iniciarlos, verifica la URL pública, el acceso seguro, los canales y los horarios. Revisa la vinculación de WhatsApp. Activa Telegram solo cuando el equipo anterior esté detenido.")+(data.rollback ? "\n"+text("Rollback backup: ","Respaldo de recuperación: ")+data.rollback : "");
    }
  } catch(error) {$("backup-progress").hidden=true;$("backup-stage").dataset.error="true";$("backup-stage").textContent=friendlyError(error);}
  finally {state.backupBusy=false;updateTray();document.querySelectorAll("#backup-dialog input,#backup-dialog select,#backup-pick,#backup-start,#backup-restore,#backup-export-mode,#backup-inspect-mode").forEach(node=>node.disabled=false);}
}
bind("backup-open",()=>fromSettings(()=>backupOpen("export")));
bind("backup-import-open",()=>fromSettings(()=>backupOpen("inspect")));
bind("backup-export-mode",()=>backupSetMode("export"));
bind("backup-inspect-mode",()=>backupSetMode("inspect"));
bind("updates-open",()=>fromSettings(()=>checkUpdates(true)));
bind("backup-close",backupClose);
$("backup-dialog").addEventListener("cancel",()=>{$("backup-password").value="";$("backup-confirm").value="";backupClearInspection();});
bind("backup-pick",async()=>{
  try {
    const path=await invoke("backup_location",{restore:$("backup-mode").value!=="export"});
    if(path){state.backupPath=path;$("backup-path").textContent=path;backupClearInspection();$("backup-result").textContent="";$("backup-progress").hidden=true;$("backup-stage").dataset.error="false";$("backup-stage").textContent=text("File selected. Enter the passphrase and continue.","Archivo seleccionado. Ingresa la contraseña y continúa.");$("backup-password").focus();}
  } catch(error) {$("backup-stage").dataset.error="true";$("backup-stage").textContent=friendlyError(error);}
});
for (const id of ["backup-password","backup-confirm"]) $(id).addEventListener("keydown",event=>{
  if(event.key!=="Enter" || event.isComposing || state.backupBusy) return;
  event.preventDefault();
  if($("backup-mode").value==="export" && id==="backup-password") $("backup-confirm").focus();
  else backupRun($("backup-mode").value);
});
bind("backup-start",()=>backupRun($("backup-mode").value));
bind("backup-restore",()=>backupRun("restore"));
if (window.__TAURI__?.event) {
  window.__TAURI__.event.listen("postforge-tray-action",async event=>{
    if (document.querySelector("dialog[open]") || state.busy || state.networkBusy) return;
    try {
      const action=event.payload;
      if(action==="home") showPage("home");
      else if(action==="new") $("start-post").click();
      else if(action==="calendar") await invoke("open_calendar");
      else if(action==="wa-review") {showPage("home");await refreshDashboard(true);$("status-card").open=true;$("status-card").scrollIntoView({block:"nearest"});}
      else if(action==="whatsapp") await whatsappSettings();
      else if(action==="telegram") await telegramSettings();
      else if(action==="backup") backupOpen();
      else if(action==="updates") await checkUpdates(true);
      else if(action==="network") await networkOpen();
      else if(action==="settings") openDialog("app-settings");
      else if(action==="help") await help();
      else if(action==="about") await modal("PostForge · "+(state.options?.version || ""),text("Idea → local caption → review → drafts or scheduling\n\nCopyright © 2026 Isaac Mateo Sarzosa Valencia (isaacmateosv) and contributors.\nFree software · GPL-3.0-or-later","Idea → texto local → revisión → borradores o programación\n\nCopyright © 2026 Isaac Mateo Sarzosa Valencia (isaacmateosv) y colaboradores.\nSoftware libre · GPL-3.0-or-later"),text("Done","Listo"));
    } catch(error) {notice(friendlyError(error));}
  });
  window.__TAURI__.event.listen("postforge-tray-refresh",updateTray);
}
checkUpdates();
setInterval(()=>checkUpdates(),6*60*60*1000);

let receiptPage=0,receiptRequest=0;
async function loadReceipts(){
  const request=++receiptRequest;
  $("receipt-rows").textContent=text("Loading receipts","Cargando recibos");
  $("receipt-prev").disabled=true;$("receipt-next").disabled=true;
  try{
    const result=await engine("whatsapp_receipts",{page:receiptPage,period:$("receipt-period").value,kind:$("receipt-kind").value});
    if(request!==receiptRequest || $("wa-receipt-history").hidden)return;
    $("receipt-rows").replaceChildren();
    for(const item of result.items){
      const row=document.createElement("article");row.className="receipt-row";
      const date=document.createElement("strong");date.textContent=new Date(Number(item.at)*1000).toLocaleString(state.language==="es"?"es-EC":"en");
      const caption=document.createElement("p");caption.textContent=item.text || (item.kind==="videoMessage"?"Video":item.kind==="imageMessage"?text("Image","Imagen"):text("Text","Texto"));
      const counters=document.createElement("small");counters.textContent=text("Received: ","Recibido: ")+(item.received ?? "—")+" · "+text("Viewed: ","Visto: ")+(item.viewed ?? "—");
      row.append(date,caption,counters);$("receipt-rows").append(row);
    }
    if(!result.items.length)$("receipt-rows").textContent=text("No receipts match these filters.","No hay recibos con estos filtros.");
    $("receipt-page").textContent=text("Page ","Página ")+(receiptPage+1);
    $("receipt-prev").disabled=receiptPage===0;$("receipt-next").disabled=!result.has_more;
  }catch(error){if(request===receiptRequest)$("receipt-rows").textContent=friendlyError(error);}
}
bind("wa-receipts",()=>{
  const open=$("wa-receipt-history").hidden;$("wa-receipt-history").hidden=!open;
  $("wa-receipts").setAttribute("aria-expanded",String(open));
  $("wa-receipts").textContent=open?text("Hide delivery receipts","Ocultar recibos de entrega"):text("View delivery receipts","Ver recibos de entrega");
  if(open)return loadReceipts();receiptRequest++;
});
bind("receipt-prev",()=>{receiptPage=Math.max(0,receiptPage-1);return loadReceipts();});
bind("receipt-next",()=>{receiptPage++;return loadReceipts();});
for(const id of ["receipt-period","receipt-kind"])$(id).onchange=()=>{receiptPage=0;loadReceipts();};
async function readAudience(){
  try{
    const settings=await engine("whatsapp_audience");$("wa-audience").value=settings.audience;$("wa-recipients").value=settings.recipients;
    $("wa-recipient-field").hidden=settings.audience!=="test";$("wa-audience-result").textContent="";
  }catch(error){$("wa-audience-result").textContent=friendlyError(error);}
}
$("wa-audience").onchange=()=>{$("wa-recipient-field").hidden=$("wa-audience").value!=="test";};
bind("wa-audience-save",async()=>{
  const audience=$("wa-audience").value,recipients=$("wa-recipients").value;
  if(!await modal(text("Apply this audience to new Status plans?","¿Aplicar esta audiencia a los planes nuevos de Estados?"),text("Already queued plans keep their previous audience.","Los planes que ya están en cola conservan su audiencia anterior."),text("Save audience","Guardar audiencia")))return;
  try{await engine("whatsapp_audience_save",{audience,recipients});$("wa-audience-result").textContent=text("Audience saved for new plans.","Audiencia guardada para los planes nuevos.");}
  catch(error){$("wa-audience-result").textContent=friendlyError(error);}
});
async function showConnections(renew=false){
  if(state.connectionsPending)return;state.connectionsPending=true;
  $("connections-refresh").disabled=true;
  $("connection-rows").textContent=renew?text("Checking connections and renewing expired access tokens","Revisando conexiones y renovando tokens de acceso vencidos"):text("Checking connections","Revisando conexiones");
  try{
    const result=await engine("connections",{renew});$("connection-rows").replaceChildren();
    const names={facebook:"Facebook",instagram:"Instagram",threads:"Threads",youtube:"YouTube",tiktok:"TikTok"};
    for(const item of result.items){
      const row=document.createElement("article");row.className="connection-row";
      const label=document.createElement("strong");label.textContent=(names[item.network] || item.network)+" · "+item.name;
      const stateLabel=document.createElement("span");stateLabel.className=item.state==="connected"?"connection-ok":item.state==="renewal"?"connection-renewal":"connection-attention";
      stateLabel.textContent=item.state==="connected"?text("✓ Connected","✓ Conectado"):item.state==="reconnect"?text("Reconnect required","Debes volver a conectar"):item.state==="renewal"?text("↻ Automatic renewal available","↻ Renovación automática disponible"):text("Paused","En pausa");
      row.append(label,stateLabel);
      if(item.state==="renewal"){const hint=document.createElement("small");hint.textContent=text("This is normal between uses: the temporary access token expired. Postiz can request a fresh one with the saved refresh credential. Use Check & renew to verify now; reconnect only if renewal fails.","Es normal entre usos: venció el token de acceso temporal. Postiz puede solicitar otro con la credencial de renovación guardada. Usa Revisar y renovar para comprobarlo ahora; reconecta solo si falla.");row.append(hint);}
      if(item.expires){const expiry=document.createElement("small");expiry.textContent=(item.state==="renewal"?text("Last access token expired: ","El último token de acceso venció: "):item.can_renew?text("Access token renews automatically · current validity: ","El token de acceso se renueva automáticamente · vigencia actual: "):text("Credential valid until: ","Credencial vigente hasta: "))+new Date(/(Z|[+-]\d{2}:\d{2})$/.test(item.expires)?item.expires:item.expires+'Z').toLocaleString(state.language==="es"?"es-EC":"en");row.append(expiry);}
      $("connection-rows").append(row);
    }
    const good=result.items.filter(item=>item.state==="connected").length;
    const renewal=result.items.filter(item=>item.state==="renewal").length;
    const attention=result.items.length-good-renewal;
    $("connections-open").textContent=attention?text("Connections · needs attention","Conexiones · requiere atención"):renewal?text("Connections · refresh on use","Conexiones · renovación al usarse"):text("Connections ","Conexiones ")+good+"/"+result.items.length;
    $("connections-open").classList.toggle("ready",good===result.items.length && good>0);
    $("connection-checked").textContent=text("Checked: ","Revisado: ")+new Date(result.checked_at).toLocaleTimeString(state.language==="es"?"es-EC":"en")+(result.checks_incomplete?text(" · Some renewal checks could not finish. Check local services and try again."," · Algunas comprobaciones no terminaron. Revisa los servicios locales y vuelve a intentar."):"");
  }catch(error){$("connection-rows").textContent=friendlyError(error);}
  finally{state.connectionsPending=false;$("connections-refresh").disabled=false;}
}
bind("connections-open",()=>{openDialog("connections-dialog");return showConnections();});
bind("connections-refresh",()=>showConnections(true));
bind("connections-close",()=>$("connections-dialog").close());

function networkFields(){
  const provider=$("network-provider").value;
  $("network-custom-fields").hidden=provider!=="cloudflare";$("network-ngrok-fields").hidden=provider!=="ngrok";
  $("network-rotate").hidden=provider!=="trycloudflare";
  $("network-hint").textContent=provider==="trycloudflare"?text("Temporary testing endpoint: its hostname changes when the connector restarts. Use Apply to synchronize a changed URL, or Rotate to request another one. No uptime guarantee.","Dirección temporal de pruebas: cambia al reiniciar el conector. Usa Aplicar para sincronizar una URL que cambió o Rotar para pedir otra. No tiene garantía de disponibilidad."):provider==="cloudflare"?text("A named tunnel keeps your domain stable. You can return to TryCloudflare without erasing these settings.","Un túnel con nombre mantiene tu dominio estable. Puedes volver a TryCloudflare sin borrar estos ajustes."):text("Uses your saved ngrok domain and credentials. The account must have bandwidth available.","Usa el dominio y las credenciales guardados de ngrok. La cuenta debe tener ancho de banda disponible.");
}
const copyFeedbackTimers=new WeakMap();
let copyNoticeTimer;
async function copyPublicLink(url,target,label){
  if(!url || state.networkBusy || state.copyPending)return;
  state.copyPending=true;
  $("network-copy-feedback").textContent=text("Checking current link","Comprobando el enlace actual");
  try{
    const current=await engine("network_status",{force:true});
    renderNetworkStatus(current);
    url=networkLinkView.resolve(url);
    await invoke("copy_public_url",{url});
    if(!target.isConnected)target=$("network-current");
    clearTimeout(copyFeedbackTimers.get(target));clearTimeout(copyNoticeTimer);
    target.classList.add("copied");
    if(label)target.textContent=text("✓ Copied","✓ Copiado");
    $("network-copy-feedback").classList.remove("copy-error");
    $("network-copy-feedback").textContent=text("✓ Link copied","✓ Enlace copiado");
    copyFeedbackTimers.set(target,setTimeout(()=>{target.classList.remove("copied");if(label)target.textContent=text("Copy link","Copiar enlace");},2000));
    copyNoticeTimer=setTimeout(()=>{$("network-copy-feedback").textContent="";},2500);
  }catch(error){target.classList.remove("copied");$("network-copy-feedback").classList.add("copy-error");$("network-copy-feedback").textContent=friendlyError(error);}
  finally{state.copyPending=false;}
}
function networkCallbacks(url){
  $("network-callbacks").replaceChildren();
  if(!url)return;
  const names={youtube:"YouTube",facebook:"Facebook",instagram:"Instagram",threads:"Threads",tiktok:"TikTok"};
  for(const name of Object.keys(names)){
    const row=document.createElement("div");row.className="callback-copy-row";
    const label=document.createElement("strong");label.textContent=names[name];
    const value=document.createElement("button");value.type="button";value.className="copyable-url";
    const link=url+"/integrations/social/"+name;value.textContent=link;
    value.title=text("Click to copy","Haz clic para copiar");
    value.setAttribute("aria-label",text("Copy "+names[name]+" callback URL","Copiar URL de redirección de "+names[name]));
    value.onclick=()=>copyPublicLink(link,value,false);row.append(label,value);$("network-callbacks").append(row);
  }
}
bind("network-copy",()=>copyPublicLink($("network-current").value,$("network-copy"),true));
$("network-current").onclick=()=>copyPublicLink($("network-current").value,$("network-current"),false);
$("network-current").onkeydown=event=>{if(event.key==="Enter" || event.key===" "){event.preventDefault();copyPublicLink(event.currentTarget.value,event.currentTarget,false);}};

const networkLinkView=window.PostForgeNetworkLinks.create({field:$("network-current"),copy:$("network-copy"),onURL:networkCallbacks});
function renderNetworkStatus(result){
  if(!networkLinkView.update(result,{busy:!!state.networkBusy,lang:state.language,placeholder:text("Synchronize the detected URL first","Primero sincroniza la URL detectada")}))return false;
  state.network=result;
  if(state.selected>=0) updateVersionControls();
  $("network-detected").hidden=!result.needs_sync;
  $("network-detected").textContent=result.needs_sync?text("Detected address: ","Dirección detectada: ")+result.discovered_url:"";
  $("network-result").textContent=result.needs_sync?text("The connector changed its temporary URL. Synchronize it before opening Postiz or copying links.","El conector cambió su URL temporal. Sincronízala antes de abrir Postiz o copiar enlaces."):result.reachable?text("✓ Public gateway is reachable. Channel sign-ins are checked separately under Connections.","✓ El gateway público está disponible. Revisa las sesiones de los canales en Conexiones."):text("Public access is unavailable. Do not retry publishing until this check succeeds.","El acceso público no está disponible. No vuelvas a publicar hasta que esta comprobación sea exitosa.");
  $("network-apply").textContent=result.needs_sync && $("network-provider").value===result.provider?text("Synchronize current URL","Sincronizar URL actual"):text("Apply configuration","Aplicar configuración");
  return true;
}
async function networkCheck(fill=false){
  $("network-result").textContent=text("Checking public access","Comprobando el acceso público");
  try{const result=await engine("network_status",{force:true});
    if(fill){$("network-provider").value=result.provider;$("network-domain").value=result.custom_domain;$("network-ngrok-domain").value=result.ngrok_domain;$("network-token").value="";networkFields();}
    renderNetworkStatus(result);return result;
  }catch(error){$("network-result").textContent=friendlyError(error);return null;}
}
async function networkOpen(){$("network-copy-feedback").textContent="";$("network-current").title=text("Click to copy link","Haz clic para copiar el enlace");openDialog("network-dialog");await networkCheck(true);}
async function networkApply(rotate=false){
  if(state.networkBusy)return;
  const confirmed=await modal(rotate?text("Rotate the temporary URL?","¿Rotar la URL temporal?"):text("Change public access?","¿Cambiar el acceso público?"),text("Finish or cancel queued posts first. This restarts Postiz and the gateway. Existing media origins are updated; published posts are not reposted. Developer OAuth callbacks must be updated manually.","Primero completa o cancela las publicaciones en cola. Se reiniciarán Postiz y el gateway. Se actualizarán los enlaces de los archivos; lo ya publicado no se reenviará. Debes actualizar manualmente las redirecciones OAuth."),text("Continue","Continuar"));
  if(!confirmed)return;
  state.networkBusy=true;document.querySelectorAll("#network-dialog input,#network-dialog select,#network-dialog button").forEach(node=>node.disabled=true);
  $("network-result").textContent=text("Applying configuration and verifying the gateway. This can take a few minutes. Keep this window open.","Aplicando la configuración y verificando el gateway. Puede tardar unos minutos. Mantén esta ventana abierta.");
  try{await engine("network_apply",{provider:$("network-provider").value,custom_domain:$("network-domain").value,ngrok_domain:$("network-ngrok-domain").value,token:$("network-token").value,rotate,confirm:true});$("network-token").value="";state.options=await engine("options");const checked=await networkCheck(true);if(checked?.reachable && !checked.needs_sync){$("network-result").textContent=reviewNeedsNetworkRefresh(current()?.plan,checked)?text("✓ Public access verified. Your caption is kept. Copy any edits and prepare a fresh review for the new URL before posting.","✓ Acceso público verificado. Se conserva tu texto. Copia cualquier edición y prepara una revisión nueva para la URL actual antes de publicar."):text("✓ Public access verified. Sign in at the new address and update OAuth callbacks before reconnecting channels.","✓ Acceso público verificado. Inicia sesión en la nueva dirección y actualiza las redirecciones OAuth antes de reconectar canales.");networkCallbacks(checked.url);}}
  catch(error){$("network-result").textContent=friendlyError(error);}
  finally{state.networkBusy=false;document.querySelectorAll("#network-dialog input,#network-dialog select,#network-dialog button").forEach(node=>node.disabled=false);if(state.network)networkLinkView.update(state.network,{busy:false,lang:state.language,placeholder:text("Synchronize the detected URL first","Primero sincroniza la URL detectada")});}
}
bind("network-open",()=>fromSettings(networkOpen));bind("network-check",()=>networkCheck());bind("network-apply",()=>networkApply());bind("network-rotate",()=>networkApply(true));bind("network-close",()=>$("network-dialog").close());$("network-provider").onchange=networkFields;
$("network-dialog").addEventListener("cancel",event=>{if(state.networkBusy)event.preventDefault();else $("network-token").value="";});

async function checkPublicAccess(){
  if(state.networkBusy || state.publicCheckPending)return;
  state.publicCheckPending=true;
  try{const result=await engine("network_status");if(!renderNetworkStatus(result))return;const warning=$("public-access-warning");const stale=reviewNeedsNetworkRefresh(current()?.plan,result);warning.hidden=result.reachable && !result.needs_sync && !stale;warning.textContent=stale && !result.needs_sync?text("Public URL updated · your caption is kept; prepare a fresh review before posting","URL pública actualizada · se conserva tu texto; prepara una revisión nueva antes de publicar"):result.needs_sync?text("Public URL changed · open network settings to synchronize","La URL pública cambió · abre los ajustes de red para sincronizar"):text("Public access could not be verified · check network settings before publishing","No se pudo verificar el acceso público · revisa los ajustes de red antes de publicar");}
  catch(error){$("public-access-warning").hidden=false;$("public-access-warning").textContent=text("Public access could not be checked · open network settings","No se pudo comprobar el acceso público · abre los ajustes de red");}
  finally{state.publicCheckPending=false;}
}
bind("public-access-warning",networkOpen);

window.addEventListener("focus",()=>{if($("network-dialog").open && !state.networkBusy)networkCheck();});
setInterval(()=>{if($("network-dialog").open && document.visibilityState==="visible" && document.hasFocus() && !state.networkBusy && !state.copyPending)networkCheck();},15000);

async function rescheduleReview() {
  const post_at = $("review-post-at").value;
  let saved = false;
  await work(text("Updating the reviewed time", "Actualizando la hora del plan"), async () => {
    // Every caption iteration keeps its text and receives the same reviewed delivery time.
    const updated = [];
    for (const version of state.history) updated.push(await engine("revise", {review_id:version.review_id, post_at}));
    state.history = updated;
    $("post-at").value = post_at;
    renderReview();
    saved = true;
  });
  return saved;
}
bind("review-save-time", rescheduleReview);
bind("review-asap", () => {
  $("review-post-at").value = new Intl.DateTimeFormat("sv-SE", {timeZone:state.options.timezone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(Date.now()+10*60000)).replace(" ","T");
  rescheduleReview();
});

bind("receipt-stay",stopReceiptReturn);
bind("receipt-dashboard",()=>showPage("home"));
$("receipt").addEventListener("pointerdown",stopReceiptReturn);
$("receipt").addEventListener("keydown",stopReceiptReturn);
// Suspend the countdown's interval when the window is away; no background timer wakeups.
window.addEventListener("blur",()=>receiptReturn.pause());
window.addEventListener("focus",()=>{if(state.page==="receipt")receiptReturn.resume();});
document.addEventListener("visibilitychange",()=>{if(document.hidden)receiptReturn.pause();else if(state.page==="receipt" && document.hasFocus())receiptReturn.resume();});
