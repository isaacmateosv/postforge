# Inicio rápido de PostForge

Este es el flujo actual del escritorio v2. Las instrucciones anteriores de Swift quedan abajo como referencia; usa solo el cliente Rust durante las pruebas de v2.

## Escritorio en Rust y Telegram guiado

**Inicio** muestra los borradores, las publicaciones programadas, la próxima
publicación y los indicadores de conexión. Abre Postiz para revisar lo guardado
o elige **Nueva publicación**.

1. **Redacta**: escribe una idea o selecciona conservar tus palabras. Adjunta
   archivos si los necesitas.
2. **Destinos**: elige redes, formatos, fecha y hora. **Pronto · +10 min** coloca
   una hora cercana en el futuro. La etiqueta del negocio empieza vacía en una
   instalación nueva; se conservan las etiquetas que configuraste expresamente.
   Para un Estado de WhatsApp solo de texto puedes elegir el color de fondo.
   Las opciones de portada y etiqueta están agrupadas debajo.
3. **Hornea y revisa**: una batidora pequeña anima la preparación. Se muestra
   un texto inicial. **Probar otro texto** añade otra versión; las flechas recorren
   las anteriores. Editar modifica la versión elegida. La adaptación más corta
   para Threads se identifica aparte. **Editar título…** modifica solo el título
   de YouTube (hasta 100 caracteres). Revisa los destinos y segmentos antes de
   crear borradores o confirmar expresamente la programación directa.

Las historias largas de Facebook e Instagram se dividen y programan con un
minuto entre cada segmento. Un video de 205 segundos genera **una publicación
más cuatro borradores de historias** por red al seleccionar ambos formatos.
YouTube Shorts prepara una copia aparte de **2:59** para videos verticales o
cuadrados más largos; las otras redes conservan el video completo. En **Automático**, los videos horizontales conservan su duración como videos normales; los verticales y cuadrados van a Shorts. Elegir Video normal no cambia la clasificación de YouTube para un video vertical corto que cumple los requisitos. Un video horizontal
no se recorta de forma automática para convertirlo en Short.

**WhatsApp** en la cabecera muestra la conexión o permite escanear el QR en la
ventana. Se conserva una sesión que ya funciona. **Eliminar publicaciones…**
distingue entre borrar borradores y cancelar publicaciones programadas. Muestra
las cantidades antes de confirmar. Lo que ya se publicó permanece en línea.

La app encuentra automáticamente su instalación local; no necesitas elegir
carpetas para usarla. **Ajustes → Avanzado · recuperación y migración** sirve
solo para localizar una instalación recuperada o migrada. No se muestra la
ruta en el inicio.

Abre **Telegram** en la cabecera de la app. Cada instalación usa su propio bot
dedicado y una cuenta privada autorizada; no hay un bot global compartido.
Créalo con **/newbot** en **@BotFather**, pega el token en el campo oculto y pulsa
**Validar bot**. Envía **/start** a tu bot y usa **Buscar mi cuenta privada**.
Elige tu cuenta y verifica su ID numérico. Configura el idioma y los avisos de
actividad (**0** = apagados; si los activas, de **5 a 1440 minutos**), activa el
bot y confirma **Guardar ajustes**. No necesitas la terminal. Mantén activa la
privacidad de grupos; no necesitas modo inline ni webhook público. Envía **/new**
a tu bot.

Los botones guían el tipo de texto, archivos, destinos, formatos, hora y revisión.
Usa **Probar otro texto**, las flechas o **Editar texto** para refinarlo.
Envía solo después de la confirmación final. El Estado de WhatsApp se aprueba
aparte. **/cancel** descarta el plan sin terminar y **/status** revisa si los
servicios responden.

El bot descarga hasta 20 MB por archivo desde la nube. Usa la app de escritorio
para videos más grandes. Mantén el equipo despierto y los servicios activos
cuando corresponda publicar. Inicia el agente después de reiniciar o configura
el inicio automático del sistema.

