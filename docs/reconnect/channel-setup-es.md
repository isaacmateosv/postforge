# Configura los canales de publicación

[English](channel-setup.md) · [Credenciales y solución de problemas](app-keys.md)

Crea aplicaciones de desarrollador solo para los canales que vas a usar.
Esta lista corresponde a la versión de Postiz que usa PostForge, con el
ajuste predeterminado de compatibilidad para Meta. Algunas API permiten
publicar con un permiso más limitado, pero ciertos conectores de Postiz
verifican toda la lista al iniciar sesión. La revisión de la aplicación y
el permiso de la cuenta para publicar se tramitan por separado.

1. Elige la dirección HTTPS de Postiz y úsala como base para las rutas de
   retorno de abajo. Registra la URL completa y exacta en cada proveedor.
   Si tienes un acceso seguro delante de Postiz, completa la autorización
   en la misma sesión del navegador.
2. Crea la aplicación y activa el producto correspondiente. Para las pruebas,
   añade solo a las personas que necesiten acceso. Tramita la revisión que
   exija el proveedor para el uso en producción.
3. Guarda el ID y el secreto en tu archivo privado `.env`. Ejecuta
   `docker compose up -d postiz` para que Postiz lea las nuevas credenciales.
4. En Postiz, abre **Add Channel**, elige el proveedor, autoriza con la cuenta
   que puede publicar y verifica que seleccionaste el perfil o canal correcto.

## Meta

- **Página de Facebook.** Configura Facebook Login for Business y el caso de
  uso de páginas. La cuenta debe poder crear contenido en la página.
  Ruta `/integrations/social/facebook`. Credenciales `FACEBOOK_APP_ID` y
  `FACEBOOK_APP_SECRET`. Permisos `pages_show_list`, `business_management`,
  `pages_manage_posts`, `pages_manage_engagement`, `pages_read_engagement` y
  `read_insights`. [Guía de Postiz](https://docs.postiz.com/self-host/providers/facebook)
- **Instagram con inicio de sesión de Facebook.** Vincula la cuenta profesional
  de Instagram a una página de Facebook y agrega el caso de uso de Instagram a
  la aplicación de Meta. Ruta `/integrations/social/instagram`. Usa
  `FACEBOOK_APP_ID` y `FACEBOOK_APP_SECRET`. Permisos `instagram_basic`,
  `pages_show_list`, `pages_read_engagement`, `business_management`,
  `instagram_content_publish` e `instagram_manage_comments`. El ajuste de
  PostForge omite `instagram_manage_insights` por defecto en este conector,
  así que las estadísticas de Instagram pueden no estar disponibles.
  [Guía de Postiz](https://docs.postiz.com/self-host/providers/instagram)
- **Instagram Standalone.** Configura Instagram Business Login para una cuenta
  profesional. Ruta `/integrations/social/instagram-standalone`. Usa el ID y
  el secreto propios de Instagram, `INSTAGRAM_APP_ID` e `INSTAGRAM_APP_SECRET`.
  Permisos `instagram_business_basic`, `instagram_business_content_publish`,
  `instagram_business_manage_comments` e `instagram_business_manage_insights`.
  [Guía de Postiz](https://docs.postiz.com/self-host/providers/instagram)
- **Threads.** Activa el caso de uso de Threads en Meta. Durante las pruebas,
  añade el perfil como tester y acepta la invitación. Ruta
  `/integrations/social/threads`. Usa `THREADS_APP_ID` y `THREADS_APP_SECRET`.
  Permisos `threads_basic`, `threads_content_publish`,
  `threads_manage_replies` y `threads_manage_insights`.
  [Guía de Postiz](https://docs.postiz.com/self-host/providers/threads)

## TikTok

Activa **Login Kit** y **Content Posting API**. En el Sandbox, añade la
cuenta de TikTok como usuaria de prueba y usa el ID y secreto de ese entorno
en `TIKTOK_CLIENT_ID` y `TIKTOK_CLIENT_SECRET`. Registra
`/integrations/social/tiktok`. Postiz verifica `user.info.basic`,
`user.info.profile`, `user.info.stats`, `video.list`, `video.upload` y
`video.publish`. PostForge envía el video a la bandeja de TikTok por
defecto y tú terminas de publicarlo allí. La publicación directa y la
visibilidad pública dependen de la revisión de TikTok.
[Formulario de la aplicación](../tiktok-app-form.md) · [Guía de TikTok](https://developers.tiktok.com/docs/en/content-posting-api-get-started-upload-content)

## YouTube

Crea un proyecto en Google Cloud. Activa **YouTube Data API v3** y
**YouTube Analytics API** para las estadísticas. Configura la pantalla de
consentimiento y agrega a la persona que administra el canal como usuaria
de prueba si la aplicación está en modo de pruebas. Crea un cliente OAuth
de tipo **Aplicación web**, registra `/integrations/social/youtube` y guarda
sus credenciales en `YOUTUBE_CLIENT_ID` y `YOUTUBE_CLIENT_SECRET`.

Postiz verifica ocho permisos con el prefijo
`https://www.googleapis.com/auth/`. Son `userinfo.profile`,
`userinfo.email`, `youtube`, `youtube.force-ssl`, `youtube.readonly`,
`youtube.upload`, `youtubepartner` y `yt-analytics.readonly`. Google acepta
`youtube.upload` por sí solo para subir videos, pero esa autorización es
insuficiente para conectar el canal en esta versión de Postiz.
[Guía de Postiz](https://docs.postiz.com/self-host/providers/youtube) · [Permisos para subir videos](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert#authorization)

## WhatsApp con Evolution

1. Configura una clave única y robusta en `AUTHENTICATION_API_KEY` y el
   nombre de la instancia en `WA_INSTANCE`. Enciende PostForge.
2. Abre **WhatsApp Manager** desde la barra de menús. Usa el servidor
   `http://localhost:8080` y la clave global. Selecciona la instancia o
   ejecuta `./scripts/link-whatsapp.sh` para crearla si hace falta y ver el QR.
3. En el teléfono principal autorizado, abre **WhatsApp → Dispositivos
   vinculados** y escanea el código. Comprueba que la instancia figure
   conectada y prueba con un mensaje a tu propio chat.

El enlace por QR con Baileys funciona como dispositivo vinculado. No exige
una aplicación de desarrollador, permisos de OAuth ni un rol de administrador
en Meta Business. La clave global sí da acceso administrativo a la API local
de Evolution. Mantén el gestor accesible solo desde el equipo y protege la clave.
[Guía de reconexión](whatsapp.md)
