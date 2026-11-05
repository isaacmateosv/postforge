# Threads

Threads connects with the bakery's Instagram account (`almadulce.bakery`) through its own Meta app
keys (`THREADS_APP_ID`, `THREADS_APP_SECRET`). Its token lasts about 60 days, but unlike Facebook and
Instagram, Postiz renews it by itself before then. Automatic renewal can fail. Reconnection may be needed if someone removes the
app (Instagram → Settings → Website permissions / Apps and websites), the keys change, or the renewal
fails, and then Postiz marks it disconnected and the menu bar warns.

## Reconnect

1. Turn PostForge on. Click the menu bar warning → **Open Postiz**, or run
   `./postforge.sh channels --reconnect threads`.
2. In Postiz, open the Threads channel's menu → **Reconnect channel**.
3. Log in with the bakery's Instagram account and allow every permission.

## If it fails

| What you see | Fix |
|---|---|
| "Invalid Scopes" or a missing permission | The Threads use case needs all four permissions Postiz asks for: `threads_basic`, `threads_content_publish`, `threads_manage_replies`, `threads_manage_insights` |
| "Invalid redirect" / can't load URL | The Threads app's redirect callback must be `https://<public address>/integrations/social/threads` ([public-address.md](public-address.md)) |
| The account can't log in | While the app has no App Review, the Instagram account must be a Threads tester of the app (App roles → Threads testers) |
| "Post text exceeds 500 characters limit" | Threads allows 500 characters; shorten the caption in Postiz |
