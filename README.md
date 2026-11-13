# PostForge

<p align="center"><strong>A human-approved publishing operations center for self-hosted social workflows.</strong></p>

<p align="center"><img src="docs/images/postforge-mark.png" width="160" height="160" alt="PostForge mark"></p>

<p align="center">
  <a href=".github/workflows/validate-and-package.yml"><img src="https://img.shields.io/badge/CI-validate%20%26%20package-informational" alt="CI: validate and package"></a>
  <a href="https://github.com/isaacmateosv/postforge/releases"><img src="https://img.shields.io/github/v/release/isaacmateosv/postforge?label=latest%20release" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg" alt="License: GPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/platform-macOS%2013%2B%20%7C%20Intel%20%26%20Apple%20Silicon-informational.svg" alt="macOS 13 or later, Intel and Apple Silicon">
  <img src="https://img.shields.io/badge/status-operational%20%7C%20self--hosted-success.svg" alt="Operational self-hosted project">
</p>

PostForge turns repetitive social-media preparation into a reviewable,
approval-gated workflow. It combines a native macOS app (a menu-bar controller plus a New Post
window), Postiz
drafts and scheduling, local caption generation, WhatsApp self-chat intake,
durable Temporal scheduling, and a guarded maintenance/rollback process.

**Publishing requires human approval:** create Postiz drafts for later approval,
or explicitly confirm **Schedule directly** in the Rust desktop app to approve
all selected destinations, including WhatsApp Status, at the reviewed time.

> **Project status:** operational on an Apple Silicon Mac; migration and
> distribution remain gated by the validation checklist below. This is a
> self-hosted integration project, not an official client or endorsement of
> any platform.

## Current v2 development

**Rust/Tauri is the desktop client going forward.** Use the [Rust desktop guide](desktop/README.md)
for the current preview. The Swift controller is retained as legacy source for
compatibility and reference, rather than a second app to run alongside Rust.
Installation paths stay inside advanced recovery; WhatsApp pairs by QR in the window. Some system integrations are still being ported; this is a beta, not a feature-complete
replacement release. Current desktop releases include a Rust macOS `.pkg` and platform ZIPs with their public backend code bundled.

## Contents

