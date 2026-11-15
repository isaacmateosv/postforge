# Install, configure or migrate PostForge

Use the current **Rust/Tauri** client. Do not run the historical Swift controller alongside it.

## Choose your route

| Situation | Start here |
|---|---|
| Moving an existing installation | Install the destination app, check requirements, then **Settings → Restore backup** |
| New business installation | Install prerequisites, configure private runtime/.env and the gateway, then connect channels |
| Daily publishing | [English Quick Start](docs/help/quick-en.md) / [Inicio rápido](docs/help/quick-es.md) |
| Advanced setup and recovery | [English technical guide](docs/help/technical-en.md) / [Guía técnica](docs/help/technical-es.md) |

## Packages and prerequisites

Download from [GitHub Releases](https://github.com/isaacmateosv/postforge/releases). Current CI artifacts are **macOS ARM64**, **Linux x86_64** and **Windows x86_64**. Choose the matching CPU/OS. On macOS the `.pkg` checks requirements and provides official download links; ZIPs also contain the public backend. The Mac app is ad-hoc signed, not notarized.

Install Python 3.9+, Docker with Compose, OpenSSL and FFmpeg/ffprobe. Ollama plus an installed model is optional for generated captions; exact captions do not need it. Windows uses `py -3` and needs Python `tzdata`. Linux needs the Tauri WebKitGTK runtime dependencies. **Settings → Check requirements** distinguishes installed tools from running services. Tools and model downloads are not bundled in a backup or silently installed by the package.

The app creates private runtime storage automatically. A backup file is not a project directory: select `.pfbackup` in **Restore backup**, not the advanced folder picker.

## Restore an existing deployment

1. Export an encrypted backup on the old host. Keep its passphrase separately and allow space for the media and temporary verification files.
2. On the destination, select the backup, enter its passphrase and **Inspect backup**. This does not modify existing data.
3. Read the result, enter the passphrase again and confirm the old publishing host is stopped. Replacing data requires explicit confirmation and a rollback backup. A destination with incompatible database credentials needs a fresh installation.
4. Restore leaves publishing services and Telegram paused. Check timezone, gateway/MFA, public URL and social sessions. Start services and explicitly enable Telegram. WhatsApp may need another QR pairing.

A closed assistant does not cancel detached work. Reopen it for live progress; **Resume progress** reconnects to the same job. Do not start another import merely because a progress request failed. Passphrases are not recoverable.

## Fresh deployment

A fresh package contains public code, not a preconfigured publishing business. An operator must populate the private `.env`, provision the gateway and connect channels. Locate private storage through Advanced recovery; use `.env.example` as the template. The current app does not include a full first-business provisioning wizard.

Follow the technical guide for database/JWT/Evolution/connector credentials and the [gateway enrollment procedure](v2/gateway/README.md) before public exposure. Keep Postiz registration disabled after controlled owner/team setup. Use the [minimum connector permissions and request attributes](docs/reconnect/channel-setup.md); Spanish instructions are [here](docs/reconnect/channel-setup-es.md).

TryCloudflare, a named Cloudflare tunnel with an owned domain, saved ngrok and private-network operation are supported configurations. A temporary hostname can change. **Manage Postiz link** distinguishes synchronization from account reconnection; changing the public URL does not edit developer-console callbacks automatically.

## Services, updates and resources

Use **Manage services** in Settings or the tray. Stop refuses scheduled/approved waiting work, pauses WhatsApp and leaves shared tools and unrelated projects alone. Start checks the APIs and scheduler and may download missing container images, but does not pull an Ollama model. Keep the host awake for scheduled work. The Rust app does not yet reproduce the old Swift automatic idle/wake controller.

Updates are checked at startup and every six hours. A manual check also inspects components. macOS installs matching client/runtime code and refreshes configured services; Windows/Linux stage a verified archive for deliberate replacement. Upstream component versions are compatibility signals, not permission to install arbitrary untested tags.

## Data ownership and removal

Keep `.env`, gateway state, databases, logs, bot tokens and backups private. The default retention window is 30 days for eligible local history/unused files; saved Postiz references and pending work protect media. Retention does not reset approval identifiers or delete all historical posts.

For removal details, see the technical guide. The macOS helper supports `--dry-run`; private-data purge is separate and explicit. Export a backup first. Shared Docker/Ollama installations are not owned by PostForge and are preserved.
