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
3. Choose local access or an authenticated HTTPS gateway. Configure provider OAuth credentials and callback URLs for the selected Postiz origin, then connect the social accounts in Postiz.
4. Turn on PostForge. Open **WhatsApp Manager**, then use the authorized phone to scan its QR code. Keep its API key private.
5. Run the read-only health checks from the project directory.

```bash
cd ~/postforge
./postforge.sh doctor
./scripts/recheck.sh --live
```

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
- Social drafts require approval in Postiz. WhatsApp Status follows its own explicit approval queue.
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