El .env privado y los respaldos cifrados de credenciales incluyen el token,
la cuenta autorizada, el idioma, los avisos de actividad y la preferencia de
activación. Al migrar, Telegram queda en pausa: detén el receptor anterior,
revisa los ajustes en el nuevo equipo y actívalo expresamente. Guarda el
respaldo y su contraseña de forma privada. Deja el token vacío para conservar
el que ya guardaste. Desactivar conserva los ajustes y funciona incluso sin
conexión con Telegram.

## Flujo anterior del Mac en Swift

Convierte una foto o un video y una idea en un borrador que puedas revisar antes de publicar.

```text
Archivos o texto → Hornea y revisa
                     ├─ Crea borradores → Aprueba en Postiz
                     └─ Confirma la programación directa
Estado de WhatsApp → aprobación aparte
```

## Haz tu primera publicación

1. Abre PostForge desde la barra de menús. Si dice **Inactivo** o **Apagado**, elige **Encender**.
2. Abre **Nueva publicación** y arrastra una foto o un video.
3. Indica dónde y cuándo quieres publicar. Añade una idea o escribe entre comillas el texto exacto.

```text
YouTube Shorts mañana a las 9 a. m. Texto: «Esto es lo que hicimos esta semana».
```

También puedes poner primero la idea y separarla con punto y coma. Por ejemplo, «galletas y cupcakes; postea en todo lado a las 7:15 pm, posts e historias».

4. Pulsa **👨‍🍳 Hornea la idea**. Revisa la hora, los canales, el texto y los avisos sobre el video.
5. Pulsa **Crear borradores** y abre el **calendario de Postiz**. Revisa el borrador y aprueba la programación ahí.

Usa **idea:** o **escribe sobre** con un tema sin comillas para generar un texto. Usa **texto:** o **caption:** para conservar la redacción que ya preparaste. Un texto entre comillas dobles se conserva, incluso después de **idea:**. Si configuraste una etiqueta final, se añade al final.

```text
Facebook y Threads mañana a las 7:15 p. m.; idea: anunciar nuestro nuevo horario
WhatsApp mañana a las 19:15; texto: "Mañana atendemos desde las 10. ¡Te esperamos! ✨"
```

La ventana más ancha mantiene el pedido y los archivos a la izquierda y el plan a la derecha. **Crear borradores** se habilita después de hornear correctamente. Cambiar el pedido, los archivos, los formatos o la portada requiere volver a hornear. El campo del pedido crece dentro de la ventana y permite desplazarte si el texto es más largo.

Pulsa **Probar otro texto** para pedir otra redacción, usa **‹ / ›** para recorrer hasta ocho versiones guardadas o **Editar texto…** para corregirlo a mano. Estas acciones cambian únicamente la sección del texto, incluidos el texto de Threads y el título de YouTube cuando correspondan. Se conservan la fecha, los destinos, la portada, las notas y las advertencias del plan. Un texto exacto se reescribe solo si pides otra versión. Las versiones pertenecen al plan actual.

En macOS, **⌘ Return** hornea la idea y **⌘Z** deshace cambios en el pedido. **Programar directamente…** programa las publicaciones seleccionadas después de confirmar. **Crear borradores** mantiene la aprobación posterior en Postiz. El Estado de WhatsApp requiere su propia aprobación.

## Enviar un anuncio solo de texto

Si no adjuntaste archivos, Hornea la idea abre una selección de destinos. Elige **Publicación de Facebook**, **Publicación de Threads**, **Estado de WhatsApp** o varios. Revisa esos destinos en el plan antes de continuar. En este flujo, las publicaciones e historias de Instagram, las historias de Facebook, TikTok y YouTube requieren un archivo. Para usarlos con un anuncio, adjunta una imagen o un video adecuado.

En WhatsApp, confirma los destinos compatibles de forma explícita, por ejemplo:

```text
Facebook y Threads mañana a las 19:15, solo texto aprobado; texto: "Mañana atendemos desde las 10. ✨"
WhatsApp mañana a las 19:15; texto: "Mañana atendemos desde las 10. ✨"
```

Responde **mejora plan 1** cuando se ofrezca para pedir otra redacción sin cambiar el plan. Revisa el texto que recibes antes de aprobarlo. También puedes enviar tus palabras exactas desde el inicio.

