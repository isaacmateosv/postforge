# PostForge Desktop · Rust/Tauri beta

The desktop composer uses a Rust/Tauri host and the operating system webview
on macOS, Windows and Linux. Its HTML/CSS/JavaScript assets are embedded.
The existing Python planner handles captions, media, signed delivery and posting.

## Opening dashboard

The app opens on the publishing dashboard: verified service/link indicators,
draft and scheduled counts, next publication and recent saved posts. It refreshes
on focus and every 30 seconds only while the dashboard is visible and focused.
Pending WhatsApp Status approvals also remain accessible here after reopening
the app. Open Postiz for social-post approval, saved-post editing and the complete calendar. Start a
new post without losing the dashboard.

## Workflow

1. **Compose**. Choose idea generation or exact words, enter the content, and
   attach optional media.
2. **Delivery**. Choose connected destinations, local date/time and formats.
   Cover and business-hashtag settings are grouped under caption options.
3. **Review and finish**. Bake with the small mixer animation, review, edit or browse caption versions, then
   create drafts or confirm direct scheduling. WhatsApp Status has a separate
   approval.

Changing inputs invalidates the review. Caption changes preserve delivery.
Changed files require another review. Preview references expire after 24 hours.
Versions share a submission family, so repeated submission returns its receipt.
A partial or uncertain submission is held for calendar review.

## Host prerequisites

The client includes its public backend and creates a private installation on a fresh host automatically. Normal use does
not ask for a project folder or show installation paths. **Settings → Advanced ·
installation folder** locates a recovered/migrated installation when needed.
The macOS `.pkg` checks tool presence and provides official download links; Settings → Check requirements checks versions and service readiness. The backend, .env and data belong to one installation; the app does not move
live Docker bind mounts when locating it. The developer environment override
POSTFORGE_PROJECT_DIR is also supported.

- Python 3.9+, with the **py** launcher on Windows.
- Docker Desktop on Mac/Windows, or Docker Engine and Compose on Linux.
- FFmpeg and ffprobe on PATH.
- Ollama and an installed model for generated captions.
- Windows Python timezone data, installed with **py -3 -m pip install tzdata**.

Start and configure the shared stack using the project setup guide. Windows
uses Linux containers. Rust is required to build the client; built clients use
the host's Python and services.

## Build

Install Rust stable and the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

~~~text
cargo build --release --locked --manifest-path desktop/Cargo.toml
python3 desktop/package.py --no-build
~~~

Use **py -3** for Python commands on Windows. Artifacts and checksums appear in
**desktop/dist**. They include licenses, dependency notices and offline guides.
Choose the artifact matching your OS and CPU architecture.

macOS ZIPs contain an ad-hoc-signed app. Windows ZIPs contain an executable.
Linux needs the WebKitGTK/GTK runtime libraries in Tauri's prerequisites.
These beta artifacts require the separately configured PostForge project.
Production signing/notarization and real-device Windows/Linux acceptance tests
remain separate release requirements. The native CI matrix builds all three OSes.

## Swift and Rust

Rust/Tauri is the active desktop development target and the only client needed
for this beta's composer workflow. Close the legacy Swift app before using it.
Swift remains in source history and compatibility code, rather than a companion
application. The Rust tray now exposes the dashboard, composer, WhatsApp review,
connections, encrypted Backup & Move, update checks, settings, Help and About.
Closing the window hides it; Quit exits the client and leaves services running.
Updates install from inside the app: it checks releases, and on your confirmation
downloads the matching build, verifies its SHA-256, replaces the installed app in
place and relaunches. The update carries matching runtime code, keeps private data outside its manifest, refreshes configured services, and retains prior code for recovery. Active WhatsApp delivery blocks the refresh. Startup never downgrades a newer developer workspace. It never
replaces the client without that confirmation. Siri and OS-login autostart still
require further platform integration. On Windows and Linux this beta stages the
verified download and opens its folder for a manual swap, since a running client
cannot overwrite itself there yet.

The Rust bridge invokes a fixed list of local Python operations over stdin/stdout.
It opens no command HTTP listener. Credentials stay out of renderer responses,
and a strict CSP protects the embedded frontend. Models are unloaded after use
by the existing planner; dashboard refreshes run only while the dashboard is visible and focused.
Release checks run at startup and every six hours; active backup tasks report progress.

## Telegram · per-installation settings

Each installation uses its own operator-owned bot. PostForge provides no global
bot and ships no bot token. This version supports one authorized private
Telegram owner per installation. Other users and groups are ignored.

