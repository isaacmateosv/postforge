# PostForge Quick Start

This is the current v2 desktop workflow. The older Swift instructions are retained below for reference; run only the Rust client during v2 testing.

## Rust desktop and guided Telegram

Start on **Dashboard** to see draft/scheduled counts, the next post and connection
indicators. Open Postiz to review saved work, or choose **New post**.

1. **Compose**: enter an idea or select exact words, then attach optional media.
2. **Delivery**: choose networks, formats and date/time. **Soon · +10 min** fills
   a nearby future time. New installations have an empty business hashtag.
   Existing configured tags are retained. For text-only WhatsApp Status, pick
   a background color. Cover and hashtag options are grouped below.
3. **Bake and review**: a small animated mixer shows preparation. One initial
   caption appears. **Try Another Caption** adds another take; arrows browse
   them. Editing the caption updates the selected take. The shortened Threads
   adaptation is labelled separately. **Edit title…** changes the YouTube title
   independently (up to 100 characters). Review the destination/segment counts,
   then create drafts or explicitly confirm direct scheduling.

Long Facebook/Instagram stories create multiple segments, scheduled one minute
apart. A 205-second video means **one feed post + four Story drafts** per network
when both formats are selected. YouTube Shorts uses a separate **2:59** copy for
longer portrait/square videos; the other networks keep the full video. In **Automatic** mode, landscape videos retain their full duration as regular uploads. Vertical/square videos use Shorts. The explicit Regular video option cannot override YouTube’s classification for eligible short portrait videos. Landscape sources are not silently cropped to Shorts.

Use **WhatsApp** in the header to see connection status or scan its QR directly
in the window. A working connection stays paired. **Remove posts…** first asks
whether to remove drafts or cancel scheduled posts, then shows counts before
confirmation. Published posts remain online.

The local backend is discovered automatically; folder selection is not part
of normal use. **Settings → Advanced · recovery and migration** is only for
locating a recovered or migrated installation. No path clutters the dashboard.

Open **Telegram** in the app header. Each installation uses its own dedicated
bot and one authorized private owner; there is no shared global bot. Create it
with **/newbot** in **@BotFather**, paste the token into the masked field and
choose **Validate bot**. Send **/start** to your bot, then use **Find my private
account**, select your account and verify its numeric ID. Choose the bot language
and a heartbeat interval (**0** = off, otherwise **5–1440 minutes**), enable it
and confirm **Save settings**. No terminal is required. Keep group privacy enabled;
inline mode and public webhooks are unnecessary. Send **/new** to your bot.

The buttons guide caption mode, media, destinations, formats, time and review.
Use **Try another caption**, arrows or **Edit caption** to refine the copy.
Submit only after the final confirmation. WhatsApp Status has its own approval.
**/cancel** discards an unfinished plan and **/status** checks reachability.

The bot's cloud download limit is 20 MB per file. Use the desktop app for larger
videos. Keep the host awake and services running when jobs are due. Start the
agent after reboot or configure your OS startup manager.

Your private .env and encrypted credential backups include the bot token,
owner, language, heartbeat and enabled preference. After migration Telegram
is paused: stop the old receiver, review the saved settings on the new host
and explicitly enable it. Keep the backup and passphrase private. A blank
token field keeps the saved token. Disabling retains your settings and works
even when Telegram is unavailable.

## Legacy Swift Mac workflow

Turn a photo or video and an idea into a draft you can review before it goes live.

```text
Media or text → Bake and review
                   ├─ Create drafts → Approve in Postiz
                   └─ Confirm direct scheduling
WhatsApp Status → separate approval
```

## Make your first post

1. Open PostForge from the menu bar. If it says **Idle** or **Off**, choose **Turn On**.
2. Open **New Post** and drag in a photo or video.
3. Say where and when to post, then give an idea or quote the exact words you want.

```text
YouTube Shorts tomorrow at 9 a.m. Caption: “Here’s what we made this week.”
```

You can also put the idea first, followed by a semicolon, such as “Cookies and cupcakes; post everywhere at 7:15 pm, posts and stories.”

4. Click **👨‍🍳 Bake idea**. Check the time, channels, caption, and video warnings.
5. Click **Create Drafts**, then open **Postiz Calendar**. Review the draft and approve the schedule there.

Use **idea:** or **write about** followed by an unquoted brief to generate a caption. Use **caption:** or **text:** for your finished wording. A caption enclosed in double quotation marks is preserved, including when it follows **idea:**. The reusable final hashtag is still appended if configured.

