# PostForge Technical Guide

PostForge is a local macOS controller for a self-hosted publishing stack. It prepares plans and drafts. Postiz and Temporal handle approved social schedules. Evolution and Baileys link the operator’s WhatsApp session.

```text
Mac composer ───────────────┐
WhatsApp → Evolution ───────┼→ Planner → Preview and approval
Local Ollama captions ──────┘                │
                                             ├→ Postiz → Temporal → Social channels
                                             └→ Approved Status queue → Evolution
```

## Install and configure

1. Install the PostForge package and the prerequisites listed in SETUP.md, including Docker Desktop, Ollama, and FFmpeg.
2. Copy .env.example to .env. Set the database credentials and JWT secret, the ngrok domain and token, and the Evolution API key. Set the project time zone with PM_TIMEZONE if you operate outside Ecuador.
3. Choose local access or an authenticated HTTPS gateway. Configure provider OAuth credentials and callback URLs for the selected Postiz origin, then connect the social accounts in Postiz. The repository’s [channel setup guide](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/channel-setup.md) lists the scopes for each connector.
4. Turn on PostForge. Open **WhatsApp Manager**, then use the authorized phone to scan its QR code. Keep its API key private.
5. Run the read-only health checks from the project directory.

```bash
cd ~/postforge
./postforge.sh doctor
./scripts/recheck.sh --live
```

## Set up Telegram

Create a dedicated bot with BotFather. In Terminal, from the PostForge folder,
run `python3 v2/telegram_setup.py --language en --heartbeat 0`. Enter the bot
token at the hidden prompt and send `/start` from your private chat when asked.
Confirm the owner, run `./postforge.sh telegram start`, then send `/status`.
The worker follows the PostForge stack, including idle shutdown. A heartbeat
of `0` is off. Choose 5–1440 minutes to enable it.

## Standalone access without ngrok

For on-premises use, run the Compose stack on the Mac, Linux host, or Windows
host with Docker Desktop. The v2 browser dashboard is available locally.
The Postiz UI is also available through its local port. The v2 README has
the Compose commands and the platform verification status.

For access from other devices, use an authenticated HTTPS gateway on the
network edge or use a private network with access controls. Point the
gateway to the Postiz origin and keep all direct ports private. Configure
the gateway’s users and MFA first. Then create the separate Postiz owner
account through that protected route. Enable Postiz registration only for
the initial owner setup if needed, then disable it.

If you use ngrok, put the access gate in front of the entire endpoint.
If you use your own domain, set the Postiz origin and provider callback
URLs to match it. Review the v2 README before making a public cutover.

## Daily operation

- The Mac composer and WhatsApp self-chat use the same planner. A quoted caption is kept as written.
- By default, social posts become drafts for Postiz approval. Schedule Directly requires confirmation before queueing. WhatsApp Status follows its own explicit approval queue.
- A stopped stack pauses intake. A WhatsApp message cannot turn on the local listener. For a local restart, use Siri to open the composer and choose **Turn On**.
- Hourly update checks compare the public PostForge release, declared Docker images, and stable upstream Evolution releases. Package upgrades refresh an active stack and preserve its runtime data.

## Media and retention

- WhatsApp videos up to 256 MiB can stream to disk. PostForge verifies their length in bytes and SHA-256 digest.
- Longer WhatsApp Status videos are split into up to 60-second clips after approval.
- Expired WhatsApp staging is cleaned when the listener runs. The default retention is 30 days. Pending sends, future confirmations, and media referenced in Postiz stay protected.
- Preview the general cleanup with the command below. Use the tray setting to change the retention period.

```bash
./postforge.sh retention
./postforge.sh retention --apply
```

## Back up and recover

Use **Backup & Move** to export encrypted credentials and a rehearsed Postiz archive. Keep the archive private because it contains channel tokens. Restore on the destination Mac before scheduling new work, verify pending posts, then link WhatsApp again. The migration excludes Temporal jobs and the WhatsApp session. If the separate gateway is configured, the same passphrase also protects `gateway.enc`, which carries the allowlist, password hashes and authenticator enrollment. Keep it with the backup. After restoring, validate the gateway and tunnel before exposing Postiz. Users sign in again with their existing passwords and authenticator codes.

