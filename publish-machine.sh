#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Publish Machine lifecycle CLI: start | stop [--force] | restart | status | pending | state | channels |
# patch | doctor | maintenance
# Bash 3.2 compatible (macOS /bin/bash). The menu bar app (tray/) drives the same commands.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Source environment (values must not contain spaces)
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

MODEL="${LOCAL_LLM_MODEL:-llama3.2:3b}"
POSTIZ_URL="${POSTIZ_LOCAL_URL:-http://localhost:4200}"
EVO_URL="http://localhost:8080"
WA_INSTANCE="${WA_INSTANCE:-status-engine}"
RUN_DIR="$DIR/run"
STATE_PY="$DIR/scripts/lib/machine_state.py"

# Gotcha #5: Postiz derives the cookie Domain from FRONTEND_URL via tldts, which yields
# ".ngrok-free.dev" (a Public Suffix), so browsers drop every cookie Postiz sets:
# login loop, logout that does nothing, broken org switch / impersonation.
# Rewriting the expression to `undefined` makes host-only cookies. patches/postiz/run.sh does
# this as pm-postiz boots; `start` checks it and only patches here if it is missing.
COOKIE_EXPR='(0, subdomain_management_1.getCookieUrlFromDomain)(process.env.FRONTEND_URL)'
COOKIE_SED='s/(0, subdomain_management_1\.getCookieUrlFromDomain)(process\.env\.FRONTEND_URL)/undefined/g'
COOKIE_FILES="
/app/apps/backend/dist/apps/backend/src/api/routes/auth.controller.js
/app/apps/backend/dist/apps/backend/src/services/auth/auth.middleware.js
/app/apps/backend/dist/apps/backend/src/api/routes/users.controller.js
/app/apps/backend/dist/libraries/nestjs-libraries/src/track/track.cookies.js
"

http_code() {
  curl -s -o /dev/null -m "${2:-5}" -w '%{http_code}' "$1" 2>/dev/null || true
}

# wait_for <label> <url> <timeout_s> <ok-code-regex>
wait_for() {
  local label=$1 url=$2 timeout=$3 ok=$4 waited=0 code=""
  while [ "$waited" -lt "$timeout" ]; do
    code=$(http_code "$url")
    if echo "$code" | grep -Eq "$ok"; then
      echo "      ✔ $label (HTTP $code)"
      return 0
    fi
    sleep 3
    waited=$((waited + 3))
  done
  echo "      ✖ $label not ready after ${timeout}s (last HTTP ${code:-none})"
  return 1
}

container_running() {
  [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || echo false)" = "true" ]
}

# wait_for_scheduler <timeout_s>: a Postiz orchestrator worker is polling Temporal
wait_for_scheduler() {
  local waited=0
  until python3 "$STATE_PY" --check-scheduler; do
    [ "$waited" -ge "$1" ] && return 1
    sleep 5
    waited=$((waited + 5))
  done
}

# Tells the menu bar app that a start/stop is in progress (removed when this script exits).
mark_lifecycle() {
  mkdir -p "$RUN_DIR"
  printf '{"action": "%s", "pid": %d, "since": %d}\n' "$1" "$$" "$(date +%s)" > "$RUN_DIR/lifecycle.json"
  trap 'rm -f "$RUN_DIR/lifecycle.json"' EXIT
}

# Starts Docker Desktop if its engine doesn't answer, then waits for it.
ensure_docker() {
  if docker info > /dev/null 2>&1; then
    echo "      Docker Desktop is running."
    return 0
  fi
  echo "      Starting Docker Desktop..."
  docker desktop start --detach > /dev/null 2>&1 || open -a Docker
  local waited=0
  until docker info > /dev/null 2>&1; do
    if [ "$waited" -ge 180 ]; then
      echo "      ✖ Docker did not answer within 180s."
      return 1
    fi
    sleep 3
    waited=$((waited + 3))
  done
  echo "      ✔ Docker Desktop is up (${waited}s)."
}

