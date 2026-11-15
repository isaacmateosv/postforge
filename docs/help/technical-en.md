# PostForge Technical Guide

Current client: Rust/Tauri with the operating system webview, shared Python planner, Postiz/Temporal scheduling, Evolution API and optional local Ollama. No Electron runtime is used. The Swift source remains historical; its automatic idle/wake and Siri integration are not features of the Rust client.

## Architecture and approval boundaries

```text
Desktop / WhatsApp self-chat / private-owner Telegram
                         ↓
               validate → local caption → reviewed snapshot
                                             ├→ Postiz → Temporal → social API
                                             └→ approved Status queue → Evolution

Remote browser → HTTPS tunnel → Caddy → Authelia MFA → Postiz login
Social media download → exact-file signed URL → verifier → Postiz file stream
```

Draft creation is not social publishing approval. Explicit desktop direct scheduling approves the selected destinations and Status audience. WhatsApp plan confirmation creates social drafts and approves its selected Status. Telegram’s final confirmation describes its draft/Status behavior. Never retry an uncertain delivery blindly; inspect Postiz and platform history first.

## Installation and first configuration

Distributed artifacts currently target **macOS ARM64**, **Linux x86_64** and **Windows x86_64**. A native build passing CI does not establish real-device publishing acceptance. macOS packages are ad-hoc signed, not notarized. Match the archive to the host architecture.

The client bundles public runtime code and prepares a private installation. It does not bundle credentials, media, databases or Ollama models. **Settings → Check requirements** checks:

| Tool | Purpose |
|---|---|
| Python 3.9+ | Shared planner and backup helper; Windows uses `py -3` |
| OpenSSL | Authenticated encrypted backup inspection/export/restore |
| Docker + Compose | Postiz, databases, scheduler, Evolution and gateway |
| FFmpeg + ffprobe | Video validation, previews and derived media |
| Ollama + installed model | Optional local caption generation; exact text works without it |
| Windows `tzdata` | Python timezone database: `py -3 -m pip install tzdata` |

The `.pkg` warns about missing tools and provides official download links. It cannot install third-party tools or grant system permissions silently. Downloading an Ollama model is a separate, deliberate operation. Starting services no longer pulls a model automatically.

For a fresh advanced deployment, locate the private runtime under **Settings → Advanced · installation folder**, copy its `.env.example` to `.env`, and populate it privately. This picker locates an installation; backup files belong in **Restore backup**. Use a plain UTF-8 file and restrict permissions to its owner (`chmod 600 .env` on Unix). A source checkout can instead use the same files in its repository root. The developer-only `POSTFORGE_PROJECT_DIR` override takes precedence over a saved workspace and permits isolated testing.

Required credential groups:

- **Postiz/database:** `POSTGRES_USER`, `POSTGRES_DB`, a unique `POSTGRES_PASSWORD`, matching `DATABASE_URL`, and a long random `JWT_SECRET`. Retain the signing secret and database credentials during migration.
- **Evolution:** a unique `AUTHENTICATION_API_KEY`, `WA_INSTANCE` and authorized phone QR pairing. This API key protects the local manager; it is not the WhatsApp phone password. The normal app shows QR/session and audience controls without opening the manager.
- **Social apps:** only the client IDs/secrets for enabled connectors. Postiz stores the resulting channel tokens. An API key alone is not YouTube OAuth authorization.
- **Public access:** a selected tunnel profile and locally provisioned Caddy/Authelia gateway. TryCloudflare does not require an ngrok account; a named Cloudflare tunnel needs its own token/domain. Saved ngrok credentials remain optional.
- **Optional Telegram:** dedicated bot token, one verified numeric owner ID, language, enable/hold flag and heartbeat interval. Never share a bot token between simultaneously active installations.

The runtime must be configured before **Manage services → Start services** can succeed. For source/advanced operation, `./postforge.sh doctor` and `./scripts/recheck.sh --live` provide diagnostics. On Windows use the Rust service controls rather than assuming Bash is installed.

## Gateway and accounts

