# PostForge — Work Progress & Resume State

## Current development state · 2026-11-12

rc.38 preserves the running temporary tunnel during service refresh, permits exact-caption operation without Ollama, and corrects platform assumptions in the new CI fixtures. The first complete installer release is rc.39; rc.37/38 publication was blocked by test-fixture failures on other platforms.

rc.37 fixes the fresh-destination ZIP packaging gap: public backend code now travels with the app and bootstraps privately. A real empty-host import inspection passed via the actual bridge and detached worker with no .env or checkout (88 tables, 224 rows, 72 media files, gateway and Telegram state). A macOS Rust product .pkg is now built with localized requirements instructions and tool-presence warnings. In-app readiness checks are bounded and read-only. Manual Updates shares/queues startup checks without vanishing; running-app version is authoritative. Runtime updates preserve private paths, save changed public code and refresh services. Services may need recovery if refresh fails; no successful live destination cutover is claimed here.

The rc.36 Help follow-up opens documentation directly, shows loading/errors inside the Help dialog and rejects stale responses across guide switches.

The rc.35 backup UX correction addresses a real import-navigation failure: Advanced selected installation folders, Restore was hidden in a mode selector, mode changes left an old Complete result visible, and Enter did not start inspection. Settings now exposes Create/Restore directly, the assistant has explicit action buttons and its picker/stage reset follows the selected action. Regression tests exercise selection, Enter, visible failure recovery and the no-restore-before-confirmation boundary. A real encrypted round-trip plus disposable Postgres restore rehearsal passed with 88 tables, 224 rows and 72 media files (1,313,912,104 bytes), including gateway and Telegram settings. No live restore was applied.

The supported desktop client is the Rust/Tauri app in `desktop/`. The Swift tray and Publish Machine app instructions below are historical; do not launch or reinstall those clients. Use `VERSION`, the current source, local installed bundle metadata and GitHub Actions to establish current publication/installation state.

The rc.32 work adds persistent next-step actions, successful cover-preview feedback, cancellable completion navigation, monitor-aware sizing, sectioned tray menus and clearer on-demand token renewal. Authelia provisioning now defaults to 30 minutes of inactivity, preserving MFA and the two-hour session maximum; encrypted migrations retain configured session preferences.

Telegram Settings / `/settings` exposes owner-only ping interval controls without discarding a posting plan or restarting the worker. WhatsApp settings are explicit standalone `postforge settings` / `postforge ajustes` / `postforge ping ...` commands; no inferred or persistent settings mode is used, and pending media is not consumed. Only the interval is changed in the private `.env`; identity, enabled state and migration hold remain untouched. No test ping is sent. The live worker must be reloaded after code updates; avoid interrupting an active WhatsApp send.

The rc.33 work adds optional WhatsApp reply buttons for plan review, caption revisions, explicit settings and confirmation before approval/discard. Tokens are owner-bound, expire, reject changed plans and cannot be reused. Text commands remain available. A narrow, tested wire-format backport runs after the existing Status patch on the pinned Evolution image. The original self-chat probe was accepted by the API but invisible on the phone. After the backport, the user confirmed the corrected card was visible, tapped it and received the acknowledgement (2026-11-12). This verifies rendering and reply routing in the linked self-chat; no real post or setting was changed.

The rc.34 follow-up replaces the remaining Unix-only WhatsApp intake lock with the existing cross-platform helper after Windows CI caught its import failure.

Validation: 159 Python script tests, 21 service/Telegram tests and 31 JavaScript tests pass. Native macOS release packaging passes. Cover image/frame selection and persistent action navigation were checked in the actual app using disposable media without creating or scheduling posts. Validate new release assets in Actions before declaring publication complete. The current public hostname lives in `.env`, never in this progress file. A forgotten Quick Tunnel was recovered and all origins synchronized; never rotate a tunnel while posts are queued or sending. OAuth callbacks must use the current hostname for future reconnects.

The guides in `docs/help/` (English and Ecuadorian Spanish), README and CHANGELOG describe the current workflow. The remainder of this file is an archived development ledger, retained for historical context.

## Historical status board

| # | Task | Status |
|---|------|--------|
| 0 | Inspect stack, logs, sources | DONE |
| 1 | WhatsApp status: diagnose + fix + image/video | DONE. Both 06:17/06:30 test statuses arrived on the test phone (you confirmed). Viewer receipts now recorded (row 8) |
| 2 | Bake Postiz cookie patch into `publish-machine.sh` | DONE (verified live: Set-Cookie has no Domain=) |
| 3 | `create-draft.sh` → Postiz DRAFT | DONE + E2E verified on a temporary channel |
| 4 | `analyze-media.sh` (Gemini) → Postiz DRAFT | DONE + E2E verified (staged after two HTTP 503 retries) |
| 5 | Verification + docs (README.md, this file) | DONE |
| 6 | Migrate to the bakery's 8 GB MacBook Air M1 ([DEPLOY-M1.md](DEPLOY-M1.md)) | Phase A (test here) in progress. Phase B tools (§5) BUILT + rehearsed: doctor, link-whatsapp, postiz-transfer, package, install. Gated by §4 |
| 7 | Menu bar app (on/off, waiting work, warnings, notifications): `tray/` | BUILT + running. Notifications allowed, Open at Login on (you). Offers "Allow Notifications…" if macOS blocks them. Still to try: Turn Off… → Turn On |
| 8 | Record who received/viewed each status | DONE and proven end to end: the test phone's view of test status #4 was recorded at 22:00 EC and shown by name in the menu bar |
| 9 | Postiz booting before Temporal (no scheduler worker) | FIXED: Temporal healthcheck + `start` verifies the worker (now matched to the running container) |
| 10 | Memory and speed for the 8 GB Air | DONE so far: containers 2.12 → 1.38 GiB (no Elasticsearch, no PM2 wrappers); start 19 s, stop 4 s; Docker VM 3 GB (you). Caption A/B run: Llama 3.2 3B 2.16 GiB vs 8B 4.67 GiB, 98% vs 93% of prompt rules with the new prompt. Next: your blind quality test, then pick `LOCAL_LLM_MODEL` |
| 11 | Gemini switched off (Google policy warning on your account, 2026-10-31) | DONE: `GEMINI_ENABLED=false` in `.env`. `analyze-media.sh` stops before sending, `test-ai.sh`/`caption-ab.sh` leave Gemini out, no retries on HTTP 429. Back on only with your OK |



### Session-1 script layout
- `scripts/lib/pmlib.py` shared helpers (env, http, multipart, psql, sips/ffmpeg normalizers,
  `Postiz` Public API client: integrations / upload / create_draft(type=draft hard-coded)).
- `scripts/broadcast-story.sh` → `lib/broadcast_story.py` (audiences test|vip|all|list|file,
  `--yes` interlock for all, `--dry-run`, `--history`, `--image/--video`, `--chunk-size`).
- `scripts/create-draft.sh` → `lib/create_draft.py` (Ollama keep_alive 0 → draft).
- `scripts/analyze-media.sh` → `lib/analyze_media.py` (inline ≤15 MB images, Files API for
  video; JSON schema output; `GEMINI_THINKING_LEVEL` default low, auto-fallback).
