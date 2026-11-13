# SPDX-License-Identifier: GPL-3.0-or-later
"""Requirements-aware macOS product installer for the Rust desktop bundle."""
from pathlib import Path
import subprocess
import plistlib

LINKS='''<ul><li><a href="https://www.python.org/downloads/macos/">Python 3.9+</a></li><li><a href="https://docs.docker.com/desktop/setup/install/mac-install/">Docker Desktop + Compose</a></li><li><a href="https://ffmpeg.org/download.html">FFmpeg + ffprobe</a></li><li><a href="https://ollama.com/download/mac">Ollama (optional / opcional)</a></li></ul>'''

def build(root,package,version,architecture,work):
    work=Path(work);resources=work/'installer-resources';resources.mkdir()
    for locale,title,description in [
      ('en','Before you install PostForge','The installer checks whether required tools are present and warns if any are missing. It does not download or install third-party tools. Python 3.9+ is required to open backups. Docker must be running with Compose to restore and publish. FFmpeg and ffprobe are required for video publishing. OpenSSL is normally supplied by macOS. Ollama and a local model are optional for generated captions. After installation, open Settings → Check requirements for actual version and running-service checks, then choose Restore backup on the destination Mac. The app and its public backend code are included; private data is stored in your user account.'),
      ('es','Antes de instalar PostForge','El instalador revisa si las herramientas necesarias están presentes y avisa si falta alguna. No descarga ni instala herramientas de terceros. Python 3.9+ es necesario para abrir respaldos. Docker debe estar ejecutándose con Compose para restaurar y publicar. FFmpeg y ffprobe se necesitan para publicar videos. macOS normalmente incluye OpenSSL. Ollama y un modelo local son opcionales para generar textos. Después de instalar, abre Ajustes → Revisar requisitos para comprobar versiones y servicios en ejecución; luego elige Restaurar respaldo en el Mac de destino. Se incluyen la app y el código público de sus servicios; los datos privados se guardan en tu cuenta de usuario.')]:
        folder=resources/(locale+'.lproj');folder.mkdir()
        body=f'<html><meta charset="utf-8"><body style="font:15px -apple-system;line-height:1.6;padding:18px"><h1>{title}</h1><p>{description}</p><h2>Downloads / Descargas</h2>{LINKS}</body></html>'
        (folder/'Welcome.html').write_text(body)
        (folder/'Localizable.strings').write_text('"requirementsWarning" = "'+('Some tools are missing. Install the items below from the official links in the Introduction, then use Check requirements in PostForge. Missing: ' if locale=='en' else 'Faltan herramientas. Instala los elementos de abajo desde los enlaces oficiales de la introducción y usa Revisar requisitos en PostForge. Faltan: ')+'";')
    component_info=work/'components.plist'
    component_info.write_bytes(plistlib.dumps([{'RootRelativeBundlePath':'Applications/PostForge Desktop.app','BundleIsRelocatable':False,'BundleOverwriteAction':'upgrade','BundleHasStrictIdentifier':True}]))
    component=work/'desktop-component.pkg'
    subprocess.run(['pkgbuild','--root',str(root),'--component-plist',str(component_info),'--identifier','local.postforge.desktop','--version',version.split('-')[0],'--install-location','/',str(component)],check=True,stdout=subprocess.DEVNULL)
    distribution=work/'Distribution.xml'
    distribution.write_text('''<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2"><title>PostForge Desktop</title>
<options customize="never" hostArchitectures="'''+architecture+'''"/>
<welcome file="Welcome.html" mime-type="text/html"/>
<installation-check script="checkRequirements()"/>
<volume-check script="true"><allowed-os-versions><os-version min="13.0"/></allowed-os-versions></volume-check>
<script><![CDATA[
function exists(paths) {for(var i=0;i<paths.length;i++) if(system.files.fileExistsAtPath(paths[i])) return true;return false;}
function checkRequirements() {
 var missing=[];
 if(!exists(['/usr/bin/python3','/opt/homebrew/bin/python3','/usr/local/bin/python3','/Library/Frameworks/Python.framework/Versions/Current/bin/python3'])) missing.push('Python 3.9+');
 if(!exists(['/Applications/Docker.app','/opt/homebrew/bin/docker','/usr/local/bin/docker'])) missing.push('Docker Desktop / Compose');
 if(!exists(['/opt/homebrew/bin/ffmpeg','/usr/local/bin/ffmpeg']) || !exists(['/opt/homebrew/bin/ffprobe','/usr/local/bin/ffprobe'])) missing.push('FFmpeg / ffprobe');
 if(!exists(['/usr/bin/openssl','/opt/homebrew/bin/openssl','/usr/local/bin/openssl'])) missing.push('OpenSSL');
 if(missing.length) {my.result.type='Warning';my.result.message=system.localizedString('requirementsWarning')+missing.join(', ');return false;}
 return true;
}
]]></script>
<choices-outline><line choice="desktop"/></choices-outline>
<choice id="desktop" visible="false"><pkg-ref id="local.postforge.desktop"/></choice>
<pkg-ref id="local.postforge.desktop" version="'''+version.split('-')[0]+'''">desktop-component.pkg</pkg-ref></installer-gui-script>''')
    subprocess.run(['productbuild','--distribution',str(distribution),'--resources',str(resources),'--package-path',str(work),str(package)],check=True,stdout=subprocess.DEVNULL)
