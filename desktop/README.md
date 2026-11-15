# PostForge Desktop · Rust/Tauri release candidate

The current desktop client uses Rust and the operating system webview with embedded HTML/CSS/JavaScript. It does not ship Electron. The bundled Python runtime code handles planning, media, backups and service integration; host Python and third-party tools are still required. Run only this client during v2 testing. Swift remains historical source.

## Daily workflow

Dashboard shows saved drafts, scheduled work, upcoming publication and connection indicators. Refreshes are gated to visible/focused use. New post has three steps:

1. **Compose:** choose generated or exact caption and optional media previews.
2. **Delivery:** choose supported destinations, formats, local time, cover and optional business hashtag.
3. **Review:** edit/browse caption versions, edit/regenerate the YouTube title independently, adjust time, then create drafts or confirm direct scheduling.

Caption-only revisions preserve the delivery plan. Apply or cancel an open edit before submission. Covers and media changes require a fresh review. Direct scheduling approves selected WhatsApp Status; draft creation leaves its separate approval. TikTok Inbox Upload remains a manual finish in TikTok, with caption-copy handoff. The current [English](../docs/help/quick-en.md) and [Ecuadorian Spanish](../docs/help/quick-es.md) guides are bundled offline.

## Settings and tray

Settings expose requirements, services, public link/access, updates, encrypted backup/restore, portable history/caption defaults and unpublished-work cleanup. WhatsApp QR/audience and Telegram setup are accessible from the header and tray. Advanced installation recovery is separate from selecting a `.pfbackup`.

The native tray groups Publishing, Connections, Local Services and App & Support. WhatsApp Plans & Receipts is at the top level. About precedes Quit. A task count/update marker accompanies the standard monochrome Mac icon. Quit leaves services running; closing hides the window. Cmd/Ctrl+N reopens New Post while PostForge is active; a second launch reuses the same app instance.

Service stop requires a verified empty scheduled queue and no approved waiting Status. Shared Docker/Ollama tools are preserved. Start checks configured APIs/scheduler and does not pull an Ollama model. The old Swift automatic sleep/wake and dedicated Siri integrations are not ported. Keep the machine awake for scheduled delivery; use an OS Open App shortcut if desired.

## Installation and migration

Current artifacts: macOS ARM64 `.pkg` and ZIP, Linux x86_64 ZIP, Windows x86_64 ZIP. Mac packages are ad-hoc signed, not notarized. Native CI builds all three platforms; physical Windows/Linux acceptance remains separate. The client creates private runtime storage and does not ask for a project folder in normal use. A fresh business deployment still needs private configuration; see [SETUP](../SETUP.md).

Requirements: Python 3.9+ (`py -3` on Windows), Docker/Compose, OpenSSL, FFmpeg/ffprobe and optional Ollama/model. Windows Python needs `tzdata`; Linux needs Tauri's WebKitGTK dependencies. Runtime code is bundled; binaries, private data and models are not all bundled into a self-contained installer.

Restore an encrypted backup through Backup & Move. Inspection is read-only; restore requires the passphrase again and old-host-stopped confirmation. Reopening finds detached live work and Resume progress reconnects safely. Restore leaves publishing and Telegram paused for destination verification. Configuration includes optional bot identity, heartbeat, gateway state, domain profile and caption defaults. Never run both old and new Telegram receivers.

## Build and validate

```text
cargo build --release --locked --manifest-path desktop/Cargo.toml
python3 desktop/package.py --no-build
node --test desktop/test/*.test.cjs
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Use Rust stable and the [official Tauri prerequisites](https://v2.tauri.app/start/prerequisites/). Artifacts/checksums appear in desktop/dist. Packaging uses a tracked public-file allowlist: add new public runtime modules to Git before packaging. Python must not write bytecode into signed bundle resources. Use `POSTFORGE_PROJECT_DIR` only for explicit isolated/developer deployments; it overrides saved recovery settings.

macOS updates verify and replace the bundle, install matching runtime code and refresh configured services. Backup/publishing/maintenance leases prevent conflicting work. Windows/Linux stage verified files for manual replacement. Upstream Evolution/container versions are checked but arbitrary tags are not automatically installed.

## Limits and evidence

One dedicated Telegram bot and one private owner per installation; groups are not authorized. Cloud Bot API downloads are limited to 20 MB. WhatsApp streamed video intake can accept up to 256 MiB with valid provider metadata; base64 has a smaller separate bound. Status audiences and segmented-send progress are reviewable in the app.

Thirty-day retention protects referenced media and pending work, does not reset database counters, and is configurable in Settings/tray. Postiz post cleanup and local file retention are different actions. Review uncertain platform results before retrying.

See the [feature audit ledger](../docs/audits/2026-11-15-feature-audit.md) for reproducible evidence, installation state and hardware/provider acceptance that remains outstanding.