## Limpiar elementos que ya no necesitas

**Limpiar…** permite reiniciar el formulario, eliminar borradores y publicaciones fallidas de Postiz, cancelar la cola y los Estados pendientes de WhatsApp o combinar ambos alcances guardados. Primero muestra cuántos elementos coinciden y después solicita confirmar. Reiniciar el formulario limpia solo los campos sin guardar. La limpieza usa la organización actual de Postiz y conserva elementos cuyo estado cambió después de la vista previa.

Las publicaciones que ya salieron quedan fuera del alcance. Un envío que ya empezó podría completarse. Revisa cualquier entrega sin confirmar antes de volver a publicar. Los archivos compartidos siguen la retención configurada. Los planes recibidos por WhatsApp que todavía esperan revisión se pueden rechazar en esa ventana.

## Elige los formatos y la portada

Abre **Opciones de borrador** en la barra de menús para acceder a los formatos y la portada.
En la ventana de publicación, usa **Crear borradores de** para elegir publicaciones,
historias o ambos formatos. **Automático** sigue tu instrucción. «Publica en todas
las redes» incluye publicaciones e historias donde se admiten. Las historias
requieren fotos o videos. WhatsApp usa su propio formato de Estado.

Si adjuntas un solo video, en **Portada del video** puedes elegir una imagen aparte
o ingresar un segundo, por ejemplo `12,5`. El plan muestra qué borradores pueden
usar la portada. Los reels de Instagram admiten ambas opciones. En los videos
de YouTube, incluidos Shorts, puedes usar una imagen o un fotograma extraído del video; la cuenta debe tener habilitadas las miniaturas personalizadas.
En publicación directa de TikTok puedes indicar el segundo. Para los envíos a
la bandeja de TikTok, elige la portada en la plataforma.

Si el plan incluye un video para un destino que admite portada y todavía no elegiste una, PostForge te pregunta si quieres continuar. En un plan listo para revisar, usa **Editar portada…** para habilitar los controles y volver a hornear el plan.

Abre **Opciones de publicación → Configurar… → Etiqueta final…** para guardar una etiqueta. Déjala en blanco si prefieres omitirla. El plan la muestra en la última línea, incluso si escribiste el texto exacto. En WhatsApp, usa el comando que te propone el bot, por ejemplo `etiqueta plan 1 #MiNegocio`. Revisa la versión nueva antes de aprobar.

## Usa WhatsApp o Siri

Envía un archivo y una instrucción a tu chat contigo en WhatsApp mientras PostForge esté encendido. Revisa el plan que te devuelve. Al confirmarlo, se preparan los borradores. Revisa los borradores de redes sociales en Postiz. Antes del texto, escribe «solo publicaciones», «solo historias», «publicaciones e historias» o «portada en el segundo 12,5». Para usar una imagen aparte, adjunta un video y una foto y escribe «imagen de portada». La respuesta muestra el plan y los comandos para aprobarlo o rechazarlo y reenviar tu pedido.

En tu Mac, importa **Nueva publicación en PostForge** con **Atajos de Siri…** en Ayuda y dile ese nombre a Siri. El atajo abre la ventana de publicación. Elige **Encender** ahí si los servicios están inactivos.

Después de crear los borradores en el Mac, aprueba por separado el Estado de WhatsApp. Usa **Aprobar Estado…** en el plan o **Aprobar Estado de WhatsApp…** en la barra de menús. Revisa la confirmación en tu propio chat. Si la hora ya pasó, el Estado puede enviarse en cuanto lo apruebes.

## Libera recursos para editar

PostForge apaga sus servicios después de una hora sin actividad ni trabajo en cola. Durante la pausa, las instrucciones de WhatsApp quedan pendientes. Activa **Avisarme por WhatsApp antes de apagar** si quieres un aviso en tu propio chat. Desactiva **Apagar al estar inactivo** si quieres que la recepción siga disponible mientras el Mac esté despierto.

## Revisa la duración de tus videos

