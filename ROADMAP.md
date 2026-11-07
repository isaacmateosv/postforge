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

The cross-platform host dashboard is Python and browser based, with no Electron
shell. The native Mac composer is Swift/AppKit. A Rust desktop wrapper and a
cross-platform composer are pending, including their keyboard shortcuts.

For guided publishing, share the planner and confirmation state across clients.
Telegram inline buttons can collect destinations, formats, date/time, caption
mode and approval. WhatsApp can use numbered replies and stable plan references
first, with native interactive controls conditional on Evolution support.
Keep every publishing action tied to a reviewed plan and reject stale callbacks.
Announcement image cards for media-only placements are also pending.

See [the v2 release candidate](v2/README.md) for setup and verification status.

Telegram credentials, code and background requests are not part of release 1.
