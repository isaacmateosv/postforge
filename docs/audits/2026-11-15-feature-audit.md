# PostForge feature and UX audit · 2026-11-15

Status: engineering audit completed; **rc.49 published and installed locally**. Baseline was rc.45, commit 7f2cb04. Final post-upgrade visual inspection is pending because the Mac locked during relaunch. This is an evidence ledger, not a claim that every platform has been tested on hardware.

## Scope and verification boundaries

Review each user-facing feature against the active Rust client, shared Python runtime, service behavior and EN/es-EC documentation. Use disposable files/databases and simulated UI states for publishing, restore, cleanup and uninstall. Do not submit real social content, replace private data, rotate the live tunnel or reset working account sessions as an audit test. Do not call Google AI. Native Windows/Linux CI proves builds, not acceptance on physical machines.

## Feature matrix

| Area | Final evidence | Remaining boundary |
|---|---|---|
| Installation / requirements | Real packaged-runtime bootstrap, platform links, Mac PKG contents | Fresh physical Windows/Linux installation |
| Dashboard / lifecycle | Live read-only checks, guarded start/stop tests, native build | Automatic Rust idle/wake policy remains unported |
| Composer / keyboard / reset | Full synthetic EN/es-EC flow, responsive checks, reset/edit guards | Final rc.49 visual inspection after unlocking |
| Captions / titles | Local Ollama sample, fact guard, metadata/version tests, independent title controls | Human review of generated facts and tone |
| Media / covers | Real FFmpeg portrait/landscape/frame tests, bounded previews | Platform thumbnail/reel rendering |
| Delivery / retries | Reviewed-family replay, uncertainty hold, explicit approval tests | Real posts deliberately not submitted |
| WhatsApp | Session/audience/split/receipt/callback tests; live connected | Per-phone display and actual view receipts |
| Telegram | Owner/callback/heartbeat/migration tests; live running | Groups deliberately unsupported |
| Network / OAuth | Existing connector synchronized without rotation; five channels renewed/connected | Future DNS and developer-console changes |
| Backup / migration | Recovery UI tests; encryption/inspection/restore guards; 64 MiB streaming envelope test | Representative physical destination restore |
| Updates / components | Actual rc.41 → rc.49 in-app upgrade; matching runtime and healthy refresh | Physical Windows manual swap / portable refresh |
| Retention / removal | Protected references, shared lease, staging fixes, disposable uninstall | No live purge/uninstall performed |
| Help / languages / tray | Offline renderer/guide tests, native build, structured tray, 18-point Mac icon behavior | Post-upgrade visual tray/Help check blocked by lock screen |
| Release | All four rc.49 workflows green; eight assets; installed signature valid | Mac package remains ad-hoc/non-notarized |

## Baseline checks

- Static HTML/JS ID inspection: no missing literal IDs and no duplicate HTML IDs.
- Source baseline test suites started; outcomes will be recorded with final validation.
- Current progress ledger and desktop README contain stale pre-rc.45/legacy deployment statements; rewrite current-state sections rather than retaining contradictory claims.

## Findings

1. Direct-schedule confirmation says all destinations publish, but TikTok Inbox Upload needs completion inside TikTok. The completion view also omits this next action.
2. The active Rust settings/tray omit retention and lifecycle controls that earlier product documentation promises.
3. The uninstall helper targets `PostForge.app` / Publish Machine and needs validation against `PostForge Desktop.app` and the current PKG/runtime layout.
4. Requirements download URLs are macOS-specific despite the cross-platform client.
5. Public network checks can finish out of order; opening Postiz must use the newest accepted result, not an ignored older response.
6. Backup progress polling aborts on the first bridge error while the detached operation may still run; review safe retry/resume without starting a second restore.

## Morning handoff

