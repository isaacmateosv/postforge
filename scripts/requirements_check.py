# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only local requirements checks; never installs third-party software."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
SOURCES={
 'python':'https://www.python.org/downloads/macos/',
 'docker':'https://docs.docker.com/desktop/setup/install/mac-install/',
 'ffmpeg':'https://ffmpeg.org/download.html',
 'ollama':'https://ollama.com/download/mac',
 'openssl':'https://www.openssl.org/'}

def command(args):
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=8)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def check():
    python=sys.version_info>=(3,9)
    docker=bool(shutil.which('docker'));engine=docker and command(['docker','info','--format','{{.ServerVersion}}'])
    compose=docker and command(['docker','compose','version'])
    rows=[{'name':'Python 3.9+','key':'python','installed':python,'ready':python},
          {'name':'OpenSSL','key':'openssl','installed':bool(shutil.which('openssl')),'ready':command(['openssl','version'])},
          {'name':'Docker Desktop / Docker Engine + Compose','key':'docker','installed':docker,'ready':bool(engine and compose),'stopped':bool(docker and not engine)},
          {'name':'FFmpeg + ffprobe','key':'ffmpeg','installed':bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),'ready':bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))},
          {'name':'Ollama · optional caption generation','key':'ollama','optional':True,'installed':bool(shutil.which('ollama')),'ready':bool(shutil.which('ollama'))}]
    for row in rows:row['url']=SOURCES[row['key']]
    return {'items':rows,'ready_for_inspection':all(row['ready'] for row in rows[:2]),'ready_for_restore':all(row['ready'] for row in rows[:3]),'ready_for_publish':all(row['ready'] for row in rows[:4]),'configured':(ROOT/'.env').is_file()}
