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

## Postiz accounts and team membership

Keep `DISABLE_REGISTRATION=true` for routine operation. The gateway allowlist
controls who can reach Postiz. Postiz team membership controls what each person
can do inside the workspace. They are separate settings.

- **Existing Postiz account:** provision the separate gateway login and its
  authenticator. If the person needs access to a workspace they have not joined,
  use Postiz’s team settings to add the existing account by email and select
  the least privileged role that fits their work.
- **First owner on an empty deployment:** create the first local Postiz account
  through the protected gateway. The currently pinned build allows this with
  registration disabled when there are no organizations.
- **Additional account on an existing deployment:** provision the gateway user
  first. Use a short, operator-controlled signup window only after verifying the
  gateway, then confirm the new user joined the intended workspace and turn
  registration back off. The currently pinned build checks the local signup
  switch before applying an invitation, so an invite alone cannot create a new
  email/password account while registration is disabled.

Without a mail provider, the pinned Postiz build can return an invitation
link without emailing it. Copy the link and hand it to the intended person
privately, such as through your own email or a direct message. The link expires
in two days. Local accounts created with no Postiz email provider are activated
at creation. The gateway password and authenticator QR code are separate from
the invitation.

Use the tray's **Gateway Access** editor for gateway authorization. Keep
workspace roles and invitations in Postiz. If a future onboarding screen
offers temporary signup, put it behind an explicit owner action, show the
expiry, and restore disabled registration automatically.

For a person who leaves, revoke gateway access and remove their Postiz workspace
membership separately. Postiz invitation delivery is independent of how the
gateway provisions authenticators.

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
