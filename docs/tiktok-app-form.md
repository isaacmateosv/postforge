# TikTok app form: texts to paste

Reviewed against your form export of 2026-10-31 ("ADP TK Posts").

## App details

- **Description** (max 120 characters; replaces "Automated publishing", since TikTok expects a person in the
  loop):
  `Internal tool for your organization: prepares our videos as drafts and posts them to our own TikTok after review.`
- **Category:** Utilities is fine (Business also fits).
- **Terms of Service URL:** `https://<YOUR_PUBLIC_SITE>/terms-of-service.html`
- **Privacy Policy URL:** `https://<YOUR_PUBLIC_SITE>/privacy-policy.html`
- **Platforms:** tick **Web**, website URL `https://<YOUR_PUBLIC_SITE>/index.html`
  (the same home page; TikTok left the bare site address unverified, see below).
- **App name:** shown to you when you authorize. "ADP TK Posts" works; "PostForge Publisher" reads clearer.

## Verify the URLs ("This URL is not verified")

1. URL properties → verify a **URL prefix**: `https://<YOUR_PUBLIC_SITE>/`.
2. Download the signature file TikTok shows (`tiktok….txt`). Hand it to me, or publish it yourself:
   copy it into `docs/site/`, then
   `git -C docs/site add -A && git -C docs/site commit -m "TikTok verification" && git -C docs/site push`.
3. A minute later, click **Verify**. The prefix covers every link that starts with it.
4. Seen 2026-10-31: the prefix verified and 2 of the 3 links with it. The third was most likely the
   website link. TikTok seems to treat the bare `…/<YOUR_PUBLIC_SITE>/` address as outside the prefix
   (it may drop the final `/`), so use the `…/index.html` address above. It's inside the prefix, and
   no second property is needed.

## Products and scopes

- **Login Kit:** redirect URI `https://<NGROK_DOMAIN>/integrations/social/tiktok`
- **Content Posting API**, with **Direct Post** turned on. Postiz asks for `video.publish` even for
  drafts (it reads the account's posting limits with it), and a login without all six scopes fails in
  Postiz ("Missing required permissions"). Drafts still go to your TikTok inbox
  (`TIKTOK_POSTING_METHOD=UPLOAD`).
- **Scopes** (all six that Postiz requests): `user.info.basic`, `user.info.profile`, `user.info.stats`,
  `video.list`, `video.upload`, `video.publish`. **Add scopes** never lists three of them, because they
  come with the products: `user.info.basic` with Login Kit ("Included in Login Kit"), `video.upload`
  and `video.publish` with Content Posting API. So add the products first.

What Postiz does with each (read from its TikTok code): `user.info.basic` / `user.info.profile` show the
connected account's name, picture and username; `user.info.stats` gives follower, like and video
counts for analytics; `video.list` finds a video after you publish it from the inbox, for its link and
stats; `video.upload` sends a draft to your inbox; `video.publish` posts directly and reads the
account's limits (longest video, privacy options).

## Sandbox: needed for the demo, and to test before any review

1. Next to the app's name, switch **Production → Sandbox** → **Create Sandbox** → name it and clone the
   production configuration → Confirm → check products and scopes → **Apply changes**.
2. Sandbox settings → **Target users** → Add account → log in with your organization’s TikTok and accept
   TikTok's developer terms (up to 10 accounts; it can take up to an hour to show).
3. Paste the **sandbox's** Client key and Client secret into `.env` (`TIKTOK_CLIENT_ID` /
   `TIKTOK_CLIENT_SECRET`) and tell me: I recreate Postiz and check it. Then Postiz → Add Channel → TikTok.
