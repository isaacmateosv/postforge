# Separate PostForge gateway login

Postiz keeps its own accounts. Caddy asks Authelia to authorize requests before
forwarding any Postiz page, API, or asset. The Authelia portal is under
`/authelia` on the same HTTPS hostname. The gateway and identity containers
publish no host ports. Ngrok sends traffic to Caddy instead of directly to Postiz.

## Provision locally

1. Initialize the private configuration with
   `python3 v2/gateway_setup.py init YOUR-EXACT-HOSTNAME`. Keep `data/gateway`
   private and back it up privately. It holds password hashes, MFA state, and keys.
2. For each user, use Authelia’s interactive password hash command. Let the
   person enter their own gateway password at its prompts. Pass only the
   resulting Argon2id hash to `python3 v2/gateway_setup.py add-user USER_EMAIL`
   at the hidden prompt. The email is a username for the gate.
3. With the gateway still offline, initialize Authelia storage and generate
   a local QR code for each account.

```bash
docker compose -f docker-compose.yml -f v2/compose.gateway.yml run --rm --no-deps postforge-auth   authelia crypto hash generate argon2
docker compose -f docker-compose.yml -f v2/compose.gateway.yml run --rm --no-deps postforge-auth   authelia storage migrate up --config /config/configuration.yml
docker compose -f docker-compose.yml -f v2/compose.gateway.yml run --rm --no-deps postforge-auth   authelia storage user totp generate USER_EMAIL --config /config/configuration.yml   --issuer PostForge --path /config/enrollment.png
```

Have each person scan the QR code from the Mac with their authenticator app.
Delete that image after enrollment, then generate a new one for the next person.
Treat the QR and enrollment output as secrets. If a phone is lost, an operator
can re-enroll that user locally. Password reset through the portal is disabled.

For email enrollment or remote recovery, configure a real SMTP notifier and
verify delivery before enabling that flow. The generated file notifier is for
isolated setup and testing. Review Authelia’s production notifier guidance
before exposing the gateway. [Notifier documentation](https://www.authelia.com/configuration/notifications/introduction/)

## Validate and activate

Validate the generated configuration and test with an isolated endpoint. Check
anonymous routes, a password-only session, an allowed user with a valid TOTP,
a denied user, Postiz sign-in, and a provider OAuth callback. The production
hostname is unchanged, so the existing Postiz origin stays the same.

Use **Settings & Tools → Gateway Access** on the Mac to allow or block a
provisioned user, or run `gateway_setup.py set-allowed USER_EMAIL allow|deny`.
The editor saves the change locally. Restart the Authelia service after changing
the list to apply it and invalidate current gateway sessions.

When moving to a purchased domain, run `gateway_setup.py set-hostname NEW-HOST`
against a private staging copy. This changes the Authelia cookie domain and
URLs while preserving the MFA storage and its encryption key. Update the
gateway host, Postiz origin, and OAuth callbacks together. Protect the new hostname before retiring the old route.