- `scripts/test-ai.sh` updated (real generation on both backends, key in header).
- Postiz Public API base: `http://localhost:4200/api/public/v1`, header `Authorization: <Organization.apiKey>`.
- Gemini latency is API-side: 40–145 s per request on this key even for trivial prompts.

### Applied changes (all originals backed up in `backups/2026-10-30-pre-finish/`)
- `docker-compose.yml`: Redis AOF + volatile-lru; Evolution `depends_on` (postgres/redis
  healthy) + `./data/postiz-uploads:/media:ro`; postiz & evolution images pinned by digest.
- `.env`: `UPLOAD_DIRECTORY=/uploads`; added `GEMINI_MODEL`, `WA_INSTANCE`,
  `WA_TEST_RECIPIENTS`, `POSTIZ_LOCAL_URL`.
- `publish-machine.sh`: start|stop|restart|status|patch. `start` re-applies the cookie patch
  to 4 files (auth.controller, auth.middleware, users.controller [logout/showorg/impersonate],
  track.cookies) = 14 sites, restarts the pm-postiz container if the backend was already running
  (session 3: `pm2 restart` orphaned the old node process, see Gotcha #17).
- Redis AOF was enabled at runtime BEFORE recreate → Signal keys preserved (862 → 867),
  0 PreKeyErrors after Evolution recreate; migration no longer races Postgres.
- Oct-25 statuses show `PENDING` with 0 updates in `evolution."Message"`. That is NOT evidence:
  Evolution v2.3.7 never records status receipts (see Task 1 diagnosis), so every status stays
  `PENDING`. The bare-digit recipient list is the evidence that they reached nobody.
- Gemini: key OK; `gemini-2.5-flash` → 404 "no longer available to new users";
  `gemini-1.5-flash` retired; `gemini-flash-latest` works (→ gemini-3.8-flash).
- This 16 GB Mac is the **orchestrator** (it runs the real thing) until the go/no-go criteria in
  [DEPLOY-M1.md](DEPLOY-M1.md) §4 pass. Then production moves to the bakery's base MacBook Air M1
  (8 GB), which is also your video-editing machine: the stack must stay light and stop completely.

## Environment facts verified this session

- Docker Desktop 29.9.2, 4 CPUs, ~3.8 GiB VM RAM. Compose limits sum = 3264 MB.
- Host has `python3` 3.9.6 (no backslashes inside f-string `{}`), `jq` (/usr/bin/jq),
  `ffmpeg`/`ffprobe` (homebrew), `curl`. No `node` on host.
- Containers were **created Oct 26** and only *restarted* on Oct 30 → the hand-applied
  cookie patch is still present in `pm-postiz` (`domain: undefined` in auth.controller.js
  and services/auth/auth.middleware.js). A `--force-recreate` would lose it (Task 2).
- Ollama was NOT running at session start (stack had been auto-restarted by Docker Desktop).
- Evolution container runs `TZ=America/Sao_Paulo` → its log timestamps are BRT (UTC-3),
  host is UTC-5.
- WhatsApp session keys are stored in Postgres (`evolution."Session"`, 1 row) because the
  image's bundled `/evolution/.env` sets `DATABASE_SAVE_DATA_INSTANCE=true`
  (`CACHE_REDIS_SAVE_INSTANCES=false`). → Recreating `pm-evolution-api` is SAFE (no re-scan).
- Evolution contacts in DB: 1193 total, 1172 with pushName, 1168 `@s.whatsapp.net`, 21 `@lid`.
- `.env` bug found: `UPLOAD_DIRECTORY=/app/uploads` but the bind mount is
  `./data/postiz-uploads:/uploads` (Postiz's internal nginx serves `/uploads/` from `/uploads`).
  Uploads currently land in the container layer and are not served. Fix planned in Task 4.
- Evolution has no `depends_on` → on cold boot it races Postgres
  (`FATAL: the database system is starting up`, migration fails, container self-restarts).
- `config/postiz/nginx.conf` is a reference copy only (not mounted).

## Task 1 diagnosis (WhatsApp status)

- The 1,167-contact broadcast **did complete, after ~117 minutes**: "Sending message to
  status@broadcast" at 00:18:58 BRT → WebMessageInfo returned 02:16:02 BRT (Oct 26).
  Earlier sends: 1-contact test took 60 s; another took 240 s.
- Evolution v2.3.7 `sendMessage()` status path: splits `statusJidList` into batches of
  **10**, awaits batch 1, then runs the rest via `Promise.allSettled` (errors swallowed),
  reusing batch 1's message id, and only then answers HTTP → curl blocks for the whole fan-out.
- `allContacts: true` **replaces** `statusJidList` with every DB contact that has a pushName
  (`formatStatusMessage`). It is NOT on-demand key computation. Same cost as the full list.
- Baileys 7.0.0-rc.9: for `status@broadcast` sender-key memory is NOT used, so every status
  re-distributes the sender key to every device in the list (O(devices) per post).
- Baileys `getStream` accepts `data:` URIs, `http(s)://` URLs and local file paths →
  image/video statuses can use a path inside the Evolution container.
- Observed ≈60 s per 10-contact batch (117 batches ≈ 117 min) — matches Baileys'
  60 s default query timeout.
- Baileys wraps every `relayMessage` in `authState.keys.transaction(..., meId)` → a mutex
  keyed on the account id, so Evolution's "parallel" `Promise.allSettled` batches are in
  fact **fully serialized**: total time = Σ batch times.
- **ROOT CAUSE**: old `broadcast-story.sh` put **bare digits** (`<TEST_RECIPIENT>`) in
  `statusJidList`. Verified live in the container: `jidDecode("<TEST_RECIPIENT>")` → undefined,
  `jidNormalizedUser(...)` → `""`. Baileys therefore resolved **no recipient devices**
  (USync on empty JIDs), each batch stalled ~60 s, and no sender-key distribution was sent →
  those statuses most likely reached **nobody**. Fix: always send full JIDs
  `<digits>@s.whatsapp.net` (the schema regex `^\d+` accepts them; Evolution's own
  `allContacts` path uses full JIDs).
- **SECOND ROOT CAUSE**: with `CACHE_REDIS_ENABLED=true`, Evolution's
  `useMultiFileAuthStatePrisma` stores ALL Signal keys (pre-keys, sessions, sender keys,
  LID maps) in Redis hash `evolution:instance:<instanceId>` (db 1); only `creds` go to
  Postgres. Redis runs `--save ""` without AOF → every stop/start wipes every session and
  pre-key (seen: `PreKeyError: Invalid PreKey ID` on boot; 837 fresh pre-keys, 17 sessions
  after 7 min uptime). Fix: Redis AOF persistence + `volatile-lru` (the key hash has no TTL).
- **RECEIPTS ARE NEVER RECORDED (session 2)**: Baileys emits status deliveries/views as
  `message-receipt.update` (baileys/lib/Socket/messages-recv.js:865, group/status branch).
  Evolution's handler (whatsapp.baileys.service.ts:1927) only calls
  `updateMessagesReadedByTimestamp` (:4734), which touches `fromMe = false` rows, and its
  `messages.update` handler skips `status@broadcast` (:1599). A sent status therefore stays
  `PENDING` with 0 `MessageUpdate` rows, delivered or not. **Fixed in session 3** by
  `patches/evolution/status-receipts.js` (applied at container boot): receipts for our statuses are
  stored in `evolution."MessageUpdate"`; `--history` counts them and `--viewers <id>` lists them.

## Session 2 (2026-10-30): changes and findings

- **First test status sent** after your OK in chat: id `3EB0CAAB5768475E7E3B16`, text "Test 🥐",
  2026-10-30 06:17 EC, to <TEST_RECIPIENT> plus the bakery's own phone. It took 1.2 s (HTTP 201) with no
  Evolution errors; old bare-digit sends took ≈60 s per 10-contact batch. Phone confirmation pending.
- **Second test status, current-sales content** (the guaguas menu as text, background `#9C4A2F`):
  id `3EB0977B028ABCFE70E922`, 2026-10-30 06:30 EC, to <TEST_RECIPIENT> plus the bakery phone. It took
  0.8 s (HTTP 201) with 0 Evolution errors. Phone confirmation pending for both test statuses.
- **The bakery's own number is always added to `statusJidList`** (not counted as audience). Baileys
  fans a status out only to the devices of listed JIDs (messages-send.js:500) and skips just the
  sending device (Utils/signal.js:108). Without it the phone never gets the post: no My status
  entry, no viewer list, no delete from the phone.
- `create_draft.py` sends `num_ctx: 2048`: llama3 8B loads at 4.67 GiB instead of 4.92 GiB (measured).
- `broadcast-story.sh` requires `--yes` for every audience except `test` (vip, all, explicit lists,
  `--to-file`). Verified with the send stubbed out: `--to vip` is refused before anything is sent.
- **Your content rule** (memory `publish-machine-status-content-approval`): unsupervised test
  statuses to the test number are fine with current-sales copy (e.g. "¿Ya ordenaste tu guagua? 🍞").
  Any wider audience needs your OK on the exact content first. The guaguas images you showed were
  examples of acceptable content, not files on this Mac.
- **Social app credentials are missing from `.env`**, so no channel can connect yet (pending item 1).
- **Postiz sign-up is open on the public URL**: `DISABLE_REGISTRATION` is not set (pending item 10).
- 8 GB footprint (measured): containers ≈2.15 GiB (Postiz 1.37 GiB = 91% of its cap: backend
  540 MiB, orchestrator 449 MiB, Next.js 177 MiB, plus pnpm/PM2 wrappers; Temporal ES 376 MiB = 98%
  of its cap), llama3 8B 4.67–4.92 GiB, idle Ollama 20 MiB. With llama3 8B the Air peaks at
  ≈10 GiB (heavy swap); the lightweight path is estimated at ≈7–7.6 GiB. See [DEPLOY-M1.md](DEPLOY-M1.md).
- **New requirements (2026-10-30):** the Air is shared with video editing, so the stack must be light
  and fully stopped when not in use; and migration happens only after success is proven on this Mac
  (go/no-go criteria in DEPLOY-M1.md §4).

## Session 3 (2026-10-30 evening): menu bar app, receipts, start race

Your input: both test statuses arrived on the test phone, but you couldn't see who viewed them.
Video editing never runs at the same time as the stack. The Air should run on demand: turn on, publish,
turn off, and stay on only while posts are scheduled, with a warning if you turn it off while work
waits. You asked for a simple menu bar app (on/off, idle/active, a counter). Order: test on this M4,
then package, then install on the Air.

- **Viewers.** Evolution's manager has no viewer screen and no setting for it: v2.3.7 drops the receipts.
  - New `patches/evolution/status-receipts.js`: docker-compose runs it before Evolution boots. It adds
    one step to the minified `message-receipt.update` handler in `dist/main.js`. Receipts for statuses
    we sent are stored in `evolution."MessageUpdate"` (DELIVERY_ACK / READ per participant), and
    every receipt logs `pm-status-receipts: ...`. The patch is idempotent and always exits 0; if
    the code it expects is missing, the log says "NOT applied". Dry-run on a copy and `node --check`
    passed; the SQL was tested in a rolled-back transaction; it's live ("applied" after 3 boots).
  - `--history` has received/viewed columns: `n/a` before 2026-10-30 18:50, when the patch went live.
    `--viewers <id>` lists numbers and contact names. Output checked with fake rows (deleted).
  - **Test status #3** (unsupervised, current sales, test number only): id `3EB08BF293DA1EECFB3EE2`,
    18:53 EC, "¿Ya ordenaste tu guagua? 🍞✨ / Entregas: sábado 31, domingo 1 y lunes 2 de noviembre 🧡 /
    ¡Pide con anticipación!", 0.7 s. **No receipt in 40+ min**: phones seem to send none on delivery,
    only when the status is opened. Opening it on the test phone is the test (pending item 3).
- **`scripts/lib/machine_state.py`** (read-only; JSON for the app, a report for the CLI).
  - Reports state: off / starting / stopping / on / partial, and idle vs active.
  - Reports waiting work: scheduled posts (`Post.state = QUEUE`, overdue flagged) and jobs in progress.
  - Also: drafts, failed posts (24 h), the last status with views, and service health including the
    scheduler.
  - While off, it reads `run/schedule-cache.json` (refreshed by every poll and by `stop`). One poll
    takes ≈0.5 s.
- **Jobs in progress:** `pmlib.Job` writes `run/jobs/<kind>-<pid>.json` during status sends and draft
  runs. If Evolution is still relaying after a client timeout, the marker stays for a while.
- **`publish-machine.sh`** (new commands: `pending`, `state`, `stop --force`):
  - **`stop` guard:** it warns and asks if work is waiting; without a terminal it refuses (exit 3).
    Verified with a fake job.
  - **`start`:** opens Docker Desktop if needed.
  - **`stop`:** saves the schedule cache, and quits Docker Desktop only if `PM_QUIT_DOCKER_ON_STOP=true`
    (planned for the Air; left unset here).
  - **`status`:** shows the scheduler, the receipts patch and the waiting work.
- **Postiz workflow v1.1.2:** a scheduled post is a Temporal workflow sleeping until `publishDate`. If
  the machine is off at that time, the post goes out **late**, as soon as the stack is back. The
  guard, the menu bar app and the docs say so.
- **Start race (found on cycle 1).**
  - Postiz booted before Temporal accepted connections. Its backend stayed at HTTP 502 for 4+ min. Its
    orchestrator logged "Failed to create worker connection" yet reported started, so **scheduled
    posts would never have published**, silently.
  - `pm2 restart` then orphaned the old orchestrator node process, which held :3002 (EADDRINUSE
    restart loop, 15 restarts in 10 s). `docker restart pm-postiz` fixed it.
  - Permanent fix: the Temporal healthcheck (`temporal operator namespace describe -n default`),
    Postiz `depends_on: service_healthy`, and a `start` step that checks a worker polls Temporal's
    `main` queue and restarts pm-postiz once if not.
  - **Cycle 2: start in 50 s (was 4 min 18 s), scheduler ✔, cookie patch ✔, WhatsApp `open`
    with no re-scan.**
- **Bug that predates this session:** `ollama list | grep -q` under `pipefail` always failed (SIGPIPE,
  exit 141), so every `start` re-pulled the llama3 manifest. The layers were already local, so nothing
  big downloaded, but an offline start would have aborted. Now it uses a here-string.
- **Menu bar app** (`tray/PublishMachineTray.swift`, built by `tray/build.sh` → `tray/build/Publish
  Machine.app`, arm64, macOS 13+, ad-hoc signed, ≈12 MB physical footprint):
  - **Menu bar icon:** a paperplane plus the number of items waiting.
  - **The menu shows:**
    - On · Idle / On · Active / Off, and Postiz / Scheduler / WhatsApp / Tunnel ticks;
    - scheduled posts (a submenu), next post, sends in progress, drafts, failed posts, last status
      views;
    - Turn On / Turn Off…, Open Postiz / Evolution / Log;
    - toggles: keep awake, reminders, Open at Login.
  - **Turn Off with work waiting:** a warning dialog whose default button is "Keep Running".
  - **Mac shutdown or log out with work waiting:** the app cancels it with a dialog ("Cancel Shutdown"
    is the default button).
  - **Notifications:**
    - turned on;
    - turned off with work waiting (with a Turn On button);
    - everything sent;
    - a post failed;
    - scheduler stopped;
    - WhatsApp disconnected;
    - a reminder before a scheduled post while off (30 min).
  - **Keep awake:** it holds an idle-sleep assertion while work waits (closing the lid still sleeps).
  - **Verified:**
    - `--dump-menu` against the live stack and against fake on/off states;
    - the Finder-launched app polls every 30 s;
    - both cycles ran the same commands the app runs.
  - **Not yet clicked:** its own Turn On/Off buttons and the dialogs (pending item 12).

## Session 4 (2026-10-30 night): receipts proven, lighter and faster, phase B tools

Your input: you opened the 18:53 status on WhatsApp, but the menu bar didn't update. "Keep optimizing,
tell me what else to do; go as far as you can, then we do the supervised things together."

- **Why no receipt ever arrived (the real cause).** Baileys drops all `status@broadcast` traffic,
  receipts included, unless the instance setting `readStatus` is on (`shouldIgnoreJid` in Evolution's
  socket config; Baileys logs it at debug level, "ignoring receipt from jid"). Session 3's patch never
  got an event. Your view of the 18:53 status was dropped and can't be recovered.
  - The patch now also skips other people's statuses (`/*pm-skip-contact-statuses*/` at the top of
    the upsert loop), so turning `readStatus` on doesn't store every contact's status or fetch a
    profile picture per status. In v2.3.7 `readStatus` has no other effect: its "mark statuses
    read" branch compares a message id with "status@broadcast" and never runs.
  - Receipts name people by LID (`…@lid`). The patch stores the phone number from Baileys'
    `lidMapping.getPNForLID`; `wa_settings.py` resolves leftovers from Redis
    (`lid-mapping-<lid>_reverse`, a doubly JSON-encoded string).
  - The patch now re-applies from `dist/main.js.pm-orig` on every boot, so a plain restart picks up
    new patch versions.
  - **Test status #4** (unsupervised, current sales, test number only): id `3EB0BAAAAC3D6D03C9081B`,
    20:38 EC, "🍞 ¡Guaguas recién horneadas! ✨ / ¿Ya ordenaste la tuya? / Entregas: sábado 31, domingo 1
    y lunes 2 de noviembre 🧡". Within seconds: a READ from the bakery phone (its own copy, never
    counted) and a DELIVERY_ACK from the test phone ("Mateo Sarzosa"). A view by the test phone is
    still to come (pending item 3).
  - `wa_settings.py` (run by `start`) keeps `readStatus` on only while the patch is applied;
    `status` shows "Status receipts: recorded".