- [What it provides](#what-it-provides)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Credentials and first connection](#credentials-and-first-connection)
- [Connections, history, and updates](#connections-history-and-updates)
- [Quick start](#quick-start)
- [Validation and stability](#validation-and-stability)
- [Connection expiry and reconnection](#connection-expiry-and-reconnection)
- [Roadmap](#roadmap)
- [Contributors and acknowledgements](#contributors-and-acknowledgements)
- [License and third-party components](#license-and-third-party-components)

## User guides

| Guide | English | Español (Ecuador) |
| --- | --- | --- |
| Quick start | [Start here](docs/help/quick-en.md) | [Inicio rápido](docs/help/quick-es.md) |
| Technical | [Setup and operation](docs/help/technical-en.md) | [Instalación y operación](docs/help/technical-es.md) |

Open **Help → PostForge Help** in the Mac app to read either guide offline in the selected app language.

## What it provides

- **Approval-safe drafting:** media and one-sentence instructions become
  reviewable Postiz drafts.
- **WhatsApp self-chat intake:** text, photos, videos up to 256 MiB, and optional voice notes become
  plans; approval/rejection commands are explicit and bilingual.
- **Durable scheduling:** Temporal preserves scheduled work across a controlled
  stop/start; late delivery is visible rather than silently discarded.
- **Native app:** a menu-bar controller (lifecycle state, pending work, channel warnings,
  maintenance prompts, tunnel URL editing) and a New Post window for dropping media, writing or
  dictating an idea, previewing the plan, and creating drafts; a WhatsApp window to approve
  or reject plans (with an editable caption) and see Status receipts; and a **Backup & Move**
  window to export, restore or uninstall. English and Ecuadorian Spanish in the native app.
- **Bounded operations:** resource limits, log rotation, 30-day retention,
  health checks, watchdog validation, rollback snapshots, and sanitized release
  packages.

## Rust desktop and Telegram

The Rust/Tauri client opens on a live draft/schedule dashboard and has structured Compose, Delivery and Review steps
and shares the existing Python planner. See the [desktop setup guide](desktop/README.md).
The legacy Swift source documents the system integrations still being ported.
Native builds run on macOS, Windows and Linux in CI; installation and real-device
acceptance remain separate release checks.

The private Telegram bot now guides caption mode, media, destinations, formats,
time, cover/tag options, revisions and final confirmation through buttons.
Each installation supplies its own bot; there is no shared global bot. Open
**Telegram** in the Rust app header to validate its token, select the private
owner and configure language, heartbeat and activation. Settings travel in the
encrypted credentials backup; migration restores Telegram paused until explicit
activation on the destination. Full bilingual instructions are in Help.

## How it works

![From idea through human approval to scheduled publishing](docs/images/publishing-flow.svg)

1. **Bring media and an idea** through the native Mac window or your WhatsApp self-chat.
2. **Bake idea locally.** Ollama prepares the caption; check the plan before creating drafts.
3. **Review and approve.** Create drafts for later approval in Postiz (with a separate WhatsApp approval), or confirm **Schedule directly** to approve every selected destination. Edit the date/time in step 3 without regenerating your caption.
4. **Let Temporal run the schedule.** Keep the Mac and stack online; the tray shows health, waiting work, and connections that need attention.

The Mac composer uses two columns, with media and the request beside the scrollable
plan. Bake with **⌘ Return**, review the resolved time and destinations, and then
use **Create Drafts** or confirm **Schedule directly**. **Try Another Caption**,
**Edit Caption…**, and the **‹ / ›** version controls update the copy section.
Changing scheduling inputs requires a fresh bake. Use **idea:** with an unquoted
brief to generate copy, or **caption:** and double quotes to preserve your wording.

With no media, the app asks which supported text destinations should receive the
announcement. **Clear…** previews and confirms cleanup of drafts, failed entries,
queued posts and pending WhatsApp Status. Work already sending may finish.
The current workflows and limitations are described in the
[English quick guide](docs/help/quick-en.md),
[guía rápida en español de Ecuador](docs/help/quick-es.md),
[English technical guide](docs/help/technical-en.md), and
[guía técnica en español](docs/help/technical-es.md).

Open **PostForge → About PostForge** for the app icon, version/build, copyright and license. **How It Works…** opens this flow; **License & Notices…** displays the bundled legal texts offline. In the tray, **About PostForge** is directly above **Quit PostForge**.


## Credentials and first connection

Start with [SETUP.md](SETUP.md) and copy `.env.example` to a private `.env` (mode `600`). These credentials serve different steps:

| Step | Required credentials or settings | Where they are used |
| --- | --- | --- |
| 1. Local services | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`; matching `DATABASE_URL`; `REDIS_URL`; a long random `JWT_SECRET` | Docker and Postiz. Keep the JWT secret when migrating to preserve logins. |
| 2. Public HTTPS | `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`; matching `FRONTEND_URL`, `MAIN_URL`, `NEXT_PUBLIC_BACKEND_URL` | Tunnel and OAuth callbacks. Use **Tunnel URL…** to change related URLs together. |
| 3. Postiz account | Your own Postiz email/password, created on first setup | Log in to the Postiz calendar. This is separate from the Evolution API key. Keep public registration disabled afterward. |
| 4. WhatsApp Manager | Local server URL `http://localhost:8080`, **global API key** = `AUTHENTICATION_API_KEY`; instance = `WA_INSTANCE` | Open **WhatsApp Manager** from the tray. There is no separate Evolution username/password in this deployment. Never put the key in a URL or screenshot. |
| 5. Link WhatsApp | Access to the intended phone's WhatsApp **Linked devices** screen | Scan the QR for that instance. `./scripts/link-whatsapp.sh` creates a missing instance and refreshes the QR; it leaves a working session untouched. Re-link on a new Mac. |
| 6. Social accounts | Account access plus provider developer-app IDs/secrets for the channels you enable | Connect each channel inside Postiz. Start with [first-time setup and permissions](docs/reconnect/channel-setup.md), then see [app keys](docs/reconnect/app-keys.md), [Meta](docs/reconnect/meta.md), [TikTok](docs/reconnect/tiktok.md), [YouTube](docs/reconnect/youtube.md), and [Threads](docs/reconnect/threads.md). |
| 7. Local captions | Installed Ollama and `LOCAL_LLM_MODEL` | No cloud API key is needed for local captions. Gemini is optional and disabled unless explicitly enabled. |
| Backup and migration | A passphrase of at least 12 characters | Encrypts the exported credentials; it is separate from all service passwords. |

**Large WhatsApp files:** PostForge streams videos above the regular intake limit to disk, up to 256 MiB, and verifies the file size and SHA-256 before using them. The regular intake limit is 32 MiB by default (`WA_MAX_MEDIA_MB`, effective range 1–64 MiB). Use New Post for bigger files or media with missing download metadata.

The host scripts obtain the Postiz organization's API key from the local database; this setup does not require a separate `POSTIZ_API_KEY` environment variable. Never reuse the Evolution global key as a Postiz password.

```mermaid
flowchart LR
  A[Configure private .env] --> B[Start PostForge]
  B --> C[Log into Postiz]
  B --> D[Evolution: local URL + global API key]
  D --> E[Select instance and scan WhatsApp QR]
  C --> F[Authorize social accounts]
  E --> G[Media + idea → preview]
  F --> G
  G --> H[Human approval → drafts → schedule]
```

The composer keeps its next-step buttons visible below the scrolling form. Cover previews confirm success explicitly; direct scheduling offers an eight-second, cancellable return to Dashboard. Telegram provides **Settings · activity ping** (`/settings`). WhatsApp settings require explicit commands or a deliberate Settings-button tap: `postforge settings`, `postforge ping 60`, or `postforge ping off`; captions never trigger a settings mode. Ping preferences travel in encrypted backups and do not start stopped services.

WhatsApp self-chat plans also offer reply buttons for approval review, caption revision and plan options. Final approval is a separate confirmation; buttons refer to the exact reviewed plan and expire after use. Copyable text commands remain available as a fallback. The pinned Evolution service receives a targeted rendering compatibility patch at every boot.

## Connections, history, and updates

- **Language:** choose **Settings & Tools → Language → Español (Ecuador)**. Open windows and the app menu update without discarding the idea or selected media. Dates use `es_EC`; captions, operator content, and raw upstream errors keep their original text. Postiz and Evolution have their own language controls.
- **Reconnection timer:** the tray and main window show days, hours, and minutes until the next nonrenewable social token expires. The tray lists every affected connection. Facebook and Instagram require reconnection; renewable channels show that they renew automatically. This is a social-channel token timer, separate from the Postiz web login. Dates saved while offline are labeled as cached; no precise expiry is invented for WhatsApp or an unknown token. The display refreshes with the existing status poll, about once a minute while on.
- **Saved history defaults to 30 days.** Change it through **Settings & Tools → Maintenance → Saved History…** (`PM_RETENTION_DAYS`). The age applies to logs and unused uploaded media. Review `./postforge.sh retention` before applying `./postforge.sh retention --apply`; changing the setting alone deletes nothing. PostForge automatically cleans expired WhatsApp staging while the listener runs. Future confirmations, approved pending sends, media referenced by Postiz, databases, credentials, and backups are preserved. If Postiz cannot be checked, uploads are retained. `--days N` overrides the setting for one cleanup.
- **App updates:** stable releases are checked on launch and hourly. Available updates appear in the main window and tray and can trigger a macOS notification. Installation is an explicit action. PostForge downloads the package, verifies its published SHA-256 checksum, and invokes the macOS installer, which may request administrator authentication. Package updates recreate running PostForge services and reload WhatsApp intake. Runtime data is retained. Prereleases are excluded. Both the main window's **Updates** button and the tray’s **Check for Updates…** item show explicit app/component results, hide the progress bar when finished, and offer **Done**, **Try Again**, or a direct update action. App and component checks run concurrently with bounded timeouts.
- **Idle mode:** after an hour with a verified empty queue and no app interaction, PostForge stops its containers. WhatsApp intake resumes when you turn it back on. You can enable **Notify My WhatsApp Before Idle** for a notice in your self-chat. Use the **New post in PostForge** Siri shortcut on your Mac to open the composer and turn it on. Use **Settings & Tools → Turn Off When Idle** to keep intake available.
- **Video checks:** the Instagram advisory concerns Reels longer than three minutes and discovery by new audiences. Automatic YouTube routing uses vertical/square videos for Shorts and horizontal videos for regular uploads; long Shorts receive a separate 2:59 copy. WhatsApp Status previews show the number of clips of up to 60 seconds. Large audiences can take several minutes per clip.
- **YouTube copy and covers:** **Try another title** uses the reviewed caption without changing it; **Edit title** is independent. The optional business hashtag closes the title within 100 UTF-16 units, while the description keeps topic hashtags and closes with that business tag (or `#shorts` if empty). Uploaded images and extracted frames are passed as thumbnails for videos and Shorts, subject to channel eligibility.
- **TikTok inbox:** Upload to Inbox sends the video for completion in TikTok; this route does not transfer a video caption. Copy the reviewed caption into TikTok. Direct Post supports captions when the developer app and account are approved for that route.
- **Activity badges:** the Dock shows a red count for active work. The tray shows the count and a separate update dot beside the logo.
- **Component updates:** checks compare local Docker image digests with the declared tags, separately from Homebrew. Approved updates save code and local image IDs, download before stopping services, restart, and run the live watchdog. Progress shows each stage and reports failure. A rollback restores code and image tags; it does not reverse database migrations. The checker reports stable upstream releases for Evolution API and its bundled Manager separately. A new upstream version needs a compatible PostForge release.

## Architecture

```text
PostForge.app (menu bar + New Post window)
        │
        ├── postforge.sh ── Docker Compose ── Postiz ── Temporal
        │                                      ├── PostgreSQL
        │                                      └── Redis (AOF)
        ├── WhatsApp self-chat worker ── Evolution API
        ├── Ollama (local captions; idle models evicted)
        └── ngrok/custom HTTPS tunnel
```

The project’s orchestration code is original to this repository. Postiz,
Evolution API, Temporal, PostgreSQL, Redis, Ollama, ngrok, Baileys, and social
platform APIs are external components with their own licenses, terms, and
operational constraints. See [NOTICE.md](NOTICE.md) and [AUTHORS.md](AUTHORS.md).

## Quick start

On macOS, download **PostForge-Desktop-<version>-darwin-arm64.pkg** and its checksum from [GitHub Releases](https://github.com/isaacmateosv/postforge/releases). Use a release matching your architecture; current macOS CI artifacts target Apple Silicon. Quit older copies, install, then open **/Applications/PostForge Desktop.app**. The installer checks tool presence and provides official download links. **Settings → Check requirements** checks actual versions and whether Docker is running. Python 3.9+ and OpenSSL are needed for backup inspection; Docker with Compose for restore; FFmpeg/ffprobe for video; Ollama is optional for generated captions.

The `.pkg` and desktop ZIPs include the public Python/service runtime. On a fresh machine, PostForge creates a private installation in the user application-data directory. A source checkout is not required. It does not start publishing or invent credentials. ZIP users must place the app in a writable Applications folder before updating. The app is ad-hoc signed; the macOS installer is unsigned and not notarized.


```bash
./install.sh --check
./scripts/recheck.sh
./postforge.sh doctor
./postforge.sh start
./scripts/recheck.sh --live
./postforge.sh status
```

`./postforge.sh` is the canonical command name; `./publish-machine.sh` remains as a legacy compatibility wrapper.

For a new Mac, follow [SETUP.md](SETUP.md). Keep `.env`, exports, databases,
logs, media, and WhatsApp session state private; they are intentionally absent
from release packages.

### Easy migration

On the source computer, choose **Settings → Create backup** and save the single encrypted `.pfbackup` file. Copy it privately to the destination. Install the current desktop release there, open **Check requirements**, then **Settings → Restore backup → Choose backup file**. Enter the passphrase and inspect it. Inspection is read-only. Re-enter the passphrase and explicitly confirm restoration only after the old publishing host is stopped. Replacing existing destination data requires a separate checkbox and creates a rollback backup first.

The file includes Postiz records, retained media, encrypted credentials, gateway/MFA state and Telegram settings. Videos can make it several gigabytes. Restored services remain stopped and Telegram remains paused; verify the public URL, channel sessions and schedules before resuming. WhatsApp linking and Temporal scheduler reconciliation are separate destination checks. Never restore over the source installation merely to test a backup.

Advanced installation-folder recovery locates existing installed code; it does not select `.pfbackup` files. The legacy `scripts/migrate.sh` folder format remains a terminal-only alternative and cannot be selected in the single-file picker.

## Validation and stability

Before creating or publishing a release:

```bash
./scripts/recheck.sh          # static and package-boundary checks
./scripts/recheck.sh --live   # runtime watchdog; requires the stack online
./postforge.sh doctor
./postforge.sh maintenance check
./scripts/package.sh  # creates a macOS PostForge-*.pkg installer
```

The live watchdog must report:

```text
Watchdog: PASS
state=on postiz=ok evolution=ok scheduler=ok whatsapp=open tunnel=ok
```

GitHub Actions run the static recheck and build the tray app on pushes and pull
requests. A sanitized package is generated only for `v*` tags or a manually
dispatched workflow. GitHub Actions never receive `.env`, runtime databases,
WhatsApp sessions, logs, media, or private exports.

## Connection expiry and reconnection

Automatic renewal is a capability, not a promise of permanent access. PostForge monitors the
installed Postiz integration, reports recorded expiry dates, and alerts when a channel needs attention.

| Connection | Renewal in this Postiz build | When you may need to reconnect |
| --- | --- | --- |
| Facebook Page | No working provider refresh method | Before its recorded expiry, or after permissions/account access change. |
| Instagram via Facebook Login | No working provider refresh method | Before its recorded expiry; reconnect both Meta channels when their dates coincide. |
| Threads | Automatic refresh supported | If the token expires before renewal, permissions are revoked, app keys change, or renewal fails. |
| TikTok | Automatic refresh supported; returned refresh tokens are stored | If refresh credentials expire/revoke, sandbox target access is removed, keys change, or switching sandbox/production credentials. |
| YouTube | Automatic refresh supported | Revoked/expired refresh credentials, prolonged disuse, account policy changes, or OAuth Testing restrictions. External Google OAuth apps in Testing generally issue refresh credentials that expire after seven days. |
| WhatsApp via Evolution | Linked-device session, not a scheduled OAuth renewal | Unlinking, phone/device inactivity or a provider session reset; scan a fresh QR. |
| Postiz web login | Separate local signed session | Sign in again when the browser session expires or the signing secret changes. This is separate from social-channel tokens. |
| Tunnel and service credentials | Configuration/credential health | Rotated/revoked ngrok or developer credentials, a changed domain, or local service failures. |

**TikTok preview/sandbox is not production approval.** Only configured target users can use a sandbox;
TikTok states that sandbox mode does not provide public-video posting. Unaudited Direct Post also
has private-viewing restrictions. The default `UPLOAD` path sends content to the TikTok inbox for
an explicit finishing action; account authorization does not guarantee posting eligibility or publication.
Token validity and app-review status are separate checks. Token lifetimes must come from actual
provider responses; do not assume a permanent connection or a universal one-year refresh period.

See the provider guides in [docs/reconnect](docs/reconnect/README.md).
Authoritative references: [Google OAuth expiry](https://developers.google.com/identity/protocols/oauth2#expiration),
[TikTok tokens](https://developers.tiktok.com/docs/en/oauth-refresh-a-user-access-token),
[TikTok sandbox](https://developers.tiktok.com/docs/en/add-a-sandbox),
[TikTok publishing restrictions](https://developers.tiktok.com/docs/en/content-sharing-guidelines), and
[WhatsApp linked devices](https://faq.whatsapp.com/378279804439436/).

## Roadmap

**Release 1 (`v1.0.x`)** provides the publishing foundation described here.
**Release 2 (`v2.0.0`)** adds a local browser dashboard, a separate MFA gateway for optional remote access, and private Telegram guided posting, status and heartbeat. See the [v2 release candidate guide](v2/README.md) for setup and acceptance checks.
Telegram code, credentials and background requests are excluded from release 1.
See [ROADMAP.md](ROADMAP.md).

## Contributors and acknowledgements

**Isaac Mateo Sarzosa Valencia** ([`isaacmateosv`](https://github.com/isaacmateosv)) is the
human orchestrator and release owner. Development and review were assisted by **GitHub Copilot
using Copilot SDK in VS Code**, **Anthropic Claude**, and **OpenAI Codex**. These AI systems are
credited as development assistants; they are not GitHub contributor accounts, legal authors,
copyright holders or maintainers. GitHub's Contributors panel reflects commit authorship.

## License and third-party components

<p align="center"><img src="docs/images/about.png" width="420" alt="PostForge About: version, copyright, GPL license and independent-project notice"></p>

PostForge's original code and app are free software under the GNU GPL v3.0 or later ([LICENSE](LICENSE), [copyright notice](COPYRIGHT)). You may use, study, modify and redistribute them under those terms; distributed covered binaries must be accompanied by Corresponding Source as required by the GPL. Provided without warranty. Postiz, Evolution API, Baileys, Temporal,
PostgreSQL, Redis, Ollama, whisper.cpp, ngrok and platform APIs retain their own terms and licenses.
See [LICENSE](LICENSE), [COPYRIGHT](COPYRIGHT), [AUTHORS.md](AUTHORS.md), [NOTICE.md](NOTICE.md), and [SECURITY.md](SECURITY.md).

The app is ad-hoc signed; the installer is unsigned and not Apple notarized. The project is provided
as-is, without a guarantee of third-party availability or approval. Provider credentials and a working
login do not make an integration official. Use platform integrations only where permitted.


### Public access providers

Use **Settings → Public access** or **Public URL & Tunnel** in the Rust menu bar to switch between temporary TryCloudflare, a named Cloudflare tunnel with your own domain, and saved ngrok. Gateway authentication stays enabled. URL changes synchronize Postiz and its media origins, but developer-console OAuth callbacks require manual updates. Temporary URLs change on connector restart and are intended for testing. Provider preferences and secrets are included in encrypted migrations. [English setup](docs/reconnect/public-address.md) · [Guía en español](docs/reconnect/public-address-es.md).

To import a `.pfbackup`, use **Settings → App & data → Restore backup → Choose backup file**, then inspect it with its passphrase. The advanced installation-folder chooser is only for locating an existing installation. Backups include retained videos and can be large. See the in-app bilingual Help for the destination-host restore checklist.