- Los **reels de Instagram** de más de tres minutos no se recomiendan a nuevas audiencias.
- **YouTube Shorts** requiere un video vertical o cuadrado de hasta tres minutos.
- Las **historias de Facebook e Instagram** dividen un video largo en clips separados. Revisa cada borrador en orden.
- **Estado de WhatsApp** divide los videos largos en partes de hasta 60 segundos después de aprobarlos.

## Encuentra las herramientas

- **Calendario de Postiz** muestra los borradores y las publicaciones programadas.
- **Buscar actualizaciones** está en el menú principal de la barra.
- **Respaldo y traslado** permite exportar un respaldo privado.
- En Ayuda, elige **Técnica** para consultar la instalación, la recuperación y el manejo de datos.


## Ventana, bandeja y migración
La ventana Rust se abre centrada y con un ancho cómodo (hasta 1120 píxeles lógicos); aprovecha más altura si el escritorio lo permite. Conserva el acceso a la barra de menús del sistema y puedes maximizarla manualmente. La cabecera y los controles inferiores permanecen visibles; el área de trabajo y los diálogos largos permiten desplazarse. En pantallas de menor altura, el espaciado se vuelve más compacto. Cerrar oculta la ventana; ⌘N (macOS) o Ctrl+N (Windows/Linux) vuelve a abrir el formulario mientras PostForge sea la app activa. El ícono del Dock de macOS también vuelve a mostrar la ventana. Salir en la bandeja cierra el cliente y los servicios de publicación siguen activos.

Usa **Respaldo y traslado** desde la ventana o la bandeja. La exportación crea un archivo `.pfbackup` cifrado y autenticado con las credenciales, la configuración del acceso seguro, los datos de Postiz y los archivos multimedia; además, verifica la restauración en una base temporal. Guarda por separado la contraseña de al menos 12 caracteres: no se puede recuperar. Revisar un respaldo no modifica los datos activos. Para restaurar, revisa el mismo archivo, vuelve a ingresar la contraseña y confirma que el equipo anterior esté detenido. Reemplazar datos existentes requiere marcar una casilla y primero crea un respaldo cifrado de recuperación. Si las credenciales de la base son distintas, necesitas una instalación de destino nueva. Los servicios restaurados quedan detenidos y Telegram permanece en pausa: verifica la URL pública, el acceso seguro, las sesiones de los canales y los horarios antes de iniciar los servicios o activar Telegram. WhatsApp puede necesitar vincularse otra vez.

La bandeja incluye Inicio, Nueva publicación, planes y aprobaciones de WhatsApp, conexiones, respaldos, actualizaciones, ajustes y Ayuda. Acerca de está casi al final, antes de Salir. Un número pequeño junto al ícono monocromático indica tareas activas. La app busca actualizaciones al iniciar y cada seis horas; la consulta manual incluye los componentes de Docker y Evolution. Las consultas incompletas se indican como tales; el cliente solo ofrece archivos ZIP Rust compatibles, no paquetes anteriores.


### Dónde encontrar las acciones en la app

Redacta → Destinos → Revisa y termina permanece en la parte superior. Elige **Generar un texto** si tienes una idea o **Usar mi texto** para conservar tu redacción. Las opciones muestran por separado la selección y el foco del teclado. El pie contiene información de privacidad y, mientras redactas, **Limpiar formulario**. El mantenimiento está en **Ajustes → App y datos**: actualizaciones, **Respaldo y traslado**, y eliminación de borradores o publicaciones en cola. El idioma también está en Ajustes. Puedes actualizar el inicio junto a **Abrir Postiz**. Estas acciones siguen disponibles en la bandeja. La limpieza muestra una vista previa y pide confirmación antes de eliminar algo. El batidor solo se anima mientras se prepara el plan y respeta la preferencia del sistema para reducir movimiento.


## Vistas previas, conexiones y entregas de WhatsApp

Usa el reproductor de Redacta para revisar los archivos. Se pausa al salir del paso o cambiar de ventana. En Destinos puedes ver la portada subida o elegir un segundo del video. **Usar fotograma actual** toma la posición del reproductor. La compatibilidad de portadas depende del destino.

