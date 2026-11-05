# PostForge v2 development preview

This branch adds a local, read-only browser dashboard and an optional Telegram
health worker. It uses Docker Compose and Python on macOS, Windows with
Docker Desktop, and Linux with Docker Engine and the Compose plugin.
The shared Compose services and the existing Postiz web app handle publishing.
The preview has not been validated on physical Windows and Linux hosts.

## Local web dashboard

From the project directory, copy `.env.example` to `.env` and configure the
database, JWT, and Evolution settings. Use the Postiz origin as `FRONTEND_URL`
and `MAIN_URL`, and its `/api` URL as `NEXT_PUBLIC_BACKEND_URL`.

Start only the local services. Listing them explicitly leaves ngrok off.

```text
docker compose -f docker-compose.yml -f v2/compose.yml --profile web up -d postiz evolution-api postforge-web
```

Open `http://localhost:8787` on the host. Postiz and Evolution publish only
loopback ports. Ollama is optional for the dashboard. Its health probe uses
the Docker host gateway, and it will show unreachable if the host Ollama
listener is accessible only on host loopback. The dashboard opens Postiz and
reports service reachability. It does not control Docker or create drafts yet.

## Internet access and initial sign-in

Keep Postiz private until a separate access gate is configured. The intended
order is **HTTPS → MFA and explicit user allowlist → Postiz login**. Register
the allowed users in the chosen identity provider or self-hosted identity
service first. They sign in at the gate before they see Postiz. Keep the Postiz
account credentials separate. The Dev Portal pattern of a loopback reverse
proxy and an independently provisioned gate is useful. Its password-only
screen-sharing setup is outside this design.

A purchased domain does not change this sequence. Use a DNS name like
`postiz.example.org`, configure HTTPS and the gate there, and update the
Postiz URLs and provider OAuth callback registrations together. Check from a
signed-out browser that the old hostname, new hostname, `/api/`, assets, and
uploads offer no alternate anonymous route. Then test a full OAuth round trip. The signed-out smoke test can check
the expected gateway response without following redirects or handling credentials:

```text
python v2/check_gateway.py https://postiz.example.org --login https://login.example.org/sso
```

A signed-out check is one step. Complete MFA as an allowed user, verify a
different account is denied, and test Postiz sign-in and the provider callback
before declaring the cutover ready.
A machine callback that cannot carry browser authentication needs its own
narrow, verified route. Keep the rest of the API gated.

The v1 tunnel switch expects anonymous public API health to return HTTP 200.
A gated endpoint will intentionally fail that check. Before a cutover,
update the switch to verify origin health locally and verify the gateway
separately from a signed-out client. Do not exempt the API from MFA to
make the old health check pass.

For a fully local deployment, no tunnel is needed. If remote access is required,
put the authenticated gateway on the network edge. Keep the dashboard,
database, Redis, Temporal, Ollama, and Evolution management endpoints private.

## Optional Telegram status and heartbeat

Create a bot with BotFather and obtain your numeric Telegram user ID.
Start a private chat with the bot. Put the token in `run/telegram/token`
inside the project. On macOS and Linux, set the directory to mode `0700`
and the file to `0444` so the non-root container can read the file mount
while other host users cannot traverse the directory. On Windows, keep the
project in a private user directory and restrict its access with Windows ACLs.
The token is mounted as a Compose secret. Keep it out of `.env` and source control.

Provide these non-secret settings when starting Compose:
- `TELEGRAM_OWNER_ID` is the one authorized private-chat user ID.
- `TELEGRAM_LANGUAGE` is `en` or `es`.
- `TELEGRAM_HEARTBEAT_MINUTES` is `0` (off) or `5` to `1440`.

```text
docker compose -f docker-compose.yml -f v2/compose.yml --profile telegram up -d postforge-telegram
```

Send `/status` and use the **Refresh status** button. The worker uses outbound
long polling, so it has no public webhook. Remove any existing webhook from a
bot before using long polling. Its Compose volume preserves the update cursor
and last heartbeat across restarts. No Telegram action publishes content.

Health messages show service reachability, separately from the worker’s own
liveness. If the host or internet goes down, an external monitor must detect
the missed heartbeat. A bot on the stopped host cannot send its own outage alert.

See [Telegram’s Bot API](https://core.telegram.org/bots/api) for bot behavior.
