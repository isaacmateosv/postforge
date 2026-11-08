# PostForge: simple setup on a new Mac

This is the complete final-user guide for installing PostForge on another
Apple Silicon Mac. You do not need to understand Docker or Python to follow it.

## What the single package contains

The file produced by `./scripts/package.sh` is one self-contained project bundle:

```text
PostForge-YYYYMMDD-HHMM.pkg
```

It contains the application source, Docker configuration, PostForge app source,
installer, setup guide, and scripts. It deliberately does **not** contain private
credentials, channel tokens, databases, WhatsApp sessions, media, or Postiz data.
Those items must travel separately so one accidentally shared package cannot expose
the organization’s account.

This is not an Apple Developer-signed or notarized installer. The PostForge app is
ad-hoc signed locally during installation. No Apple Developer subscription is
needed.

## Distribution disclaimer and license

The source is available under the [GNU GPL v3.0-or-later](LICENSE), but the external
services and images it uses are not relicensed by this project. In particular,
Evolution API/Baileys may be unofficial WhatsApp integrations. This package
does not guarantee platform approval or prevent account restrictions. Follow
each platform's current terms, use accounts and recipients you are authorized
to control, and stop if a provider objects. Never distribute `.env`, exports,
databases, logs, media, or WhatsApp session state.

## Permissions and approvals

The installer cannot grant macOS permissions silently. The first run may require
these approvals:

- **Docker Desktop:** allow Docker Desktop to install its privileged helper and
  allow network access. The installer uses Docker only after you start the machine.
- **Ollama:** allow its background service and local network access. Ollama runs
  locally; captions are not sent to a third party when local mode is configured.
- **Notifications:** allow notifications when the PostForge app asks. This is
  optional, but needed for local off-machine and failed-post alerts.
- **Login Items:** enable **Open at Login** in the PostForge app. It is required for
  automatic startup of the controller after a reboot and wake recovery.
- **Browser/network:** allow the browser to open the ngrok URL and approve the
  social-channel permissions when connecting Facebook, Instagram, TikTok,
  YouTube, or Threads in Postiz.
- **WhatsApp:** scan the QR code with the authorized phone. This is the
  only required account-login step for the WhatsApp door.
- **Test recipients:** copy `config/whatsapp/vip-list.example.txt` to
  `config/whatsapp/vip-list.txt` and replace the example number only if you
  explicitly need the VIP test audience. This operational file is excluded from
  release packages.

The installer does not request Full Disk Access, Accessibility, Contacts, or
Camera permissions. If macOS asks for one of those unexpectedly, stop and check
the application or contact the maintainer before approving it.

### Scheduled posts, wake recovery, and idle resources

The tray schedules macOS to wake 15 minutes before the next queued publication and starts
PostForge after the wake event. Keep **Open at Login** enabled; otherwise no controller
will be available after a reboot. The lead time can be changed with `PM_WAKE_LEAD_MINUTES` in
the private `.env`.

After one continuous hour without pending work or app interaction, PostForge verifies the live queue
again and stops its containers. While the tray shows **Idle · services off**, WhatsApp intake is paused
until you choose **Turn On**. Turn off **Settings & Tools → Turn Off When Idle** if you want WhatsApp
intake to stay available while the Mac is awake. The automatic stop is enabled by default.
Enable **Notify My WhatsApp Before Idle** to get a notice in your self-chat before the listener stops.
An incoming WhatsApp message waits until PostForge is running again.

To open the composer with Siri on your Mac, import **New post in PostForge.shortcut** or **Nueva publicación en PostForge.shortcut**
from **PostForge Help → Siri Shortcuts…** and say its name. Previously imported shortcuts keep their original names until you rename or replace them. The shortcut opens the composer. Choose **Turn On**
in that window if PostForge is idle.

