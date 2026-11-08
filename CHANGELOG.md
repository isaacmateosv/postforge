# Changelog

## [2.0.0-rc.22]

- Rust desktop opens tall and centered at a comfortable width, bounded by the monitor work area, with scrolling content, persistent controls and compact short-screen spacing. Native Cmd/Ctrl+N reopens the hidden composer; macOS Dock reopening also restores the window.
- Native tray, active-task badges, six-hour release checks and a private encrypted Backup & Move assistant now share the main window workflows. Restore requires inspection and confirmation, preserves a rollback backup when replacing data, and leaves publishing services paused.


- Restore a colorful, status-aware dashboard as the opening view, with saved drafts, upcoming posts and focused refreshes.
- Hide installation paths in advanced recovery, remove duplicate Telegram setup actions, add in-window WhatsApp QR linking and a compact animated mixer.
- Clarify Story segment counts, caption adaptations and version history; add separate YouTube title editing, a +10-minute shortcut and text Status background colors.
- Prepare an independent 2:59 YouTube Shorts copy for longer portrait/square videos while retaining other destinations' full media; offer explicit full-video mode.
- Keep the optional business hashtag empty for fresh installations and retain explicitly configured tags.

## [2.0.0-rc.21]

- Add per-installation Telegram configuration in the Rust UI: private token entry, bot validation, private owner discovery, language, heartbeat and enable/disable.
- Store portable settings in the private .env; carry legacy and new bot secrets in encrypted credential exports. Restores pause Telegram until explicit activation, preserving preferences without two pollers.
- Keep saved tokens out of UI responses and logs, validate private chat access, and roll back settings and conversation state if restarting the worker fails.

## [2.0.0-rc.20]

- Reorder the Mac composer around request, optional media, grouped options and review-side completion.
- Add a Rust/Tauri composer with structured delivery fields and native build artifacts.
- Share reviewed snapshots and replay-safe submission guards between desktop and Telegram.
- Add private Telegram workflow buttons, caption versions and explicit confirmations.
- Add a local Status agent, portable locks and conversion, native CI, and bilingual setup guides.

## [2.0.0-rc.19]

- Use a wide two-column composer and prominent bake and draft actions.
- Revise only the copy section and browse caption versions with arrows.
- Preserve quoted captions, validate dates and times, and confirm text-only announcement destinations.
- Add scoped cleanup with a preview, confirmation, state rechecks, and scheduler cancellation.
- Hide model identifiers in the composer, add a third baking sparkle, and update bilingual workflows and technical guides.

## [2.0.0-rc.18]

- Restore media delivery through the protected gateway with expiring, file-scoped signed links.
- Split long single-video Meta Stories into individual clips and space scheduled parts.
- Verify public byte-range downloads before creating social posts, including cover images.
- Preserve the media signing key in encrypted gateway backups and restore older backups.
- Explain media delivery failures and link expiry in English and Ecuadorian Spanish.

## [2.0.0-rc.17]

- Revise or edit captions without rebuilding the plan, and request revisions in WhatsApp.
- Add the Mac bake shortcut, undo support, and an expanding request field.
- Offer explicit direct scheduling for eligible social posts.
- Improve local caption model support and contextual emojis.

## [2.0.0-rc.16]

- Put each channel name above its countdown and prevent text selection in the connection popover.

## [2.0.0-rc.15]

- Add padding and centered connection details with bold network names.
- Label Postiz’s estimated Meta expiry dates and refresh the snapshot when opening Connections.

## [2.0.0-rc.14]

- Move channel reconnection countdowns into a Connections popover beside the service status.

## [2.0.0-rc.13]

- Preview a concise YouTube title with AI help when the first line is too long, and keep the full description.
- Keep generated hashtags together with the final business tag.
- Warn about new-audience recommendations for Instagram Reels over three minutes.
- Center the composer steps and add sparks to the mixing animation.

## [2.0.0-rc.12]

- Add an editable final hashtag and a WhatsApp review step for changing it per plan.

## [2.0.0-rc.11]

- Place the composer steps near the top and add a brief, interruptible opening highlight.

## [2.0.0-rc.10]

- Preview the YouTube title and enforce its 100-character limit separately from the caption.

## [2.0.0-rc.9]

- Confirm missing video covers before review and require an explicit edit to change a reviewed cover.
- Show a small mixing animation while preparing the plan.

## [2.0.0-rc.8]

- Clarify generated versus exact captions and improve Ecuadorian Spanish caption prompts.
- Generate alternate captions and restore earlier versions from the Mac composer.

## [2.0.0-rc.7]

- Add private Telegram setup with owner detection and keep the worker in the normal Mac lifecycle.
- Preserve reviewed caption text when creating drafts and show any shortened Threads version before approval.

## [2.0.0-rc.6]

- Move WhatsApp Plans & Receipts to the top-level menu bar menu.
- Hold WhatsApp Status sends for review after uncertain delivery, and prepare smaller clips for Evolution.

## [2.0.0-rc.5]

- Improve generated caption tone, hashtag layout, and contextual emoji filtering.
- Surface separate WhatsApp Status approval in the plan and menu bar.

## [2.0.0-rc.4]

- Give the plan more vertical space and organize it into review sections.
- Highlight Bake Idea and show the steps before creating drafts.
- Accept topic-first requests and colloquial Spanish for posting everywhere.

## [2.0.0-rc.3]

- Add menu bar shortcuts for draft formats, cover images, and cover timestamps.

## [2.0.0-rc.2]

- Choose posts, stories, or both in the Mac composer and WhatsApp plans.
- Set a video cover from an image or a timestamp on supported channels.
- Render the menu bar glyph at 18 points without automatic enlargement.
- Document first-time channel setup and API options in English and Ecuadorian Spanish.

## [2.0.0-rc.1]

- Add an optional Docker-based browser dashboard for local service status and access to Postiz.
- Add an optional Telegram bot with private status, a refresh button, and a configurable heartbeat.
- Add separate password and authenticator sign-in in front of Postiz for remote deployments.
- Preserve gateway users and authenticator enrollment in encrypted migration backups.
- Verify the gateway separately from the Postiz scheduler when changing a protected tunnel URL, with rollback on failure.

## [1.0.8]

- Add illustrated flow diagrams and bilingual quick-start and technical guides to the repository and offline app Help.
- Ship freshly signed PostForge-branded English and Ecuadorian Spanish Siri shortcuts.

## [1.0.7]

- Offer an optional WhatsApp self-chat notice before idle shutdown, and a Turn On button in the composer opened by Siri.
- Show Facebook length advisories, YouTube Shorts limits, and WhatsApp Status segment counts in the plan.
- Automatically clean expired WhatsApp staging and abandoned download files while preserving pending work and referenced Postiz media.
- Rename the preview button to **👨‍🍳 Bake idea**.

## [1.0.6]

- Require a continuous idle period and recheck the live queue before automatically stopping services.
- Show idle status in the window and tray and expose an idle-stop toggle for operators who need continuous WhatsApp intake.
- Reduce polling while stopped and avoid repeat macOS wake requests for the same post.
- Keep shared Docker and Ollama resources available during an automatic stop.

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
