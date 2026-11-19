# Guía técnica de PostForge

Cliente actual: Rust/Tauri con la vista web del sistema, planificador compartido en Python, Postiz/Temporal, Evolution API y Ollama local opcional. No usa Electron. Swift queda como código histórico; sus controles automáticos de reposo/encendido y su integración con Siri no forman parte del cliente Rust.

## Arquitectura y aprobaciones

```text
Escritorio / chat contigo mismo en WhatsApp / cuenta privada de Telegram
                              ↓
                  validar → texto local → revisión guardada
                                            ├→ Postiz → Temporal → API social
                                            └→ Estado aprobado → Evolution

Navegador remoto → túnel HTTPS → Caddy → Authelia con MFA → acceso a Postiz
Descarga de una red social → URL firmada del archivo → verificador → Postiz
```

Crear un borrador no equivale a aprobar su publicación. La programación directa del escritorio aprueba los destinos y la audiencia del Estado elegidos. Confirmar un plan en WhatsApp crea borradores de redes y aprueba el Estado seleccionado. Telegram explica su comportamiento de borradores y Estados antes de confirmar. No reintentes una entrega incierta a ciegas: revisa Postiz y el historial de la plataforma.

## Instalación y configuración inicial

Los artefactos actuales son para **macOS ARM64**, **Linux x86_64** y **Windows x86_64**. Compilar en CI no demuestra aceptación de publicaciones en equipos reales. Los paquetes de macOS tienen firma ad hoc, sin notarización. Usa el archivo correspondiente a tu arquitectura.

El cliente incluye código público y prepara una instalación privada. No incluye credenciales, archivos del usuario, bases de datos ni modelos de Ollama. **Ajustes → Revisar requisitos** comprueba:

| Herramienta | Uso |
|---|---|
| Python 3.9+ | Planificador y respaldos; Windows utiliza `py -3` |
| OpenSSL | Revisar, crear y restaurar respaldos cifrados y autenticados |
| Docker + Compose | Postiz, bases, planificador, Evolution y gateway |
| FFmpeg + ffprobe | Validación, vistas previas y copias derivadas de video |
| Ollama y modelo instalado | Generación local opcional; conservar el texto funciona sin modelo |
| `tzdata` en Windows | Zonas horarias de Python: `py -3 -m pip install tzdata` |

El `.pkg` avisa qué herramientas faltan y enlaza sus fuentes oficiales. No instala herramientas externas ni concede permisos del sistema silenciosamente. Descargar un modelo es una operación separada y explícita. Iniciar servicios ya no descarga un modelo de Ollama automáticamente.

Para una instalación avanzada nueva, localiza el directorio privado en **Ajustes → Avanzado · carpeta de instalación**, copia su `.env.example` a `.env` y completa los valores de forma privada. El selector localiza instalaciones; los respaldos se abren en **Restaurar respaldo**. Usa UTF-8 y limita permisos al propietario (`chmod 600 .env` en Unix). Desde código fuente puedes usar los mismos archivos en la raíz del repositorio. La variable de desarrollo `POSTFORGE_PROJECT_DIR` tiene prioridad sobre una carpeta guardada y permite pruebas aisladas.

Grupos de credenciales:

- **Postiz/base de datos:** `POSTGRES_USER`, `POSTGRES_DB`, una contraseña única en `POSTGRES_PASSWORD`, `DATABASE_URL` coincidente y un `JWT_SECRET` largo y aleatorio. Conserva el secreto y las credenciales al migrar.
- **Evolution:** una `AUTHENTICATION_API_KEY` única, `WA_INSTANCE` y la vinculación QR con el teléfono autorizado. La clave protege el administrador local; no es la contraseña del teléfono. La app muestra el QR, la sesión y la audiencia sin abrir el administrador.
- **Apps sociales:** solo los identificadores y secretos de los conectores usados. Postiz guarda los tokens resultantes. Una clave API no reemplaza la autorización OAuth de YouTube.
- **Acceso público:** perfil de túnel y gateway Caddy/Authelia configurado localmente. TryCloudflare no requiere ngrok; un túnel con nombre requiere su propio token y dominio. Las credenciales guardadas de ngrok son opcionales.
- **Telegram opcional:** token de bot dedicado, un ID numérico privado verificado, idioma, activación/pausa de migración e intervalo de avisos. No uses el mismo token en dos instalaciones activas.

