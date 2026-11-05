# Changelog

## [1.0.5]

- Refresh running PostForge services and reload WhatsApp intake after package updates while preserving runtime data.
- Check for updates hourly and surface available releases in the window, menu bar, and macOS notifications.
- Check the upstream stable release for Evolution API and its bundled Manager.
- Show active work on the Dock icon and beside the tray artwork.
- Make built-in captions, prompts, UI copy, and setup guides business-agnostic.

## [1.0.4]

- Stream WhatsApp videos up to 256 MiB to disk and verify their size and SHA-256.
- Check the requested schedule before downloading media.
- Flag ineligible videos when the request explicitly says YouTube Shorts.

After updating, restart PostForge services to reload an already-running WhatsApp listener.

## [1.0.3]

- Verify the public Postiz endpoint and scheduler when changing the tunnel URL, and automatically restore the previous settings if verification fails.
- Apply the tunnel change without restarting the database, WhatsApp, or the rest of the stack.
- Reject malformed or ambiguous tunnel settings before applying changes.

## [1.0.2]

- Put **About PostForge** directly above **Quit PostForge** in the menu bar menu.
- Move **Check for Updates…** to the top-level menu and show an install shortcut when a new app version is available.
- Group posting activity and channel connections separately so reconnection timers are easier to scan.

## [1.0.1]

- Backup export verifies the Postiz archive in a temporary database and can run without a Swift compiler.
- Restore rehearses the archive before replacing Postiz data, replaces the media directory, and restores the previous credentials and media if the database restore fails.
- Standard uninstall preserves project data. Purge stops on Docker cleanup errors and removes package-managed system files and the installer receipt with administrator approval.
- Backup and restore progress is available in English and Ecuadorian Spanish.

## [1.0.0]

First stable public release of PostForge, licensed GPL-3.0-or-later.

- Native macOS publishing window and menu bar with English and Ecuadorian Spanish.
- Colorful app artwork and a monochrome menu bar glyph.
- About panel with icon, version/build, full copyright, GPL notice and independent-project statement.
- Publishing-flow diagram and offline license/notices viewer accessible from About.
- Human-approved Postiz drafts, local captions and WhatsApp self-chat intake.
- Facebook/Instagram reconnection countdowns and automatic-renewal health alerts.
- Clear update-check results with Done/Retry/update actions and bounded parallel checks.
- Configurable 30-day history retention with pending/referenced media protection.
- Encrypted credential exports, backup/restore rehearsal and guarded maintenance/rollback.
- Universal Intel/Apple silicon installer with checksum and artifact validation.

Telegram integration is planned for release 2 (v2.0.0) and is excluded from release 1.
