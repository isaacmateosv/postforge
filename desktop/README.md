# PostForge Desktop · Rust/Tauri beta

The desktop composer uses a Rust/Tauri host and the operating system webview
on macOS, Windows and Linux. Its HTML/CSS/JavaScript assets are embedded.
The existing Python planner handles captions, media, signed delivery and posting.

## Workflow

1. **Compose**. Choose idea generation or exact words, enter the content, and
   attach optional media.
2. **Delivery**. Choose connected destinations, local date/time and formats.
   Cover and business-hashtag settings are grouped under caption options.
3. **Review and finish**. Bake, review, edit or browse caption versions, then
   create drafts or confirm direct scheduling. WhatsApp Status has a separate
   approval.

Changing inputs invalidates the review. Caption changes preserve delivery.
Changed files require another review. Preview references expire after 24 hours.
Versions share a submission family, so repeated submission returns its receipt.
A partial or uncertain submission is held for calendar review.

## Host prerequisites

Connect the client to a current, configured PostForge project folder. It defaults
to **~/postforge** and offers a folder chooser for another location.

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

The Swift/AppKit Mac app retains its tray, Siri, login, update and maintenance
integrations. The Rust client provides a shared composer across OSes. It does
not yet replicate every Mac-specific system feature.

The Rust bridge invokes a fixed list of local Python operations over stdin/stdout.
It opens no command HTTP listener. Credentials stay out of renderer responses,
and a strict CSP protects the embedded frontend. Models are unloaded after use
by the existing planner; the client has no periodic background polling.

## Telegram

Create a dedicated bot with **/newbot** in **@BotFather**, then configure it locally.
The helper discovers the private owner, registers commands and stores the token
privately. Keep group privacy enabled. Inline mode and a public webhook are
unnecessary.

~~~text
python3 v2/telegram_setup.py --language en --heartbeat 15
python3 scripts/host_agent.py restart
python3 scripts/host_agent.py status
~~~

Use **--language es** for Ecuadorian Spanish. Use **/new** for guided buttons,
**/status** for health and **/cancel** to discard an unfinished plan. A second
confirmation is required for submission, and WhatsApp Status is approved separately.

One bot requires one poller. The host agent takes over from legacy Docker health
polling. Restart it after settings changes. Start it after reboot or configure OS
autostart. Keep the host awake and the stack running when jobs are due. A sleeping
host cannot receive a command.

The cloud Bot API downloads up to 20 MB per file; use the desktop path for larger
videos. Completed/cancelled Telegram intake is removed after staging. Abandoned
intake and review records follow retention. Before migration, stop the old agent,
configure the bot on the new host and start a fresh conversation.
