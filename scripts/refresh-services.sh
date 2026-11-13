#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Recreate service containers without disconnecting the public tunnel connector.
refresh_container_stack() {
  local service
  local services=()
  while IFS= read -r service; do
    [ -n "$service" ] && [ "$service" != "ngrok" ] && services+=("$service")
  done < <(docker compose config --services)
  [ "${#services[@]}" -gt 0 ] || return 1
  docker compose up -d --no-deps --force-recreate "${services[@]}"
}

# A newly restarted backend can answer once, then briefly reset while workers settle.
# Require every condition, but retry transient failures instead of rejecting a healthy update.
wait_refreshed_stack() {
  local attempt=0 attempts="${1:-10}" postiz_code evolution_code tunnel_ok scheduler_ok
  while [ "$attempt" -lt "$attempts" ]; do
    attempt=$((attempt + 1))
    postiz_code=$(http_code "$POSTIZ_URL/api/")
    evolution_code=$(http_code "$EVO_URL/")
    tunnel_ok=false; scheduler_ok=false
    if container_running pm-tunnel; then tunnel_ok=true; fi
    if wait_for_scheduler 0; then scheduler_ok=true; fi
    if [ "$postiz_code" = "200" ] && [ "$evolution_code" = "200" ] && "$tunnel_ok" && "$scheduler_ok"; then
      echo "      ✔ Refreshed services healthy (Postiz, Evolution, scheduler, tunnel)."
      return 0
    fi
    echo "      Health attempt $attempt/$attempts: Postiz=$postiz_code Evolution=$evolution_code scheduler=$scheduler_ok tunnel=$tunnel_ok"
    [ "$attempt" -ge "$attempts" ] || sleep 3
  done
  return 1
}