```text
Facebook and Threads tomorrow at 7:15 pm; idea: announce our new opening hours
WhatsApp tomorrow at 7:15 pm; caption: "We open at 10 tomorrow. See you! ✨"
```

The wider Mac composer keeps the request and media on the left and the plan on the right. **Create Drafts** becomes available after a successful bake. Changing the request, media, formats, or cover requires another bake. The request box grows within the window and scrolls for longer text.

Use **Try Another Caption** for another wording, **‹ / ›** to browse up to eight retained versions, and **Edit Caption…** for manual corrections. These actions change only the copy section, including the related Threads caption and YouTube title. Time, destinations, cover, notes, and warnings stay on the same plan. An exact caption is rewritten only when you explicitly request another version. Versions belong to the current baked plan.

On macOS, **⌘ Return** bakes the idea and **⌘Z** undoes request edits. **Schedule Directly…** schedules the selected social posts after confirmation. **Create Drafts** keeps the separate Postiz approval step. WhatsApp Status requires its own approval.

## Send a text-only announcement

When no media is attached, Bake idea opens a destination check. Select **Facebook post**, **Threads post**, **WhatsApp Status**, or a combination. The plan shows your choices before creation. Instagram feed posts and Stories, Facebook Stories, TikTok, and YouTube require media in this workflow. To use an announcement on those placements, attach a suitable image or video.

In WhatsApp, confirm supported text destinations explicitly, for example:

```text
Facebook y Threads mañana a las 19:15, solo texto aprobado; texto: "Mañana atendemos desde las 10. ✨"
WhatsApp tomorrow at 7:15 pm; caption: "We open at 10 tomorrow. ✨"
```

Use **improve plan 1** when offered to request new wording while preserving the plan. Review the returned caption before approval. You can use your own exact text from the start.

## Clear unwanted work

**Clear…** offers a local composer reset, deletion of Postiz drafts and failed entries, cancellation of queued posts and pending WhatsApp Status items, or both stored-work scopes. It previews the number of matching entries before a separate confirmation. A composer reset clears unsaved fields only. Cleanup uses the current Postiz organization and skips entries whose state changed after the preview.

Published entries are outside the cleanup scope. A send that already started may finish. Review any item with unconfirmed delivery before posting again. Shared media follows the configured retention period. Intake plans still waiting in the WhatsApp review window can be rejected there.

## Choose formats and a cover

Use **Draft Options** in the menu bar for shortcuts to the formats and cover controls.
In the composer, use **Create drafts for** to choose posts, stories, or both.
**Automatic** follows your instruction. “Post everywhere” includes posts and
stories where supported. Stories need media. WhatsApp uses its own Status format.

For a single video, use **Video cover** to choose a separate image or enter a
second, such as `12.5`. The plan shows which drafts can use the cover.
Instagram Reels accept both options. Regular YouTube videos use an image or a
frame extracted from the video. TikTok Direct Post can use a frame timestamp.
Choose the cover on the platform for TikTok inbox uploads. YouTube videos and Shorts send the selected image or extracted frame as a custom thumbnail; channel eligibility still applies.

If the plan has a video for a destination that accepts a cover and you haven’t chosen one, PostForge asks whether to continue. After reviewing the plan, use **Edit cover…** to unlock the cover controls and bake the revised plan again.

Expand **Publishing options** and choose **Configure…** beside **Final hashtag** to set a reusable hashtag. Leave the field blank to omit it. The preview includes the tag on the last line, even with an exact caption. In WhatsApp, reply with the suggested `tag plan 1 #MyBusiness` command to change it for that plan, then review and approve.

## Use WhatsApp or Siri

Send a file and instruction to your own WhatsApp chat while PostForge is on. Review the plan it sends back. Confirming the plan prepares your drafts. Review social drafts in Postiz. Add “only posts”, “only stories”, “posts and stories”, or “cover at 12.5 s” before your caption. For a separate cover, attach one video and one photo and say “cover image”. The reply shows the plan and gives you the commands to approve it or reject it and resend your request.

On your Mac, import **New post in PostForge** using **Siri Shortcuts…** in Help and say its name to Siri. The shortcut opens the composer. Choose **Turn On** there if services are idle.

After creating drafts in the Mac composer, approve any queued WhatsApp Status separately. Use **Approve Status…** in the plan or **Approve WhatsApp Status…** in the menu bar. Check the confirmation in your WhatsApp self-chat. Overdue statuses can send as soon as approved.

## Free up your Mac for editing

PostForge turns off its services after an hour without activity or queued work. While idle, incoming WhatsApp commands wait. Enable **Notify My WhatsApp Before Idle** if you want a note in your self-chat before shutdown. Turn off **Turn Off When Idle** if you need continuous intake while your Mac is awake.