# Prints the number of unpatched cookie sites left in pm-postiz, or "missing" if a
# target file no longer exists (image changed).
cookie_sites_left() {
  local total=0 f n
  for f in $COOKIE_FILES; do
    if ! docker exec pm-postiz test -f "$f" 2>/dev/null; then
      echo "missing"
      return 0
    fi
    n=$(docker exec pm-postiz grep -cF "$COOKIE_EXPR" "$f" 2>/dev/null || true)
    total=$((total + ${n:-0}))
  done
  echo "$total"
}

# Checks the cookie patch; if it is missing (pm-postiz running the image's stock command),
# patches the files and restarts the container so the apps load them.
patch_cookie_domain() {
  local left f n
  if ! container_running pm-postiz; then
    echo "      ✖ pm-postiz is not running; cannot check the cookie domain patch."
    return 1
  fi

  left=$(cookie_sites_left)
  if [ "$left" = "missing" ]; then
    echo "      ✖ Cookie patch targets not found in pm-postiz (image changed?). Login may loop."
    return 1
  fi
  if [ "$left" -eq 0 ]; then
    echo "      ✔ Cookie domain patch present (host-only cookies)."
    return 0
  fi

  for f in $COOKIE_FILES; do
    n=$(docker exec pm-postiz grep -cF "$COOKIE_EXPR" "$f" 2>/dev/null || true)
    if [ "${n:-0}" -gt 0 ]; then
      docker exec pm-postiz sed -i "$COOKIE_SED" "$f"
      echo "      patched $(basename "$f") ($n cookie sites)"
    fi
  done

  left=$(cookie_sites_left)
  if [ "$left" != "0" ]; then
    echo "      ✖ Cookie patch incomplete ($left sites left)."
    return 1
  fi
  # The running backend loaded the old code; the patched files survive a container restart.
  docker restart pm-postiz > /dev/null
  echo "      ✔ Cookie domain patch applied; restarted pm-postiz to load it."
}

evict_ollama_models() {
  local loaded
  loaded=$(curl -s -m 5 http://localhost:11434/api/ps 2>/dev/null \
    | python3 -c 'import sys, json; print("\n".join(m["name"] for m in json.load(sys.stdin).get("models", [])))' 2>/dev/null || true)
  if [ -z "$loaded" ]; then
    echo "      No models loaded in VRAM."
    return 0
  fi
  echo "$loaded" | while read -r name; do
    [ -n "$name" ] || continue
    curl -s -m 30 http://localhost:11434/api/generate \
      -d "{\"model\": \"$name\", \"keep_alive\": 0}" > /dev/null || true
    echo "      Evicted $name"
  done
}

# Names .env must set (see .env.example).
REQUIRED_ENV="JWT_SECRET POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB DATABASE_URL REDIS_URL FRONTEND_URL
NEXT_PUBLIC_BACKEND_URL NGROK_AUTHTOKEN NGROK_DOMAIN AUTHENTICATION_API_KEY WA_INSTANCE WA_TEST_RECIPIENTS
STORAGE_PROVIDER UPLOAD_DIRECTORY"

