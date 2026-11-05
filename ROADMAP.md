# Roadmap

## Release 1 — publishing foundation

Native macOS app, Postiz drafts, WhatsApp intake, local captions, connection monitoring,
backups, retention and safe update checks.

## Release 2 (v2.0.0) — browser access and Telegram

- Read-only browser dashboard and link to Postiz on macOS, Windows, and Linux.
- Authenticated HTTPS gateway for optional remote access. Keep the local deployment usable without ngrok.
- Telegram private-chat setup, service reachability, and optional heartbeat with persisted state.
- External missed-heartbeat monitoring for host or network loss.
- Later Telegram workflow buttons for reviewing drafts and fixing issues, with explicit authorization and human approval.

See [the v2 release candidate](v2/README.md) for setup and verification status.

Telegram credentials, code and background requests are not part of release 1.