**Conexiones** muestra el estado de cada sesión en Postiz y la vigencia real del token: conectado, renovación pendiente, en pausa o reconexión necesaria. No garantiza una publicación exitosa.

En **WhatsApp → Audiencia**, elige todos los contactos o números seleccionados con código de país y guarda. Los planes nuevos usan esa audiencia; los que ya están en cola conservan la anterior. No se puede cambiar mientras se envía un Estado. Una audiencia grande puede requerir varios minutos por segmento: revisa el progreso antes de reenviar. Puedes mostrar u ocultar los recibos, filtrarlos por fecha o tipo y recorrerlos de cinco en cinco.

La descripción de YouTube termina con la etiqueta del negocio; si está vacía, se usa `#shorts`. No se añade una etiqueta automática al título. La descripción es independiente del límite de 100 caracteres del título.


## URL pública y túnel

Abre **Ajustes → Acceso público** o **URL pública y túnel** en la barra de menús. Elige TryCloudflare temporal, tu dominio con un túnel de Cloudflare con nombre o ngrok guardado. Comprueba el acceso antes de publicar. Rotar o reiniciar un conector temporal cambia el dominio: aplica la URL detectada y actualiza las redirecciones OAuth antes de reconectar los canales. El dominio y el token se conservan al volver al modo temporal. Los ajustes viajan en Respaldo y migración de forma cifrada; verifica la URL del destino antes de reanudar las publicaciones. Consulta la Ayuda técnica para ver el procedimiento completo.


Haz clic en la URL pública actual o en **Copiar enlace** para copiarla. El control cambia brevemente a verde y confirma **Enlace copiado**. Las URL de redirección OAuth también se copian al hacer clic; con el teclado, usa Tab y Enter o Espacio.


La ventana de red se actualiza al volver a ella y mientras está visible. Antes de copiar la URL o una redirección, se consulta la configuración actual. Si el conector temporal cambió de dominio y necesita sincronizarse, se deshabilitan los enlaces anteriores y se muestra la dirección detectada. Pulsa **Sincronizar URL actual** antes de copiar o abrir Postiz.


Un token de acceso vencido que tiene una credencial de actualización guardada se muestra como **Se renueva al volver a usarse**, no como una tarea de renovación en cola. Pulsa **Conexiones → Revisar y renovar** para intentarlo mediante consultas de estadísticas de solo lectura. Solo se consultan canales con tokens vencidos que admiten renovación. PostForge vuelve a leer el estado guardado; no marca el canal como conectado únicamente por recibir HTTP 200. Reconecta solo si la renovación falla. Esta acción no publica nada y las comprobaciones en segundo plano no envían solicitudes de renovación.

### Revisar sin empezar de nuevo

En el paso 3 puedes cambiar la fecha y hora o elegir **En 10 minutos**, y luego **Actualizar hora**. Se conservan las versiones del texto, la portada y los destinos. Al enviar también se guarda la hora modificada antes de pedir confirmación.

**Probar otro título** genera únicamente un título de YouTube a partir del texto actual. **Editar título** permite escribirlo manualmente. El hashtag del negocio cierra el título dentro de sus 100 caracteres; la descripción conserva los hashtags temáticos y termina con el del negocio, o con `#shorts` si no configuraste uno.

**Programar directamente** aprueba todos los destinos seleccionados, incluido el Estado de WhatsApp para el público configurado a la hora revisada. **Crear borradores** conserva la aprobación separada de WhatsApp. Con públicos grandes, cada segmento del Estado puede tardar varios minutos; el indicador de envío no significa que haya fallado.

### Pasos claros y ajustes de mensajería

La siguiente acción permanece al pie de la ventana: **Elegir destinos**, **Hornea y revisa** y luego **Crear borradores** o **Programar directamente**. El aviso verde **Portada lista** confirma que la vista previa de la imagen o del fotograma se preparó correctamente; los errores se mantienen visibles. Esto confirma la selección, no que todos los destinos acepten esa portada.

Después de programar directamente, la pantalla de confirmación vuelve al inicio tras **ocho segundos activos**. Pulsa **Quedarme aquí** o interactúa con el comprobante para detener la cuenta. Si la ventana está oculta o hay un diálogo abierto, se pausa. Al crear borradores se mantiene el comprobante para que puedas completar la aprobación separada de WhatsApp.