PostForge unloads its own caption model after each request. Idle stop leaves Docker Desktop and the
Ollama daemon available to other apps. If no containers are running, Docker Desktop’s
[Resource Saver](https://docs.docker.com/desktop/use-desktop/resource-saver/) can stop its Linux VM.

## Requirements before installing

Complete this checklist before opening the package:

### Computer

- Apple Silicon Mac: M1, M2, M3, or M4.
- macOS 15 or newer.
- At least 8 GB RAM; 16 GB is recommended.
- At least 20 GB free disk space. More is needed if you keep many videos.
- Internet access for Docker images, Ollama model download, and ngrok.

### Applications

Install these before running the PostForge installer:

1. **Docker Desktop for Apple silicon** from `docker.com`.
   Open it once and wait until it says Docker is running.
2. **Ollama** from `ollama.com`.
   Open it once so macOS permits its background service.
3. **Homebrew** from `brew.sh`.
4. **Xcode Command Line Tools**. In Terminal, run:

   ```bash
   xcode-select --install
   ```

   If macOS says they are already installed, continue. Swift is not required on
   the destination Mac because the PostForge app is included prebuilt.
5. **ffmpeg**:

```bash
brew install ffmpeg
```

The installer also checks Python, Docker, Ollama, ffmpeg, disk space, and memory.
Swift is only needed when building the app from source, not for normal installation.

### Private files from the old computer

Obtain these from the current computer before starting:

- `.env`: deployment settings, passwords, API keys, and the ngrok token.
- A Postiz export made with `./scripts/postiz-transfer.sh export`.

Transfer both privately using AirDrop, an encrypted drive, or another trusted
method. Never put either file in a public repository or chat.

### Safely moving credentials

The easiest way is the app: **Backup & Move → Export Backup** encrypts `.env` with a passphrase you choose
(at least 12 characters) together with your Postiz data. To do only the credentials, from a terminal on the old Mac,
in `~/postforge`, run:

```bash
python3 scripts/credentials.py export
```

Choose a long passphrase and move `exports/credentials.env.enc` separately from
the application package. On the new Mac, copy that encrypted file into the
project and run:

```bash
python3 scripts/credentials.py import exports/credentials.env.enc
```

Enter the same passphrase. The command restores `.env` with permissions `600`.
The passphrase is never saved by the application and cannot be recovered. Delete the encrypted copy from
the project after restoring it, or keep it only in a private encrypted backup.

### One-folder migration (recommended)

In the PostForge app on the old Mac, open **Backup & Move…**, choose where to save, enter a passphrase and press
**Export Backup**. Docker Desktop must be running. The backup contains encrypted `.env` credentials, a rehearsed
Postiz export, and a matching installer if one is already available locally. Copy the entire folder privately.
The Postiz archive contains channel tokens and media.

1. Install the same PostForge version from the included package or
   [GitHub Releases](https://github.com/isaacmateosv/postforge/releases), then open Docker Desktop.
2. In the app, open **Backup & Move → Restore…**, choose the folder, enter the passphrase and confirm.
3. Turn PostForge on and link WhatsApp again by QR (`./scripts/link-whatsapp.sh`).

The terminal equivalent is:

```bash
# Old Mac
./scripts/migrate.sh export
# New Mac, after installing the .pkg
cd ~/postforge
./scripts/migrate.sh import ~/Desktop/PostForge-migration-YYYYMMDD-HHMM --skip-installer --replace
./postforge.sh start
./scripts/link-whatsapp.sh
./scripts/recheck.sh --live
```

The import restores credentials and Postiz data. Link WhatsApp again by QR and verify pending posts after
moving. WhatsApp session data, Redis state and Temporal jobs are outside the archive.

## Install from the single package

1. Copy `PostForge-X.Y.Z.pkg` to your Mac (check it with `shasum -a 256 -c PostForge-X.Y.Z.pkg.sha256` in the
   same folder).
2. Double-click the `.pkg` and follow the installer: a welcome page, the requirements, the license, then it installs
   the project in `~/postforge` and installs and opens the PostForge app for you. It needs macOS 13 or later.
3. Open **Terminal** from Applications → Utilities and copy the private `.env`:

```bash
cp /path/to/private/.env ~/postforge/.env
```

4. Run the project installer to check the prerequisites (Docker Desktop, Ollama, ffmpeg and so on):

```bash
~/postforge/install.sh
```

The package already installed the app in `~/Applications/PostForge.app` (and removed an old `Publish Machine.app`, the
app's former name, if one was there); the project installer re-checks the Mac, refreshes the app, and runs a doctor
check. Neither step starts services, links WhatsApp, creates drafts, or sends anything.

If the installer reports an error, fix the named requirement and run
`./install.sh` again. To check without installing the app, use:

```bash
~/postforge/install.sh --check
```

### Upgrade or uninstall

Install the new `PostForge-*.pkg` directly or use **Check for Updates…** in the tray.
The package merges application files and preserves credentials, databases, media, exports, logs,
and runtime state. If PostForge is running, the installer recreates its services and reloads
WhatsApp intake. Expect a short interruption. If it was stopped, it stays stopped.

See `~/Library/Logs/PostForge-install.log` for details. If the app does not open, run
`~/postforge/install.sh`.

For a complete removal, use **Uninstall PostForge…** in the app (menu bar → Settings & Tools → Maintenance, the
PostForge app menu, or **Backup & Move**). It lists everything that will be deleted (the app and project folder,
`.env`, all Postiz posts and media, the WhatsApp session, logs, Docker containers, and installer files), shows the
date of your last backup, and warns that **if no backup was exported everything is lost and cannot be recovered**.
You can choose **Export Backup First…**, then you must tick a box and type `UNINSTALL`. Posts already published on
your social networks stay published. Docker Desktop, shared images and other shared tools stay installed.
Keep any backup you want to retain outside the project folder. Start Docker Desktop before removing PostForge.
A package installation also requires administrator approval to remove the system files and receipt.

From a terminal, run `./scripts/uninstall.sh --purge-data` and type `PURGE` to confirm. With no purge flag,
uninstall stops the services and removes the app while preserving the project and private data.

### WhatsApp Status audience

The default status audience is public to saved WhatsApp contacts:

```env
WA_STATUS_AUDIENCE=all
```

For private testing, first choose **WhatsApp Status Audience → Configure test numbers…** and enter
comma-separated country-code numbers without `+`. Then choose **Private: test recipients**. This
stores `WA_TEST_RECIPIENTS` in the private `.env`. Switch back to **Public: all contacts** only
after the test is complete. Approved WhatsApp status sends use this setting.

### If macOS blocks the app

Because the app is not Apple-notarized:

1. Open `~/Applications`.
2. Control-click **PostForge.app**.
3. Choose **Open**, then choose **Open** again.

If macOS still blocks it, open **System Settings → Privacy & Security** and
choose **Open Anyway** for PostForge. This is expected for a private,
unsigned distribution.

## Restore your Postiz data

Create the private export folder, copy the export into it, then run:

```bash
mkdir -p exports
cp /path/to/postiz-export.tar exports/
cd ~/postforge
./scripts/postiz-transfer.sh import exports/postiz-export.tar
```

Use the real filename and extension. Restore the export **before** the first
`start` on the new computer. Do not use `--replace` unless you intentionally want
to overwrite existing Postiz data.

## Start the machine

```bash
cd ~/postforge
./postforge.sh start
./postforge.sh status
```

For a final pre-distribution check:

```bash
./scripts/recheck.sh
./scripts/recheck.sh --live
```

The first command validates source syntax, Compose configuration when Docker is
available, and the private-file boundary. The live form additionally requires
the machine to be `on`, Postiz/Evolution/Scheduler/Tunnel healthy, and WhatsApp
`open`. Both must pass before creating or uploading a release package.

The status output should show Postiz, Scheduler, WhatsApp, and Tunnel as healthy.
Open the public Postiz URL printed by the command. Do not use the localhost URL
for normal browser access.

A healthy status normally includes:

```text
Postiz UI (local)      : HTTP 307
Postiz API (local)     : HTTP 200
Public tunnel          : HTTP 307
WhatsApp (...)         : open
Scheduler (Temporal)   : Postiz worker polling
Status receipts        : recorded
WhatsApp door          : listening
Redis AOF persistence  : yes
```

The exact HTTP status can vary with an upstream release, but the endpoints must
be reachable and the scheduler, WhatsApp connection, receipts, and tunnel must
be healthy.

The first start downloads Docker images and the Ollama model, so it can take
several minutes. This is normal.

## Model and storage choices

The default local caption model is `llama3.2:3b`, configured by
`LOCAL_LLM_MODEL` in `.env`. On first start, PostForge checks Ollama and
downloads that model automatically. The model stays local and is unloaded when
the machine stops.

For a stronger but heavier model, change `LOCAL_LLM_MODEL` before starting and
make sure the Mac has enough memory and disk. For the lightest supported setup,
keep the default. Do not copy Ollama model files inside the application package;
they are machine-specific and are downloaded by Ollama.

Docker images are also downloaded automatically by the first start. Keep at
least 20 GB free before starting, and more if you choose larger models or retain
many videos.

## Set up publishing channels

Use the [first-time channel setup and permissions guide](docs/reconnect/channel-setup.md)
to create developer apps, register OAuth callbacks, and link WhatsApp through Evolution.

## Reconnect WhatsApp

If WhatsApp did not reconnect automatically:

```bash
cd ~/postforge
./scripts/link-whatsapp.sh
```

Scan the QR code using the phone linked to the WhatsApp account. This only links the configured
WhatsApp account; it does not publish anything.

## First safety check

Before creating a real post:

1. Open the PostForge menu (the calendar-and-paper-plane icon at the top right of the screen) or
   click the PostForge icon in the Dock to open the New Post window.
2. Confirm the menu says **Ready to post** and the window's status says **Running**.
3. In the wide composer, attach media or confirm the text-only announcement destinations.
   Use **idea:** for a brief or **caption:** with double quotes for exact wording.
4. Bake with **⌘ Return**, review the time and destinations, then choose **Create Drafts**.
5. Create one test draft for a future time.
6. Confirm it appears as a **Draft** in Postiz.
7. Reject the test draft using **Clear…** or the Postiz calendar.

Nothing should publish unless you explicitly approve it in the intended workflow.

## Expected first-run views and sessions

After a successful first start, the menu should show:

```text
● Ready to post
New Post…
Open Postiz Calendar
Turn Off…
Coming up · No scheduled posts waiting
WhatsApp Plans & Receipts…
Check for Updates…
Settings & Tools ▸
About PostForge
Quit PostForge (posting keeps running)
```

The New Post window shows **Running** at the top right and the counters In queue, Drafts and
Next post. If work is waiting, the icon gets the number of waiting items beside it. **Needs
attention**, a warning triangle, a missing Scheduler check, or a tunnel that does not answer
means setup is not complete. Choose **Restore All Services**, then run `./postforge.sh status`.
A dimmed icon means the stack is off: choose **Turn On**.

The first safe WhatsApp session should look like this:

```text
You: Instagram mañana a las 18:00; idea: pan de yuca
Publish Machine: Plan 1 is waiting for confirmation.
You: aprobar plan 1
Publish Machine: Plan approved. Postiz drafts were created.
```

The first test must use a future time and a test audience. Reject the resulting
draft or WhatsApp plan. Do not use a real public audience until the complete
review flow has passed.

## What the installer does not do

For safety, installation never:

- sends a WhatsApp message;
- scans a WhatsApp QR code;
- publishes or schedules a post;
- imports over existing Postiz data;
- deletes old files;
- changes social-channel permissions.

Those are deliberate, final-user approval steps.

## Everyday commands

```bash
cd ~/postforge
./postforge.sh status       # health and resource usage
./postforge.sh pending      # scheduled work and waiting approvals
./postforge.sh stop         # safely turn the machine off
./postforge.sh start        # turn it back on
./postforge.sh retention    # preview history older than 30 days
./postforge.sh retention --apply
./postforge.sh maintenance check
```

The PostForge app checks stable app releases, declared Docker image digests, and upstream Evolution API and Manager releases hourly. Available updates appear in the tray and main window; the main window’s Updates button opens the same progress flow. It never silently upgrades Homebrew, macOS, Docker Desktop, Ollama, or
social integrations.

Saved history defaults to **30 days**, configurable through the tray’s **Settings & Tools → Maintenance → Saved History…** (`PM_RETENTION_DAYS`). Always preview `retention` before applying it. Manual cleanup removes old logs and unused uploads. The running WhatsApp listener also cleans expired staging daily. It preserves referenced Postiz media, future confirmations, pending sends, databases, schedules, queues and credentials. If the database cannot be checked, uploads are retained. Changing the setting alone deletes nothing.
Application logs rotate at 10 MiB with four older copies. Docker service logs retain
five 10 MiB files per service. The 30-day retention command still removes older
project log files.

Before any maintenance update, run `./postforge.sh maintenance check`. The
safe update command is:

```bash
./postforge.sh maintenance update --apply
```

It creates a rollback snapshot before changing the Docker stack. It never updates
macOS, Docker Desktop, Ollama, Homebrew, or social-channel permissions
automatically. Those require separate user-controlled installers and approvals.

To change the public URL, first provision the domain in ngrok and wait for DNS and TLS to be ready.
[ngrok custom-domain setup](https://ngrok.com/docs/gateway/domains/custom-domains)

With PostForge running, choose **Settings & Tools → Tunnel URL…** or run:

```bash
./postforge.sh tunnel-url https://publish.example.com
```

Use an HTTPS domain without a path or port. PostForge updates the public URL settings together and
recreates Postiz and ngrok. Expect a brief interruption. It checks local Postiz, the public HTTPS API,
and the scheduler before accepting the change. If a check fails, it restores the previous configuration.
If recovery itself fails, the command reports where it kept the previous settings.

Open the new URL and check that you can sign in to Postiz and stay signed in after refreshing.
Update each provider’s registered OAuth callback URL for the new domain before connecting or
reconnecting channels. PostForge cannot change settings in your provider dashboards.

## Moving the project again

On the old Mac:

```bash
cd ~/postforge
./scripts/postiz-transfer.sh export
./scripts/package.sh
```

Copy the resulting package, the export, and `.env` privately to the new Mac. Never
upload `.env`, `data/`, `logs/`, `run/`, or `exports/` to a public service.

WhatsApp’s regular intake defaults to **32 MiB per file** (`WA_MAX_MEDIA_MB`, effective range 1–64). PostForge streams larger videos up to **256 MiB** to disk and verifies their size and SHA-256 before planning. Use New Post for bigger files or media with missing download metadata.


## Rust desktop and Telegram preview

The Rust/Tauri client uses structured Compose, Delivery and Review screens.
See [desktop setup](desktop/README.md) for host prerequisites, platform builds,
artifact signing limitations and the shared Python bridge. The Swift Mac
controller retains its existing system integrations.

For Telegram, create a private BotFather bot, run the local setup helper and
start the host agent. It registers commands and restricts messages and buttons
to the configured private owner. Full English and Ecuadorian Spanish setup
steps, file limits and approval flow are bundled in Technical Help.
