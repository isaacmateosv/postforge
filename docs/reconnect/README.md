# Something expired? Start here

PostForge posts through accounts that were connected once. Some of those connections expire,
and a few keys can be reset. There's one guide for each.

## How you find out

- **Menu bar:** a line such as "⚠︎ Reconnect Instagram by Wed 30 Dec…" (✗ once it has stopped).
  Click it for the steps and an **Open Postiz** button. A notification comes with the first warning,
  a week, three days and a day before, and when it stops. This works while PostForge is off too.
- **Terminal:** `./postforge.sh channels` lists every channel and when it stops working.
- **Postiz** marks a broken channel "Channel disconnected, click to reconnect".

## The quick way (about 2 minutes)

1. Click the warning in the menu bar → **Open Postiz** (or **Turn On and Open Postiz**).
2. In Postiz, in the channel list on the left, open the channel's menu → **Reconnect channel**.
3. Log in as asked and pick the same Page or account, with every permission ticked.
4. The warning clears within a minute, and a "works again" notification confirms it.

In Terminal, `./postforge.sh channels --reconnect` does the same: it opens Postiz, waits until
each channel works again and says so. `--reconnect meta` renews Facebook and Instagram before they
expire, which restarts their 60 days.

## What expires

| What | How long it lasts | Renews itself? | Guide |
|---|---|---|---|
| Instagram and Facebook Page connections | 60 days | No | [meta.md](meta.md) |
| YouTube connection | until withdrawn (the Google app is verified since 2026-11-01; 7 days if it ever goes back to Testing) | Yes | [youtube.md](youtube.md) |
| TikTok connection | about a year | Yes, until then | [tiktok.md](tiktok.md) |
| Threads connection | about 60 days | Yes | [threads.md](threads.md) |
| WhatsApp link (statuses, the WhatsApp door) | until the phone unlinks it, or 14 days with the phone offline | No | [whatsapp.md](whatsapp.md) |
| Keys and secrets in `.env` (Meta, TikTok, Google, Gemini, ngrok, Evolution) | no expiry; replace them when reset or leaked | n/a | [app-keys.md](app-keys.md) |
| The public address (ngrok domain) | no expiry; if it changes, every login link changes | n/a | [public-address.md](public-address.md) |

`PM_CHANNEL_WARN_DAYS` in `.env` (default 10) sets how many days ahead the menu bar starts warning.
Background: README Gotchas #21 and #22, and DEPLOY-M1.md §6 (how each app was set up).
