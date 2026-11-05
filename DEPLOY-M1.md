# Deploying PostForge on an 8 GB Mac

Use [SETUP.md](SETUP.md) for credentials and installation. PostForge supports macOS 13+
with compatible prerequisites on Apple silicon or Intel; use a current supported macOS
version for the Docker Desktop release you install.

## Resource budget

The Compose stack caps Postiz at 1.5 GiB, Evolution at 512 MiB, Temporal at 384 MiB,
PostgreSQL at 256 MiB, Redis at 128 MiB and the tunnel at 64 MiB. Those are limits,
not typical consumption. Leave memory for macOS, browsers and local inference.
Use the configured small Ollama model; caption generation releases the model afterward.
WhatsApp intake defaults to 32 MiB per attachment so base64 downloads cannot exhaust Evolution.
Use the native window for larger media. Never reduce database/session persistence to save memory.

## Install and configure

1. Install the verified package from GitHub Releases and the prerequisites in SETUP.md.
2. Configure a private `.env`, with mode `600`, using `.env.example` and the README's credential table.
3. Use one active PostForge project at `~/postforge`. Keep its databases, uploads and queues private.
4. Run `./postforge.sh doctor`, then `./postforge.sh start`.
5. Sign into Postiz, authorize the social accounts and link WhatsApp by QR.

## Acceptance checks

Before relying on scheduled publishing:

- `./postforge.sh doctor` reports ready.
- `./scripts/watchdog.sh` passes with Postiz, Evolution, scheduler, WhatsApp and tunnel healthy.
- A local caption preview produces the intended language, media, channels and future time.
- Drafts remain drafts until explicitly approved in Postiz.
- Reconnection dates and alerts are visible; automatic renewal is not treated as permanent access.
- A private backup can be rehearsed into an isolated database and its row/media counts match.
- Normal use stays within memory limits without container restart loops.

## Move to another Mac

Use **Backup & Move → Export Backup** with a passphrase of at least 12 characters.
Carry the resulting folder privately. Install its package on the destination and use
**Backup & Move → Restore**. The passphrase cannot be recovered.

Backups include encrypted credentials, Postiz data/media and the exact release installer/checksum.
They exclude WhatsApp session and Redis state; link WhatsApp on the destination by QR.
Use one active machine for the same tunnel and account workflow during cutover.

## Operations

Keep backups before maintenance and retain old local Docker images until a new version is verified.
Rollback restores code/image references; it does not reverse database migrations.
The file-history age defaults to 30 days and is configurable in the tray. Cleanup requires review/apply;
credentials, pending work and referenced media are preserved. See [ROLLBACK.md](ROLLBACK.md).
