# PostForge Quick Start

PostForge prepares publishing plans on your computer. You review the words, destinations and time before anything is submitted. The Rust desktop app is the current client; do not run the older Swift app alongside it.

## Start here

1. Install the package for your system. On macOS use the `.pkg`; the ZIP also includes the app and public backend.
2. Open **Settings → Check requirements**. Install missing tools from the provided official links, then start Docker.
3. Moving an existing installation? Use **Settings → Restore backup**. A fresh business installation still needs the advanced setup described in the technical guide.
4. Open **Settings → Manage services** to start the configured stack. Check **Manage Postiz link** before opening Postiz.
5. On Dashboard, choose **New post**.

No project folder is needed for normal use. The advanced installation-folder picker finds an existing installation; it does not import a backup.

```text
Compose → Choose delivery → Bake and review
                                  ├→ Create Drafts → approve in Postiz
                                  │                  approve Status separately
                                  └→ Schedule directly → confirm selected destinations
```

## 1 · Compose

Choose **Generate a caption** for an idea, or **Use my caption** to preserve your finished words. Put only the subject, facts and tone in this field; select destinations and time in the next step. You can attach up to ten files and preview them before continuing.

Example idea: “Announce our new opening hours. Warm, concise, with a couple of emojis.”

Example exact caption: “Starting tomorrow, we open at 10. See you soon! ✨”

With no media, PostForge offers Facebook feed posts, Threads and WhatsApp text Status. Instagram, YouTube, TikTok and Story media placements need a photo or video in this workflow. Text Status can have a background color.

## 2 · Choose delivery

Select connected destinations, local date/time and formats. **Soon · +10 min** fills a nearby future time. “Posts and stories where supported” includes both; a long Story can produce several segments rather than duplicate posts.

Expand **Caption and cover options** to choose an image or a video timestamp. The preview and green confirmation show that the selection is ready; the plan explains which destinations can use it. If you skip a supported cover, PostForge asks whether to continue. Changing media or a cover afterward requires another review.

The optional business hashtag starts empty on fresh installations. It follows the generated topical hashtags. Set a reusable default in **Settings → Edit preferences**, or override it for this plan.

For YouTube, Automatic uses portrait/square media for Shorts and landscape media for a regular video. A long Short gets a separate **2:59** copy; other destinations keep their own media. A short vertical video remains a Short even if you call it a regular video. Supply the appropriate aspect ratio; PostForge does not crop a landscape video automatically.

Choose **Bake and review**. On Mac, ⌘Enter advances from Compose to Delivery and bakes from Delivery; Windows/Linux use Ctrl+Enter. Standard text undo remains available.

## 3 · Review and finish

Check destinations, segment counts, date, caption and warnings.

- **Try Another Caption** changes copy while keeping the delivery plan. Use **‹ / ›** to browse up to eight versions.
- **Edit caption** lets you correct a version. Apply or cancel it before creating drafts or scheduling; unsaved edits cannot be submitted accidentally.
- **Edit title** changes only YouTube’s title. **Try another title** generates one from the caption. Titles have a 100-character limit; the description is separate.
- Change the date/time here without regenerating your copy, then choose **Update time**. Submission also saves an edited time before confirmation.
- **Create Drafts** leaves social posts for approval in Postiz and WhatsApp Status for separate approval.
- **Schedule directly** asks you to confirm the reviewed destinations and also approves the selected WhatsApp Status for its saved audience.

YouTube descriptions end with the business hashtag, or `#shorts` if it is blank. Titles use the configured business hashtag when present, within the limit.

**TikTok Inbox Upload is a handoff:** finish publishing in TikTok, paste the prepared caption and choose the cover there. The completion screen stays available with **Copy caption for TikTok**. Direct Post is a different, audited API configuration.

After other direct schedules, an eight-second active countdown returns to Dashboard. Choose **Stay here** or interact with the receipt to stop it. Hidden windows and open dialogs pause it.

## WhatsApp

Open **WhatsApp** to see the connection or scan the QR with your authorized phone. A working session is preserved. Choose its default Status audience in the same window; queued plans keep the audience they were approved with.

Send media and a request to your self-chat while services are running. Be explicit:

```text
Facebook and Threads tomorrow at 7:15 pm; idea: announce our new hours
WhatsApp tomorrow at 7:15 pm; caption: "We open at 10 tomorrow. See you! ✨"
```

Unquoted `idea:` asks for generation; `caption:` / `text:` or quoted wording preserves your words. The response gives a review and action buttons. **Review approval → Confirm plan** creates social drafts and approves selected WhatsApp Status; it does not automatically publish the social drafts. Typed fallback commands are included when needed. Expired buttons cannot approve a newer version.

