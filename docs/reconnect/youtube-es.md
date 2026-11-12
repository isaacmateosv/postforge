# YouTube: configuración, formatos y reconexión

**YouTube Data API v3** y el mismo cliente OAuth sirven para Shorts y videos normales. No existe un permiso exclusivo para Shorts. Postiz gestiona el inicio de sesión de Google; la aplicación de escritorio no recibe la respuesta OAuth.

## Google Cloud Console

1. Selecciona el proyecto de tu instalación. En **APIs y servicios → Biblioteca**, habilita **YouTube Data API v3** y **YouTube Analytics API**. El conector instalado usa Data para subir videos y Analytics para estadísticas.
2. En **Google Auth Platform → Branding**, configura la identidad de la aplicación. Declara únicamente dominios que controles; no intentes verificar el dominio compartido `ngrok-free.dev`.
3. En **Audience**, elige la audiencia interna o externa que corresponda. Si está en Testing, agrega como usuarios de prueba las cuentas de Google que administran los canales. Con estos permisos, los tokens de actualización de aplicaciones externas en pruebas normalmente caducan en siete días. Pasar a Production está sujeto a las políticas de verificación y de cuentas de Google.
4. En **Clients**, crea o conserva un cliente OAuth de tipo **Web application**. El origen JavaScript debe ser el origen público de Postiz. La URI de redirección debe coincidir exactamente con `https://TU-HOST-PUBLICO/integrations/social/youtube`. Conserva la protección del gateway y conecta desde un navegador que ya haya pasado su autenticación.
5. En **Data Access**, configura los permisos del conector instalado. Todos los siguientes llevan el prefijo `https://www.googleapis.com/auth/`:

   `userinfo.profile`, `userinfo.email`, `youtube`, `youtube.force-ssl`, `youtube.readonly`, `youtube.upload`, `youtubepartner`, `yt-analytics.readonly`.

   Google admite `youtube.upload` para una subida, pero este conector de Postiz verifica los ocho al iniciar sesión. Son requisitos del conector, no los permisos mínimos de una aplicación propia dedicada solo a subir videos. Los permisos amplios pueden requerir verificación adicional.
6. Guarda `YOUTUBE_CLIENT_ID` y `YOUTUBE_CLIENT_SECRET` en el `.env` privado. Ambos deben pertenecer al mismo cliente web. Una API key no reemplaza OAuth. No publiques `.env` ni compartas secretos en reportes.
7. Si cambiaste las credenciales, recrea Postiz mediante el flujo normal de actualización o reinicio de componentes para que reciba el nuevo entorno. Si ya son correctas, conserva ambas y usa **Reconnect channel** en Postiz. Inicia sesión como propietario y elige el canal o la cuenta de marca correspondiente.

Los tokens de actualización se guardan en la base de datos de Postiz, no en `.env`. **Respaldo y migración** incluye ambos de forma cifrada. Después de migrar, revisa el gateway, la dirección pública y la URI OAuth. Cambiar de dominio requiere actualizar los orígenes y redirecciones del cliente; no necesariamente cambiar el secreto.

## Formatos y revisión

- **Automático**: los videos verticales o cuadrados van a Shorts; si superan tres minutos, se prepara una copia de **2:59** para YouTube. Los horizontales conservan su duración y van como videos normales. Los demás destinos mantienen sus propios archivos.
- **Shorts**: usa un archivo vertical o cuadrado. PostForge no recorta automáticamente un video horizontal.
- **Video normal**: usa un archivo horizontal. YouTube clasifica como Shorts los videos verticales o cuadrados que cumplen el límite de tres minutos; un selector o hashtag no cambia esa regla. Para publicar ambos formatos, prepara y revisa versiones separadas.
- El título admite hasta 100 caracteres. La descripción es independiente y no se recorta a ese límite. Revisa o edita el título antes de crear los borradores.
- La descripción termina con la etiqueta configurada para el negocio, además de las etiquetas temáticas. Si está vacía, termina con `#shorts`. No se añade `#Shorts` al título. La etiqueta no determina el formato.
- Revisa el archivo en el reproductor local de Redacta. En Destinos puedes ver la portada subida o el fotograma elegido. Que exista una vista previa no significa que todos los destinos admitan portadas personalizadas: los videos y Shorts de YouTube envían la imagen o el fotograma mediante la API de miniaturas, según los permisos de la cuenta.

## Estado de conexión y prueba

Abre **Conexiones** en la cabecera. Se consultan las credenciales guardadas en Postiz, la señal de reconexión, la caducidad real del token y los errores de autenticación. Un inicio de sesión nuevo prevalece sobre errores anteriores. Un token de acceso vencido con token de actualización se muestra pendiente de renovación. Este indicador describe la sesión; no garantiza una publicación, permisos completos ni cuota disponible.

Primero crea un borrador de prueba. Revisa título, descripción y formato; luego programa explícitamente una prueba con la visibilidad deseada. Comprueba su resultado en Postiz y YouTube Studio antes de reintentar el resto. Para subir videos de más de 15 minutos, verifica el canal en YouTube.

## Recuperar publicaciones fallidas

No vuelvas a crear las publicaciones que sí salieron. Con una audiencia grande, cada segmento de un Estado de WhatsApp puede tardar varios minutos: revisa el estado de entrega primero. En Postiz, corrige la causa del error y revisa únicamente las entradas fallidas antes de asignarles una hora futura. Reconectar no reenvía los errores anteriores. Las subidas a la bandeja de TikTok todavía deben completarse en TikTok.

| Error | Qué hacer |
|---|---|
| `401 Invalid Credentials` / refresh token | Reconecta el canal como propietario. Conserva el ID y secreto si son correctos. |
| `redirect_uri_mismatch` | Haz coincidir exactamente la URI pública de redirección del cliente web. |
| Aplicación bloqueada o sin verificar | Revisa usuarios de prueba, verificación y políticas de Workspace. |
| Error de cuota | Revisa las cuotas actuales del proyecto en Google Cloud. |
| El enlace del archivo devuelve HTML, autenticación o error de rangos | Corrige la entrega mediante enlaces firmados por archivo. Conserva el gateway y no hagas pública la biblioteca. |

Fuentes: [subidas y permisos](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert), [clasificación de Shorts](https://support.google.com/youtube/answer/15424877?hl=es), [caducidad OAuth](https://developers.google.com/identity/protocols/oauth2/#expiration), [Google Auth Platform](https://support.google.com/cloud/answer/15544987?hl=es), [videos largos](https://support.google.com/youtube/answer/71673?hl=es), [configuración de Postiz](https://docs.postiz.com/self-host/providers/youtube).

[English guide](youtube.md)