If Postiz becomes unreachable after a tunnel change, check the log for rollback status. For connection-specific recovery, see the repository’s docs/reconnect guides. Review **Open Log** in the tray before restarting or purging anything.

```bash
./postforge.sh status
./postforge.sh channels
./postforge.sh maintenance check
```

### Media delivery through the gateway

PostForge gives each attached file a signed download URL for the social platform.
The link permits GET and HEAD for that exact file and expires 48 hours after the
planned publication time. Scheduling through this route supports up to 30 days
ahead. If you move a draft beyond its link expiry or change the public hostname,
prepare fresh drafts before approval. Anyone holding an unexpired link can read
that file, so treat the link as private. The Postiz dashboard, API, and unsigned
uploads continue to require gateway sign-in.

Before creating posts, PostForge checks a one-byte download through every signed
media URL, including cover images. A failed check stops creation and reports the
problem. The verifier authorizes requests while Postiz streams the bytes directly.
It creates no second video copy. Existing retention rules still govern deletion.

New gateway setups create a private 32-byte media signing key. On an older gateway,
create it once with the following command, then apply the updated gateway Compose
file and Caddy configuration.

    python3 scripts/lib/media_links.py init-key data/gateway/media-signing.key

Keep that key private. Backup & Move includes it in the encrypted gateway archive.
Older archives receive a fresh key during restore. An expired or revoked provider
login still requires reconnection in Postiz.

Long single videos are split into balanced Story clips under 60 seconds when
Facebook or Instagram Stories are selected. The full video stays on feed posts.
Review each Story draft in order. Direct scheduling spaces Story parts one minute
apart. Encoded temporary clips are removed after upload, and their uploaded copies
follow the normal Postiz retention rules.

## Composer state and advanced configuration

Caption revision and version navigation patch only the stored caption fields.
The native view replaces the attributed copy range, preserving plan metadata and
scroll position. Editing the request or attachment options invalidates that plan
and clears its version history. The two-column composer grows its request field
within a fixed-height workspace and keeps the plan independently scrollable.

The request parser separates scheduling instructions from caption content.
Double-quoted content and explicit caption/text fields preserve wording. An
unquoted idea field requests generation. Ecuadorian day/month dates, ISO dates,
weekdays, AM/PM including spaced “p. m.”, and local timezone scheduling are
supported. Review the resolved date and hour before creation. Invalid dates,
invalid times, and past or too-soon times produce an error. For predictable
results, place the destinations and schedule before the caption or brief.

The local model is an advanced setting. Install the desired Ollama model and set
LOCAL_LLM_MODEL in the private .env file. OLLAMA_HOST_URL selects the local server.
The next bake reads these settings. The ordinary composer uses descriptive copy
labels and hides the model identifier. Choosing a larger model increases memory
and generation time. Models remain external to the installer.

Cleanup first snapshots eligible unpublished groups for the selected organization.
Confirmation applies only to that snapshot, rechecks each group and uses Postiz's
public DELETE endpoint so its scheduler cancellation path executes. Changed work
is skipped. Pending WhatsApp Status records are cancelled under the queue lock,
and items already marked sending are excluded. Cancellation may race with an
external publish already in progress. Failures and skipped entries are reported,
and a retry requires another preview. The tool does not purge media shared by
other posts or bypass retention.

Text-only announcements require explicit supported-destination selection in the
Mac UI. The CLI accepts --text-networks facebook,threads,whatsapp with no media.
WhatsApp uses the explicit “only text approved” / “solo texto aprobado” command.
Facebook and Threads use feed posts and WhatsApp uses Status. Instagram and
Facebook Story publishing in this app use media. Text-to-image announcement
cards and interactive Telegram publishing buttons are future work.

Windows/Linux currently use the Python browser dashboard and shared Docker
services. It is read-only and has no native composer or Rust desktop wrapper.
There is no Electron shell. The Mac app is Swift/AppKit. Ctrl+Enter for a
cross-platform composer remains pending that implementation.