Open settings only with the explicit **Settings** action or `postforge settings`. A regular caption never activates a settings conversation. `postforge ping 60` changes the Telegram heartbeat; `postforge ping off` disables it. These commands do not consume a waiting publishing request.

Videos over one minute become ordered Status segments. Large audiences can take several minutes per part. Look at progress and receipts before resending. The app supports a streamed video intake up to 256 MiB when the provider supplies valid download metadata; use the desktop path if that transfer fails. Smaller base64 transfers have a separate configured limit.

On Dashboard, expand **WhatsApp Status · review & approval**. Receipt history opens and closes, has date/type filters and five rows per page. “Accepted” is not proof that every contact viewed a Status. An uncertain send is held for review rather than replayed automatically.

## Telegram

Each installation uses its own dedicated bot and one private owner. In **Telegram**, validate the BotFather token, send `/start` to the bot, find/select your private account, choose language and heartbeat, then explicitly enable and save.

Send `/new` for guided buttons, `/status` for service reachability, `/settings` for heartbeat options or `/cancel` to abandon an unfinished request. Caption mode, destinations, formats, time and confirmation are separate steps. Group posting is not supported, even if Telegram lets you add the bot to a group.

The cloud Bot API download path accepts files up to 20 MB. Use the desktop app for larger media. A heartbeat reports a running receiver; it cannot wake a sleeping Mac. After migration, the bot remains paused until you stop the old receiver and enable the destination.

## Which link or login do I need?

| What you see | What to do |
|---|---|
| Postiz link ready | Open or copy that link. Do not rotate it routinely. |
| New temporary link detected | Choose **Use detected link**, then wait for verification. |
| Public link unreachable | Check Docker/internet and try **Check access**. Green account tokens do not verify file delivery. |
| Token renews on next use | Use **Connections → Check & renew**. Reconnect only if renewal fails. |
| One account needs reconnection | Follow that account’s reconnect guide; keep other channels intact. |

```text
Public link → gateway password + authenticator → Postiz login → calendar
Social-account authorization is a separate connection inside Postiz.
```

A changed hostname may require the two browser logins again without invalidating every social token. When reconnection is actually needed, update that provider’s matching OAuth callback first. Callback URLs are settings to copy, not pages to visit. Instagram’s two connectors have different callbacks.

TryCloudflare’s temporary hostname can change after a connector restart. Synchronize the detected link instead of repeatedly rotating it. A named tunnel and your own domain avoid that routine change. After a hostname change, keep your caption edits and prepare a fresh review before submitting old media links.

## Backup & Move

1. On the old host, **Create backup**. Choose a destination and a passphrase of at least 12 characters. Videos can make the `.pfbackup` large.
2. On the destination, **Restore backup → Choose backup file**, enter its passphrase and **Inspect backup**. Inspection changes no live data.
3. Read the result, enter the passphrase again and confirm that the old publishing host is stopped. Replacing existing data requires an extra confirmation and rollback backup.
4. After restore, services and Telegram remain paused. Check the public URL, gateway, channel sessions and timezone, then start services and explicitly enable Telegram. WhatsApp may need pairing again.

Closing the assistant does not cancel a running job. Reopening finds live progress. If progress reads fail, **Resume progress** reconnects to the same task; do not start a second restore. The passphrase is not retained and cannot be recovered.

## Updates, resources and cleanup

Updates run at startup and every six hours. The tray marks an available update; a manual check also inspects components. macOS installs the matching client/runtime and refreshes configured services. Windows/Linux prepare a verified archive for manual replacement. Upstream Evolution versions require a tested compatibility update, not an arbitrary image replacement.

**Manage services** stops only this stack after confirming no scheduled/approved work is waiting. It pauses WhatsApp intake and leaves shared Docker/Ollama tools and other projects alone. Start it again before publishing. Telegram’s lightweight host receiver may stay available while the computer is awake. Automatic legacy Swift sleep/wake controls are not part of the Rust client. Keep the host awake for scheduled delivery.

**History & caption defaults** uses 30 days by default. Unused staged WhatsApp files are cleaned automatically; referenced media and saved Postiz posts are protected. Changing the window does not delete immediately or reset approval identifiers. Do not expect a 30-day setting to delete every historical Postiz video. The technical guide explains explicit broader cleanup.

**Remove posts** previews unpublished drafts/failed entries and queued work before confirmation. It does not remove content already published on social networks. A send already in progress may finish. Check platform history before retrying a failed batch.

The tray groups publishing, connections, local services and support. **About** is near the end, before **Quit**. Quit closes the desktop client; services keep running. Closing the window hides it; ⌘N/Ctrl+N reopens it while PostForge is active. Siri can use an OS **Open App** shortcut; the older Swift-specific shortcut integration has not been ported.