## Video limits worth checking

- **Instagram Reels** over three minutes aren’t recommended to new audiences.
- **YouTube Shorts** need a vertical or square video of up to three minutes.
- **Facebook/Instagram Stories** split a long single video into separate clips. Review each Story draft in order.
- **WhatsApp Status** splits longer videos into clips of up to 60 seconds after approval.

## Find things again

- **Postiz Calendar** shows drafts and scheduled posts.
- **Check for Updates** is in the top-level tray menu.
- **Backup & Move** lets you export a private backup.
- Switch to **Technical** in Help for setup, recovery, and data details.


## Window, tray and migration
The Rust window opens centered at a comfortable width (up to 1120 logical pixels), using extra height when the desktop allows it. It keeps the system menu bar accessible and can still be maximized manually. Its header and bottom controls stay visible; the working area and long dialogs scroll. On shorter displays, spacing becomes more compact. Close hides the window; ⌘N (macOS) or Ctrl+N (Windows/Linux) reopens the composer while PostForge is the active app. Clicking the Mac Dock icon also restores the window. Quit in the tray exits the client while publishing services continue.

Use **Backup & Move** in the window or tray. Export creates one authenticated, encrypted `.pfbackup` containing credentials, gateway configuration, Postiz data and media, and rehearses restoration in a disposable database. Keep the passphrase (at least 12 characters) separately; it cannot be recovered. Inspection does not change live data. Restore requires inspecting the same file, entering the passphrase again and confirming the old host is stopped. Replacing initialized data needs an explicit checkbox and creates an encrypted rollback backup first. Different database credentials require a fresh destination installation. Restored services stay stopped and Telegram stays paused: verify the public URL, gateway access, channel sessions and schedules before starting services or enabling Telegram. WhatsApp may need linking again.

The tray provides Dashboard, New Post, WhatsApp plans and approvals, connections, backups, updates, settings and Help. About is near the bottom before Quit. A small count beside the monochrome icon indicates active work. Update checks run at startup and every six hours; manual checks include Docker components and Evolution. An incomplete check is reported as incomplete; the desktop checker only offers matching Rust desktop ZIP assets, not legacy packages.


### Finding actions in the desktop app

Compose → Delivery → Review stays at the top of the window. Choose **Generate a caption** for an idea or **Use my caption** to keep your wording. Radio choices have separate focus and selection indicators. The footer contains privacy information and, while composing, **Clear composer**. Maintenance lives in **Settings → App & data**: update checks, **Backup & Move**, and removal of unpublished drafts or queued posts. Language is also in Settings. Dashboard refresh is next to **Open Postiz**. These actions remain available in the tray. Selecting a cleanup scope still shows a preview and asks for confirmation before removing anything. The mixer only animates while preparing a plan and respects the system reduced-motion preference.


## Previews, connection health and WhatsApp delivery

Use the Compose player to preview selected media; playback pauses when leaving the window or step. In Delivery, preview an uploaded cover or enter its video timestamp. **Use current frame** selects the paused player position. Cover support depends on the destination.

**Connections** reports each channel’s Postiz session state and actual token validity. It distinguishes connected, renewal pending, paused and reconnect required; it does not guarantee publication success.

In **WhatsApp → Audience**, select all contacts or selected international phone numbers and save. New plans use this audience; already queued plans retain their previous audience. Changes are blocked while a Status is sending. Large audiences may take several minutes per segment; follow the visible segment progress instead of resending. Delivery receipts can be expanded or hidden, filtered by date/type, and browsed five per page.

YouTube descriptions end with your business hashtag, or `#shorts` if it is empty. Titles do not receive an automatic hashtag. The description remains independent of the 100-character title.


## Public URL and tunnel

Open **Settings → Public access** or **Public URL & Tunnel** in the menu bar. Choose temporary TryCloudflare, your own domain through a named Cloudflare tunnel, or saved ngrok. Check access before posting. Rotating or restarting a temporary connector changes its hostname: apply the detected URL and update provider OAuth callbacks before reconnecting channels. Domain and token settings remain saved when returning to temporary mode. All provider settings travel in encrypted Backup & Move; verify the destination URL before restarting publishing. See Technical Help for the complete procedure.


Click the current public URL or **Copy link** to copy it. The control briefly turns green and confirms **Link copied**. OAuth callback URLs are clickable copy controls too; use Tab and Enter/Space with the keyboard.


The network window refreshes when you return to it and while it is visible. URL and callback copy actions check the current configuration first. If a temporary connector has changed hostnames and needs synchronization, stale links are disabled and the detected address is shown. Choose **Synchronize current URL** before copying or opening Postiz.


