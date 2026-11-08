# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Owner-only guided composer with versioned buttons and durable submission guards."""
import json
from pathlib import Path
import secrets
import time

TTL = 24 * 3600


class Conversation:
    def __init__(self, path, owner, es, actions, send, save):
        self.path = Path(path)
        self.owner = owner
        self.es = es
        self.actions = actions
        self.send = send
        self.write = save
        self.state = {}
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
        if self.state.get("owner") != owner:
            self.state = {}
        if self.state.get("stage") == "submitting":
            self.state["stage"] = "needs_review"
            self.persist()

    def t(self, english, spanish):
        return spanish if self.es else english

    def persist(self):
        self.state["owner"] = self.owner
        self.write(self.path, self.state)

    def emit(self, message, rows):
        self.state["version"] = self.state.get("version", 0) + 1
        self.persist()
        prefix = self.state.get("id", "home") + ":" + str(self.state["version"]) + ":"
        markup = {"inline_keyboard": [
            [{"text": label, "callback_data": prefix + action} for label, action in row] for row in rows]}
        chunks = [message[i:i + 3900] for i in range(0, len(message), 3900)] or [""]
        for index, chunk in enumerate(chunks):
            extra = {"reply_markup": markup} if index == len(chunks) - 1 else {}
            self.send("sendMessage", chat_id=self.owner, text=chunk, **extra)

    def home(self):
        rows = [[(self.t("New post / announcement", "Nueva publicación / anuncio"), "new")],
                [(self.t("Service status", "Estado de los servicios"), "status")]]
        if self.state.get("stage") in ("ready", "review", "assets", "destinations", "time", "formats"):
            rows.insert(0, [(self.t("Resume current plan", "Retomar el plan actual"), "resume")])
        note = self.t("PostForge · What would you like to do?", "PostForge · ¿Qué quieres hacer?")
        if self.state.get("stage") == "needs_review":
            note += self.t("\nA submission was interrupted. Review Postiz before starting another batch.",
                           "\nSe interrumpió un envío. Revisa Postiz antes de preparar otro lote.")
        self.emit(note, rows)

    def start(self):
        self.actions.discard(self.state.get("data") or {})
        last_update = self.state.get("last_update", -1)
        self.state = {"owner": self.owner, "id": secrets.token_hex(4), "version": 0,
                      "created_at": time.time(), "stage": "mode", "last_update": last_update,
                      "data": {"media": [], "language": "es" if self.es else "en", "placement": "both"},
                      "history": [], "selected": -1}
        self.emit(self.t("1 · How should we prepare the caption?", "1 · ¿Cómo preparamos el texto?"), [
            [(self.t("Write from my idea", "Redactar a partir de mi idea"), "mode_idea")],
            [(self.t("Use my exact words", "Usar mis palabras exactas"), "mode_exact")],
            [(self.t("Cancel", "Cancelar"), "cancel")]])

    def assets(self):
        self.state["stage"] = "assets"
        count = len(self.state["data"]["media"])
        self.emit(self.t(f"2 · Media attached: {count}. You can add media or make a text-only announcement.",
                         f"2 · Archivos adjuntos: {count}. Puedes añadir archivos o crear un anuncio solo de texto."), [
            [(self.t("Add photo / video", "Añadir foto / video"), "add_media")],
            [(self.t("Continue with these files", "Continuar con estos archivos"), "assets_next")] if count else
            [(self.t("Text-only announcement", "Anuncio solo de texto"), "text_only")],
            [(self.t("Cancel", "Cancelar"), "cancel")]])

    def destinations(self):
        self.state["stage"] = "destinations"
        data = self.state["data"]
        options = self.state.get("options") or self.actions.options()
        self.state["options"] = options
        available = [item for item in options["networks"] if data["media"] or item["text"]]
        self.state["available"] = available
        selected = set(data.get("networks", []))
        rows = [[(("✓ " if item["id"] in selected else "") + item["name"], "dest_" + item["id"])]
                for item in available]
        rows += [[(self.t("Select all supported", "Elegir todos los compatibles"), "dest_all")],
                 [(self.t("Continue", "Continuar"), "dest_next")],
                 [(self.t("Cancel", "Cancelar"), "cancel")]]
        note = self.t("3 · Choose destinations.", "3 · Elige los destinos.")
        if not data["media"]:
            note += self.t("\nText uses Facebook posts, Threads posts or WhatsApp Status. Other placements require media.",
                           "\nEl texto usa publicaciones de Facebook, Threads o un Estado de WhatsApp. Los otros formatos requieren archivos.")
        self.emit(note, rows)

    def formats(self):
        self.state["stage"] = "formats"
        self.emit(self.t("Choose post formats where supported.", "Elige los formatos compatibles."), [
            [(self.t("Posts and stories", "Publicaciones e historias"), "format_both")],
            [(self.t("Posts only", "Solo publicaciones"), "format_feed"),
             (self.t("Stories only", "Solo historias"), "format_story")]])

    def times(self):
        self.state["stage"] = "time"
        self.emit(self.t("4 · Choose a future time in your configured local timezone.",
                         "4 · Elige una hora futura en tu zona horaria configurada."), [
            [(self.t("Today 19:00", "Hoy 19:00"), "time_today"),
             (self.t("Tomorrow 09:00", "Mañana 09:00"), "time_tomorrow")],
            [(self.t("Enter date and time", "Ingresar fecha y hora"), "time_custom")],
            [(self.t("Cancel", "Cancelar"), "cancel")]])

    def ready(self):
        self.state["stage"] = "ready"
        data = self.state["data"]
        self.emit(self.t("Ready to bake your plan.", "Todo listo para hornear el plan.") +
                  "\n" + ", ".join(data["networks"]) + "\n" + data["post_at"] +
                  "\n" + self.t("Mode: ", "Modo: ") + data["mode"] +
                  "\n" + self.t("Cover: ", "Portada: ") + str(data.get("cover_second") or data.get("cover_image") or
                                                              self.t("platform default", "predeterminada")) +
                  "\n" + self.t("Final hashtag: ", "Etiqueta final: ") + data.get("final_tag", ""), [
            [(self.t("👨‍🍳 Bake and review", "👨‍🍳 Hornea y revisa"), "bake")],
            [(self.t("Cover frame…", "Fotograma de portada…"), "cover_frame"),
             (self.t("Cover image…", "Imagen de portada…"), "cover_image")],
            [(self.t("Business hashtag…", "Etiqueta del negocio…"), "tag")],
            [(self.t("Change delivery", "Cambiar destinos"), "delivery"),
             (self.t("Cancel", "Cancelar"), "cancel")]])

    def current(self):
        return self.state["history"][self.state["selected"]]

    def remember(self, result):
        history = self.state["history"]
        history.append(result)
        if len(history) > 8:
            history.pop(0)
        self.state["selected"] = len(history) - 1

    def review(self):
        self.state["stage"] = "review"
        current = self.current()
        plan = current["plan"]
        targets = [item["network"] + " · " + item["placement"] for item in plan["targets"]]
        body = (self.t("Plan ready to review", "Plan listo para revisar") + "\n" + plan["when_local"] +
                "\n" + "\n".join(targets) + "\n\n" + plan["caption"])
        if plan.get("youtube_title"):
            body += "\n\nYouTube: " + plan["youtube_title"]
        if plan.get("threads_caption"):
            body += "\n\nThreads: " + plan["threads_caption"]
        warnings = plan.get("warnings", []) + plan.get("notes", [])
        if warnings:
            body += "\n\n⚠ " + "\n".join(warnings)
        body += "\n\n" + self.t("Caption ", "Texto ") + str(self.state["selected"] + 1) + "/" + str(len(self.state["history"]))
        rows = [[(self.t("Try another caption", "Probar otro texto"), "another"),
                 (self.t("Edit caption", "Editar texto"), "edit")]]
        navigation = []
        if self.state["selected"] > 0:
            navigation.append(("‹", "previous"))
        if self.state["selected"] + 1 < len(self.state["history"]):
            navigation.append(("›", "next"))
        if navigation:
            rows.append(navigation)
        rows.append([(self.t("Create Drafts", "Crear borradores"), "create")])
        if plan.get("direct_schedule_available"):
            rows.append([(self.t("Schedule directly…", "Programar directamente…"), "schedule")])
        rows.append([(self.t("Change delivery", "Cambiar destinos"), "delivery"),
                     (self.t("Cancel", "Cancelar"), "cancel")])
        self.emit(body, rows)

    def handle(self, update):
        message = update.get("message")
        callback = update.get("callback_query")
        container = message or (callback or {}).get("message") or {}
        actor = (message or callback or {}).get("from") or {}
        chat = container.get("chat") or {}
        if chat.get("type") != "private" or chat.get("id") != self.owner or actor.get("id") != self.owner:
            return False
        update_id = update.get("update_id", -1)
        if update_id >= 0 and update_id <= self.state.get("last_update", -1):
            return True
        if update_id >= 0:
            self.state["last_update"] = update_id
            self.persist()
        if message:
            value = message.get("text", "").strip()
            if value in ("/start", "/help"):
                self.home()
            elif value == "/new":
                self.start()
            elif value == "/cancel":
                self.cancel()
            elif value == "/status":
                self.actions.status()
            else:
                self.accept_message(message)
            return True
        self.send("answerCallbackQuery", callback_query_id=callback["id"])
        expected = self.state.get("id", "home") + ":" + str(self.state.get("version", 0)) + ":"
        value = callback.get("data", "")
        if not value.startswith(expected) or (self.state.get("created_at") and time.time() > self.state["created_at"] + TTL):
            self.send("sendMessage", chat_id=self.owner, text=self.t(
                "This button is outdated. Use /new for a fresh plan.",
                "Este botón ya no está vigente. Usa /new para preparar otro plan."))
            return True
        try:
            self.accept_button(value[len(expected):])
        except Exception:
            self.send("sendMessage", chat_id=self.owner, text=self.t(
                "The action could not finish. Check local services and the calendar before submitting again.",
                "No se pudo completar la acción. Revisa los servicios locales y el calendario antes de volver a enviar."))
            self.persist()
        return True

    def cancel(self):
        if self.state.get("stage") == "submitting":
            return
        self.actions.discard(self.state.get("data") or {})
        self.state = {"owner": self.owner, "last_update": self.state.get("last_update", -1)}
        self.home()

    def accept_message(self, message):
        stage = self.state.get("stage")
        if not stage:
            self.home()
            return
        value = message.get("text", "").strip()
        data = self.state["data"]
        try:
            has_file = any(key in message for key in ("photo", "video", "document"))
            if has_file and stage in ("content", "wait_media", "wait_cover"):
                path = self.actions.download(message)
                if stage == "wait_cover":
                    if not self.actions.is_image(path):
                        self.actions.discard({"media": [path]})
                        raise ValueError("Image required")
                    data["cover_image"], data["cover_second"] = path, None
                    self.ready()
                    return
                if len(data["media"]) >= 10:
                    self.actions.discard({"media": [path]})
                    raise ValueError("Ten files maximum")
                data["media"].append(path)
                if stage == "content" and not message.get("caption"):
                    self.emit(self.t("Now send your idea or exact caption as text.",
                                     "Ahora envía tu idea o el texto exacto."), [[(self.t("Cancel", "Cancelar"), "cancel")]])
                    return
                if stage == "content":
                    data["body"] = message["caption"]
                self.assets()
                return
            if stage == "content" and value:
                data["body"] = value
                self.assets()
            elif stage == "wait_time" and value:
                data["post_at"] = self.actions.time_value(value)
                self.ready()
            elif stage == "wait_frame" and value:
                seconds = float(value.replace(",", "."))
                if not 0 <= seconds < 86400:
                    raise ValueError("Invalid frame")
                data["cover_second"], data["cover_image"] = seconds, None
                self.ready()
            elif stage == "wait_tag":
                data["final_tag"] = self.actions.tag("" if value == "-" else value)
                self.ready()
            elif stage == "edit" and value:
                self.remember(self.actions.revise(self.current()["review_id"], value))
                self.review()
            else:
                self.emit(self.t("Use the current buttons or /new.", "Usa los botones actuales o /new."),
                          [[(self.t("New post", "Nueva publicación"), "new")]])
        except Exception:
            note = self.t(
                "That input could not be used. Check the format and local services. Bot downloads support up to 20 MB; use the desktop app for larger files.",
                "No se pudo usar ese dato. Revisa el formato y los servicios locales. El bot descarga hasta 20 MB por archivo; usa la app de escritorio para archivos más grandes.")
            self.send("sendMessage", chat_id=self.owner, text=note)

    def accept_button(self, action):
        stage = self.state.get("stage")
        data = self.state.get("data", {})
        if action == "resume":
            renderers = {"ready": self.ready, "review": self.review, "assets": self.assets,
                         "destinations": self.destinations, "time": self.times, "formats": self.formats}
            if stage in renderers:
                renderers[stage]()
        elif action == "new":
            self.start()
        elif action == "status":
            self.actions.status()
        elif action == "cancel":
            self.cancel()
        elif action in ("mode_idea", "mode_exact") and stage == "mode":
            data["mode"] = action.removeprefix("mode_")
            self.state["stage"] = "content"
            self.emit(self.t("Send your idea or finished caption. You can attach a photo/video with it.",
                             "Envía tu idea o el texto terminado. Puedes adjuntar una foto o un video."),
                      [[(self.t("Cancel", "Cancelar"), "cancel")]])
        elif action == "add_media" and stage == "assets":
            self.state["stage"] = "wait_media"
            self.emit(self.t("Send a photo or video, up to 20 MB per file.",
                             "Envía una foto o un video de hasta 20 MB por archivo."),
                      [[(self.t("Cancel", "Cancelar"), "cancel")]])
        elif action in ("assets_next", "text_only") and stage == "assets":
            data["text_confirmed"] = not data["media"]
            self.state["options"] = self.actions.options()
            data["final_tag"] = self.state["options"]["final_tag"]
            self.destinations()
        elif action.startswith("dest_") and stage == "destinations":
            if action == "dest_all":
                data["networks"] = [item["id"] for item in self.state["available"]]
            elif action == "dest_next":
                if not data.get("networks"):
                    return self.destinations()
                if data["media"]:
                    self.formats()
                else:
                    data["placement"] = "both"
                    self.times()
                return
            else:
                network = action.removeprefix("dest_")
                if network not in {item["id"] for item in self.state["available"]}:
                    return
                chosen = data.setdefault("networks", [])
                if network in chosen:
                    chosen.remove(network)
                else:
                    chosen.append(network)
            self.destinations()
        elif action.startswith("format_") and stage == "formats":
            placement = action.removeprefix("format_")
            if placement not in ("both", "feed", "story"):
                return
            data["placement"] = placement
            self.times()
        elif action.startswith("time_") and stage == "time":
            if action == "time_custom":
                self.state["stage"] = "wait_time"
                self.emit(self.t("Send YYYY-MM-DD HH:MM in your configured local timezone.",
                                 "Envía AAAA-MM-DD HH:MM en tu zona horaria configurada."),
                          [[(self.t("Cancel", "Cancelar"), "cancel")]])
            else:
                data["post_at"] = self.actions.time_value(action.removeprefix("time_"))
                self.ready()
        elif action in ("cover_frame", "cover_image", "tag") and stage == "ready":
            if action.startswith("cover_") and not self.actions.has_video(data["media"]):
                self.ready()
                return
            self.state["stage"] = {"cover_frame": "wait_frame", "cover_image": "wait_cover", "tag": "wait_tag"}[action]
            prompts = {
                "cover_frame": self.t("Send the cover second, for example 12.5.", "Envía el segundo de portada, por ejemplo 12,5."),
                "cover_image": self.t("Send one cover image.", "Envía una imagen de portada."),
                "tag": self.t("Send a hashtag, or - to omit it.", "Envía una etiqueta o - para omitirla.")
            }
            self.emit(prompts[action], [[(self.t("Cancel", "Cancelar"), "cancel")]])
        elif action == "delivery" and stage in ("ready", "review"):
            self.destinations()
        elif action == "bake" and stage == "ready":
            self.send("sendMessage", chat_id=self.owner, text=self.t("👨‍🍳 Baking your plan…", "👨‍🍳 Horneando tu plan…"))
            result = self.actions.preview(data)
            self.state["history"] = []
            self.remember(result)
            self.review()
        elif action in ("previous", "next") and stage == "review":
            index = self.state["selected"] + (-1 if action == "previous" else 1)
            if 0 <= index < len(self.state["history"]):
                self.state["selected"] = index
            self.review()
        elif action == "another" and stage == "review":
            self.remember(self.actions.revise(self.current()["review_id"]))
            self.review()
        elif action == "edit" and stage == "review":
            self.state["stage"] = "edit"
            self.emit(self.t("Send the complete replacement caption.", "Envía el texto completo corregido."),
                      [[(self.t("Back to review", "Volver a la revisión"), "review_back")]])
        elif action == "review_back" and stage == "edit":
            self.review()
        elif action in ("create", "schedule") and stage == "review":
            if action == "schedule" and not self.current()["plan"].get("direct_schedule_available"):
                return
            self.state["stage"], self.state["submit_mode"] = "confirm", "draft" if action == "create" else "schedule"
            self.emit(self.t("Confirm the reviewed plan. Direct scheduling publishes automatically at its time. WhatsApp Status still needs separate approval.",
                             "Confirma el plan revisado. La programación directa publica automáticamente a esa hora. El Estado de WhatsApp requiere aprobación aparte."), [
                [(self.t("Confirm", "Confirmar"), "confirm_submit"), (self.t("Back", "Volver"), "confirm_back")]])
        elif action == "confirm_back" and stage == "confirm":
            self.review()
        elif action == "confirm_submit" and stage == "confirm":
            self.state["stage"] = "submitting"
            self.persist()
            try:
                receipt = self.actions.submit(self.current()["review_id"], self.state["submit_mode"])
            except Exception:
                self.state["stage"] = "needs_review"
                self.persist()
                raise
            self.state["receipt"] = receipt
            self.state["stage"] = "done"
            self.actions.discard(data)
            rows = [[(self.t("New post", "Nueva publicación"), "new")]]
            if receipt.get("whatsapp_pending_id"):
                rows.insert(0, [(self.t("Review WhatsApp approval…", "Revisar aprobación de WhatsApp…"), "status_approval")])
            self.emit(self.t("Plan submitted. Review the Postiz calendar for the social entries.",
                             "Plan enviado. Revisa los elementos de redes en el calendario de Postiz."), rows)
        elif action == "status_approval" and stage == "done":
            self.state["stage"] = "confirm_status"
            self.emit(self.t("Send this WhatsApp Status to the configured audience at its scheduled time?",
                             "¿Enviar este Estado de WhatsApp al público configurado a la hora programada?"),
                      [[(self.t("Approve Status", "Aprobar Estado"), "confirm_status")],
                       [(self.t("Cancel approval", "Cancelar aprobación"), "cancel")]])
        elif action == "confirm_status" and stage == "confirm_status":
            self.actions.approve_status(self.state["receipt"]["whatsapp_pending_id"])
            self.state["stage"] = "status_approved"
            self.emit(self.t("Status approved. The local agent will dispatch it when due.",
                             "Estado aprobado. El agente local lo enviará cuando corresponda."),
                      [[(self.t("New post", "Nueva publicación"), "new")]])
