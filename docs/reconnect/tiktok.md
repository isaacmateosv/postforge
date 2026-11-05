# TikTok

Postiz supports automatic access-token renewal and stores the refresh token returned by TikTok.
Refresh credentials can expire or be revoked; use provider-returned `expires_in` and
`refresh_expires_in` rather than assuming a fixed lifetime. TikTok's documentation currently
contains differing lifetime statements/examples, so a universal one-year guarantee is inappropriate.

Sandbox/preview is a separate restriction: only configured target users can authorize, and sandbox
mode does not provide public-video posting. A connected account does not mean an app has passed
review or that an upload has been published. Switching sandbox/production keys requires reconnection.

Sources: [token refresh](https://developers.tiktok.com/docs/en/oauth-refresh-a-user-access-token),
[sandbox](https://developers.tiktok.com/docs/en/add-a-sandbox),
[publishing restrictions](https://developers.tiktok.com/docs/en/content-sharing-guidelines).

Setup and the sandbox: [../tiktok-app-form.md](../tiktok-app-form.md).

## Reconnect

1. Turn PostForge on. Click the menu bar warning → **Open Postiz**, or run
   `./postforge.sh channels --reconnect tiktok`.
2. In Postiz, open the TikTok channel's menu → **Reconnect channel**.
3. Log in with the organization’s TikTok account and allow every permission.

## When the keys change (sandbox ↔ production, or a reset secret)

1. developers.tiktok.com → the app → the **Production** or **Sandbox** toggle → App details →
   Credentials.
2. In `.env`: Client key → `TIKTOK_CLIENT_ID`, Client secret → `TIKTOK_CLIENT_SECRET`. Both must come
   from the same app (production and sandbox have different keys).
3. Run `docker compose up -d postiz`, then reconnect TikTok. A connection made with the old keys
   doesn't carry over.

## If it fails

| What you see | Fix |
|---|---|
| TikTok's login page shows an error right away | `TIKTOK_CLIENT_ID` is empty or from another app, or Postiz wasn't recreated after `.env` changed |
| A sandbox login refuses the account | Add it in the sandbox: Sandbox settings → Target users (it can take up to an hour) |
| Postiz says "Missing required permissions" | The app lacks one of the six scopes Postiz asks for ([../tiktok-app-form.md](../tiktok-app-form.md)) |
| `unaudited_client_can_only_post_to_private_accounts` | Apps TikTok hasn't audited can direct-post only privately, to private accounts. Use inbox drafts (the default, `TIKTOK_POSTING_METHOD=UPLOAD`) |
