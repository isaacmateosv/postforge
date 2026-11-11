# YouTube setup, formats and reconnection

The same **YouTube Data API v3** and OAuth client upload Shorts and regular videos. There is no Shorts-only API permission. Postiz handles Google login; the Rust desktop is not the OAuth callback server.

## Google Cloud Console

1. Select the project used by your existing Postiz installation. In **APIs & Services → Library**, enable **YouTube Data API v3** and **YouTube Analytics API**. The pinned connector uses Data for uploads and Analytics for reporting.
2. In **Google Auth Platform → Branding**, configure the app identity. Only list domains you control; do not attempt to verify the shared `ngrok-free.dev` domain.
3. Under **Audience**, select the appropriate internal/external audience. In Testing, add each Google account that operates a channel as a test user. External apps in Testing normally receive refresh tokens that expire after seven days for these scopes. Moving to Production is subject to Google's verification and account policies.
4. Under **Clients**, create or reuse a **Web application** OAuth client. Set the authorized JavaScript origin to your public Postiz origin, and the authorized redirect URI to exactly `https://YOUR-PUBLIC-HOST/integrations/social/youtube`. Scheme, host and path must match. Retain your gateway protection; connect in a browser that has passed the gateway login.
5. Under **Data Access**, configure the scopes required by the installed connector. Every name below has the prefix `https://www.googleapis.com/auth/`:

   `userinfo.profile`, `userinfo.email`, `youtube`, `youtube.force-ssl`, `youtube.readonly`, `youtube.upload`, `youtubepartner`, `yt-analytics.readonly`.

   Google's upload endpoint accepts `youtube.upload` alone, but this pinned Postiz connector checks all eight at login. These are the connector's requirements, not the minimum permissions of a custom upload-only app. Google may require additional verification for broad scopes.
6. Keep `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` in the private `.env`. Use the ID and secret from the same web client. No API key substitutes for OAuth upload authorization. Never commit `.env` or paste secrets into issue reports.
7. If credentials changed, recreate Postiz through the normal component update/restart flow so its container receives the new environment. If they are already correct, reconnect the existing channel without changing them. In Postiz choose **Reconnect channel**, sign in as its owner and select the intended channel/brand account.

Refresh tokens belong to the Postiz database, not `.env`. Encrypted Backup & Move carries the database and credentials; after migration, verify the gateway/public origin and OAuth redirect before reconnecting anything. A changed domain needs updated client origins/redirects, not necessarily a new client secret.

## Choose the format and review

- **Automatic**: vertical or square videos use Shorts; longer sources get a separate **2:59** YouTube copy. Landscape videos retain their full length as regular uploads. Other destinations retain their own media.
- **Shorts**: supply a portrait or square video. PostForge does not silently crop landscape footage.
- **Regular video**: supply landscape footage. YouTube classifies eligible portrait/square uploads of up to three minutes as Shorts; a menu selection or hashtag cannot override that classification. To publish both formats, prepare and review separate landscape and portrait versions.
- A title has a 100-character limit. The description remains separate and is not shortened to the title limit. Review/edit the generated title before creating drafts.
- The description ends with the configured business hashtag, alongside the other topic hashtags. If no business hashtag is configured, it ends with `#shorts`. PostForge does not append `#Shorts` to the title. A hashtag does not decide the video's format.
- Use the local player in Compose to review the selected file. In Delivery, preview an uploaded cover or a video timestamp. A preview does not guarantee the platform supports custom thumbnails: choose Shorts covers in YouTube itself.

## Check connection health and test safely

Open **Connections** in the desktop header. It reads Postiz's stored credentials, refresh-needed flag, actual token expiry and authentication failures. A new successful login supersedes older authentication failures. An expired access token with a refresh token is shown as awaiting renewal, not silently declared healthy. This is session metadata, not a successful publication test or a guarantee of permissions/quota.

First prepare a disposable draft, check the title, full description and format, then explicitly schedule one test with the visibility you intend. Inspect its Postiz result and YouTube Studio before retrying other entries. Uploads longer than 15 minutes require YouTube channel verification.

## Recover a failed batch

Do not recreate successful posts. A completed WhatsApp plan may take several minutes per segment for a large audience; inspect delivery status first. For stopped Postiz ERROR entries, fix the underlying problem, review each entry and select a new future publishing time in Postiz. Reconnection does not automatically replay old failures. TikTok inbox uploads still need completion in TikTok.

| Error | Action |
|---|---|
| `401 Invalid Credentials` / refresh token | Reconnect the existing channel as its owner. Keep a correct client ID and secret. |
| `redirect_uri_mismatch` | Match the web client's exact public callback URI. |
| Access blocked / unverified app | Check Audience test users, verification and Workspace policy. |
| Quota error | Check the project's current YouTube API quotas. |
| Media URL returns HTML, authentication or range errors | Repair file-scoped gateway delivery; do not remove gateway login or make the uploads library public. |

Sources: [YouTube uploads and authorization](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert), [Shorts classification](https://support.google.com/youtube/answer/15424877?hl=en), [Google OAuth expiry](https://developers.google.com/identity/protocols/oauth2/#expiration), [Google Auth Platform](https://support.google.com/cloud/answer/15544987?hl=en), [longer uploads](https://support.google.com/youtube/answer/71673?hl=en), [Postiz setup](https://docs.postiz.com/self-host/providers/youtube).

[Guía en español](youtube-es.md)
