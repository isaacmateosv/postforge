# Set up publishing channels

[Español (Ecuador)](channel-setup-es.md) · [Reconnect an existing channel](README.md)

Create developer apps only for the channels you plan to use. The scope lists
below describe what the Postiz image pinned in PostForge requests, with
PostForge's default Meta compatibility patch applied. A provider may accept
fewer scopes for a single API operation. Some Postiz connectors check the
whole list at login, so a scope for comments or analytics can still be needed
to connect. Provider app review and the account's permission to publish are
separate from OAuth consent.

## Connect for the first time

1. Choose the stable HTTPS address for Postiz. Use it as the base for every
   callback below. Register the exact URL, including the path, with the
   provider. Keep the gateway in front of Postiz and complete the OAuth flow
   in the same browser session.
2. Create the app and enable the matching product or use case. For development,
   add only the operator accounts that need to test. Request the listed scopes
   for the channels you enable. Complete provider review when required for
   production access or users outside your developer and tester roles.
3. Copy the matching ID and secret into the private `.env`. Run
   `docker compose up -d postiz` to recreate Postiz with the new credentials.
4. In Postiz, select **Add Channel**, choose the corresponding provider,
   authorize with the account that can publish to the intended page or
   channel, and verify the selected destination before scheduling a real post.

## Meta

- **Facebook Page.** In Meta for Developers, create or select an app with
  Facebook Login for Business and the Pages use case. Register
  `/integrations/social/facebook`. Use `FACEBOOK_APP_ID` and
  `FACEBOOK_APP_SECRET`. The authorizing account needs access to create
  content on the Page. The connector requests `pages_show_list`,
  `business_management`, `pages_manage_posts`, `pages_manage_engagement`,
  `pages_read_engagement`, and `read_insights`.
  [Postiz Facebook setup](https://docs.postiz.com/self-host/providers/facebook)
- **Instagram via Facebook Login.** Use a professional Instagram account
  linked to a Facebook Page. Add the Instagram use case to the Meta app,
  register `/integrations/social/instagram`, and use the same
  `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET`. The connector requests
  `instagram_basic`, `pages_show_list`, `pages_read_engagement`,
  `business_management`, `instagram_content_publish`, and
  `instagram_manage_comments`. PostForge drops `instagram_manage_insights`
  by default for this connector. Instagram analytics through this connection
  may be unavailable.
  [Postiz Instagram setup](https://docs.postiz.com/self-host/providers/instagram)
- **Instagram Standalone.** Use a professional account with Instagram
  Business Login. Register `/integrations/social/instagram-standalone`, use
  the Instagram app credentials `INSTAGRAM_APP_ID` and
  `INSTAGRAM_APP_SECRET`, and select the standalone option in Postiz.
  The connector requests `instagram_business_basic`,
  `instagram_business_content_publish`, `instagram_business_manage_comments`,
  and `instagram_business_manage_insights`.
  [Postiz Instagram Standalone setup](https://docs.postiz.com/self-host/providers/instagram)
- **Threads.** Create a Meta app with the Threads API use case and configure
  its OAuth redirect as `/integrations/social/threads`. Copy the Threads app
  ID and secret into `THREADS_APP_ID` and `THREADS_APP_SECRET`. In development,
  add the intended Threads profile as a tester and accept its invitation.
  The connector requests `threads_basic`, `threads_content_publish`,
  `threads_manage_replies`, and `threads_manage_insights`.
  [Postiz Threads setup](https://docs.postiz.com/self-host/providers/threads)

## TikTok

Create a developer app with **Login Kit** and **Content Posting API**. Register
`/integrations/social/tiktok` and use the client key and secret from the same
environment in `TIKTOK_CLIENT_ID` and `TIKTOK_CLIENT_SECRET`. For Sandbox,
add the intended TikTok account as a target user. The pinned connector checks
all six scopes: `user.info.basic`, `user.info.profile`, `user.info.stats`,
`video.list`, `video.upload`, and `video.publish`. TikTok's inbox upload
endpoint uses `video.upload`, while this connector also requests
`video.publish`. PostForge defaults to inbox upload. You finish the post in
TikTok. Direct Post eligibility and public visibility depend on TikTok review.
[TikTok app form](../tiktok-app-form.md) · [TikTok inbox upload](https://developers.tiktok.com/docs/en/content-posting-api-get-started-upload-content)

## YouTube

Create a Google Cloud project. Enable **YouTube Data API v3** and
**YouTube Analytics API** for this connector's analytics. Configure the OAuth
consent screen and add the channel operator as a test user if the app is in
Testing. Create a **Web application** OAuth client with the authorized redirect
`/integrations/social/youtube`. Copy its ID and secret into
`YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET`. Select the intended channel
during authorization.

The pinned connector checks these eight scopes, each prefixed with
`https://www.googleapis.com/auth/`: `userinfo.profile`, `userinfo.email`,
`youtube`, `youtube.force-ssl`, `youtube.readonly`, `youtube.upload`,
`youtubepartner`, and `yt-analytics.readonly`. Google's upload endpoint
accepts `youtube.upload` alone, but that grant does not satisfy the pinned
connector's login check. Google OAuth verification and test-user rules still
apply.
[Postiz YouTube setup](https://docs.postiz.com/self-host/providers/youtube) · [YouTube upload authorization](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert#authorization)

## WhatsApp through Evolution

1. Set a unique, strong `AUTHENTICATION_API_KEY` and choose `WA_INSTANCE` in
   the private `.env`. Start PostForge and open **WhatsApp Manager** from the tray.
2. Use server `http://localhost:8080` and the global API key. Select the
   configured instance, or run `./scripts/link-whatsapp.sh` to create a
   missing instance and show its QR code.
3. With the authorized primary phone, open **WhatsApp → Linked devices** and
   scan the QR. Check that the Manager shows the instance connected. Send a
   harmless request in your self-chat to verify intake.

The Baileys connection uses linked-device access. It requires no developer
app, OAuth scopes, or Meta Business admin role. The Evolution global key is
an administrative credential for the local API. Keep the Manager on loopback
and keep the key private. Use only the WhatsApp account you are authorized
to link. [WhatsApp reconnection](whatsapp.md)