Follow the repository’s [gateway provisioning guide](https://github.com/isaacmateosv/postforge/blob/main/v2/gateway/README.md). It documents `v2/gateway_setup.py`, password hashing and local authenticator enrollment. No Google sign-in or SMTP is required for local enrollment. The QR seed and enrollment image are secrets; do not include them in screenshots or public logs.

Gateway users and Postiz workspace membership are separate. Provision the gateway first, then the Postiz owner/team account through the protected route. Keep `DISABLE_REGISTRATION=true` routinely. An operator-controlled signup window is an advanced provisioning task, not an always-open public registration feature. Without SMTP, deliver an invitation privately using an existing trusted channel; no email is sent magically by PostForge.

Default gateway inactivity is **30 minutes without authenticated requests**, with a **two-hour session maximum**. A page can make requests in the background; this is not a browser-mouse-activity timer. Existing custom values survive migration. Public dashboard/API access remains protected. The controlled exception is a signed URL for one media file, not an authentication bypass for the dashboard.

## Public links and migration between providers

Normal entry point: **Manage Postiz link** in Settings or **Postiz Link & Access** in the tray. The screen distinguishes reachable, unreachable, detected-but-unsynchronized and account-reconnect states. Clicking a usable URL copies it with visible confirmation. Old URLs cannot be copied while a changed connector needs synchronization.

| Mode | Behavior |
|---|---|
| TryCloudflare | Temporary hostname; restart can replace it, no uptime guarantee |
| Named Cloudflare tunnel | Stable owned domain; saved token and domain are portable secrets/settings |
| ngrok | Uses the saved account/domain; account quotas still apply |
| Standalone/private network | No public tunnel required for local access; remote access still needs a protected HTTPS route |

A detected temporary hostname should be adopted with **Use detected link**. Requesting a different random address is an advanced repair action, not normal renewal. Changes preserve the gateway, update configured public origins and validate access. Network maintenance is blocked while publishing/backup work is active. A connector is preserved during ordinary app/service refresh rather than recreated needlessly.

When moving to an owned domain, create/configure the named tunnel, select that mode, save the token/domain and apply. Returning to temporary mode retains the saved named profile. Verify the gateway and signed media delivery on the new origin. This app cannot edit Google, Meta or TikTok developer consoles for you.

OAuth callback values must match the **connector**, including the distinction between Instagram via Facebook Login and Instagram Standalone. Copy the matching value from the per-account reconnect guide. Existing tokens may remain usable after a hostname change; do not disconnect every account. If reconnection is required, update the provider callback, reconnect the existing Postiz channel and check again. See [public address guide](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/public-address.md).

## Social API configuration and formats

The authoritative project setup references are [channel setup and minimum permissions](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/channel-setup.md) and [request attributes](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/app-keys.md). Enable only the permissions required by the selected connector and behavior. Do not replace connector scopes with guessed generic permissions.

### YouTube

Enable **YouTube Data API v3** in the Google Cloud project. Configure the OAuth consent audience and a **Web application OAuth client**, not an API key or desktop client. Store its ID/secret as `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`. Add the current Postiz YouTube redirect URI shown in the app, then authorize the existing channel as its owner. In testing mode, include the intended test users; testing-mode refresh tokens can require frequent reauthorization. Do not switch client IDs merely to repair an expired access token.

The same upload API handles Shorts and regular videos. Follow the current connector’s required scopes in the [YouTube setup guide](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/youtube.md); they include upload and the connector’s read/management needs. The API does not offer a switch that turns arbitrary horizontal media into a Short. Automatic routes vertical/square to Shorts and horizontal to regular video. Shorts copies are capped at 179 seconds when needed. Title regeneration is independent from the description and delivery plan. Uploaded image/extracted frame thumbnails require channel eligibility; an accepted thumbnail request is not proof of its final rendering in every YouTube surface.

### TikTok

**Inbox Upload** uses `video.upload` and transfers video for completion inside TikTok. That video endpoint has no caption or cover fields. The app retains a copy-caption handoff; select the cover in TikTok. **Direct Post** uses `video.publish`, caption and a cover-frame timestamp. Public direct posting requires a TikTok-audited client. An external cover image is not a video cover parameter. See [official Direct Post reference](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post).

### Meta and Threads

A successful Facebook Reel can also appear in its feed; check the returned placement rather than creating a duplicate feed video. Instagram Story success does not prove Reel success. Long Facebook/Instagram Story media becomes ordered parts spaced one minute apart. The preview lists each part count. Threads may need an independent shorter adaptation. Connection health reports stored token/renewal state, not guaranteed publishing success or media-policy approval.

## Composer state and media security

Each review is a server-validated snapshot with a submission family. Caption variants retain destinations, time, media and cover. Up to eight versions are shown; identical takes are not duplicated. Applying manual copy updates the selected version. The title has its own edit/regenerate controls. Time changes preserve copy. Changing media, destinations, formats or origin requires renewed validation; keep user-edited wording.

A shared maintenance lease prevents runtime replacement, tunnel changes, backup/restore, cleanup and submission from overlapping. Cross-process requests fail visibly rather than silently racing. Replay returns an existing receipt; partial or uncertain submissions are held for inspection rather than reposted automatically.

Gateway media URLs authorize **GET/HEAD for an exact file**, expire 48 hours after its planned publication and are bounded to schedules up to 30 days ahead. They are bearer links: keep them private. One-byte delivery probes validate all attached/cover URLs before creation. Postiz streams the data; the verifier does not duplicate full videos. Moving a saved draft beyond link expiry or changing the origin requires fresh media links/review before approval.

## WhatsApp and Telegram operations

Evolution QR pairing is embedded in the window. The API key/session remains private. Polling stops when the dialog closes; a healthy session is never replaced just to get a QR. Audience controls support all contacts or selected numbers with country code. Changing the default does not alter approved queued recipients.

Video Status uses ordered parts of at most 60 seconds. A part is not replayed automatically after an uncertain provider response; progress and the confirmed/uncertain distinction matter more than a simple timeout. Receipts are paginated/filterable and omit recipient identities from the desktop response. Accepted sends are not view confirmations.

WhatsApp interactive messages were tested with the current provider format. Typed actions remain available for clients that do not show buttons. Callbacks are bound to the private self-chat, action/version and expiry. Settings require an explicit settings command or action; ordinary publishing text cannot turn into a settings reply. Large-video streaming up to 256 MiB depends on provider download metadata; `WA_MAX_MEDIA_MB` separately bounds base64 intake (default 32 MiB, configurable 1–64).

Telegram uses one dedicated installation bot, one private owner and long polling; no public webhook is required. Set it up in the window: token validation, `/start`, private-owner discovery, language, heartbeat and explicit save/enable. `/new`, `/cancel`, `/status` and `/settings` are the main commands. Button callbacks use versioned reviewed snapshots. Groups are deliberately rejected. The cloud Bot API download path is limited to 20 MB per file.

Heartbeat is off by default; supported intervals are 5–1440 minutes. Telegram buttons and explicit WhatsApp `postforge ping` commands save the same portable setting. The host receiver must be running and the computer awake. A local heartbeat cannot report its own dead host; use an external monitor for missed-heartbeat alerts.

## Resource use and service lifecycle

The dashboard refreshes on focus and at most every 30 seconds while visible/focused. QR polling and completion countdowns pause or end when their context closes. Caption calls use `keep_alive: 0`; the local model unloads after requests. Advanced model selection only chooses an installed model and does not enable a cloud provider. Gemini remains disabled.

**Manage services** exposes fixed start/stop actions. Stop requires a verified empty scheduled queue and no approved waiting Status. It stops this Compose stack, pauses WhatsApp intake and leaves shared Docker/Ollama tools and unrelated projects alone. Starting resumes configured containers/receivers and checks APIs/scheduler; missing container images may download. It does not pull an Ollama model. Temporary tunnel links may need synchronization after a real stop/start.

The Rust app does not yet provide the older Swift controller’s automatic sleep/wake scheduler or one-hour idle shutdown. Keep the host awake for scheduled delivery and configure OS startup deliberately for unattended use. Quit closes the desktop client, not the services. Do not run both clients as competing controllers.

## Retention, identifiers and safe cleanup

`PM_RETENTION_DAYS` defaults to **30** and is editable in Settings and the tray. It is an age policy for local unused files/history, not a database reset or automatic deletion of every saved Postiz post. Pending plans and any non-deleted Postiz post protect their referenced media. If references cannot be verified, uploads are retained. Both Status staging and WhatsApp message staging are covered by automatic WhatsApp cleanup. Large original files and derived uploads may remain when still referenced.

For advanced broader cleanup, run `python3 scripts/retention.py` to preview and `python3 scripts/retention.py --apply` only after review. This removes eligible unused files/logs; saved Postiz posts remain protected. Database counters/approval identifiers do not restart merely because logs expire. Do not manually reset database sequences or delete upload folders.

**Remove posts** is a separate operation: preview and confirm unpublished drafts/failed posts and/or cancellation of queued items. It skips entries whose state changed after preview and does not delete published social content. Active sends may finish. Retention and queue cleanup are not substitutes for checking delivery history.

## Encrypted backup and destination restore

Use **Backup & Move**, not the recovered-installation picker. Export includes credentials, Postiz data/uploads and the gateway state in an authenticated encrypted `.pfbackup`. The database export is checked in a temporary database. Ollama models, application binaries and third-party installations are separate. Keep the backup and its passphrase private; the passphrase needs at least 12 characters and cannot be recovered.

On the destination: select the file, enter the passphrase, inspect, review, enter it again and confirm the old host is stopped. Inspection never replaces live data. Existing data replacement requires explicit consent and an encrypted rollback backup; incompatible existing database credentials need a fresh destination installation. Backup jobs are detached from the window. Reopening discovers live work; **Resume progress** reattaches after transient bridge errors without starting another restore. Requests/passphrases are not saved in the recovery task reference.

Restore leaves services stopped, publishing paused and Telegram on migration hold. Review timezone, public provider/domain, gateway users/MFA, Postiz sessions and WhatsApp pairing before starting. Only one Telegram receiver should own the token. Temporary public hostnames are not portable identities. Named-domain credentials/settings travel encrypted; configure DNS/routing at the destination as required.

## Updates, packaging and removal

Startup and six-hour update checks follow the installed app’s stable/prerelease channel. Manual checks inspect Docker/Evolution too. ZIP checksums and platform/architecture are verified before installation. macOS replaces the signed bundle and refreshes the matching public runtime/configured services while retaining private files. Active backup/publishing blocks installation. Windows/Linux reveal the verified archive for manual replacement rather than overwriting a running executable. On the next Windows launch, matching runtime/service refresh uses Python rather than requiring Bash; stopped stacks remain stopped.

Evolution Manager is part of the pinned Evolution deployment, not a separately updated desktop app. A newer upstream version is shown as compatibility work; the updater does not blindly install untested container tags. A failed check is incomplete, not “up to date.”

macOS advanced removal: `./scripts/uninstall.sh --dry-run` lists the intended scope, then use the script’s interactive flow. The additional purge is explicit and removes private data; export a backup first. Matching bundle identities are checked, source Git checkouts are preserved, and shared tools/images are not removed. Actual removal is not run as an audit test. Windows/Linux: stop this installation first, remove its client using the OS, and handle its private runtime separately; the macOS shell helper is not a cross-platform uninstaller.

## Diagnostics and acceptance limits

Check Dashboard, Connections, service progress, per-post errors and private logs. Never publish `.env`, database dumps, QR seeds, bot tokens, backup passphrases or signed media URLs in issues. An audit can replay mocked provider responses and disposable restore databases; final social rendering, physical destination migration and Windows/Linux device behavior still need real acceptance tests.

The [feature audit ledger](https://github.com/isaacmateosv/postforge/blob/main/docs/audits/2026-11-15-feature-audit.md) records tested paths and remaining limitations. For daily use, return to the Quick Start tab.