# Preflight for this Mac or the Air: prerequisites, .env, disk and memory. Changes nothing.
# Exit status 1 if anything required is missing.
doctor() {
  local fails=0 warns=0 v ram_gb free_gb mode missing="" name
  ok()   { echo "  ✔ $1"; }
  bad()  { echo "  ✖ $1"; fails=$((fails + 1)); }
  warn() { echo "  ⚠ $1"; warns=$((warns + 1)); }

  echo "--- Mac ---"
  ram_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
  echo "  macOS $(sw_vers -productVersion), $(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -m), ${ram_gb} GB memory"
  [ "$ram_gb" -ge 8 ] && ok "memory: ${ram_gb} GB" || bad "memory: ${ram_gb} GB (8 GB is the minimum this was sized for)"
  free_gb=$(df -g "$DIR" | awk 'NR == 2 {print $4}')
  if [ "$free_gb" -ge 25 ]; then ok "free disk: ${free_gb} GB"; else warn "free disk: ${free_gb} GB (keep 25 GB free: images ≈11 GB, model 2–5 GB)"; fi

  echo "--- Tools ---"
  if command -v docker > /dev/null 2>&1; then
    if docker info > /dev/null 2>&1; then
      ok "Docker Desktop running ($(docker info --format '{{.ServerVersion}}'), VM memory $(( $(docker info --format '{{.MemTotal}}') / 1048576 )) MiB)"
    else
      ok "Docker CLI installed (Docker Desktop not running; start opens it)"
    fi
  else
    bad "Docker Desktop not installed (DEPLOY-M1.md §7 step 4)"
  fi
  if command -v ollama > /dev/null 2>&1; then
    if grep -qF "$MODEL" <<< "$(ollama list 2>/dev/null || true)"; then
      ok "Ollama with $MODEL"
    elif pgrep -x ollama > /dev/null; then
      warn "Ollama has no $MODEL yet: ollama pull $MODEL"
    else
      warn "Ollama installed but not running, so its models can't be listed (start runs it)"
    fi
  else
    warn "Ollama not installed (needed for local captions only)"
  fi
  v=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)
  [ -n "$v" ] && ok "python3 $v" || bad "python3 missing (xcode-select --install)"
  command -v ffmpeg > /dev/null 2>&1 && ok "ffmpeg" || warn "ffmpeg missing: brew install ffmpeg (video statuses and analysis)"
  command -v swiftc > /dev/null 2>&1 && ok "Swift compiler (menu bar app)" || warn "Swift compiler missing: xcode-select --install (to build the menu bar app)"
  if command -v whisper-cli > /dev/null 2>&1 && [ -f "$DIR/data/whisper/ggml-small.bin" ]; then
    ok "whisper.cpp + small model (WhatsApp voice notes)"
  else
    warn "voice notes off: ./scripts/get-whisper-model.sh installs whisper.cpp and its model (≈466 MB)"
  fi

  echo "--- Settings (.env) ---"
  if [ ! -f "$DIR/.env" ]; then
    bad ".env missing (copy .env.example, fill it in, chmod 600)"
  else
    mode=$(stat -f '%Lp' "$DIR/.env")
    [ "$mode" = "600" ] && ok ".env readable only by you (600)" || bad ".env mode is $mode: chmod 600 .env"
    for name in $REQUIRED_ENV; do
      [ -n "${!name:-}" ] || missing="$missing $name"
    done
    [ -z "$missing" ] && ok "required names set" || bad "missing in .env:$missing"
    [ "${UPLOAD_DIRECTORY:-}" = "/uploads" ] || bad "UPLOAD_DIRECTORY must be /uploads (the bind mount), is '${UPLOAD_DIRECTORY:-}'"
    case "${FRONTEND_URL:-}" in
      "https://${NGROK_DOMAIN:-none}"|"https://${NGROK_DOMAIN:-none}/") ok "FRONTEND_URL uses NGROK_DOMAIN" ;;
      *) warn "FRONTEND_URL is not https://\$NGROK_DOMAIN (fine only for a localhost dev setup)" ;;
    esac
    [ "${DISABLE_REGISTRATION:-}" = "true" ] && ok "Postiz sign-up closed" || warn "DISABLE_REGISTRATION is not true: anyone with the public URL can register"
    [ "${PM_QUIT_DOCKER_ON_STOP:-false}" = "true" ] && ok "stop quits Docker Desktop" \
      || echo "  · stop leaves Docker Desktop running for other containers (PM_QUIT_DOCKER_ON_STOP=true quits it)"
  fi

  echo "--- Project ---"
  for f in docker-compose.yml patches/postiz/run.sh patches/evolution/status-receipts.js scripts/lib/machine_state.py tray/PostForgeTray.swift; do
    [ -f "$DIR/$f" ] || bad "missing $f"
  done
  if docker info > /dev/null 2>&1; then
    if [ -f "$DIR/.env" ]; then
      docker compose config --quiet 2>/dev/null && ok "docker-compose.yml valid" \
        || bad "docker-compose.yml does not parse; run docker compose config for the exact error"
    else
      bad ".env missing; Docker Compose cannot resolve the required environment file"
    fi
  fi
  if [ -d "$HOME/Applications/PostForge.app" ] || [ -d "$HOME/Applications/Publish Machine.app" ] || [ -d "$DIR/tray/build/PostForge.app" ] || [ -d "$DIR/tray/build/Publish Machine.app" ]; then
    ok "menu bar app built"
  else
    echo "  · menu bar app not built yet: ./tray/build.sh --install"
  fi

  echo ""
  if [ "$fails" -gt 0 ]; then
    echo "Doctor: $fails problem(s), $warns warning(s)."
    return 1
  fi
  echo "Doctor: ready ($warns warning(s))."
}

