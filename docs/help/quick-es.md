# Inicio rápido de PostForge

PostForge prepara planes de publicación en tu equipo. Revisas el texto, los destinos y la hora antes de enviar nada. El cliente actual está hecho en Rust; no ejecutes la app anterior de Swift al mismo tiempo.

## Empieza aquí

1. Instala el paquete de tu sistema. En macOS usa el `.pkg`; el ZIP también incluye la app y el código público de sus servicios.
2. Abre **Ajustes → Revisar requisitos**. Instala lo que falte desde los enlaces oficiales e inicia Docker.
3. ¿Vas a mover una instalación existente? Usa **Ajustes → Restaurar respaldo**. Una instalación nueva para otro negocio todavía requiere la configuración avanzada de la guía técnica.
4. En **Ajustes → Administrar servicios**, inicia la instalación configurada. Revisa **Administrar enlace de Postiz** antes de abrir Postiz.
5. En Inicio, elige **Nueva publicación**.

No necesitas elegir una carpeta de proyecto para el uso diario. El selector avanzado localiza una instalación existente; no importa respaldos.

```text
Redacta → Elige destinos → Hornea y revisa
                                ├→ Crear borradores → aprobar en Postiz
                                │                     aprobar Estado por separado
                                └→ Programar directamente → confirmar destinos elegidos
```

## 1 · Redacta

Elige **Generar un texto** si tienes una idea o **Usar mi texto** para conservar tus palabras. Aquí escribe solo el tema, los datos y el tono; los destinos y la hora se eligen en el siguiente paso. Puedes adjuntar hasta diez archivos y revisarlos antes de continuar.

Ejemplo de idea: «Anuncia nuestro nuevo horario. Cercano, breve y con un par de emojis».

Ejemplo de texto exacto: «Desde mañana atendemos a partir de las 10. ¡Te esperamos! ✨».

Sin archivos, puedes preparar publicaciones de Facebook, Threads y Estados de WhatsApp solo de texto. En este flujo, Instagram, YouTube, TikTok y las historias con archivos requieren una foto o un video. El Estado de texto admite un color de fondo.

## 2 · Elige los destinos

Selecciona las cuentas conectadas, la fecha y hora local y los formatos. **Pronto · +10 min** coloca una hora cercana en el futuro. La opción de publicaciones e historias incluye ambos formatos donde se admiten; una historia larga puede generar varios segmentos, sin que sean publicaciones duplicadas.

Abre **Opciones de texto y portada** para elegir una imagen o un segundo del video. La vista previa y la confirmación verde indican que la selección está lista; el plan muestra qué destinos pueden usarla. Si omites una portada compatible, PostForge pregunta si deseas continuar. Si cambias los archivos o la portada después, debes preparar otra revisión.

El hashtag opcional del negocio empieza vacío en una instalación nueva. Se coloca después de las etiquetas temáticas generadas. Guarda uno predeterminado en **Ajustes → Editar preferencias** o cámbialo solo para este plan.

En YouTube, Automático usa videos verticales o cuadrados para Shorts y horizontales para videos normales. Un Short largo recibe una copia independiente de **2:59**; los otros destinos mantienen su propio archivo. Un video vertical corto sigue siendo Short aunque lo llames video normal. Usa la proporción adecuada; PostForge no recorta automáticamente un video horizontal.

Pulsa **Hornea y revisa**. En Mac, ⌘Enter pasa de Redacta a Destinos y hornea desde Destinos; en Windows/Linux se usa Ctrl+Enter. Puedes deshacer los cambios de texto con el atajo habitual.

## 3 · Revisa y termina

Comprueba destinos, segmentos, fecha, texto y advertencias.

- **Probar otro texto** cambia la redacción y conserva el plan de entrega. Usa **‹ / ›** para recorrer hasta ocho versiones.
- **Editar texto** permite corregir una versión. Aplica o cancela la edición antes de crear borradores o programar; no se envían por accidente cambios sin guardar.
- **Editar título** cambia solo el título de YouTube. **Probar otro título** genera uno a partir del texto. El título admite hasta 100 caracteres; la descripción va aparte.
- Cambia la fecha u hora aquí sin regenerar el texto y pulsa **Actualizar hora**. Al enviar también se guarda una hora editada antes de pedir confirmación.
- **Crear borradores** deja las publicaciones para aprobarlas en Postiz y el Estado de WhatsApp para una aprobación separada.
- **Programar directamente** pide confirmar los destinos revisados y también aprueba el Estado de WhatsApp para la audiencia guardada.

