# Guía técnica de PostForge

El desarrollo actual de v2 usa el cliente de escritorio Rust. Las secciones anteriores del controlador del Mac describen el comportamiento de Swift y no implican que esas funciones ya estén en Rust. Consulta Implementación de Rust y Telegram para conocer el alcance actual de la beta.

PostForge controla desde macOS una instalación local de publicación. Prepara planes y borradores. Postiz y Temporal gestionan las publicaciones aprobadas. Evolution y Baileys vinculan la sesión de WhatsApp del operador.

```text
Ventana de publicación ───────┐
WhatsApp → Evolution ─────────┼→ Plan → Vista previa y aprobación
Textos locales con Ollama ────┘              │
                                            ├→ Postiz → Temporal → Redes sociales
                                            └→ Cola de estados aprobados → Evolution
```

## Instala y configura

1. Instala el paquete de PostForge y los requisitos de SETUP.md, incluidos Docker Desktop, Ollama y FFmpeg.
2. Copia .env.example a .env. Configura las credenciales de la base de datos, el secreto JWT, el dominio y token de ngrok y la clave de Evolution. Si trabajas fuera de Ecuador, configura PM_TIMEZONE.
3. Elige acceso local o una puerta de enlace HTTPS con autenticación. Configura las credenciales y URL de retorno de OAuth para la dirección de Postiz y conecta las redes sociales. Consulta los permisos de cada conector en la [guía de configuración de canales](https://github.com/isaacmateosv/postforge/blob/main/docs/reconnect/channel-setup-es.md).
4. Enciende PostForge. Abre **WhatsApp Manager** y escanea el código QR con el teléfono autorizado. Mantén la clave de la API en privado.
5. Ejecuta las verificaciones de solo lectura desde la carpeta del proyecto.

```bash
cd ~/postforge
./postforge.sh doctor
./scripts/recheck.sh --live
```

## Configura Telegram

Crea un bot exclusivo con BotFather. En Terminal, desde la carpeta de PostForge,
ejecuta `python3 v2/telegram_setup.py --language es --heartbeat 0`. Ingresa el
token en el campo oculto y envía `/start` en tu chat privado con el bot cuando
se te indique. Confirma la cuenta, ejecuta `./postforge.sh telegram start` y
envía `/status`. El agente sigue disponible mientras la infraestructura está inactiva; redactar y enviar requiere los servicios correspondientes.
Con `0` no se envían avisos periódicos. Para activarlos, elige entre 5 y 1440
minutos.

## Acceso independiente sin ngrok

Para una instalación local, ejecuta Compose en el Mac, en Linux o en Windows
con Docker Desktop. El panel web de v2 está disponible en el equipo anfitrión.
También puedes abrir Postiz en su puerto local. El README de v2 incluye los
comandos de Compose y el estado de las pruebas por plataforma.

Para entrar desde otros equipos, usa una puerta de enlace HTTPS con autenticación
o una red privada con controles de acceso. Mantén los puertos directos en privado.
Configura primero los usuarios y la autenticación de varios factores de la puerta
de enlace. Luego crea la cuenta de Postiz por esa ruta protegida. Si necesitas
habilitar el registro para crear la cuenta inicial, vuelve a deshabilitarlo al terminar.

Si usas ngrok, protege toda la dirección pública. Si usas un dominio propio,
actualiza la dirección de Postiz y las URL de retorno de los proveedores.
Revisa el README de v2 antes de cambiar una instalación pública.

## Operación diaria

- La ventana del Mac y tu chat contigo en WhatsApp usan el mismo planificador. El texto entre comillas se conserva.
- Los borradores de redes se aprueban en Postiz. Los estados de WhatsApp tienen su propia cola de aprobación explícita.
- Con los servicios apagados se pausa la recepción. Un mensaje de WhatsApp no puede encender el receptor local. Desde el Mac, usa Siri para abrir la ventana de publicación y elige **Encender**.
- Cada hora se revisan la versión pública de PostForge, las imágenes de Docker declaradas y las versiones estables de Evolution. El instalador refresca los servicios activos y conserva sus datos.

## Archivos y retención

- Los videos de WhatsApp de hasta 256 MiB se descargan por flujo al disco. PostForge verifica el tamaño en bytes y el resumen SHA-256.
- Los estados largos de WhatsApp se dividen en partes de hasta 60 segundos después de aprobarlos.
- La limpieza de archivos temporales de WhatsApp se ejecuta cuando el receptor está activo. La retención predeterminada es de 30 días. Se protegen los envíos pendientes, las confirmaciones futuras y los archivos vinculados a publicaciones de Postiz.
- Revisa qué borraría la limpieza general antes de aplicarla. Puedes ajustar la retención en el menú de la barra.

```bash
./postforge.sh retention
./postforge.sh retention --apply
```

## Respalda y recupera

En **Respaldo y traslado**, exporta las credenciales cifradas y el archivo verificado de Postiz. Mantén ese archivo en privado porque contiene tokens de los canales. Restaura en el Mac de destino antes de programar contenido nuevo, verifica los envíos pendientes y vuelve a vincular WhatsApp. La migración excluye las tareas de Temporal y la sesión de WhatsApp. Si configuraste el acceso seguro, la misma contraseña también protege `gateway.enc`. Ese archivo contiene la lista de acceso, los hashes de las contraseñas y el registro de los autenticadores. Guárdalo junto con el respaldo. Después de restaurar, valida el acceso seguro y el túnel antes de exponer Postiz. Los usuarios vuelven a iniciar sesión con su contraseña y los códigos de su autenticador.

Si Postiz queda inaccesible al cambiar el túnel, revisa en el registro si se restauró la configuración anterior. Para recuperar una conexión específica, consulta docs/reconnect en el repositorio. Usa **Abrir registro** en la barra antes de reiniciar o eliminar datos.

```bash
./postforge.sh status
./postforge.sh channels
./postforge.sh maintenance check
```

### Entrega de archivos con el acceso seguro

PostForge genera un enlace firmado para que cada red social descargue el archivo
adjunto. El enlace permite GET y HEAD únicamente para ese archivo y vence 48 horas
después de la hora planificada. Esta ruta permite programar hasta 30 días por
adelantado. Si cambias un borrador a una fecha posterior al vencimiento del enlace
o cambias el dominio público, prepara nuevos borradores antes de aprobarlos.
Quien tenga un enlace vigente puede descargar ese archivo, así que trátalo como
información privada. El panel de Postiz, la API y los archivos sin enlace firmado
siguen requiriendo el inicio de sesión del acceso seguro.

Antes de crear publicaciones, PostForge verifica una descarga de un byte en cada
enlace firmado, incluidas las portadas. Si falla, detiene la creación y muestra
el problema. El verificador autoriza la solicitud y Postiz transmite el archivo
directamente. No se crea otra copia del video. Las reglas de retención vigentes
siguen controlando su eliminación.

Las nuevas configuraciones del acceso seguro crean una clave privada de 32 bytes
para firmar los enlaces. En una instalación anterior, créala una sola vez con
este comando y aplica los archivos actualizados de Compose y Caddy.

    python3 scripts/lib/media_links.py init-key data/gateway/media-signing.key

Mantén la clave privada. Respaldo y traslado la incluye en el archivo cifrado del
acceso seguro. Al restaurar un respaldo anterior, se genera una clave nueva.
Una sesión revocada o vencida en una red social todavía requiere volver a
conectarla desde Postiz.

Si seleccionas historias de Facebook o Instagram y adjuntas un solo video largo,
se preparan clips equilibrados de menos de 60 segundos. Las publicaciones del
feed conservan el video completo. Revisa cada borrador de historia en orden.
La programación directa separa las partes por un minuto. Los clips temporales
se eliminan después de subirlos y sus copias en Postiz siguen las reglas
normales de retención.

## Estado del formulario y configuración avanzada

La revisión y navegación de versiones modifican solo los campos del texto.
La vista nativa reemplaza esa sección y conserva los datos del plan y la posición
de desplazamiento. Editar el pedido o las opciones de los archivos invalida el
plan y limpia sus versiones. La ventana de dos columnas permite crecer al campo
del pedido dentro del espacio disponible y desplazar el plan por separado.

El analizador separa la programación del contenido. Las comillas dobles y los
campos texto/caption conservan la redacción. Una idea sin comillas solicita
generación. Se admiten fechas día/mes de Ecuador, fechas ISO, días de la semana,
AM/PM incluso con espacios como “p. m.” y la zona horaria configurada. Revisa la
fecha y hora resueltas antes de crear borradores. Las fechas u horas inválidas,
pasadas o demasiado próximas producen un error. Para obtener resultados
predecibles, escribe los destinos y la hora antes del texto o la idea.

El modelo local es una configuración avanzada. Instala el modelo de Ollama que
necesites y define LOCAL_LLM_MODEL en el archivo privado .env. OLLAMA_HOST_URL
selecciona el servidor local. El siguiente horneado lee esos valores. El formulario
muestra etiquetas descriptivas y oculta el identificador del modelo. Un modelo
más grande consume más memoria y tarda más en generar. Los modelos se mantienen
fuera del instalador.

La limpieza toma una vista previa de los grupos pendientes en la organización
seleccionada. Al confirmar, vuelve a revisar cada grupo y usa el DELETE de la API
pública de Postiz para ejecutar su cancelación del programador. Conserva los
elementos que cambiaron. Los Estados pendientes de WhatsApp se cancelan con el
bloqueo de la cola; los que ya están enviándose quedan excluidos. Una publicación
externa que ya empezó puede completarse. Se muestran los fallos y elementos
omitidos; un nuevo intento requiere otra vista previa. Los archivos compartidos
por otras publicaciones siguen la retención normal.

Los anuncios sin archivos requieren elegir destinos compatibles en la interfaz
del Mac. La CLI acepta --text-networks facebook,threads,whatsapp sin archivos.
En WhatsApp se usa la confirmación “solo texto aprobado” / “only text approved”.
Facebook y Threads usan publicaciones del feed; WhatsApp usa Estados.
Las historias de Instagram y Facebook en esta app requieren archivos. Las
tarjetas que convierten texto en imagen siguen pendientes. Los botones guiados
de Telegram usan el formulario compartido descrito abajo.

Windows y Linux también cuentan con el nuevo formulario Rust/Tauri descrito
abajo. El panel web existente conserva su modo de solo lectura.


## Implementación de Rust y Telegram

El cliente Rust/Tauri integra su interfaz e invoca el puente local de Python
por entrada/salida estándar. Acepta operaciones conocidas y no abre un servidor
HTTP de comandos. Las credenciales quedan fuera de la interfaz. Python, Docker,
FFmpeg y Ollama para generar textos siguen siendo requisitos. Windows necesita
el iniciador py y tzdata. desktop/README.md describe dependencias y artefactos.

Los registros privados en run/composer-plans conservan los campos revisados,
el desplazamiento horario, las huellas de archivos y una familia de envío.
Las vistas previas vencen después de 24 horas. Todas las versiones del texto
comparten la protección contra repeticiones. Un envío terminado devuelve su
confirmación; uno parcial o incierto queda en needs_review y no se repite
automáticamente. Cambiar archivos requiere otra revisión. La retención incluye
estos registros. La compilación en CI y la aceptación en equipos reales son
verificaciones separadas.

scripts/host_agent.py despacha Estados de WhatsApp aprobados y ejecuta el bot.
Permite start, stop, restart y status. Se detiene de forma cooperativa para que
una operación en curso registre su resultado. Los bloqueos de procesos en Unix
y Windows protegen los datos compartidos. Las imágenes usan sips en Mac y FFmpeg
en otros sistemas. Los Estados se envían invocando Python directamente. El agente
no mantiene un modelo activo mientras espera.

Telegram usa un token local, un propietario numérico privado y la posición
persistida del receptor. Los botones incluyen referencias de conversación y
versión y vencen con el plan. Se ignoran otros usuarios y grupos. Enviar requiere
otra confirmación. Los envíos interrumpidos quedan retenidos para revisar el
calendario. Las consultas son salientes y se conserva el acceso seguro. El
receptor antiguo en Docker se detiene antes de activar el agente local. Un bot
debe tener un solo receptor.

Usa v2/telegram_setup.py localmente con --language es o en y, si deseas,
--heartbeat 15. Rechaza un webhook existente, valida el token, identifica un
/start privado, pide confirmar al propietario y registra comandos. Los ajustes
están en run/telegram y deben ser privados. Reinicia después de cambiarlos.
Configura por separado el inicio automático del sistema. Un equipo apagado o
suspendido no avisa de su propia caída; hace falta un monitor externo para
detectar la ausencia de avisos de actividad.

Las descargas del bot tienen un límite de 20 MB. Se guardan por bloques y con
verificación de tamaño en data/postiz-uploads/telegram-intake. Las fuentes de
planes terminados o cancelados se eliminan después de guardar su contenido
necesario; las abandonadas siguen la retención. Antes de migrar, detén el agente
anterior, configura el bot en el destino y empieza otra conversación. Una
conversación activa no es un trabajo portátil.

La beta Rust cubre redacción, revisión, envío, limpieza y aprobación de Estados.
Siri, inicio de sesión, actualizaciones, notificaciones y desinstalación siguen
en el controlador del Mac. Los ZIP de escritorio del Mac tienen firma ad hoc;
los de Windows carecen de firma de publicación. La firma de producción y las
pruebas de instalación son verificaciones separadas.