4. Limits while unaudited (TikTok's docs, read 2026-10-31): direct posts are private only, and only to
   **private** accounts (error `unaudited_client_can_only_post_to_private_accounts`); the sandbox gives
   no access to public videos. For inbox drafts the docs state no such limit, so we test it. At most 5
   drafts can wait in the inbox per 24 h.

## Before you submit: review risks

TikTok's review guidelines (read 2026-10-31) turn down apps for private or personal use and apps still
in development or testing, and the website URL can't be a landing or login page. An internal tool for
one organization’s account may be turned down on the first point however good the demo is, so test in the
sandbox first, then decide. The demo must also show the website's domain (GitHub Pages); the tool
itself runs on the ngrok domain, which the explanation below names.

## App review explanation (max 1000 characters)

One paragraph, 927 characters:

```
This app is our team's publishing tool: a self-hosted Postiz instance at https://<NGROK_DOMAIN> (team login only); our website and policies are at https://<YOUR_PUBLIC_SITE>/. Login Kit: we connect our TikTok account once; user.info.basic and user.info.profile show which account is connected, user.info.stats shows follower, like and video counts in the tool's analytics, and video.list finds our published videos so the tool can show their links and stats. Content Posting API: after a person on our team reviews and approves a draft in the calendar, the tool sends the video to our TikTok inbox (video.upload), where we finish and publish it in the TikTok app; video.publish reads our posting options and can post directly instead. Nothing is posted without human approval, and no other users' data is accessed.
```

## Demo video (mp4 or mov; up to 5 files of 50 MB each)

What it is: a screen recording of one to three minutes in which someone uses the integration from
start to finish, so TikTok's reviewers see every product and scope at work. It can only be made once
the sandbox works with Postiz (keys in `.env`, TikTok connected, a test draft in the inbox). Then I
prepare a short test video and the draft, and you click through while recording. TikTok requires a
first review's demo to come from the sandbox. The shots:
1. Open the website URL (`…/<YOUR_PUBLIC_SITE>/index.html`) and its privacy and terms links.
2. Postiz → Add Channel → TikTok → TikTok's login and consent screen with the scopes listed (Login Kit)
   → authorize. Show the connected account's name and picture (`user.info.basic`, `user.info.profile`).
3. Create a post with a video, approve it, and send it to TikTok as an upload (`video.upload`). On the
   phone, show it arriving in the TikTok inbox, then publish it there.
4. Send a second one as a direct post with privacy "Only me" (`video.publish`). Unaudited apps can
   direct-post only to private accounts: if your organization’s account is public, add a private TikTok
   account as a second target user for this part.
5. Back in Postiz: the published video found and linked (`video.list`), and the channel's analytics
   with follower and like counts (`user.info.stats`).

Record the Mac with Cmd+Shift+5, and the phone with its own screen recording (or mirror it through
QuickTime → New Movie Recording → your iPhone as the camera). Put the files in Downloads: I'll cut and
compress them under 50 MB.

## Staying in the sandbox (no review)

What TikTok's docs say (read 2026-10-31): the sandbox gives no access to the Content Posting API "for
public videos", and whatever an app TikTok hasn't audited posts is restricted to private viewing
(direct posts only work on private accounts). So a sandbox app can't publish publicly. The docs don't
say whether its inbox drafts arrive, or whether the TikTok app then lets you post them as Everyone:
only a test shows that. (Gemini's "completely disables access" goes further than the docs.)

The test (about 15 minutes, nothing public):
1. Sandbox → Add products → **Content Posting API** → Direct Post on → **Apply changes**.
2. `.env`: the sandbox's Client key → `TIKTOK_CLIENT_ID`, Client secret → `TIKTOK_CLIENT_SECRET`.
3. `docker compose up -d postiz`, then Postiz → Add Channel → TikTok → log in as `your organization’s TikTok account`.
4. Send one short video as an upload (the default). In the TikTok app: does it reach the inbox, and
   can you post it as Everyone?

- **If it can:** TikTok works through the sandbox, as drafts you finish in the TikTok app. TikTok
  means the sandbox for testing, so it may change that.
- **If it can't:** "TikTok assist" (to build): at the planned time the PostForge sends the
  TikTok video and caption to your own WhatsApp chat, to post in the TikTok app in a few taps (where
  you can also add a TikTok sound, which the API can't). Or schedule it in TikTok Studio on the web.
- Other routes: Postiz Cloud has its own audited TikTok app, but it's a paid hosted service outside
  this setup. This Postiz build also has a "TikTok Business" channel (`TIKTOK_BUSINESS_CLIENT_ID` /
  `TIKTOK_BUSINESS_CLIENT_SECRET`, TikTok's API for Business); it needs its own developer app and
  approval, not checked yet.

## Photo posts (optional)

URL properties → verify the URL prefix `https://<NGROK_DOMAIN>/uploads/` with the file
TikTok gives you (put it in `data/postiz-uploads/`). Videos don't need this.
