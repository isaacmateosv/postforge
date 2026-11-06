# PostForge 2 release candidate

This branch adds a local, read-only browser dashboard and an optional Telegram
health worker. It uses Docker Compose and Python on macOS, Windows with
Docker Desktop, and Linux with Docker Engine and the Compose plugin.
The shared Compose services and the existing Postiz web app handle publishing.
The release candidate still needs end-to-end Windows and Linux host validation.

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

On the v2 release candidate, **Tunnel URL** in the Mac tray and
`./postforge.sh tunnel-url NEW-HOST` update the Postiz origin and gateway
cookie settings together. The switch verifies local Postiz and its scheduler,
then confirms that the new public API redirects signed-out visitors to the
gateway. It restores the previous configuration if verification fails.
Set up TLS, DNS and the ngrok hostname first. Provider OAuth callback changes
and their full sign-in round trips are operator checks.

For a fully local deployment, no tunnel is needed. If remote access is required,
put the authenticated gateway on the network edge. Keep the dashboard,
database, Redis, Temporal, Ollama, and Evolution management endpoints private.

## Separate gateway sign-in

The [Caddy and Authelia setup guide](gateway/README.md) covers a separate
allowlisted password and authenticator login. The gateway is independent of
Postiz credentials and can use the existing ngrok hostname.

## Managed access on the existing ngrok hostname

The managed Google policy authenticates every request and then denies email
addresses outside an exact allowlist. Enable 2-Step Verification on every
allowed account. The managed policy does not independently require a fresh
second factor. Use an identity provider with an enforced MFA policy when that
is required.

Prepare the policy locally and validate the Compose merge:

```text
python v2/ngrok_policy.py
docker compose -f docker-compose.yml -f v2/compose.ngrok-access.yml config --quiet
```

The command takes only email addresses. It does not need a Google password or
a verification code. Keep the generated file in the private run directory.
The override keeps the hostname and origin from the existing deployment and
fails to start if the mounted policy is missing. It makes no change to the
running tunnel until explicitly applied.

Test the gate on a staging endpoint before installing the override as the
local Compose override. Confirm signed-out, allowlisted, and denied access,
then test Postiz login and a provider OAuth round trip. Restart only ngrok
for this cutover. The Postiz origin and provider callback URLs can stay the
same because the hostname stays the same.

When moving to a new domain, provision TLS and attach the access gate before
routing traffic to Postiz. Update the Postiz origin and OAuth callback URLs,
then disable the old public route after checking the new one.

## Optional Telegram status and heartbeat

Create a dedicated bot with BotFather and open its private chat in Telegram.
From the project folder, run the setup helper. It asks for the token through
a hidden prompt, validates the bot, and identifies your numeric user ID from
a private `/start` message. If automatic detection finds more than one candidate,
use `--owner-id YOUR_NUMERIC_ID` and confirm the account explicitly.

```sh
python3 v2/telegram_setup.py --language en --heartbeat 0
./postforge.sh telegram start
./postforge.sh telegram status
```

Use `--language es` for Ecuadorian Spanish. Set heartbeat to `0` (off) or
`5`–`1440` minutes. On macOS, the worker follows the PostForge stack lifecycle,
including idle shutdown. Run the start command again after changing the token
or settings. The worker remembers its update cursor and restarts with the
same settings when the stack comes back on.

On Windows or Linux, start the optional worker with Compose from the project
folder. Include your gateway override if you use one.

```text
docker compose --env-file .env --env-file run/telegram/settings.env -f docker-compose.yml -f v2/compose.yml --profile telegram up -d --build --force-recreate --no-deps postforge-telegram
```

The token lives in `run/telegram/token`, separate from `.env`. Compose mounts
it as a file readable by the non-root container. On macOS and Linux the
enclosing directory is private. On Windows, use a private user folder and
restrict access with Windows ACLs. Keep the token out of chats, screenshots
and source control.

Send `/status` and use the **Refresh status** button. The worker uses outbound
long polling, so it has no public webhook. Remove any existing webhook from a
bot before using long polling. Its Compose volume preserves the update cursor
and last heartbeat across restarts. No Telegram action publishes content.

Health messages show service reachability, separately from the worker’s own
liveness. If the host or internet goes down, an external monitor must detect
the missed heartbeat. A bot on the stopped host cannot send its own outage alert.

See [Telegram’s Bot API](https://core.telegram.org/bots/api) for bot behavior.

## Release candidate acceptance checks

1. On each host, start the local dashboard and Postiz. Open the dashboard on
   localhost, check service status, and sign in to Postiz.
2. On a remote deployment, open the public URL in a private browser window.
   Sign in with the gateway password and authenticator, then with Postiz.
   Confirm an account outside the allowlist cannot reach Postiz. On a test
   channel, complete an OAuth reconnection before using a new hostname.
3. Export **Backup & Move** and restore on a spare host. Verify the gateway
   accepts the same password and authenticator and verify pending Postiz work.
4. From the Telegram owner's private chat, run `/status`, use **Refresh
   status**, and verify a heartbeat arrives if one was configured.