# WhatsApp door (scripts/wa-inbox.sh): your own chat -> drafts. Runs with the stack; PM_WA_DOOR=false turns it off.
WA_DOOR_PID="$DIR/run/wa-inbox.pid"
wa_door_running() { [ -f "$WA_DOOR_PID" ] && kill -0 "$(cat "$WA_DOOR_PID")" 2> /dev/null; }
rotate_log() {
  local path=$1 max_bytes=10485760
  [ -f "$path" ] || return 0
  [ "$(stat -f '%z' "$path" 2>/dev/null || echo 0)" -lt "$max_bytes" ] && return 0
  local n
  for n in 4 3 2 1; do
    [ -f "$path.$n" ] && mv "$path.$n" "$path.$((n + 1))"
  done
  mv "$path" "$path.1"
}
start_wa_door() {
  [ "${PM_WA_DOOR:-true}" = "false" ] && { echo "      WhatsApp door off (PM_WA_DOOR=false)."; return 0; }
  wa_door_running && { echo "      WhatsApp door already listening."; return 0; }
  mkdir -p "$DIR/run" "$DIR/logs"
  rotate_log "$DIR/logs/wa-inbox.log"
  nohup python3 "$DIR/scripts/lib/wa_inbox.py" >> "$DIR/logs/wa-inbox.log" 2>&1 &
  echo $! > "$WA_DOOR_PID"
  echo "      WhatsApp door listening to your own chat (log: logs/wa-inbox.log)."
}
stop_wa_door() {
  if wa_door_running; then
    kill "$(cat "$WA_DOOR_PID")" 2> /dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do wa_door_running || break; sleep 1; done
  fi
  rm -f "$WA_DOOR_PID"
}

print_health() {
  local code state
  code=$(http_code "$POSTIZ_URL/")
  echo "  Postiz UI (local)      : HTTP ${code}"
  code=$(http_code "$POSTIZ_URL/api/")
  echo "  Postiz API (local)     : HTTP ${code} $( [ "$code" = "502" ] && echo '(backend down)' || true)"
  if [ -n "${NGROK_DOMAIN:-}" ]; then
    code=$(http_code "https://${NGROK_DOMAIN}/" 10)
    echo "  Public tunnel          : HTTP ${code}  https://${NGROK_DOMAIN}"
  fi
  if container_running pm-postiz; then
    state=$(cookie_sites_left)
    if [ "$state" = "0" ]; then
      echo "  Cookie domain patch    : applied"
    else
      echo "  Cookie domain patch    : NOT applied ($state) -> run ./publish-machine.sh patch"
    fi
  fi
  state=$(curl -s -m 5 "$EVO_URL/instance/connectionState/$WA_INSTANCE" -H "apikey: ${AUTHENTICATION_API_KEY:-}" 2>/dev/null \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["instance"]["state"])' 2>/dev/null || echo "unreachable")
  echo "  WhatsApp ($WA_INSTANCE) : $state"
  if container_running pm-temporal; then
    if python3 "$STATE_PY" --check-scheduler; then
      echo "  Scheduler (Temporal)   : Postiz worker polling"
    else
      echo "  Scheduler (Temporal)   : NO WORKER -> scheduled posts won't publish (docker restart pm-postiz)"
    fi
  fi
  if container_running pm-evolution-api; then
    state=$(python3 "$DIR/scripts/lib/wa_settings.py" --check 2>&1 | tail -1)
    echo "  Status receipts        : ${state#Status receipts: }"
  fi
  if wa_door_running; then
    echo "  WhatsApp door          : listening to your own chat (pid $(cat "$WA_DOOR_PID"))"
  else
    echo "  WhatsApp door          : off"
  fi
  if container_running pm-redis; then
    state=$(docker exec pm-redis redis-cli config get appendonly 2>/dev/null | tail -1)
    echo "  Redis AOF persistence  : $state"
  fi
}

