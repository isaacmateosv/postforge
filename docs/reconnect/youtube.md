# YouTube

Postiz renews YouTube's access by itself with Google's refresh token. It only stops when Google
withdraws that token:
- **While the OAuth consent screen is in Testing, Google withdraws it after 7 days.** Fix this once:
  console.cloud.google.com → APIs & Services → OAuth consent screen (Audience) → **Publish app**
  ("In production") when appropriate. Google verification and Workspace policies can still restrict access.
- When someone removes the app's access (myaccount.google.com → Security → Third-party connections),
  or when refresh access is unused for 6 months, a granted time limit expires, or account/organization policy invalidates access.

Source: [Google OAuth token expiration](https://developers.google.com/identity/protocols/oauth2#expiration).

## Reconnect

1. Turn PostForge on. Click the menu bar warning → **Open Postiz**, or run
   `./postforge.sh channels --reconnect youtube`.
2. In Postiz, open the YouTube channel's menu → **Reconnect channel**.
3. Sign in with the Google account that owns the YouTube channel (for a brand channel, pick it in the
   list) and allow every permission.
4. The warning clears within a minute.

## If it fails

| What you see | Fix |
|---|---|
| "Access blocked: … has not completed the Google verification process" | The consent screen is in Testing and this Google account isn't a test user: add it under Audience → Test users, or publish the app (above) |
| "Error 400: redirect_uri_mismatch" | The OAuth client's Authorized redirect URI must be `https://<public address>/integrations/social/youtube` ([public-address.md](public-address.md)) |
| No channel to choose | The Google account doesn't own or manage a YouTube channel |
| Uploads fail with a quota error | Check the project’s Video Uploads quota in Google Cloud. See [the current upload quota](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert). |