1. Open **Telegram** in the app header, on any workflow screen.
2. Create a dedicated bot with **/newbot** in **@BotFather** and paste its token
   into the masked local field. Choose **Validate bot**.
3. Open that bot in Telegram, send **/start**, then choose **Find my private
   account**. Select and verify your numeric account ID. A numeric ID can also
   be entered directly; saving verifies that the bot can access that private chat.
4. Choose English or Ecuadorian Spanish, enable/disable the bot, and set a
   heartbeat interval: **0** disables unsolicited heartbeats; otherwise use
   **5–1440 minutes**. Confirm the bot and authorized owner, then save.
5. Send **/new** for guided posting buttons. **/status** checks services and
   **/cancel** discards an unfinished plan. Submission and WhatsApp Status
   approval remain explicit.

A blank token field keeps the saved secret; saved tokens are never returned to
the renderer. To change the active bot's owner through discovery, disable and
save first, send a new **/start**, then select the intended owner and re-enable.
Disabling works without contacting Telegram and retains credentials/preferences.
Keep group privacy enabled. Inline mode and a public webhook are unnecessary.
A bot already using a webhook is rejected rather than silently reconfigured.

The private **.env** is the portable source of truth for enabled state, bot
identity/token, private owner, language and heartbeat. Runtime token files are
derived caches, with legacy settings imported on save or encrypted export.
Settings saves validate first, restart the host agent and roll back on failure.
The terminal helper remains optional for advanced use.

Encrypted credential exports include these granular settings and the token.
Treat the backup and passphrase as secrets. On restore **TELEGRAM_MIGRATION_HOLD=true**
pauses Telegram while preserving the previous enabled preference. Stop the old
host agent, open Telegram settings on the destination, review the bot/owner and
explicitly enable it. Only one machine may poll the bot. Activation after
migration or a bot/owner change ignores older commands and starts a fresh
conversation. Conversation state and in-flight approvals are not migrated as
new commands. Migration requires no new bot or token unless you choose to rotate it.

Opening the Rust app resumes an enabled bot automatically, except after a
migration hold. For unattended use before opening the app after reboot,
configure OS autostart for the host agent. A sleeping host
cannot receive commands. The cloud Bot API downloads up to 20 MB per file;
use the desktop path for larger videos. Completed/cancelled intake is removed
after staging; abandoned intake/review records follow retention. Encrypted
backup/restore uses OpenSSL on PATH, including on Windows.

## Formats, versions and local connections

- Automatic delivery includes posts and supported stories. A long video produces
  one feed post plus multiple Story drafts per Facebook/Instagram account.
  The preview lists each Story target's segment count; segments are scheduled
  one minute apart. These are intentional parts, not repeated submissions.
- YouTube defaults to Shorts: portrait/square video longer than 2:59 gets an
  independent 179-second copy. Other networks retain their full source. A
  landscape source requires choosing full-video mode or supplying portrait media;
  it is not silently cropped. The full-video mode bypasses trimming.
- **Edit title…** edits YouTube's title separately, with a 100-character limit.
  It preserves the reviewed caption and delivery. Manual titles are not clipped
  to append #Shorts. Shorts classification depends on the media, not that hashtag.
- **Try Another Caption** adds a take; arrows revisit previous takes. Manual
  caption/title edits update the selected take. Identical captions are not added
  as extra takes. The Threads adaptation is collapsed and labelled separately.
- **Soon · +10 min** sets a future time in the configured timezone, including
  crossing midnight. The date/time field remains editable.
- A fresh installation has no business hashtag. Explicitly configured hashtags
  remain available; clearing the field omits the tag for that plan.
- Text-only WhatsApp Status supports a background color. It is frozen into the
  reviewed queue item, including for delivery after a restart, and sent only
  after approval. Media Status keeps its media appearance.
- **WhatsApp** in the header shows the existing connection or an embedded QR.
  QR polling happens only while its dialog is open, and image data is cleared on
  close/link completion. A healthy paired session is never recreated for a QR.
- **Remove posts…** distinguishes unpublished drafts from cancellation of
  scheduled posts/pending Status. It previews counts and requires confirmation.
  Published content is outside this cleanup.

Telegram remains private-owner-only in PostForge. Telegram can host bots in
groups, but adding this bot to a group does not authorize group actions. A future
group workflow needs explicit group and sender allowlists and isolated sessions.
Older unsubmitted reviews require rebaking after the media policy update; already
completed submissions still return their existing receipt rather than republishing.