Configura el entorno antes de usar **Administrar servicios → Iniciar servicios**. Para operación avanzada desde el código, `./postforge.sh doctor` y `./scripts/recheck.sh --live` ofrecen diagnósticos. En Windows usa los controles Rust; no supongas que Bash está instalado. Si editas `.env` con los servicios en ejecución, usa **Administrar servicios → Aplicar cambios de ajustes**: recrea solo los servicios cuyos ajustes cambiaron y conserva el enlace actual del túnel, así tus redes siguen conectadas.

## Gateway y cuentas

Sigue la [guía de configuración del gateway](https://github.com/isaacmateosv/postforge/blob/main/v2/gateway/README.md): documenta `v2/gateway_setup.py`, los hashes de contraseñas y la vinculación local del autenticador. No requiere Google ni SMTP para vincular localmente. La semilla y la imagen QR son secretos; no las publiques en capturas ni registros.

Los usuarios del gateway y los miembros de Postiz son ajustes distintos. Configura primero el gateway y luego la cuenta/equipo de Postiz por la ruta protegida. Mantén `DISABLE_REGISTRATION=true` normalmente. Una ventana de registro controlada por el operador es una tarea avanzada de configuración, no un registro público permanente. Sin SMTP, entrega la invitación por un canal privado existente; PostForge no envía correos por sí solo.

El gateway usa **30 minutos sin solicitudes autenticadas**, con **dos horas como máximo por sesión**. Una página puede hacer solicitudes de fondo; no es un contador de actividad del ratón. La migración conserva los valores personalizados. El panel y la API siguen protegidos. La excepción controlada es una URL firmada para un archivo concreto, no un acceso libre al panel.

## Enlaces públicos y cambio de proveedor

Usa **Administrar enlace de Postiz** en Ajustes o **Enlace y acceso a Postiz** en la bandeja. Se distingue entre acceso disponible, inaccesible, dirección detectada sin sincronizar y reconexión de cuenta. Hacer clic en una URL válida la copia con confirmación visible. No se pueden copiar direcciones antiguas mientras falta sincronizar un cambio.

| Modo | Comportamiento |
|---|---|
| TryCloudflare | Dominio temporal que puede cambiar al reiniciar; sin garantía de disponibilidad |
| Túnel Cloudflare con nombre | Dominio propio estable; token y dominio son ajustes portátiles privados |
| ngrok | Usa la cuenta/dominio guardados y sus cuotas |
| Red privada/instalación independiente | No requiere túnel público para uso local; el acceso remoto necesita una ruta HTTPS protegida |

Adopta una dirección detectada con **Usar enlace detectado**. Pedir otro dominio aleatorio es una reparación avanzada, no una renovación habitual. El cambio conserva el gateway, actualiza los orígenes y verifica el acceso. El mantenimiento de red se bloquea durante publicaciones o respaldos. Una actualización normal conserva el conector en ejecución.

Cuando tengas dominio propio, configura su túnel con nombre, elige ese modo, guarda token/dominio y aplica. Volver al modo temporal conserva ese perfil. Comprueba el gateway y la entrega firmada en el nuevo origen. La app no puede editar por ti las consolas de Google, Meta o TikTok.

La redirección OAuth debe corresponder al **conector**, incluida la diferencia entre Instagram mediante Facebook Login e Instagram Standalone. Copia el valor de la guía de la cuenta. Los tokens existentes pueden seguir funcionando tras cambiar el dominio; no desconectes todas las cuentas. Si hace falta reconectar, actualiza la redirección del proveedor, reconecta el canal existente y comprueba su estado. Consulta la [guía de dirección pública](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/public-address-es.md).

## Configuración de API y formatos

Las referencias del proyecto son [configuración y permisos mínimos](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/channel-setup-es.md) y [atributos de solicitudes](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/app-keys.md). Activa solo los permisos del conector y comportamiento elegidos. No reemplaces sus permisos por otros genéricos supuestos.

### YouTube

Activa **YouTube Data API v3** en Google Cloud. Configura la audiencia de consentimiento OAuth y un cliente de **Aplicación web**, no una clave API ni un cliente de escritorio. Guarda el identificador y secreto en `YOUTUBE_CLIENT_ID` y `YOUTUBE_CLIENT_SECRET`. Añade la redirección de YouTube que muestra PostForge y autoriza el canal existente como su propietario. En modo de prueba, añade los usuarios previstos; los tokens de actualización pueden exigir reautorización frecuente. No cambies de cliente solo para reparar un token temporal vencido.

La misma API carga Shorts y videos normales. Sigue los permisos del conector en la [guía de YouTube](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/youtube-es.md), incluidos los de carga y lectura/gestión que necesita. La API no tiene un interruptor para convertir cualquier video horizontal en Short. Automático envía vertical/cuadrado a Shorts y horizontal a video normal. La copia de Shorts se limita a 179 segundos si hace falta. Generar otro título no cambia la descripción ni el plan. Las miniaturas subidas o extraídas requieren elegibilidad del canal; aceptar la solicitud no prueba cómo se verá en todas las pantallas de YouTube.

### TikTok

**Carga a la bandeja** usa `video.upload` y transfiere el video para terminar dentro de TikTok. Ese endpoint no admite texto ni portada. La app conserva la acción para copiar el texto; elige la portada en TikTok. **Publicación directa** usa `video.publish`, texto e instante de portada. Publicar directamente para todo público requiere un cliente auditado por TikTok. Una imagen externa no es un parámetro de portada de video. Consulta la [referencia oficial](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post).

### Meta y Threads

Un Reel de Facebook también puede aparecer en el feed; revisa el formato devuelto antes de crear otro video duplicado. Que una historia de Instagram funcione no demuestra que el Reel funcionó. Las historias largas de Facebook/Instagram se dividen y programan con un minuto entre partes. La revisión muestra las cantidades. Threads puede necesitar una adaptación más corta. El estado de conexión refleja tokens y renovación, no garantiza la publicación ni que el archivo cumpla todas las políticas.

## Estado del plan y seguridad de archivos

Cada revisión es una instantánea validada con una familia de envío. Las variantes conservan destinos, hora, archivos y portada. Se muestran hasta ocho versiones sin duplicar textos idénticos. La edición manual actualiza la versión elegida. El título tiene sus propios controles. Cambiar la hora conserva el texto. Cambiar archivos, destinos, formatos u origen exige otra validación; conserva la redacción editada.

Un bloqueo de mantenimiento impide que se crucen reemplazo del código, cambios de túnel, respaldo/restauración, limpieza y envío. Las solicitudes de procesos distintos fallan de forma visible en vez de competir silenciosamente. Repetir un envío terminado devuelve su comprobante; los resultados parciales o inciertos quedan para revisión y no se publican otra vez automáticamente.

Las URL firmadas autorizan **GET/HEAD de un archivo concreto**, vencen 48 horas después de la publicación prevista y admiten programación de hasta 30 días. Quien tenga el enlace vigente puede leer el archivo: mantenlo privado. Se comprueba la descarga de un byte de cada archivo/portada antes de crear las publicaciones. Postiz transmite los datos; el verificador no duplica videos completos. Mover un borrador más allá del vencimiento o cambiar de origen exige enlaces y revisión nuevos antes de aprobar.

## Operación de WhatsApp y Telegram

El QR de Evolution se muestra en la ventana. Clave y sesión siguen privadas. La consulta termina al cerrar; una sesión sana no se reemplaza para mostrar otro QR. La audiencia admite todos los contactos o números elegidos con código de país. Cambiar el valor predeterminado no altera destinatarios aprobados.

Los Estados de video se dividen en partes ordenadas de hasta 60 segundos. Una parte no se reenvía automáticamente ante una respuesta incierta; importa distinguir entre confirmado e incierto. Los recibos tienen filtros y páginas y no exponen identidades de destinatarios en la respuesta del escritorio. Aceptación del envío no equivale a visualización.

Los mensajes interactivos de WhatsApp se probaron con el formato actual del proveedor. Hay comandos escritos para clientes sin botones. Las acciones están ligadas al chat propio, la versión y el vencimiento. Los ajustes requieren una acción o comando explícito; el texto de una publicación no se convierte en respuesta de configuración. El video por descarga directa de hasta 256 MiB depende de sus metadatos; `WA_MAX_MEDIA_MB` limita por separado el ingreso base64 (32 MiB por defecto, de 1 a 64).

Telegram usa un bot dedicado, una cuenta privada y consultas prolongadas; no requiere webhook público. Configura token, `/start`, cuenta privada, idioma, avisos y activación en la ventana. Los comandos principales son `/new`, `/cancel`, `/status` y `/settings`. Los botones usan revisiones con versión. Se rechazan los grupos expresamente. La descarga de la API en la nube tiene un límite de 20 MB por archivo.

Los avisos de actividad empiezan apagados y admiten intervalos de 5 a 1440 minutos. Los botones de Telegram y los comandos explícitos `postforge ping` de WhatsApp guardan el mismo ajuste portátil. El receptor y el equipo deben estar activos. Un aviso local no puede informar de su propio equipo apagado; para detectar avisos ausentes hace falta un monitor externo.

## Recursos y servicios

Inicio se actualiza al recuperar el foco y como máximo cada 30 segundos mientras esté visible y activo. Las consultas QR y la cuenta del comprobante se detienen o pausan al salir de su contexto. Los modelos usan `keep_alive: 0` y se descargan de memoria al terminar. El ajuste avanzado solo selecciona un modelo instalado y no activa proveedores de nube. Gemini sigue desactivado.

**Administrar servicios** tiene acciones fijas para iniciar/detener. Detener exige comprobar que no hay publicaciones programadas ni Estados aprobados pendientes. Detiene esta instalación, pausa WhatsApp y conserva herramientas compartidas y otros proyectos. Iniciar retoma contenedores/receptores y revisa API/planificador; podría descargar imágenes de contenedores que falten. No descarga modelos de Ollama. El enlace temporal puede necesitar sincronización después de detener e iniciar.

Rust todavía no incluye el planificador automático de reposo/encendido ni el apagado tras una hora inactiva del controlador Swift. Mantén el equipo despierto para publicar y configura el inicio del sistema de forma explícita. Salir cierra el cliente, no los servicios. No ejecutes dos controladores al mismo tiempo.

## Retención, identificadores y limpieza

`PM_RETENTION_DAYS` usa **30** días por defecto y se edita en Ajustes o la bandeja. Es un plazo para archivos locales sin uso e historial; no reinicia la base ni elimina automáticamente cada publicación guardada. Los planes pendientes y las publicaciones de Postiz no eliminadas protegen sus archivos. Si no se pueden comprobar las referencias, se conservan los archivos. La limpieza automática de WhatsApp cubre tanto Estados como archivos temporales de mensajes. Los originales y derivados pueden seguir ocupando espacio si aún se utilizan.

Para una limpieza avanzada más amplia, ejecuta `python3 scripts/retention.py` para revisar y `python3 scripts/retention.py --apply` solo después de comprobar la lista. Se eliminan archivos y registros elegibles, no publicaciones guardadas. Los identificadores de aprobación y contadores no se reinician porque venzan los registros. No reinicies secuencias de la base ni borres carpetas de archivos manualmente.

**Eliminar publicaciones** es otra acción: revisa y confirma borradores/fallos o cancelación de la cola. Conserva elementos que cambiaron de estado después de la revisión y no borra contenido ya publicado en las redes. Un envío activo podría terminar. La retención y la limpieza no reemplazan revisar el historial.

## Respaldo cifrado y restauración

Usa **Respaldo y traslado**, no el selector de instalación recuperada. Exportar incluye credenciales, datos/archivos de Postiz y estado del gateway en un `.pfbackup` cifrado y autenticado. La exportación se prueba en una base temporal. Los modelos de Ollama, binarios y herramientas externas van aparte. Guarda el respaldo y su contraseña de forma privada; requiere al menos 12 caracteres y no se puede recuperar.

En destino: elige el archivo, ingresa la contraseña, revisa, vuelve a ingresarla y confirma que el equipo anterior esté detenido. Revisar no reemplaza datos actuales. Reemplazar exige consentimiento y un respaldo cifrado de recuperación; credenciales de base incompatibles requieren una instalación de destino nueva. Las tareas siguen fuera de la ventana. Al abrirla se encuentra el progreso activo; **Retomar progreso** vuelve a la misma tarea si falla la comunicación. La referencia de recuperación no guarda la solicitud ni la contraseña.

La restauración deja servicios detenidos, publicación pausada y Telegram en espera de migración. Revisa zona horaria, proveedor/dominio, usuarios/MFA, sesiones de Postiz y WhatsApp antes de iniciar. Solo un receptor debe usar el token de Telegram. Los dominios temporales no son identidades portátiles. El perfil del dominio propio viaja cifrado; configura DNS y rutas en destino según corresponda.

## Actualizaciones, paquetes y desinstalación

La consulta al iniciar y cada seis horas sigue el canal estable o de prueba de la app instalada. La consulta manual incluye Docker/Evolution. Se verifican sumas, plataforma y arquitectura. macOS reemplaza la app firmada y actualiza el código y servicios correspondientes sin cambiar archivos privados. Las publicaciones o respaldos activos bloquean la instalación. Windows/Linux abren el archivo verificado para reemplazarlo manualmente, sin sobrescribir un ejecutable activo. Al abrir de nuevo en Windows, el código y los servicios se actualizan con Python, sin exigir Bash; una instalación detenida permanece detenida.

Evolution Manager forma parte de la versión fijada de Evolution, no es otra app de escritorio. Una versión nueva se muestra como trabajo de compatibilidad; no se instalan etiquetas de contenedor sin probar. Una consulta fallida se muestra incompleta, no como «actualizado».

En macOS, `./scripts/uninstall.sh --dry-run` muestra el alcance previsto; luego usa el flujo interactivo. La eliminación adicional de datos exige confirmación: exporta primero un respaldo. Se comprueba la identidad de la app, se conservan repositorios Git y no se borran herramientas/imágenes compartidas. La auditoría no desinstala el equipo real. En Windows/Linux, detén la instalación, elimina el cliente con el sistema y administra por separado sus datos privados; el script de macOS no es un desinstalador multiplataforma.

## Diagnóstico y límites de las pruebas

Revisa Inicio, Conexiones, progreso de servicios, errores por publicación y registros privados. No publiques `.env`, bases, semillas QR, tokens, contraseñas de respaldo ni enlaces firmados en incidencias. Las pruebas aisladas pueden reproducir respuestas y restauraciones en bases temporales; el resultado final en redes, la migración física y el funcionamiento en Windows/Linux requieren pruebas reales.

El [registro de auditoría](https://github.com/isaacmateosv/postforge/blob/main/docs/audits/2026-11-15-feature-audit.md) enumera lo comprobado y los límites pendientes. Para el uso diario, vuelve a la pestaña Guía rápida.