An expired access token with a saved refresh credential is shown as **Renews on next use**, not a queued renewal job. Choose **Connections → Check & renew** to attempt renewal now through read-only channel analytics. Only expired, renewable channels are checked. PostForge rereads the saved result; it does not mark a channel healthy just because the request returned HTTP 200. Reconnect only if renewal fails. This action does not publish posts, and background status polling does not trigger refresh requests.

### Review without starting again

In step 3, edit the publication date/time or choose **In 10 minutes**, then **Update time**. Your caption iterations, cover and destinations stay intact. Submission also saves a changed review time before confirmation.

**Try another title** generates only a YouTube title from the current caption. **Edit title** lets you write it yourself. The configured business hashtag ends the title within its 100-character limit; the description keeps its generated topic hashtags and ends with the business hashtag, or `#shorts` when no business hashtag is set.

**Schedule directly** approves every selected destination, including WhatsApp Status for the configured audience at the reviewed time. **Create drafts** keeps the separate WhatsApp approval. Split Status videos can take several minutes per segment for large audiences. A sending indicator does not mean failure.

### Clear next steps and messaging settings

The next action stays at the bottom of the composer: **Choose delivery**, **Bake and review**, then **Create Drafts** or **Schedule directly**. A green **Cover ready** message confirms that the selected image/frame preview succeeded; preview errors stay visible. Confirmation means the cover was selected, not that every destination accepts it.

After direct scheduling, a success screen returns to Dashboard after **eight active seconds**. Choose **Stay here** or interact with the receipt to stop the countdown. Hidden windows and open dialogs pause it. Draft creation stays on the receipt so you can finish any separate WhatsApp approval.

In Telegram, open **Settings · activity ping**, or send `/settings`. Choose Off, every 30 minutes, hourly, every six hours, or daily. Your current posting plan stays intact. The next interval starts after the change; no test ping is sent. The worker must remain running to send activity messages; a ping cannot wake a stopped Mac or stopped service.

In your WhatsApp self-chat, send **only** `postforge settings` to see preferences. Change the Telegram ping with `postforge ping 60`, or disable it with `postforge ping off`. These are standalone commands: they never open automatically from caption text, change the next message into a settings reply, or consume media waiting for a posting request. Granular 5–1440-minute intervals remain available; 0 means off. Preferences are saved in the installation configuration and included in encrypted migrations. Restoring a backup keeps Telegram paused until you explicitly activate it.

The tray groups **Publishing**, **Connections**, and **App & Support**. WhatsApp Plans & Receipts stays in the main menu; About sits directly before Quit.

Gateway sign-in now defaults to **30 minutes without requests**, with a **two-hour maximum session**. Postiz has a separate login. Backups retain your configured timeout. YouTube's short-lived access token can expire between uses; **Automatic renewal available** means a refresh credential is stored, not that publishing has been tested. Use **Check & renew** to verify it now; reconnect only if renewal fails.

### WhatsApp buttons

When you prepare a plan in your self-chat, PostForge sends its copyable caption and a compact action card. **Review approval** shows exactly what will happen; **Confirm plan** creates the social drafts and approves WhatsApp Status when selected. It does not automatically publish social drafts. **Try another caption** changes the copy, and **More options** offers preview cancellation or Settings. Discarding a preview also requires confirmation and leaves saved Postiz posts alone.

Open ping settings with `postforge settings` or the explicit **Settings** button. Interval buttons change only the Telegram activity-ping preference; **Back** returns to your plan. A normal caption never opens settings. Typed commands remain available if a client cannot display the card. Outdated, expired or already-used buttons cannot approve a changed plan; use the latest review instead.

### Restore a `.pfbackup` file

On the destination computer, open **Settings → App & data → Restore backup**. You can also choose **Restore backup** inside **Backup & Move** from the tray. Click **Choose backup file**, select the `.pfbackup` file, enter the passphrase and press Enter or **Inspect backup**. Inspection leaves live data unchanged. Then re-enter the passphrase and follow the explicit restore confirmation. Stop the previous publishing host before restoring; do not replace the source installation merely to check its backup. **Advanced → Installation folder** locates an existing installed project folder; it does not import backup files.

The backup includes all retained uploaded media. Videos can make it several gigabytes; that alone does not indicate failure. Switching between Create and Restore clears the previous result so an old “Complete” message cannot be mistaken for a new inspection result. A backup passphrase cannot be recovered.

Help opens its quick guide immediately. Choose Technical guide for setup details. Loading and retryable errors appear inside Help; no separate Open guide confirmation is required.