Use **[v2.0.0-rc.49](https://github.com/isaacmateosv/postforge/releases/tag/v2.0.0-rc.49)**. It includes all audit corrections; rc.46 failed Windows validation, while rc.47/48 are retained intermediate candidates.

- **Installed:** `~/Applications/PostForge Desktop.app` and the private runtime both report rc.49. The actual in-app updater downloaded, verified, replaced and relaunched from rc.41. Strict code-signature verification passes; signed Runtime resources contain zero bytecode files.
- **Private state:** saved fingerprints of `.env` and existing gateway configuration files match after the update. Social authorization was renewed through the normal read-only Check & renew action, without posting.
- **Live health:** Postiz online; WhatsApp connected; Telegram running; public URL reachable and synchronized; all five social channels report connected. Zero drafts, queued posts or active Status sends at the final observation.
- **Validation:** 189 backend + 21 v2/service + 60 JavaScript tests, local Rust build, package/digest checks, actual bootstrap/upgrade, and all-platform CI. A 64 MiB envelope round-trip used approximately 2 MiB Python traced peak memory. UI fixtures exercised both languages and compact window sizes.
- **Locked-screen limit:** the Mac locked during the final relaunch, and automatic unlock failed. No lock bypass was attempted. Final native rc.49 visual inspection (Help, tray and composer) must happen after unlocking; the earlier native rc.41 update/reopen check and new-source synthetic UI passed.
- **Next user check:** unlock, open the installed app, inspect About/Help, preview one media plan, and review its caption/time/cover before deliberately posting. A physical destination restore and Windows/Linux device acceptance remain separate checks.

No real social content was published, no user media/drafts were cleared, no live database restore/uninstall was performed, and no Google AI was called. The live URL repair adopted the already-running connector and did not request a new hostname.

Current capability gaps are explicit: full fresh-business UI provisioning, automatic Rust idle/wake, dedicated Siri integration, authorized Telegram groups and a portable graphical uninstaller remain future work. Use explicit service stop for heavy editing and keep the host awake when scheduled work must publish. This remains a release candidate.

## First audit pass · implemented, not yet released

- Baseline passed: 165 scripts, 21 service and 38 JavaScript tests.
- Fixed platform-specific prerequisite download links in Python and the Rust allowlisted opener, including the missing-Python fallback.
- Clearing media also clears an orphaned cover timestamp. Re-selecting already attached files does not falsely exceed the ten-file limit. A reset clears the caption editor and gives the next plan a future delivery time.
- A network check returns the newest accepted state when an older response is discarded; an old success cannot open a stale origin.
- Confirmation copy reflects selected destinations. TikTok Inbox Upload is explicitly a handoff; the completion screen remains visible with a caption-copy action when manual completion is needed.
- Added a shared, process-safe maintenance lease for backup/restore, network changes, runtime replacement, reviewed submissions/caption revisions, planner runs, Status delivery and cleanup. Same-operation nested helpers share the lease; competing operations cannot overlap. Updates check live Status, publishing and backup tasks before downloading or replacing code. Dead/completed backup records do not block future updates.
- Prevented synthetic operation tests from appending to live publishing logs. New planner/maintenance tests use disposable data and no social posts.
- Current checks: 169 script tests and 44 JavaScript tests passed; rerun all suites after the remaining passes. No live tunnel rotation, data restore, uninstall or social test publication was performed.

Next passes: backup progress retry/resume; retention and advanced preferences; lifecycle controls; current Rust uninstall paths; full UI fixture and keyboard/responsive/accessibility checks; Telegram/WhatsApp interaction review; corrected current documentation; final release/package validation.

## Backup, preferences and update follow-up

- Backup progress now retries transient bridge errors, holds the original task reference on repeated failure and exposes Resume progress. Reopening the assistant discovers live detached work without saving its passphrase or original request. An inspected backup still requires a newly entered passphrase, old-host confirmation and explicit restore approval.
- Restore/backup and maintenance use a shared lease. Publisher, caption and Status work cannot overlap destructive service changes. Tests verify nested same-operation use and exclusion across competing threads.
- Rust preferences now expose the retention window (30-day default), an optional default business hashtag and local-model selection in Advanced, with installed-model discovery. Saving touches only those three portable .env keys, performs no deletion and leaves reviewed captions/queued audiences intact. New bot caption requests read the changed caption defaults without changing bot identity.
- WhatsApp/Telegram preference writes also use the shared lease to avoid racing restore or network configuration.
- Service update results now explain pinned compatibility rather than implying arbitrary upstream versions were installed. A failed Evolution upstream check is incomplete, not “current.” Active backup/migration blocks update installation and runtime replacement.
- macOS uninstall helper now recognizes the current Rust app bundle, checks bundle identity before removal, stops the host agent, includes Rust settings in explicit data purge, and preserves Git source checkouts. Dry-run verified with disposable private files; actual machine uninstall was deliberately not executed.
- Current checks: 175 Python script, 21 service and 52 JavaScript tests passed. Native packaging and the complete UI exercise remain pending after the rest of the audit.

Local bundle observation: `~/Applications/PostForge Desktop.app` reports **rc.41** (`local.postforge.desktop`), while source/release baseline is rc.45. Source fixes are not proof of installed UI behavior. Validate and install a matching tested package at the end only when no delivery/backup is active; do not claim an upgrade until the installed bundle, signature and restart are observed.

Official prerequisite sources verified during the audit: [Python Windows](https://www.python.org/downloads/windows/), [Docker Windows](https://docs.docker.com/desktop/setup/install/windows-install/), [Docker Linux Engine](https://docs.docker.com/engine/install/), [Ollama Windows](https://ollama.com/download/windows). These informed the OS-specific links in the requirements screen.

## Local caption and agnostic-service review

Two fictional, local-only Ollama samples exposed invented details (a laptop brand and a location hashtag). Generated captions now get a bounded local editing pass, followed by conservative named-detail/numeric checks and at most one repair. This reduces those observed mistakes; it does not establish that generated copy is factually infallible, so the human review remains required. Exact words bypass generation. The editor uses the configured local model, never Google AI.

Removed business-specific delivery-emoji substitutions and preserved multi-codepoint emoji clusters, flags and skin tones. Context checks for known topic-specific emojis remain. The original caption path also had a duplicate prompt construction and excessively long individual HTTP waits; duplicate work is removed and generation/editor calls are bounded. Verify final latency and unloaded-model state in the final evidence section.

Google’s current [thumbnail API reference](https://developers.google.com/youtube/data/reference/rest/v3/thumbnails/set) explicitly includes Shorts, so the existing thumbnail request path should not be removed based on outdated platform advice. Actual final rendering on the user’s channel remains a platform acceptance check; this audit did not publish another video to test it.

Checkpoint: source version is now **rc.46 (unreleased)**. Latest complete source checks: **178 Python script, 21 service, 52 JavaScript** tests, plus static recheck. The actual local repair-service caption completed in 6.12 seconds without an invented named brand; Ollama `/api/ps` reported zero loaded models afterward. No social post was submitted. The installed app is still rc.41; final publication/install/acceptance checks remain pending.

The native developer override now takes precedence over saved recovered-workspace settings, allowing isolated UI acceptance against a disposable installation. Validate that route in the upcoming full UI pass. New public modules must be tracked before packaging because the Runtime manifest uses Git's tracked-file allowlist.

## Final source validation · rc.46

- 185 backend tests, 21 v2 service/Telegram tests and 59 JavaScript tests passed. Rust release build completed locally in 49 seconds. Static syntax/version/private-file checks pass; final package and GitHub validation follow below.
- New service controls are wired through the actual Rust → Python bridge. Tests cover disabled profiles, preserved connector identity, queued-work refusal, explicit confirmation, pause markers and visible failures. Live read-only status verified Docker, Postiz and Evolution running with an empty queue. No start/stop was performed on the live stack as a test.
- Fixed a full-interface finding: unapplied caption edits no longer allow submission or version navigation. The editor has an accessible label and Apply/Cancel guidance. Cancelling restores submission; manual exact words remain distinct from generation.
- Broadened automatic WhatsApp staging retention to both owned upload folders. Applying cleanup shares the maintenance lease; a competing maintenance operation refuses deletion before scanning. Referenced Postiz uploads and pending plans remain protected. No user media was deleted in this audit.
- Offline help renders tables, strong text, inline/code blocks and safe official reference links with DOM nodes, without interpreting HTML. Documentation is consolidated around the current Rust workflow instead of appending contradictory Swift instructions.
- Complete UI assets were exercised against synthetic bridge data in the local browser: exact-caption → delivery → review, caption-only variants preserving metadata, manual-edit safeguards, Settings, EN/es-EC, preferences, service controls and offline Help. At 1024×700 and 820×600, primary actions stayed visible and body width did not overflow. The preview deliberately rejects publication and contains no private installation files.
- Live read-only overview confirmed connected WhatsApp, running Telegram, Postiz online, zero drafts/queue and no Status sends. This is operational reachability, not a new social publication test.

## Coverage and limits after review

| Feature | Acceptance evidence | Remaining external check |
|---|---|---|
| Requirements / runtime / PKG | Bootstrap and dependency regression suites; official platform links | Fresh physical Windows/Linux setup |
| Composer / exact text / caption versions | Backend replay/metadata tests, complete synthetic UI, editor and reset checks | User preference for generated copy; facts still human-reviewed |
| Media / covers / formats | Probe/orientation/splitting/signed-media tests and existing provider adapters | Final cover rendering and per-platform media acceptance |
| Scheduling / retries / cleanup | Reviewed-family idempotency, held uncertain sends, preview/confirmation tests | Actual provider delivery; no real posts submitted here |
| WhatsApp | QR/session/audience, callback safety, two-part/uncertain-send and receipt tests | Client-specific buttons and actual views beyond earlier user tests |
| Telegram | Owner-only callbacks, group rejection, migration hold, heartbeat settings tests | Real BotFather/account setup for a different installation |
| Public URL / account renewal | Provider rollback/callback/race tests and prior contextual-guide UI | Owned-domain DNS and future provider-console changes |
| Backup / restore | Encryption/authentication, request privacy, inspection/confirmation, detached progress/recovery tests | Physical destination + representative large backup; no live restore here |
| Updates / components | Channel/platform/digest/runtime tests; active-work guard | Package installation and final CI recorded below |
| Retention / uninstall | Referenced-media fail-closed tests, competing lease, disposable uninstall fixtures | No real machine uninstall/purge performed |
| Desktop / tray / help | Native build, standard template icon/sections, local responsive/EN/es-EC check | Final native reopen/help/update acceptance below |

Known capability gaps are now explicit in README/SETUP/help: no full fresh-business UI wizard; no Rust automatic OS wake/one-hour idle shutdown; dedicated legacy Siri shortcut integration not ported; no authorized Telegram groups; no portable GUI uninstaller; Windows/Linux in-place update remains a verified manual swap; Mac artifacts are ad-hoc signed, not notarized. These are not represented as working features. OS Open App shortcuts remain available. Release 2 is still a release candidate.

## Cross-platform release gate

The rc.46 Windows job correctly stopped publication: a new preference test asserted POSIX `0600` mode bits on Windows, where Python reports different native permission semantics. Fixed the assertion to check POSIX bits only on Unix while retaining all content/secret-preservation tests on Windows. Publishing continues as **rc.47**, preserving rc.46's tag rather than moving release history. No rc.46 GitHub release was published.

Native pre-upgrade check: the installed rc.41 opens a visible progress dialog, completes its manual check and correctly reports installed rc.41 / available rc.45 while the new release is still building. Closing the window and pressing Cmd+N reopens New Post successfully. No content was entered or sent. A live pre-existing temporary-hostname/configuration mismatch was detected and is being diagnosed separately from social account authorization.

## Native/package follow-up

- Locally generated portrait and landscape MP4 fixtures passed real FFprobe inspection, PNG cover extraction and invalid-timestamp rejection. Temporary media was removed; no persistent preview copies or social posts were created.
- The complete rc.47 ZIP bootstrapped a fresh disposable private runtime, opened the Spanish offline guide, included the new service/maintenance modules and retained a valid sealed app signature without `.pyc` writes. The destination path was resolved to avoid macOS's `/var` symlink alias; the installer intentionally rejects symbolic-link installation paths.
- Package contents/checksums were inspected: macOS ARM64 PKG, EN/es prerequisite introductions and checks, official links, public runtime only. ZIP and PKG are approximately 4.2/4.1 MiB. The app has valid ad-hoc signing; the PKG has no Developer ID signature/notarization.
- Recovered a pre-existing live temporary-hostname mismatch by synchronizing the **existing** connector with `rotate=False`. The same connector URL was verified before/after, protected public access became reachable, synchronization was complete and the bot agent reloaded links. No new random address was requested and no social account was disconnected.
- Native inspection exposed tray About using the backend's source version. Fixed it to query a fixed native app-version command, independently from Postiz availability. A regression test covers a differing backend and an offline backend. Final source/release is **rc.48**, including the rc.47 Windows assertion fix. The complete JavaScript suite now has **60 passing tests**.

## Windows runtime refresh correction · final candidate rc.49

Release rc.48 passed all three platform builds and published eight assets. Before installing locally, the remaining fresh-host review identified a runtime portability issue not exercised by compilation: a configured Windows update invoked host Bash. Added a fixed Python refresh path for Windows under the parent installer maintenance lease. It leaves stopped/Docker-unavailable deployments stopped, reloads active receivers against the updated code, recreates non-tunnel services and preserves the connector. Tests cover command routing without Bash, private-file preservation, lease presence, stopped-stack preservation and active receiver/container refresh. The Windows manual client-swap limitation remains; this fixes the backend refresh afterward. Final candidate is **rc.49**. No earlier tag was moved or release removed.

The 64 MiB encryption envelope round-trip matched SHA-256 after decrypting, with approximately 2 MiB Python traced peak memory. This verifies streaming encryption/authentication, not an actual large destination database restore. Idle observation found zero loaded Ollama models; the live stack still consumed roughly 1.5 GiB across its containers, with Postiz the largest component. Explicit service stop is available; automatic Rust idle/wake policy remains a known gap.

## Final release and installed evidence

Release commit: `fa2860a` (documentation-only handoff may follow on main). All rc.49 workflows completed successfully:

- [Publish desktop release](https://github.com/isaacmateosv/postforge/actions/runs/43709330881)
- [Rust desktop client](https://github.com/isaacmateosv/postforge/actions/runs/43709329080)
- [Validate and package · branch](https://github.com/isaacmateosv/postforge/actions/runs/43709329053)
- [Validate and package · tag](https://github.com/isaacmateosv/postforge/actions/runs/43709330826)

Eight assets are uploaded: Mac ARM64 PKG/ZIP, Linux x86_64 ZIP, Windows x86_64 ZIP and four checksums. The installed app matches the final version, its EN/es-EC Help files match the release source, full legal notices are present, and the matching configured service refresh passed after transient startup HTTP 502 responses. The existing connector survived the refresh. Final read-only renewal completed with all five channels connected and no incomplete checks. No preview server remains listening on the temporary audit port.
