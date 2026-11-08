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
const labels = {
  subtitle: ["Compose, choose delivery, then review", "Redacta, elige destinos y revisa"],
  help: ["Help", "Ayuda"], reconnect: ["Refresh status", "Actualizar estado"], workspace: ["Locate recovered installation…", "Localizar instalación recuperada…"],
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
  cleanup: ["Remove posts…", "Eliminar publicaciones…"]
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
  $("telegram-owners").setAttribute("aria-label", text("Detected private accounts", "Cuentas privadas encontradas"));
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
  state.page = page;
  $("steps").hidden = page === "home";
  if (page === "home") refreshDashboard(true);
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

async function work(message, action, baking=false) {
  if (state.busy) return;
  state.busy = true;
  renderSteps();
  const controls = document.querySelectorAll("main button, main input, main textarea, main select, header button, header select, footer button, #telegram-settings button, #telegram-settings input, #telegram-settings select");
  controls.forEach(node => node.disabled = true);
  notice(message, true);
  $("baking-visual").hidden = !baking;
  try {
    await action();
    notice();
  } catch (error) {
    notice(text("Please review this before continuing.\n", "Revisa esto antes de continuar.\n") + friendlyError(error));
  } finally {
    $("baking-visual").hidden = true;
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
    const placement = target.placement === "story" ? text(" · Story", " · Historia")
      : target.placement === "feed" ? text(" · Post", " · Publicación") : "";
    item.textContent = network + (target.network === "whatsapp" ? "" : " · " + target.channel + placement)
      + (target.parts > 1 ? text(" · ", " · ") + target.parts + text(" segments / drafts", " segmentos / borradores") : "");
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
  main.className = "copy-primary";
  if (plan.youtube_title) {
    const section = document.createElement("div"); section.className = "platform-copy";
    const heading = document.createElement("h3"); heading.textContent = text("YouTube title", "Título de YouTube");
    const value = document.createElement("p"); value.textContent = plan.youtube_title;
    const button = document.createElement("button"); button.textContent = text("Edit title…", "Editar título…");
    button.onclick = editYoutubeTitle;
    section.append(heading,value,button); $("copy").append(section);
  }
  if (plan.threads_caption) {
    const details = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = text("Threads adaptation · same idea, shorter", "Adaptación para Threads · misma idea, más corta");
    const value = document.createElement("p"); value.textContent = plan.threads_caption;
    details.append(summary,value); $("copy").append(details);
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
  }, true);
}

async function revise(edited) {
  const id = current()?.review_id;
  if (!id) return;
  await work(text("Preparing another caption…", "Preparando otro texto…"), async () => {
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
    refreshDashboard(true);
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
  await work(text("Reading unpublished work…", "Leyendo los elementos pendientes…"), async () => {
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
    ["Postiz", data.postiz_online, data.available, () => invoke("open_calendar")],
    ["WhatsApp", data.whatsapp?.connected, data.whatsapp?.connected, whatsappSettings],
    ["Telegram", data.telegram?.running, data.telegram?.configured, telegramSettings]
  ]) {
    const button = document.createElement("span");
    button.className = "health-pill " + (ready ? "ready" : "waiting");
    button.textContent = (ready ? "✓ " : "○ ") + label + " · " + (ready ? text("Connected", "Conectado")
      : configured ? text("Paused", "En pausa") : text("Set up", "Configurar"));
    $("health").append(button);
  }
  const statusItems = data.status_items || [];
  $("status-card").hidden = statusItems.length === 0;
  $("dashboard-status").replaceChildren();
  for (const item of statusItems) {
    const row = document.createElement("article"); row.className = "post-row";
    const content = document.createElement("div");
    const title = document.createElement("strong"); title.textContent = item.caption.slice(0,120) || text("Media Status", "Estado con archivos");
    const note = document.createElement("p"); note.textContent = momentLabel(item.when) + " · " + (item.status === "needs_review"
      ? text("Delivery needs review · automatic retry is held", "Revisa la entrega · el reintento automático está detenido")
      : item.approved ? text("Approved · waiting for delivery", "Aprobado · esperando el envío") : text("Awaiting your approval", "Espera tu aprobación"));
    content.append(title,note); row.append(content);
    if (item.status === "pending" && !item.approved) {
      const approve = document.createElement("button"); approve.textContent = text("Review Status…", "Revisar Estado…");
      approve.onclick = async () => {
        const note = item.caption + "\n\n" + momentLabel(item.when) + "\n" + item.media.join("\n") + "\n" + text("Text background: ", "Fondo del texto: ") + item.background
          + text("\nIf the time has passed, approval sends it now.", "\nSi la hora ya pasó, aprobarlo lo enviará ahora.");
        if (!await modal(text("Approve this WhatsApp Status?", "¿Aprobar este Estado de WhatsApp?"), note, text("Approve Status", "Aprobar Estado"))) return;
        await work(text("Approving Status…", "Aprobando Estado…"), async () => { await engine("approve_status",{id:item.id}); await refreshDashboard(true); });
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
  try { state.dashboard = await engine("dashboard"); state.dashboardAt = Date.now(); renderDashboard(); }
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
    $("wa-state").textContent = result.connected ? text("✓ WhatsApp connected", "✓ WhatsApp conectado") : text("○ Waiting for the phone…", "○ Esperando al teléfono…");
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
  $("wa-state").textContent = text("Checking connection…", "Comprobando conexión…");
  $("wa-refresh").hidden = false;
  $("whatsapp-settings").showModal();
  await waState();
  if ($("whatsapp-settings").open && !$("wa-refresh").hidden) waTimer = setInterval(waState, 4000);
}

async function editYoutubeTitle() {
  const input = document.createElement("textarea"); input.rows = 3; input.maxLength = 100;
  input.value = current().plan.youtube_title || "";
  input.setAttribute("aria-label", text("YouTube title · up to 100 characters", "Título de YouTube · hasta 100 caracteres"));
  if (!await modal(text("Edit YouTube title · 100 characters", "Editar título de YouTube · 100 caracteres"), input, text("Save title", "Guardar título"))) return;
  await work(text("Saving title…", "Guardando título…"), async () => {
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
  $("telegram-settings").showModal();
  $("telegram-settings").querySelector(".telegram-body").scrollTop = 0;
}

async function telegramAction(action) {
  const buttons = $("telegram-settings").querySelectorAll("button, input, select");
  buttons.forEach(node => node.disabled = true);
  try { await action(); }
  catch (error) { $("telegram-feedback").textContent = friendlyError(error); }
  finally { buttons.forEach(node => node.disabled = false); }
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
  updateNetworkOptions();
});
bind("go-home", () => showPage("home"));
bind("start-post", async () => { if (state.receipt) await reset(true); else showPage("compose"); });
bind("home-calendar", () => invoke("open_calendar"));
bind("show-drafts", () => { state.dashFilter = state.dashFilter === "DRAFT" ? null : "DRAFT"; renderDashboard(); });
bind("show-queue", () => { state.dashFilter = state.dashFilter === "QUEUE" ? null : "QUEUE"; renderDashboard(); });
bind("asap", soon);
bind("settings-open", () => $("app-settings").showModal());
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
bind("cleanup", cleanup);
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
    placeholder.textContent = text("Choose your account…", "Elige tu cuenta…");
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
localize();
showPage("home");
loadOptions();
setInterval(() => { if (!state.busy && state.page === "home" && document.visibilityState === "visible" && document.hasFocus()) refreshDashboard(); }, 30000);
window.addEventListener("focus", () => { if (state.page === "home") refreshDashboard(); });
engine("telegram_resume").catch(() => {
  $("telegram-open").textContent = text("Telegram · paused", "Telegram · en pausa");
});
