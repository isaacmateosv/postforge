# Instagram and Facebook Page

Both connect through Facebook Login in the same Meta app. This installed Postiz build has no working refresh method for either provider. Use each recorded expiry date and reconnect before it. Meta token types differ; this does not mean every Facebook Page token universally expires after 60 days. They usually expire together, so reconnect both in one go.

## Reconnect (before the date, or after they stopped)

1. Turn PostForge on. Then click the menu bar warning → **Open Postiz**, or run
   `./postforge.sh channels --reconnect meta` (it confirms when each one works again).
2. In Postiz, in the channel list on the left, open the **Facebook Page**'s menu → **Reconnect channel**.
3. Facebook asks you to log in. Use an account that **manages the bakery's Page** and has a **role on
   the Meta app** . Continue as yourself (not as the Page), keep every permission
   ticked, and select the bakery's Page.
4. Do the same for **Instagram**, selecting the Page and its Instagram account.
5. Within a minute the menu bar shows the new date, and a "works again" notification confirms it.

Reconnecting early is fine: it restarts the 60 days.

## Who can reconnect

Without Meta's App Review, only accounts with a role on the app (admin, developer or tester) can log
in, and the account must manage the Page. To let someone else do it:
- **Role:** developers.facebook.com → the app → **App roles → Roles → Add People → Tester**. They sign
  up as a Meta developer (a short form) and accept at developers.facebook.com/requests.
- **Page access:** Page settings → Page setup → **Page access** → Add New, full control (or Business
  settings → People, with the Page and the Instagram account as assets).

## If it fails

| What you see | Why | Fix |
|---|---|---|
| Only "This content isn't available right now" | The account has no role on the app | Log in with an account that has one, or add a role (above) |
| "Invalid Scopes: X" (shown to the app's developers) | The app doesn't offer permission X | Use cases → that use case → Customize → **Permissions and features** → X → **Add**. If Meta no longer offers X at all, Postiz can stop asking for it: add `X=` to `PM_META_SCOPE_FIX` in `.env`, run `docker compose up -d postiz` |
| "Invalid Scopes: pages_read_user_content" | Meta adds it for the comments permission | Add it under **Manage everything on your Page** → Permissions and features |
| "Can't load URL: the domain of this URL isn't included in the app's domains" | The public address isn't in the app | App settings → Basic → App domains and the Website platform ([public-address.md](public-address.md)) |
| The Page or the Instagram account isn't offered | The account doesn't manage it, or Instagram isn't linked to the Page | Page access (above); Instagram must be a professional account linked to the Page |
| Postiz says "Missing required permissions" | A permission was unticked | Reconnect and keep every permission ticked |

## Instagram stats

Postiz no longer asks for `instagram_manage_insights` (Meta rejected it on 2026-10-31), so Instagram
stats are off. To turn them back on, find the insights permission's current name under the Instagram
use case's **Permissions and features** and **Add** it. Then set `instagram_manage_insights=<that name>`
in `PM_META_SCOPE_FIX`, run `docker compose up -d postiz`, and reconnect Instagram.
