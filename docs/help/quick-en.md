# PostForge Quick Start

This is the current v2 desktop workflow. The older Swift instructions are retained below for reference; run only the Rust client during v2 testing.

## Rust desktop and guided Telegram

The Rust/Tauri client separates **Compose**, **Delivery** and **Review & finish**.
Enter the message without schedule commands, choose idea generation or exact
words, then attach optional media. Choose destinations and a local date/time
on the next screen. Review the baked plan before finishing. Cover and business
hashtag settings live in one options section. Caption versions preserve delivery.

Create a bot with **/newbot** in **@BotFather**. Enter the token in the local
setup prompt. It identifies your private owner account and registers commands.
Keep group privacy enabled. Inline mode and public webhooks are unnecessary.

```text
python3 v2/telegram_setup.py --language en --heartbeat 15
python3 scripts/host_agent.py restart
python3 scripts/host_agent.py status
```

Use **py -3** instead of python3 on Windows. Send **/new** to the private bot.
The buttons guide caption mode, media, destinations, formats, time and review.
Use **Try another caption**, arrows or **Edit caption** to refine the copy.
Submit only after the final confirmation. WhatsApp Status has its own approval.
**/cancel** discards an unfinished plan and **/status** checks reachability.

The bot's cloud download limit is 20 MB per file. Use the desktop app for larger
videos. Keep the host awake and services running when jobs are due. Start the
agent after reboot or configure your OS startup manager.

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
Choose the cover on the platform for TikTok inbox uploads and YouTube Shorts.

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
