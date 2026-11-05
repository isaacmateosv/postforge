# If the public address changes

Every network login comes back to PostForge's public address
(`https://<NGROK_DOMAIN>` today). It doesn't expire, but it changes if you
move to another ngrok account or another tunnel. If that happens, update every place below, then
reconnect every channel.

1. **`.env`:** `NGROK_DOMAIN`, `FRONTEND_URL`, `NEXT_PUBLIC_BACKEND_URL` and `MAIN_URL` take the new
   address.
2. **Meta app** (developers.facebook.com):
   - App settings → Basic → **App domains**, and the **Website** platform's Site URL.
   - Redirect URLs `…/integrations/social/facebook` and `…/integrations/social/instagram`: under
     Facebook Login for Business → Valid OAuth Redirect URIs, and in the Instagram API use case's
     redirect list.
3. **TikTok app** (developers.tiktok.com), in Production and in the Sandbox:
   - Login Kit → Redirect URI `…/integrations/social/tiktok`.
   - URL properties: `…/uploads/`, only if you post photos.
4. **Threads app** (Meta): redirect callback `…/integrations/social/threads`.
5. **Google OAuth client** (console.cloud.google.com → Credentials): Authorized redirect URI
   `…/integrations/social/youtube`.
6. `./postforge.sh restart`, then reconnect each channel ([README.md](README.md)).

The policy pages on GitHub Pages (`https://isaacmateosv.github.io/almadulce-bakery/`) don't change.