case "${1:-}" in
  start)
    echo "======================================================"
    echo "  STARTING PUBLISH MACHINE (M1 Optimized Mode)"
    echo "======================================================"
    mark_lifecycle starting

    # 1. Docker Desktop (quit by `stop` when PM_QUIT_DOCKER_ON_STOP=true)
    echo "[1/6] Checking Docker Desktop..."
    ensure_docker

    # 2. Verify Native Ollama is alive
    if ! pgrep -x "ollama" > /dev/null; then
      echo "[2/6] Starting Ollama host daemon in background..."
      nohup ollama serve > /dev/null 2>&1 &
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        curl -s -m 2 http://localhost:11434/api/tags > /dev/null 2>&1 && break
        sleep 1
      done
    else
      echo "[2/6] Ollama host service is active."
    fi

    # 3. Check for local quantization model
    echo "[3/6] Checking LLM model: ${MODEL}..."
    # Here-string, not a pipe: under pipefail, `grep -q` exiting early makes `ollama list`
    # die of SIGPIPE, which looked like a missing model and re-pulled it on every start.
    if ! grep -qF "$MODEL" <<< "$(ollama list 2>/dev/null || true)"; then
      echo "      Model not found. Pulling quantized weights..."
      ollama pull "$MODEL"
    fi

    # 4. Spin up Docker containers. Both apps patch themselves as they boot: Postiz its cookie
    #    domain (patches/postiz/run.sh), Evolution its status receipts (patches/evolution/).
    echo "[4/6] Starting container stack (hard memory limits active)..."
    docker compose up -d --remove-orphans

    # 5. Wait for the services to answer
    echo "[5/6] Waiting for services..."
    wait_for "Evolution API" "$EVO_URL/" 120 '^2' || true
    wait_for "Postiz backend" "$POSTIZ_URL/api/" 240 '^[234]' || true
    wait_for "Postiz frontend" "$POSTIZ_URL/" 240 '^[23]' || true
    # Scheduled posts need the orchestrator's Temporal worker. If Postiz booted before Temporal
    # was ready, the worker is missing although Postiz looks healthy: restart the container once.
    if wait_for_scheduler 60; then
      echo "      ✔ Scheduler (Postiz worker polling Temporal)"
    else
      echo "      ✖ No Postiz worker on Temporal: restarting pm-postiz once..."
      docker restart pm-postiz > /dev/null
      wait_for "Postiz backend" "$POSTIZ_URL/api/" 240 '^[234]' || true
      if wait_for_scheduler 90; then
        echo "      ✔ Scheduler (Postiz worker polling Temporal)"
      else
        echo "      ✖ Scheduler still missing: scheduled posts will NOT publish. See README Gotcha #16."
      fi
    fi

    # 6. Check the boot-time patches and the WhatsApp setting status receipts need
    echo "[6/6] Checking patches..."
    patch_cookie_domain || true
    python3 "$DIR/scripts/lib/wa_settings.py" | sed 's/^/      /' || true
    start_wa_door

    echo "======================================================"
    echo "  MACHINE IS ONLINE"
    echo "  Postiz Dashboard : https://${NGROK_DOMAIN:-<NGROK_DOMAIN unset>}  (use this URL, not localhost)"
    echo "  Evolution Manager: ${EVO_URL}/manager"
    echo "======================================================"
    ;;

  stop)
    # Scheduled posts and sends in progress: warn first (the menu bar app asks, then passes --force)
    if [ "${2:-}" != "--force" ] && ! python3 "$STATE_PY" --guard; then
      if [ -t 0 ]; then
        printf "Turn it off anyway? [y/N] "
        read -r answer
        case "$answer" in
          y|Y|yes|YES) ;;
          *) echo "Kept running."; exit 1 ;;
        esac
      else
        echo "Not stopped. To stop anyway: ./publish-machine.sh stop --force"
        exit 3
      fi
    fi

    echo "======================================================"
    echo "  SHUTTING DOWN PUBLISH MACHINE & RECLAIMING RAM"
    echo "======================================================"
    mark_lifecycle stopping


    stop_wa_door  # before Evolution goes away

    # 1. Spin down Docker containers
    echo "[1/3] Stopping Docker containers..."
    if docker info > /dev/null 2>&1; then
      python3 "$STATE_PY" --cache > /dev/null 2>&1 || true  # the menu bar app shows the schedule while off
      docker compose down --remove-orphans  # also removes services dropped from the compose file
    else
      echo "      Docker Desktop is not running: nothing to stop."
    fi

    # 2. Force unload every Ollama model from Unified VRAM
    echo "[2/3] Releasing Ollama VRAM back to macOS..."
    if pgrep -x "ollama" > /dev/null; then
      evict_ollama_models
    else
      echo "      Ollama daemon offline."
    fi

    # 3. Docker Desktop's VM keeps its memory until Docker Desktop quits
    echo "[3/3] Docker Desktop..."
    if [ "${PM_QUIT_DOCKER_ON_STOP:-false}" = "true" ]; then
      docker desktop stop > /dev/null 2>&1 || osascript -e 'quit app "Docker"' > /dev/null 2>&1 || true
      echo "      Quit (PM_QUIT_DOCKER_ON_STOP=true)."
      docker_note="Docker Desktop quit too"
    else
      echo "      Left running for other containers. Quit it yourself to give its memory back."
      docker_note="Docker Desktop still running"
    fi

    echo "======================================================"
    echo "  PUBLISH MACHINE IS OFF ($docker_note)"
    echo "======================================================"
    ;;

  restart)
    "$0" stop --force
    "$0" start
    ;;

  pending)
    python3 "$STATE_PY"
    ;;

  state)
    python3 "$STATE_PY" --json
    ;;

  patch)
    echo "Checking the Postiz host-only cookie patch..."
    patch_cookie_domain
    ;;

  doctor)
    doctor
    ;;

  channels)
    # Connected channels, when each stops working, and a guided reconnect (docs/reconnect/).
    shift
    python3 "$DIR/scripts/lib/channels.py" "$@"
    ;;

  retention)
    shift
    python3 "$DIR/scripts/retention.py" "$@"
    ;;

  maintenance)
    shift
    "$DIR/scripts/maintenance.sh" "$@"
    ;;

  tunnel-url)
    shift
    [ "$#" -eq 1 ] || {
      echo "Usage: ./postforge.sh tunnel-url <https://domain.example> (legacy alias: ./publish-machine.sh)" >&2
      exit 2
    }
    python3 "$DIR/scripts/tunnel_url.py" --env-file "$DIR/.env" "$1"
    echo "Tunnel URL saved. Restart PostForge to apply it."
    ;;

  status)
    echo "======================================================"
    echo "  POSTFORGE RESOURCE MONITOR"
    echo "======================================================"
    echo "--- Docker Containers Memory Usage ---"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" || echo "Containers offline."
    echo ""
    echo "--- Service Health ---"
    print_health
    echo ""
    echo "--- Work Waiting ---"
    python3 "$STATE_PY" || true
    echo ""
    echo "--- Host Ollama Memory Status ---"
    if pgrep -x "ollama" > /dev/null; then
      curl -s http://localhost:11434/api/ps || echo "No models loaded in VRAM."
      echo ""
    else
      echo "Ollama daemon offline."
    fi
    ;;

  *)
    echo "Usage: ./postforge.sh {start|stop [--force]|restart|status|pending|state|channels [--reconnect [network]]|retention [--apply]|maintenance {check|snapshot|update --apply}|tunnel-url <https://domain>|patch|doctor}"
    echo "Legacy alias still works: ./publish-machine.sh"
    exit 1
    ;;
esac
