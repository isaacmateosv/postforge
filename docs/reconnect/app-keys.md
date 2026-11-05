# Keys and secrets in `.env`

These don't expire on their own. Replace one when you reset it on the provider's site, when it
leaks, or when you switch apps (for example TikTok sandbox → production). Paste keys only into
`.env` (it stays on this Mac), never into a chat or a commit.

After editing `.env`, recreate the container that uses the key: `docker compose up -d postiz`
(Postiz reads `.env` only when its container is created; a plain restart keeps the old values), or
`./postforge.sh restart` for everything.

| Key in `.env` | Where it comes from | After changing it |
|---|---|---|
| `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` | developers.facebook.com → the app → App settings → Basic (App secret: Show or Reset) | `docker compose up -d postiz`; if posting fails, reconnect Facebook and Instagram ([meta.md](meta.md)) |
| `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` | Meta for Developers → Instagram API with Instagram Login → Instagram app credentials | `docker compose up -d postiz`; reconnect Instagram Standalone ([setup](channel-setup.md#meta)) |
| `TIKTOK_CLIENT_ID`, `TIKTOK_CLIENT_SECRET` | developers.tiktok.com → the app (Production or Sandbox) → App details → Credentials | `docker compose up -d postiz`, then reconnect TikTok ([tiktok.md](tiktok.md)) |
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` | console.cloud.google.com → APIs & Services → Credentials → the OAuth client (add a new secret, then delete the old one) | `docker compose up -d postiz`; reconnect YouTube if it was a different client ([youtube.md](youtube.md)) |
| `THREADS_APP_ID`, `THREADS_APP_SECRET` | developers.facebook.com → the app → the Threads use case → settings (Threads app ID and secret) | `docker compose up -d postiz`, then reconnect Threads ([threads.md](threads.md)) |
| `GEMINI_API_KEY` | aistudio.google.com → API keys | Nothing else; only `analyze-media.sh` uses it |
| `NGROK_AUTHTOKEN` | dashboard.ngrok.com → Your Authtoken | `docker compose up -d ngrok` (the domain must stay the same: [public-address.md](public-address.md)) |
| `AUTHENTICATION_API_KEY` (Evolution) | You choose it | `docker compose up -d evolution-api`; the scripts read it from `.env` |
| `PM_META_SCOPE_FIX` (not a secret) | README Gotcha #21 | `docker compose up -d postiz`, then reconnect the channel it affects |

Leave `JWT_SECRET` alone unless it leaked: changing it logs everyone out of Postiz.
