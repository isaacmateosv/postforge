# Guía técnica de PostForge

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
3. Habilita el dominio HTTPS en ngrok, configura las credenciales y URL de retorno de OAuth y conecta las redes sociales en Postiz.
4. Enciende PostForge. Abre **WhatsApp Manager** y escanea el código QR con el teléfono autorizado. Mantén la clave de la API en privado.
5. Ejecuta las verificaciones de solo lectura desde la carpeta del proyecto.

```bash
cd ~/postforge
./postforge.sh doctor
./scripts/recheck.sh --live
```

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

En **Respaldo y traslado**, exporta las credenciales cifradas y el archivo verificado de Postiz. Mantén ese archivo en privado porque contiene tokens de los canales. Restaura en el Mac de destino antes de programar contenido nuevo, verifica los envíos pendientes y vuelve a vincular WhatsApp. La migración excluye las tareas de Temporal y la sesión de WhatsApp.

Si Postiz queda inaccesible al cambiar el túnel, revisa en el registro si se restauró la configuración anterior. Para recuperar una conexión específica, consulta docs/reconnect en el repositorio. Usa **Abrir registro** en la barra antes de reiniciar o eliminar datos.

```bash
./postforge.sh status
./postforge.sh channels
./postforge.sh maintenance check
```
