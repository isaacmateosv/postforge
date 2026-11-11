#!/bin/sh
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
# Boots the pinned Postiz image without its pnpm + PM2 + dotenv wrapper chain (README Gotcha #19).
#
# The stock command (`nginx && pnpm run pm2`) keeps ten idle Node processes beside the three
# apps: pnpm and dotenv wrappers, the PM2 daemon and `pm2 logs`, about 300 MB together. It also
# resolves Prisma through `pnpm dlx` on every boot. This runs the same three apps directly, with
# the image's own Prisma 6.5.0 (the version the stock command asks for), and applies the cookie
# patch (Gotcha #5) before anything loads, so no restart is needed.
#
# If any app exits, the others are stopped and the container exits; Docker's restart policy
# (unless-stopped) brings it back, as PM2 would have. `docker stop` reaches the apps through
# tini (compose `init: true`), so they stop in seconds instead of at Docker's 10 s timeout.
# Debian's sh (dash), POSIX only.
cd /app || exit 1

# Gotcha #5: Postiz derives the cookie Domain from FRONTEND_URL via tldts, which yields
# ".ngrok-free.dev" (a Public Suffix), so browsers drop every cookie Postiz sets. `undefined`
# makes host-only cookies. publish-machine.sh checks the same files.
COOKIE_EXPR='(0, subdomain_management_1.getCookieUrlFromDomain)(process.env.FRONTEND_URL)'
COOKIE_SED='s/(0, subdomain_management_1\.getCookieUrlFromDomain)(process\.env\.FRONTEND_URL)/undefined/g'
COOKIE_FILES="
apps/backend/dist/apps/backend/src/api/routes/auth.controller.js
apps/backend/dist/apps/backend/src/services/auth/auth.middleware.js
apps/backend/dist/apps/backend/src/api/routes/users.controller.js
apps/backend/dist/libraries/nestjs-libraries/src/track/track.cookies.js
"
patched=0
missing=""
for f in $COOKIE_FILES; do
  if [ ! -f "$f" ]; then
    missing="$missing $f"
  elif grep -qF "$COOKIE_EXPR" "$f"; then
    sed -i "$COOKIE_SED" "$f" && patched=$((patched + 1))
  fi
done
if [ -n "$missing" ]; then
  echo "[pm-patch] cookie domain: NOT applied, missing:$missing (image changed?)"
elif [ "$patched" -gt 0 ]; then
  echo "[pm-patch] cookie domain: applied ($patched files)"
else
  echo "[pm-patch] cookie domain: already applied"
fi

# Gotcha #21: Meta's login rejects scopes this Postiz build still requests (2026-10-31: "Invalid
# Scopes: instagram_manage_insights"). PM_META_SCOPE_FIX (.env) holds space-separated old=new
# pairs: old=new renames a scope, old= drops it. Only the scope arrays of the two Meta providers
# change, in the backend (login) and orchestrator copies. A new list needs a recreate
# (`docker compose up -d postiz`), which also restores the original files first.
META_DIRS="apps/backend/dist apps/orchestrator/dist"
for pair in $PM_META_SCOPE_FIX; do
  old=${pair%%=*}
  new=${pair#*=}
  case "$pair" in *=*) ;; *) echo "[pm-patch] meta scopes: skipped '$pair' (expected old=new)"; continue ;; esac
  case "$old$new" in *[!a-z_]*) echo "[pm-patch] meta scopes: skipped '$pair'"; continue ;; esac
  [ -n "$old" ] || { echo "[pm-patch] meta scopes: skipped '$pair'"; continue; }
  hits=0
  for d in $META_DIRS; do
    for name in facebook.provider.js instagram.provider.js; do
      f="$d/libraries/nestjs-libraries/src/integrations/social/$name"
      [ -f "$f" ] && grep -q "^[[:space:]]*'$old',\{0,1\}[[:space:]]*\$" "$f" || continue
      if [ -z "$new" ]; then
        sed -i "/^[[:space:]]*'$old',\{0,1\}[[:space:]]*\$/d" "$f"
      else
        sed -i "s/^\([[:space:]]*\)'$old'\(,\{0,1\}\)[[:space:]]*\$/\1'$new'\2/" "$f"
      fi
      hits=$((hits + 1))
    done
  done
  if [ -z "$new" ]; then action="dropped $old"; else action="$old -> $new"; fi
  echo "[pm-patch] meta scopes: $action ($hits files)"
done

node /pm-patches/preserve-media.js || exit 1

nginx || exit 1

# Same schema sync as the stock boot (`pnpm dlx prisma@6.5.0 db push`), without pnpm.
node_modules/.bin/prisma db push --schema ./libraries/nestjs-libraries/src/database/prisma/schema.prisma || exit 1

PIDS=""
# start_app <dir under apps/> <command...>: the subshell execs the app, so $! is the app itself.
start_app() {
  dir=$1
  shift
  (cd "apps/$dir" && PATH="/app/apps/$dir/node_modules/.bin:/app/node_modules/.bin:$PATH" exec "$@") &
  PIDS="$PIDS $!"
  echo "[pm-run] started $dir (pid $!)"
}

stop_apps() {
  echo "[pm-run] stopping apps"
  for pid in $PIDS; do kill -TERM "$pid" 2>/dev/null; done
  nginx -s quit 2>/dev/null
  waited=0
  while [ "$waited" -lt 8 ]; do
    alive=0
    for pid in $PIDS; do kill -0 "$pid" 2>/dev/null && alive=1; done
    [ "$alive" -eq 0 ] && return 0
    sleep 1
    waited=$((waited + 1))
  done
  for pid in $PIDS; do kill -KILL "$pid" 2>/dev/null; done
}

trap 'stop_apps; exit 0' TERM INT

start_app backend node --experimental-require-module ./dist/apps/backend/src/main.js
start_app orchestrator node --experimental-require-module ./dist/apps/orchestrator/src/main.js
start_app frontend /app/node_modules/.bin/next start -p 4200

# `wait` (unlike a plain sleep) returns as soon as a signal arrives, and it reaps exited apps,
# so `kill -0` stops finding them.
while :; do
  for pid in $PIDS; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "[pm-run] an app exited (pid $pid); stopping the rest so Docker restarts the container"
      stop_apps
      exit 1
    fi
  done
  sleep 5 &
  wait $!
done
