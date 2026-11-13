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