- **Menu bar app:** the "Last WhatsApp status" item has a submenu: the text, received/viewed counts,
  and up to 15 viewer names. Opening the menu triggers a fresh check.
- **Postiz without PM2** (`patches/postiz/run.sh`, README Gotcha #19). Ten idle wrapper processes held
  ≈300 MiB private memory (measured with smaps_rollup). The runner starts the three apps directly,
  applies the cookie patch at boot (no more restart in `start`), and uses the image's Prisma 6.5.0
  instead of `pnpm dlx` (which re-resolved Prisma online at every boot). Crash → container exits →
  Docker restarts it; tini forwards SIGTERM. Tested with stand-in apps (stop in 1 s, crash → exit 1)
  before going live. Evolution runs `node dist/main` directly too (−21 MiB npm wrapper).
- **No Elasticsearch** (README Gotcha #20): Temporal keeps visibility in Postgres
  (`temporal_visibility`). Temporal had 0 workflows, so nothing was lost; ES was never persisted
  anyway (no volume). The first start failed: Postiz's backend couldn't register `postId` because
  Temporal's 7 sample attributes held 2 of the 3 Text slots. Fixed with
  `SKIP_ADD_CUSTOM_SEARCH_ATTRIBUTES=true` and a one-time removal of the samples. Postiz's
  `postId="…" AND ExecutionStatus="Running"` query works.
- **Measured:** containers 2.12 → 1.38 GiB (Postiz 1.24 → 0.91, ES 0.38 → 0, Evolution 158 → 111 MiB);
  cgroup peaks: Postiz 1.33 GiB at boot, all far below caps, 0 OOM events. Full `start` 19 s (50 s
  this morning, 4 min 18 s yesterday); `stop` 4–5 s.
- **Also:** Evolution `LOG_LEVEL=ERROR,WARN,INFO,LOG`, `LOG_COLOR=false`; json-file log rotation
  (10 MB × 2) on every container; `start`/`stop` use `--remove-orphans`; the scheduler check only
  counts the running container's worker; `pmlib.http` turns dropped connections into a normal failure
  (the menu bar app logged a traceback during a restart).
- **Done from the pending list (no decision needed):** `DISABLE_REGISTRATION=true` (Postiz then allows
  sign-up only while no organization exists; yours does), `chmod 600 .env` (a pre-change copy is in
  `backups/2026-10-30-receipts/env.bak`, also mode 600), Evolution log level.
- **Phase B tools (DEPLOY-M1.md §5), built and rehearsed here:**
  - `./publish-machine.sh doctor`: passes;
  - `scripts/link-whatsapp.sh`: a throwaway instance got a QR, then was deleted; the real link was untouched;
  - `scripts/postiz-transfer.sh export|rehearse|import`: the rehearsal restored 88 tables with identical
    counts into a throwaway database, then dropped it; the test export was deleted (it holds account data);
  - `.env.example`;
  - `caffeinate -i` in the three send/draft wrappers;
  - `scripts/package.sh` + `install.sh`: an 84 KB bundle, no `.env` or data; `install.sh --check` in a
    throwaway copy built the app and passed `doctor`; the copy and its temporary `.env` were deleted.
- Backups of everything changed: `backups/2026-10-30-receipts/`.

## Session 5 (2026-10-30 late evening): views proven, 3 GB Docker VM, caption A/B

Your input: views work; the Docker VM cap is at 3 GB; you couldn't find "quit Docker on Turn Off"
in Docker's settings; you didn't see Turn Off / Turn On / Open at Login in the menu; the ngrok
login/logout check passed; you're creating the social apps now; OK to download a 3B model.

- **Test-phone view recorded:** status #4 viewed at 22:00 EC ("READ … from <TEST_RECIPIENT> … stored"),
  `--viewers` and the menu bar name "Mateo Sarzosa". Go/no-go item ticked (DEPLOY-M1.md §4).
- **Docker VM 3 GB** (you, 22:19 EC): the VM reports 2.83 GiB; containers came back with 0 OOM kills.
  Postiz used 1.12 GiB right after your login/logout (anon 974 MiB, cap 1.5 GiB); Temporal hits its
  384 MiB cap only with page cache (anon 126 MiB), which the kernel reclaims, no OOM.
- **Menu bar app:** the menu was right; it shows only the action that applies (Turn Off… while on).
  Open at Login was already on (BTM: enabled, at `tray/build/…`), notifications allowed. Added
  "Allow Notifications…" when macOS blocks them, and `--dump-menu` prints the permission state.
- **Docker Desktop stays running on Turn Off** (your call: other containers may be running). I had
  set `PM_QUIT_DOCKER_ON_STOP=true` after your note; it's back to `false`, here and in the Air plan.
  `stop` now says Docker Desktop was left running (the banner used to claim "100% RAM reclaimed").
- **Evolution log times:** the image runs on `America/Sao_Paulo` (logs 2 h ahead of the bakery);
  compose now sets `TZ=America/Guayaquil`, applied at the next start.
- **Meta setup notes corrected** (DEPLOY-M1.md §6, from Postiz's provider docs): a Development-mode
  app's Facebook posts are visible only to app roles, so the app must go Live; Instagram standalone
  needs the account added as Instagram Tester.
- **Caption A/B** (`scripts/caption-ab.sh`, results in `logs/caption-ab/`): 12 topics (8 Spanish,
  4 English; the guagua ones from the bakery's own statuses), the drafting script's prompt and
  options, each caption loading the model fresh as real drafts do.
  - Round 1, original English-only prompt: llama3 8B median 9.8 s, prompt rules met 87%;
    Llama 3.2 3B median 3.9 s, 64%. In Spanish the 3B copied the prompt's English call to action,
    used English hashtags and made agreement errors ("nuestro delicioso guaguas rellenos"). Gemini
    met every rule but took 42–241 s per caption with repeated HTTP 503s (6 of 12 done when stopped;
    log in `logs/caption-ab/round1-original-prompt.log`). The 8B wrote "Navidad" for guaguas.
  - Prompt trial on the 3B: a Spanish prompt alone (74%) stopped the English but the 3B parroted
    the instruction ("Queremos que nos visiten…"); a Spanish prompt with one example post, a
    no-invented-facts rule and hashtag tidying reached 93%.
  - `create_draft.py` now uses that prompt (Spanish gets its own; other languages the English one)
    and `finish()`: strips English/Spanish preambles and wrapping quotes, drops `____` lines, puts
    hashtags on one line after a blank line, max 8, no repeats. Pre-change copy:
    `backups/2026-10-30-session5/create_draft.py`.
  - Round 2, new prompt (`logs/caption-ab/20261030-2250.json`): Llama 3.2 3B **98%** of the
    rules, median 4.1 s per caption (41 tokens/s, loads in 0.5 s), **2.16 GiB** on the GPU; llama3
    8B 93%, 9.7 s (19 tokens/s), 4.67 GiB. The 3B still slips in Spanish now and then ("La
    guaguas", "vosotros", 🎃 for Día de Difuntos), so quality is your call: blind test next.
    Gemini (`gemini-3.8-flash`) in round 2: 4 of 12 captions, 88–246 s each (median 200 s), all
    four meeting every rule. Topic 1 failed after three "high demand" 503s, topic 4 timed out at
    300 s, and topics 7–12 got HTTP 429 "You exceeded your current quota": these runs used up the
    key's quota, so `analyze-media.sh` fails the same way until it resets (Google resets daily
    quotas at midnight Pacific time, 02:00 in Ecuador). The blind test is local only (8B vs 3B).
  - **Caption Taste Test** (blind, private artifact): https://claude.ai/artifact/Daq4eMtqHyBXBfhPgM3DEk.
    For each of the 12 topics you pick A or B (letters shuffled per topic) or tick "Wouldn't post".
    Picks save to the page's `picks` collection (doc per topic: `choice`, `choiceEngine`,
    `unusable`, `note`); read them with ArtifactData `list`. Built from round 2's results by a
    one-off script in the session scratchpad (not part of the project).
  - **Your verdict on test 1** (copy: `logs/caption-ab/taste-test-round2/picks/`): picks 8B 4,
    3B 3; "wouldn't post" 8B 7, 3B 5; on 5 of 8 Spanish topics you rejected both. Your notes set
    the brand rules (now in the prompts, and in memory):
    - Alma Dulce has **no shop**: orders only, which customers **retiran** (pick up) or receive
      through an **Uber** courier. Never "visit us", a shop, or a neighborhood.
    - **Premium voice:** avant-garde gourmet pastry and a premium, person-centered experience at
      relatively low prices. Everything should sound classy.
    - **Ecuadorian / Latin American Spanish:** no "vosotros" or Spain's phrasing ("deliciosos
      tratados"); say "retirar", not "recoger"; never call the products "dulces" (in Ecuador
      that means candy).
  - Rounds 3–5 (`logs/caption-ab/20261030-2351.json`, `-2357`, `20261031-0001.json`):
    - With the facts in the prompt, both models still got the call to action wrong. So
      `create_draft.py` now adds it as fixed text ("Haz tu pedido por WhatsApp y retíralo o
      recíbelo con Uber." / "Order on WhatsApp, then pick it up or have it delivered by Uber.";
      `.env` `CAPTION_CTA_ES` / `CAPTION_CTA_EN` replace it). It also adds the brand hashtags.
    - The model writes 1–2 sentences plus topic hashtags. It gets two examples instead of one
      (the 3B had copied the single example verbatim), and runs at temperature 0.5 (0.7 gave "se
      desploman por la ciudad").
    - The script drops the model's own ordering sentence and strips Halloween emojis
      (🎃👻🕷️ appeared for Día de Difuntos). The A/B gained a "fits Alma Dulce" check.
    - Round 5: 3B 99% of checks, median 2.8 s; 8B 97%, 7.9 s. Remaining slips: the 3B
      repeated a sentence (topic 5); the 8B wrote "un delicia" and dropped "¡".
    - Pre-change copies: `backups/2026-10-30-session5/`.
  - **Taste test round 2 published** at the same link (version 2): round 5's captions, saved
    to `picks-2`, with separate browser storage so round 1's reveal doesn't un-blind it.
- **Meta app:** "Other" wouldn't select (Meta is retiring it), so DEPLOY-M1.md §6 now uses the use
  cases "Manage everything on your Page" + "Manage messaging & content on Instagram". It lists the
  exact permissions this Postiz build requests, read from its provider code. `.env` has empty
  `FACEBOOK_APP_*` / `INSTAGRAM_APP_*` lines ready for the keys.
- **TikTok prepared** (you asked, 2026-10-31), from Postiz's `tiktok.provider.js` and `tiktok.dto.js`:
  - Postiz asks for six scopes and uses the redirect `…/integrations/social/tiktok`; steps are in
    DEPLOY-M1.md §6, and `.env` has empty `TIKTOK_CLIENT_ID` / `TIKTOK_CLIENT_SECRET` lines.
  - A post needs a video or photos. Videos must be `.mp4`: Postiz treats anything else as a photo.
    `create-draft.sh` now converts media (`pmlib.normalize_media`, moved from `analyze_media.py`)
    and refuses Instagram, TikTok or YouTube drafts without `--media`.
  - Drafts keep UPLOAD (inbox, finish in the TikTok app within 24 h, 5 waiting per day) until
    TikTok audits the app. `.env` `TIKTOK_POSTING_METHOD` / `TIKTOK_PRIVACY_LEVEL` switch to direct
    public posts afterwards (`pmlib.draft_settings`).
  - Photo posts make TikTok fetch from `…/uploads/` (URL prefix verification needed). Tested
    2026-10-31: ngrok's free plan gives browser user agents its warning page there, so photo posts
    may fail; videos are unaffected.
  - `docs/privacy-policy.md` and `docs/terms-of-service.md` are templates for the URLs TikTok's form
    and Meta's Live switch require (fill in the contact email, publish somewhere always on).
- **Instagram route changed** (2026-10-31, your screenshot): Meta says "API setup with Instagram login
  is not available for newer apps" and uses "Unified login". So Instagram connects through the
  Facebook app (Postiz "Instagram (Facebook Business)"): register `…/integrations/social/instagram`
  as a redirect URL, add its seven permissions, and keep `INSTAGRAM_APP_*` empty (DEPLOY-M1.md §6).
- **YouTube Shorts prepared** (you asked):
  - Postiz's `youtube.provider.js` needs `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`, eight Google
    scopes, the redirect `…/integrations/social/youtube`, and exactly one `.mp4` per post. Google
    Cloud steps are in DEPLOY-M1.md §6; `.env` has empty lines for the keys.
  - `pmlib.youtube_short()` refuses photos and detects Shorts (vertical or square, at most 3 min,
    rotation respected; tested on sample clips). The title gets " #Shorts".
    `selfDeclaredMadeForKids: "no"` is now explicit.
  - Caveat: API uploads from a Google project YouTube hasn't audited are locked private. Public
    Shorts from Postiz need the YouTube API Services audit; until then, publish from the YouTube app.
- **Facebook keys in, "client_id=undefined" fixed** (2026-10-31): Postiz reads `.env` only when its
  container is created, so `docker compose up -d postiz` loaded the keys (16 and 32 characters).
  Health after: API 200, cookie patch applied, scheduler polling.
- **Taste test round 2 verdict** (`picks-2`): picks 3B 5, 8B 3; you rejected both on 4 topics.
  - Most rejections were emojis (🍎 for figs, 🥭/🥔 for pan de yuca, 🍰 for guaguas, 💔 for Día de
    Difuntos, 🚚 for deliveries) or my topic wording ("every morning": you bake fresh the same day,
    not necessarily in the morning).
  - You liked the 3B's sensory descriptions and its seasonal hook.
  - Done:
    - **`LOCAL_LLM_MODEL=llama3.2:3b`**, also the default in `create_draft.py`, `test-ai.sh`,
      `publish-machine.sh` and `.env.example`.
    - Emoji guard: always-safe set plus food/occasion emojis only when named in the text; 🚚→🛵,
      💔→🤍; at most 2.
    - Filters for repeated sentences, sentences copying the prompt's rules (the 3B pasted "de 1 a 2
      frases cortas sobre el tema"), and morning-baking claims.
    - One retry when nothing usable is left. The prompts now say: baked fresh the same day,
      sourdough cared for daily.
  - Check run `logs/caption-ab/20261031-0942.json`: 3B 99% of checks, 2.9 s. Still for your review:
    "nos entregamos a las guaguas" on delivery topics.
  - A dry run of `create-draft.sh` produced a clean Spanish caption with the fixed order line.
- **Hands-free posting** (your core idea, 2026-10-31): drop media and say or type "publish this on X
  and Y at this time", optionally with a caption idea. Drafts land on the Postiz calendar at that
  time for you to review and approve. You chose both front doors.
  - **Engine built:** `scripts/plan-post.sh` → `lib/plan_post.py`.
    - Rules (not AI) read networks, days and times in Spanish and English, from the part before
      your idea, so dates inside the idea don't hijack the schedule. Tested on 16 sentences:
      "mañana por la mañana", "seis y media de la tarde", "ya tengo el video, el viernes".
    - Caption from your idea (3B + brand rules) or your exact text; per-network media checks; the
      Shorts check; one draft per network; `--dry-run` / `--json`; assumptions listed.
    - End-to-end dry run with stand-in channels: video → IG + TikTok + YouTube Short; exact text
      kept; photo → YouTube skipped with a warning.
  - **Door A built:** menu bar → **New Post…** window (drop or choose files, type or Dictate,
    Preview, Create Drafts, Open Postiz Calendar). `publishmachine://new-post` opens it, so a
    Shortcut or Siri can too. `--snapshot-new-post out.png` renders it for checks. Not yet tried
    by you, and not yet run against real channels (none connected).
  - **Siri (2026-10-31):** signed shortcuts `tray/shortcuts/Nueva publicación.shortcut` and `New post.shortcut`
    open `publishmachine://new-post` (link registered with macOS). Add each once by double-clicking.
  - **Door B (WhatsApp self-chat): built and live** (2026-10-31, `scripts/wa-inbox.sh` →
    `lib/wa_inbox.py`, started and stopped with the stack, `status` line, `logs/wa-inbox.log`).
    - It polls Evolution's `Message` table for your own chat (phone JID or LID from Redis); photos
      and videos from 10 minutes before the instruction go with it; media comes from
      `chat/getBase64FromMediaMessage`.
    - Voice notes: whisper.cpp 1.9.5 (Homebrew) + `data/whisper/ggml-small.bin` (SHA-1 verified),
      with a bakery vocabulary hint ("guaguas" was heard as "huaguas" without it).
    - It acts only on a network plus a time or posting verb, replies only to your own chat, never
      acts on its own replies, and quotes what it heard.
    - Offline simulation passed: a real Spanish voice note in WhatsApp's audio format (OGG/Opus) plus
      a waiting video → Instagram + TikTok for "vie 06 nov 18:00" with a caption from the idea;
      personal notes and old replies ignored. Transcription: Spanish ~1 s warm (9 s cold), English
      0.8 s, ≈0.85 GiB.
    - **Not yet tried with your phone** (together step: item 13). Plan engine fix: "Idea, …" with a
      comma (as speech transcribes) now counts as the idea.
- **TikTok form reviewed** (your PDF, 2026-10-31): Terms and Privacy URLs empty (the form's error), no
  platform ticked, no products or scopes, no review text or demo. The description "Automated publishing"
  works against review. Texts to paste are in `docs/tiktok-app-form.md`.
- **Platform setup help** (2026-10-31): your email is in `docs/privacy-policy.md` /
  `docs/terms-of-service.md`. Both gained the YouTube API Services clauses Google requires (YouTube
  ToS, Google Privacy Policy, revoke link). `docs/*.html` are formatted versions for pasting into a
  free Google Site (recommended over buying a domain). Meta's "Invalid Scopes" and "Can't load URL"
  have their fixes in DEPLOY-M1.md §6. YouTube: an OAuth client, not the API key you made (delete
  that); free.
- **Public pages live** (2026-10-31, your OK): `docs/site/` is a git checkout of the public repo
  `isaacmateosv/almadulce-bakery` (commits as `isaacmateosv` with GitHub's noreply address; pushes
  go through `gh` via a repo-local credential helper). GitHub Pages serves it at
  https://isaacmateosv.github.io/almadulce-bakery/ (HTTPS; checked byte-identical to `docs/site/`).
  The two policy pages gained a phone viewport tag. The identical `docs/*.html` copies moved to
  `backups/2026-10-31-site/`, so `docs/site/` is the one copy. `scripts/package.sh` leaves
  `docs/site/.git` out of the bundle.
- **Channel expiry warnings** (2026-11-01, your request): Facebook and Instagram tokens last 60 days
  and this Postiz build can't renew them. `machine_state.py` now reports each channel's expiry
  (cached for when the stack is off) and warns from `PM_CHANNEL_WARN_DAYS` (10) days ahead.
  - Menu bar: "⚠︎ Reconnect Instagram by …" opens the steps with Open Postiz (or Turn On and Open
    Postiz) and Open Guide. Notifications at the first warning, 7, 3 and 1 days, when it stops, and
    "works again" after the reconnect.
  - `./publish-machine.sh channels [--reconnect [network]]` lists the channels and guides the
    reconnect (opens Postiz, waits, confirms, refreshes the menu bar's cache).
  - Guides in `docs/reconnect/`: README (start here), meta, youtube, tiktok, whatsapp, app-keys,
    public-address. Checked with a forced 90-day window (menu dump and CLI); app reinstalled.
- **First five-channel try failed** (2026-11-01 18:36 EC): New Post → "Postiz POST /upload -> HTTP 500"
  (an image over Postiz's 10 MB limit; README Gotcha #23, now resized first, re-tested with a 44 MB
  PNG). The WhatsApp door had answered once (18:14), then every pass failed: with more than one
  message waiting, json_agg's line breaks split the psql output. Fixed (`::jsonb::text`), door
  restarted at 18:47 with the three stale requests skipped. Both need your retry.
- **HITL verified** (you asked): AI text reaches Postiz only through `pmlib.Postiz.create_draft`
  (type fixed to `draft`); no Postiz AI or auto-post keys are set. `broadcast-story.sh` no longer
  has a built-in default text (it used to send an English line when given none); it now refuses to
  send without your text or media. Its help examples no longer suggest a shop ("We open at 7am!").

## 2026-10-31 night: Gemini switched off

- Google emailed a Gemini "Policy violation alert" for your account (interfering with or disrupting
  Google's services). The cause is unconfirmed. Every Claude session on this Mac was checked: our only
  Gemini traffic was fewer than 100 ordinary API-key requests on 2026-10-30 (00:30–00:58 tests,
  22:32–23:13 caption A/B, which ended in HTTP 429 quota errors), none since, and nothing sends any
  automatically.
- At your request, Gemini is off: `GEMINI_ENABLED=false` in `.env` and `.env.example`, read by
  `pmlib.gemini_enabled`. `analyze-media.sh` stops before any work, `caption-ab.sh` and `test-ai.sh`
  leave Gemini out, and neither Python script retries a 429 any more. Originals:
  `backups/2026-10-31-gemini-off/`.
- Turn it back on (`GEMINI_ENABLED=true`) only with your OK.

## E2E verification (2026-10-30, temporary placeholder channel)

- Placeholder `Integration` row `pmverify-*` ('TEMP verify (agent, auto-removed)',
  instagram-standalone, fake token) was inserted, used, then REMOVED with its posts/media.
- analyze-media (Gemini 3.8 flash, Spanish + hint) staged a DRAFT after two 503 retries (~200 s).
- create-draft (Ollama caption + image upload) → Post row: state DRAFT, publishDate now+1h,
  group UUID from Postiz, creationMethod API, settings {post_type, __type}, image JSON.
- Public API GET /posts (same service the calendar uses) returned it as DRAFT.
- Media saved to data/postiz-uploads/YYYY/MM/DD and served HTTP 200 locally and via ngrok.
- Temporal: no workflow for the draft's postId (HITL guardrail holds).
- Even drafts are validated against provider DTOs → PROVIDER_DEFAULTS in pmlib.py.

### Cleanup of verification data — DONE 2026-10-30
Verification data was removed (Integration/Post/Media back to 0, uploads + logs empty).
For reference, the statements used were equivalent to:
```sql
-- run: docker exec -i pm-postgres psql -U postiz -d postiz
BEGIN;
DELETE FROM "Post"  WHERE "integrationId" LIKE 'pmverify-%';
DELETE FROM "Media" WHERE "organizationId"='2881f04d-1397-4931-b254-1f58cbf175ad'
                      AND "createdAt" >= '2026-10-30 05:50:00';   -- only the verification uploads
DELETE FROM "Integration" WHERE id LIKE 'pmverify-%';
COMMIT;
```
and delete the uploaded copies under `data/postiz-uploads/2026/10/30/` (bakery-sign test PNGs).

## Pending YOUR action (collected while running unsupervised)

1. **Create the social developer apps, then connect channels.** Postiz reads each network's
   credentials from `.env`, and none are set, so no channel can connect yet: `FACEBOOK_APP_ID/SECRET`
   (Facebook + Instagram), `INSTAGRAM_APP_ID/SECRET` (Instagram standalone), `TIKTOK_CLIENT_ID/SECRET`
   (+ `TIKTOK_BUSINESS_*`), `YOUTUBE_CLIENT_ID/SECRET`. Register redirect URLs on the production
   domain (`…/integrations/social/<network>`); details in DEPLOY-M1.md §6. Then Launches → Add
   Channel. Drafts need a channel. *(2026-10-30 22:40: you're creating the Meta apps; TikTok's
   steps are ready too.)* Both forms want privacy-policy and terms URLs: publish
   `docs/privacy-policy.md` and `docs/terms-of-service.md` somewhere always on first. After pasting
   the keys into `.env` (not in chat), recreate Postiz so it reads them: `docker compose up -d
   postiz` (a plain restart keeps the old values).
2. ~~Log in/out via the ngrok URL~~ Done 2026-10-30 (you): all fine.
3. ~~Open the 20:38 test status on the test phone~~ Done: viewed 22:00 EC, recorded and named.
4. Did <TEST_RECIPIENT> ever see the Oct-25 statuses? Analysis says they reached nobody. Only that
   person can say: statuses expire after 24 h, and Evolution's `PENDING` state cannot tell.
5. Before `--to all --yes` (1,166 contacts): consider a VIP list first. Unofficial clients
   posting to many contacts who may not have the bakery saved carries some ban risk.
7. Optional: Postiz's Next.js frontend also computes the cookie domain in some OAuth/social-login
   callback paths (compiled chunks, not patched). Email/password login is covered.
8. **Deployment decisions** for the bakery's 8 GB MacBook Air (multi-use, never running the stack
   while you edit; migration only after the go/no-go criteria pass here): DEPLOY-M1.md §3. Next is
   the caption engine (decision 2): judge **round 2** of the blind Caption Taste Test
   (https://claude.ai/artifact/Daq4eMtqHyBXBfhPgM3DEk, 12 topics, llama3 8B vs Llama 3.2 3B, your
   notes now in the prompt; picks save to `picks-2` and I read them), then I set `LOCAL_LLM_MODEL`.
   Round 1 is done (your notes became the brand rules). llama3 8B would push
   the Air to a ≈9–9.6 GiB peak (heavy swap); the 3B to ≈6.4–7.1 GiB.
9. ~~Docker VM cap 4 → 3 GB~~ Done 2026-10-30 22:19 EC (you). The VM reports 2.83 GiB; all six
   containers came back with 0 OOM kills. Now a week of normal use, watching `status`.
10. ~~Try `PM_QUIT_DOCKER_ON_STOP=true`~~ Decided 2026-10-30 (you): Turn Off must not quit Docker
    Desktop, since other containers may be running. The setting stays `false` on both Macs.
11. Elasticsearch is gone (session 4). If you'd rather keep it, say so: putting it back is a
    docker-compose change.
12. **Try the menu bar app** (the paperplane icon, top right; it is running now):
    - Notifications are allowed and **Open at Login** is on (both done; click Open at Login to undo).
    - The menu shows only the action that applies: **Turn Off…** while it's on, **Turn On** while it's
      off. Click Turn Off… (it stops this stack only; Docker Desktop keeps running), then Turn On.
      With nothing scheduled there's no warning; you get "is off" and "is on" notifications.
    - To see the warning, schedule a test post in Postiz once a channel is connected, then Turn Off.
13. **Try the WhatsApp door with your phone:** in your own chat ("Message yourself"), send a photo, then a
    text or voice note like "Instagram mañana a las 6 de la tarde, idea: rollos de canela". You should get a
    "🤖 Publish Machine" reply within ~15 s. Until a channel is connected it answers that the network
    isn't connected yet, which still proves the listening and voice parts.
14. ~~GitHub Pages for the TikTok URLs~~ Published 2026-10-31 (your OK): public repo
    `isaacmateosv/almadulce-bakery`, live at https://isaacmateosv.github.io/almadulce-bakery/ (plus
    `privacy-policy.html` and `terms-of-service.html`). Left for you:
    - TikTok: the URL prefix `https://isaacmateosv.github.io/almadulce-bakery/` is verified (file
      `tiktok3iSb8NDw49gg8kKKriRifPZ0tJE4o0Mr.txt`, served since 17:08 EC), and 2 of the 3 links with
      it. For the third (most likely the website link), set the website URL to
      `https://isaacmateosv.github.io/almadulce-bakery/index.html`, which is inside the verified prefix.
      Your retry's file (`tiktokDJnklOzof92OMHPaHxma2iO59uOHxicp.txt`) is on the site too, which
      covers a property under the same prefix. If that property is the bare
      `https://isaacmateosv.github.io/`, its file belongs in your personal site repo
      (`isaacmateosv.github.io`, untouched: needs your OK). Keep the files in `docs/site/`: TikTok
      may check them again. Steps: `docs/tiktok-app-form.md`.
    - Google: empty the three App domain links (the "google.com" error) and skip the logo.
    - Meta (optional until Live): Settings → Basic → Privacy Policy URL and Terms of Service URL.
15. **Meta channels: both connected** (2026-11-01 15:02 EC, through your Facebook account with full
    control of the Page; Postiz shows "Alma Dulce Bakery" for each). It took Postiz no longer asking
    for `instagram_manage_insights` (`PM_META_SCOPE_FIX`, Gotcha #21), an account with a role on the
    app, and `pages_read_user_content` added in Meta. Both tokens run until 2026-12-30 and can't
    renew themselves (Gotcha #22): the menu bar warns from 2026-12-20; steps in docs/reconnect/meta.md.
    - Instagram stats: send a screenshot of the Instagram use case's Permissions and features list;
      I set the insights permission's current name, then you reconnect Instagram once.
    - App settings → Basic: Privacy Policy and Terms URLs, data deletion instructions URL (the privacy
      page), a category; an icon if asked (a plain bakery logo, not the TikTok-styled one).
    - Before real posts: switch the app to Live.
16. **TikTok: connected** (2026-11-01, sandbox app "ADB TK Sandbox", account `tk.almadulce.bakery`;
    Postiz renews it daily). Still unknown: whether sandbox drafts reach the TikTok inbox and can be
    posted as Everyone. Item 20 tests it; if not, "TikTok assist" (docs/tiktok-app-form.md, "Staying
    in the sandbox").
17. **Second operator** (the Page's other owner/admin, who will run the Air): to connect channels with
    their own accounts they need a Meta Tester role, a Postiz login (sign-up opened briefly) and,
    while YouTube's consent screen is in Testing, a Google test-user entry. Steps: DEPLOY-M1.md §8.
    The migration itself doesn't need it: channels move with Postiz.
18. **Generic repo** (Phase 2, after go-live): DEPLOY-M1.md §11.
19. **YouTube (Shorts) and Threads: connected and verified** (2026-11-01, your word). YouTube renews
    itself (the Google app being verified means no 7-day Testing expiry); Threads renews itself too.
20. **End-to-end test, all five channels** (your step; nothing publishes without approval):
    1. Menu bar → New Post…: one vertical video under 60 s plus "Instagram, Facebook, TikTok, YouTube y
       Threads mañana a las 6 de la tarde, idea: …" → Preview → Create Drafts. Expect five drafts on the
       Postiz calendar, YouTube marked Short.
    2. Same by WhatsApp: in your own chat, a photo + a voice note "Facebook y Threads hoy a las 7 de la
       noche, idea: …" → the 🤖 reply within ~15 s, two drafts.
    3. In Postiz, open each draft, check the caption, approve one per network for a time 10 minutes
       ahead (TikTok: it lands in the TikTok inbox to finish there; YouTube: post it unlisted/private
       first if you prefer). Then check each network shows it.
    4. Siri: re-import tray/shortcuts/*.shortcut (delete the old ones first) → "New post" opens the window.
    5. Menu bar: Turn Off… with a post scheduled → the warning; Turn On → it goes out.

## Resume instructions

- Read this file, then continue the first task not marked DONE.
- Migration to the 8 GB Air: [DEPLOY-M1.md](DEPLOY-M1.md) (§3 decisions, §4 go/no-go criteria,
  §5 packaging tasks, §7 runbook). Nothing moves before every §4 criterion passes.
- Menu bar app: `tray/` (rebuild with `./tray/build.sh`, debug with
  `"$HOME/Applications/Publish Machine.app/Contents/MacOS/PublishMachineTray" --dump-menu`). It polls
  `scripts/lib/machine_state.py --json`. Runtime files live in `run/` (safe to delete while stopped).
- Source of Evolution v2.3.7 TS can be extracted from the `.js.map` files inside
  `pm-evolution-api` (`sourcesContent`), e.g. whatsapp.baileys.service.js.map.