En Telegram, abre **Ajustes · aviso de actividad** o envía `/settings`. Elige apagado, cada 30 minutos, cada hora, cada seis horas o una vez al día. Se conserva tu plan de publicación. El siguiente intervalo comienza después del cambio; no se envía un aviso de prueba. El agente debe seguir activo para enviar los avisos; el ping no puede despertar un Mac ni un servicio apagados.

En tu chat contigo mismo de WhatsApp, envía únicamente `postforge ajustes` para ver las preferencias. Cambia el aviso de Telegram con `postforge ping 60` o apágalo con `postforge ping apagado`. Son comandos independientes: no se activan desde el texto de una publicación, no convierten tu siguiente mensaje en una respuesta de ajustes ni consumen archivos que esperan un pedido de publicación. Puedes usar de 5 a 1440 minutos; 0 significa apagado. Las preferencias se guardan en la configuración local y viajan en la migración cifrada. Al restaurar, Telegram queda en pausa hasta que lo actives expresamente.

El menú de la barra organiza **Publicación**, **Conexiones** y **App y ayuda**. Planes y recibos de WhatsApp permanece en el menú principal; Acerca de PostForge está justo antes de Salir.

El acceso del gateway usa por defecto **30 minutos sin solicitudes**, con un **máximo de dos horas por sesión**. Postiz tiene su propio inicio de sesión. Los respaldos conservan el tiempo configurado. El token temporal de YouTube puede vencer entre usos; **Renovación automática disponible** significa que hay una credencial de renovación guardada, no que se haya probado la publicación. Usa **Revisar y renovar** para comprobarlo ahora; vuelve a conectar solo si falla.

### Botones de WhatsApp

Al preparar un plan en tu chat contigo mismo, PostForge envía el texto para copiar y una tarjeta compacta de acciones. **Revisar aprobación** muestra qué ocurrirá; **Confirmar plan** crea los borradores de redes y aprueba el Estado de WhatsApp si lo seleccionaste. No publica automáticamente los borradores de redes. **Probar otro texto** cambia el texto y **Más opciones** permite descartar la revisión o abrir Ajustes. Descartar una revisión también requiere confirmación y no elimina publicaciones guardadas en Postiz.

Abre los avisos de actividad con `postforge ajustes` o con el botón explícito **Ajustes**. Los botones de intervalo solo cambian el aviso de Telegram; **Volver** regresa al plan. Un texto normal nunca abre los ajustes. Los comandos escritos siguen disponibles si un cliente no muestra la tarjeta. Los botones vencidos, ya usados o de una versión anterior no pueden aprobar un plan modificado; usa la revisión más reciente.

### Restaurar un archivo `.pfbackup`

En el equipo de destino, abre **Ajustes → App y datos → Restaurar respaldo**. También puedes elegir **Restaurar respaldo** dentro de **Respaldo y traslado** desde la barra de menú. Haz clic en **Elegir archivo de respaldo**, selecciona el archivo `.pfbackup`, ingresa su contraseña y presiona Enter o **Revisar respaldo**. La revisión no modifica los datos actuales. Después, vuelve a ingresar la contraseña y sigue la confirmación explícita de restauración. Detén el equipo que publicaba anteriormente antes de restaurar; no reemplaces la instalación de origen solo para comprobar el respaldo. **Avanzado → Carpeta de instalación** localiza una carpeta instalada existente; no importa archivos de respaldo.

El respaldo incluye todos los archivos subidos que aún se conservan. Los videos pueden ocupar varios gigabytes; ese tamaño por sí solo no indica una falla. Cambiar entre Crear y Restaurar limpia el resultado anterior para que un mensaje viejo de “Completado” no se confunda con el resultado de una nueva revisión. La contraseña del respaldo no se puede recuperar.

Ayuda abre la guía rápida de inmediato. Elige Guía técnica para los detalles de configuración. La carga y los errores con opción de reintento aparecen dentro de Ayuda; no necesitas confirmar Abrir guía por separado.
