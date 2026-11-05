# Changelog

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
