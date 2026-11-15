# Roadmap

## Release 2 · current release candidates

Rust/Tauri desktop client for macOS, Windows and Linux; structured composition and review; native tray; bilingual offline help; optional private Telegram and WhatsApp guided flows; authenticated public gateway; portable encrypted backups; verified updates and bounded local service controls.

The [feature audit](docs/audits/2026-11-15-feature-audit.md) separates implemented behavior, automated validation and real-device acceptance. See [SETUP](SETUP.md) and the [desktop guide](desktop/README.md) for current use.

## Before a stable v2 claim

- Physical Windows/Linux installation, restore and publishing acceptance beyond CI compilation.
- Destination-machine migration rehearsal with representative large media and user-owned credentials.
- Social-platform rendering and permission acceptance, including covers, Reel placements and TikTok audited Direct Post where configured.
- Production signing/notarization and a complete fresh-business setup wizard.
- Port and test OS startup, scheduled wake and automatic idle policy; the Rust client currently offers explicit service controls.
- A portable, explicitly reviewed uninstaller; current automated removal helper is macOS-specific.

## Later scope

Authorized Telegram groups with isolated sender/group sessions; external missed-heartbeat monitoring; optional announcement-image rendering; platform-specific Siri/OS automation beyond Open App shortcuts. These are not silently enabled by adding a bot to a group or installing the desktop client.

Release 1 and the Swift controller remain historical source. Run one current client/controller at a time.