La descripción de YouTube termina con el hashtag del negocio o con `#shorts` si está vacío. El título usa el hashtag configurado cuando cabe dentro de su límite.

**La carga a la bandeja de TikTok requiere terminar en TikTok:** pega el texto preparado y elige la portada allí. El comprobante mantiene disponible **Copiar texto para TikTok**. La publicación directa utiliza una configuración de API distinta y auditada.

Después de otras programaciones directas, una cuenta de ocho segundos activos vuelve al inicio. Pulsa **Quedarme aquí** o interactúa con el comprobante para detenerla. Se pausa si ocultas la ventana o abres un diálogo.

## WhatsApp

Abre **WhatsApp** para ver la conexión o escanear el QR con el teléfono autorizado. Se conserva una sesión que funciona. Configura la audiencia predeterminada de los Estados en esa ventana; los planes en cola mantienen la audiencia con la que se aprobaron.

Envía los archivos y una solicitud a tu chat contigo mismo mientras los servicios estén activos. Sé explícito:

```text
Facebook y Threads mañana a las 19:15; idea: anunciar nuestro nuevo horario
WhatsApp mañana a las 19:15; texto: "Mañana atendemos desde las 10. ¡Te esperamos! ✨"
```

`idea:` sin comillas pide generar un texto; `caption:`, `texto:` o un texto entre comillas conserva tus palabras. La respuesta muestra la revisión y botones. **Revisar aprobación → Confirmar plan** crea los borradores de redes y aprueba el Estado elegido; no publica automáticamente los borradores de redes. También se incluyen comandos escritos de respaldo. Un botón vencido no puede aprobar una versión nueva.

Los ajustes se abren solo con la acción explícita **Ajustes** o `postforge ajustes`. Un texto normal nunca activa una conversación de configuración. `postforge ping 60` cambia el aviso de actividad de Telegram y `postforge ping apagado` lo desactiva. Esos comandos no consumen una solicitud de publicación pendiente.

Los videos de más de un minuto se dividen en segmentos de Estado ordenados. Una audiencia grande puede tardar varios minutos por parte. Revisa el progreso y los recibos antes de reenviar. El ingreso de video por descarga directa admite hasta 256 MiB cuando el proveedor entrega los datos válidos; si falla, usa la app de escritorio. Los envíos pequeños en base64 tienen otro límite configurable.

En Inicio, abre **Estados de WhatsApp · revisión y aprobación**. El historial de recibos se puede mostrar u ocultar, filtrar por fecha o tipo y recorrer de cinco en cinco. «Aceptado» no prueba que cada contacto haya visto el Estado. Un envío incierto queda para revisión y no se repite automáticamente.

## Telegram

Cada instalación usa su propio bot y una cuenta privada autorizada. En **Telegram**, valida el token de BotFather, envía `/start` al bot, busca y elige tu cuenta privada, configura el idioma y los avisos de actividad y, finalmente, actívalo y guarda.

Usa `/new` para el flujo con botones, `/status` para comprobar servicios, `/settings` para los avisos de actividad y `/cancel` para descartar una solicitud sin terminar. El tipo de texto, los destinos, formatos, hora y confirmación son pasos separados. Los grupos no están admitidos, aunque Telegram permita añadir el bot a uno.

La descarga mediante la API en la nube admite archivos de hasta 20 MB. Para archivos más grandes usa el escritorio. Un aviso de actividad confirma que el receptor está funcionando; no puede despertar un Mac suspendido. Después de migrar, el bot permanece en pausa hasta que detengas el receptor anterior y actives el nuevo.

## ¿Qué enlace o inicio de sesión necesito?

| Lo que aparece | Qué hacer |
|---|---|
| Enlace de Postiz listo | Abre o copia ese enlace. No lo rotes por rutina. |
| Enlace temporal nuevo detectado | Pulsa **Usar enlace detectado** y espera la verificación. |
| Enlace público inaccesible | Revisa Docker/internet y usa **Revisar acceso**. Las conexiones verdes no comprueban la entrega de archivos. |
| El token se renueva al usarse | Usa **Conexiones → Revisar y renovar**. Reconecta solo si falla. |
| Una cuenta requiere reconexión | Sigue la guía de esa cuenta y conserva los otros canales. |

