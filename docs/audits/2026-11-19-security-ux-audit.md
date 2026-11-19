# Security, workflow and UX audit · 2026-11-19 · 2.0.0

Scope: the repository and its full history, the local runtime, the desktop bridge, the gateway,
WhatsApp/Telegram control paths, and every desktop window.

## Repository and history

| Check | Result |
| --- | --- |
| Live secret values (16 from `.env` and gateway keys) searched in all 91 commits | Not found |
| Key/token patterns (cloud, Meta, Google, Telegram, ngrok, TikTok, JWT, private keys) in all 1,110 file versions | Not found |
| Commit identities | GitHub noreply address only |
| Personal contact address | Present only in five 1.0.x commits (privacy/terms drafts); removed from current files since 1.0.5 |
| Client business name and handles | Present in `PROGRESS.md` history; replaced with placeholders in 2.0.0 |
| Test phone numbers | Synthetic sequences (`5939912345…`) only |

Removing the historical occurrences requires rewriting public history; that is a separate,
owner-approved operation.

## Runtime and application

| Area | Finding | Status |
| --- | --- | --- |
| Network exposure | Postiz, Evolution and Temporal listen on `127.0.0.1`; databases are container-internal; the public path is the authenticated gateway | OK |
| Desktop window | Strict CSP (`script-src 'self'`, no remote content), `core:default` capability only, bridge operation allowlist | OK |
| Signed media | HMAC-signed, expiring, read-only paths; signatures verified before proxying | OK |
| Private files | Project folder is `0700`; `.env` and keys are `0600` | OK |
| Network recovery copies | Every switch kept a full `.env` copy and none were pruned (19 found) | **Fixed**: only the newest successful set is kept |
| Legacy upgrade folders | 13 old 1.x app bundles left in `run/` | **Removed** |
| WhatsApp control | Reads only messages the linked phone sends to its own chat; strangers cannot trigger work; SQL inputs are validated | OK |
| Telegram control | Single private owner (chat and sender must match); groups rejected | OK |
| Desktop updates | HTTPS + SHA-256 from the release, size-bounded, platform-checked; not signed with an owner-held key | Recommendation: add detached signatures (for example minisign) with an offline key |
| Facebook video upload | Postiz retried a non-idempotent upload, publishing a reel three times | **Fixed** (single attempt) |

## Messaging workflows

WhatsApp, Telegram and the desktop share one planner, so 2.0.0's media handling applies everywhere:
video above 5 Mbps is re-encoded before upload, separate Facebook video Stories are skipped on
temporary Cloudflare links (Facebook still shares each reel to the Page Story), and planner warnings
are relayed in both chat replies.

New controls: the WhatsApp window shows the linked profile and number and offers **Unlink this
phone** (Evolution logout, falling back to instance removal) for clean re-enrolment; the Telegram
window offers **Disconnect bot** (forgets token and owner, stops the receiver, removes the bot's
commands).

## Desktop UX

- One type scale (12/14/16/20/24/30 px) replaces 17 ad-hoc sizes.
- Filled buttons meet WCAG AA (≥ 4.5:1) at rest and on hover; form-control borders meet 3:1.
- Every window uses the same footer: secondary and disruptive actions on the left; Close/Done and
  the main action on the right, main action last.
- Healthy status reads green everywhere; yellow is reserved for attention.
- Background work shows a header activity pill, busy-notice and pressed-button spinners, and a
  scheduling animation with progress steps. Narrow windows keep all header buttons on one line.
