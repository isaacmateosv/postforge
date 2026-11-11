# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, local-only media inspection and cover frames. No persistent copies."""
import base64
import json
import math
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/"lib"))
import pmlib


def inspect(path):
    path=Path(path)
    if not path.is_file() or path.suffix.lower() not in pmlib.VIDEO_EXT|pmlib.IMAGE_EXT:
        raise pmlib.PMError('Choose a media file. / Elige un archivo multimedia.')
    try:
        result=subprocess.run(['ffprobe','-v','error','-print_format','json','-select_streams','v:0',
            '-show_entries','format=duration:stream=width,height:stream_tags=rotate:stream_side_data=rotation',str(path)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8)
        if result.returncode or len(result.stdout)>1_000_000:raise ValueError
        data=json.loads(result.stdout);stream=data['streams'][0]
        duration=float(data.get('format',{}).get('duration') or 0);width=int(stream.get('width') or 0);height=int(stream.get('height') or 0)
        rotations=[stream.get('tags',{}).get('rotate',0)]+[item.get('rotation',0) for item in stream.get('side_data_list',[])]
        if any(abs(float(value))%180==90 for value in rotations):width,height=height,width
        if not width or not height or not math.isfinite(duration):raise ValueError
    except (OSError,subprocess.TimeoutExpired,ValueError,KeyError,IndexError,TypeError):
        raise pmlib.PMError('Media details could not be read. / No se pudieron leer los datos del archivo.') from None
    return {'video':path.suffix.lower() in pmlib.VIDEO_EXT,'duration':duration,'width':width,'height':height,
            'orientation':'square' if width==height else 'vertical' if height>width else 'horizontal'}


def frame(path,second=0):
    info=inspect(path)
    try:second=float(second)
    except (ValueError,TypeError):raise pmlib.PMError('Choose a valid cover timestamp. / Elige un segundo válido para la portada.') from None
    if not math.isfinite(second) or second<0 or (info['video'] and second>=info['duration']):
        raise pmlib.PMError('The cover timestamp must be within the video. / El segundo de la portada debe estar dentro del video.')
    args=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-threads','1']
    if info['video']:args+=['-ss',str(second)]
    args+=['-i',str(path),'-frames:v','1','-vf',"scale=640:640:force_original_aspect_ratio=decrease",'-threads','1','-f','image2pipe','-c:v','png','pipe:1']
    try:result=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    except (OSError,subprocess.TimeoutExpired):raise pmlib.PMError('The preview could not be prepared. / No se pudo preparar la vista previa.') from None
    if result.returncode or not result.stdout.startswith(b'\x89PNG\r\n\x1a\n') or len(result.stdout)>3_000_000:
        raise pmlib.PMError('The preview could not be prepared. / No se pudo preparar la vista previa.')
    return {'image':'data:image/png;base64,'+base64.b64encode(result.stdout).decode(),'second':second,**info}