```text
Enlace público → contraseña del gateway + autenticador → acceso a Postiz → calendario
La autorización de cada red social es una conexión separada dentro de Postiz.
```

Un dominio nuevo puede pedir los dos accesos del navegador otra vez sin invalidar todos los tokens de redes sociales. Cuando una cuenta realmente requiera reconexión, actualiza primero su redirección OAuth correspondiente. Las URL de redirección son ajustes para copiar, no páginas para visitar. Los dos conectores de Instagram usan redirecciones distintas.

El dominio temporal de TryCloudflare puede cambiar al reiniciar el conector. Sincroniza la dirección detectada en lugar de rotarla repetidamente. Un túnel con nombre y dominio propio evita ese cambio habitual. Después de cambiar el dominio, conserva tus ediciones y prepara una revisión nueva antes de enviar enlaces de archivos antiguos.

## Respaldo y traslado

1. En el equipo anterior, elige **Crear respaldo**, un destino y una contraseña de al menos 12 caracteres. Los videos pueden hacer que el `.pfbackup` sea grande.
2. En el destino, usa **Restaurar respaldo → Elegir archivo de respaldo**, ingresa la contraseña y pulsa **Revisar respaldo**. La revisión no cambia datos actuales.
3. Lee el resultado, vuelve a ingresar la contraseña y confirma que el equipo anterior esté detenido. Reemplazar datos existentes exige otra confirmación y crea un respaldo de recuperación.
4. Después de restaurar, los servicios y Telegram siguen en pausa. Revisa la URL pública, el gateway, las sesiones y la zona horaria; luego inicia los servicios y activa Telegram expresamente. WhatsApp podría necesitar vincularse otra vez.

Cerrar el asistente no cancela una tarea en ejecución. Al abrirlo otra vez, encuentra el progreso activo. Si falla la consulta del progreso, **Retomar progreso** vuelve a la misma tarea; no inicies otra restauración. La contraseña no se conserva ni se puede recuperar.

## Actualizaciones, recursos y limpieza

La app busca actualizaciones al iniciar y cada seis horas. La bandeja indica si hay una disponible; la consulta manual también revisa componentes. macOS instala el cliente y el código correspondiente y actualiza los servicios configurados. Windows/Linux preparan un archivo verificado para reemplazarlo manualmente. Una versión nueva de Evolution requiere compatibilidad probada, no cambiar su imagen arbitrariamente.

**Administrar servicios** detiene solo esta instalación si no hay publicaciones programadas o Estados aprobados pendientes. Pausa el ingreso por WhatsApp y conserva Docker, Ollama y otros proyectos. Inicia los servicios antes de publicar otra vez. El receptor ligero de Telegram puede seguir activo mientras el equipo esté despierto. Los controles automáticos de reposo y encendido de Swift no forman parte del cliente Rust. Mantén el equipo despierto para las entregas programadas.

**Historial y ajustes del texto** usa 30 días por defecto. Los archivos temporales de WhatsApp sin uso se limpian automáticamente; los archivos referenciados y las publicaciones guardadas en Postiz se protegen. Cambiar el plazo no elimina nada de inmediato ni reinicia los identificadores de aprobación. No esperes que ese ajuste borre todos los videos históricos de Postiz. La guía técnica explica la limpieza más amplia.

**Eliminar publicaciones** muestra los borradores, fallos y elementos en cola antes de confirmar. No borra contenido que ya se publicó en las redes. Un envío que empezó podría terminar. Revisa el historial de cada plataforma antes de reintentar un lote.

La bandeja agrupa publicación, conexiones, servicios locales y ayuda. **Acerca de** está casi al final, antes de **Salir**. Salir cierra el cliente; los servicios siguen activos. Cerrar la ventana la oculta; ⌘N/Ctrl+N la abre otra vez mientras PostForge sea la app activa. Siri puede usar un atajo del sistema para **Abrir app**; la integración específica de Swift todavía no se ha portado.
