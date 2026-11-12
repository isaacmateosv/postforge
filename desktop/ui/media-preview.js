// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
"use strict";
window.PostForgeMedia = (() => {
  const $=id=>document.getElementById(id);
  const video=$('video-preview');
  let language='en',selected=null,files=[],cover=null,second=null,sequence=0,frameSequence=0,framePending=null,frameRunning=false;
  let onFrame=()=>{},onInfo=()=>{},onCover=()=>{},coverSignature=null;
  const say=(en,es)=>language==='es'?es:en;
  const engine=(operation,payload)=>window.__TAURI__.core.invoke('engine',{operation,payload});
  const source=path=>window.__TAURI__.core.convertFileSrc(path);
  const isVideo=path=>/\.(mp4|mov|m4v|webm|mkv|avi|3gp)$/i.test(path);
  const basename=path=>path.split(/[\\/]/).pop();
  function pause(){video.pause();}
  async function drainFrame(){
    if(frameRunning)return;
    frameRunning=true;
    try {
      while(framePending){
        const job=framePending;framePending=null;
        try {
          const result=await engine('media_frame',{path:job.path,second:job.second});
          if(job.id!==frameSequence)continue;
          $('cover-preview').src=result.image;$('cover-preview').hidden=false;
          $('cover-preview-status').textContent=job.uploaded?say('✓ Cover ready · ','✓ Portada lista · ')+basename(job.path):say('✓ Cover ready · frame at ','✓ Portada lista · fotograma en ')+result.second.toFixed(2)+' s';
          $('cover-preview-box').dataset.state='ready';
          onCover({state:'ready',message:$('cover-preview-status').textContent});
        }catch(error){if(job.id===frameSequence){$('cover-preview').hidden=true;$('cover-preview-box').dataset.state='error';$('cover-preview-status').textContent=String(error).split(' / ')[language==='es'?1:0]||String(error);onCover({state:'error',message:$('cover-preview-status').textContent});}}
      }
    }finally{frameRunning=false;}
  }
  function updateCover(){
    frameSequence++;framePending=null;$('cover-preview-box').dataset.state='empty';
    $('cover-preview').hidden=true;$('cover-preview').removeAttribute('src');
    const chosen=cover || (second!==null && second!=='' && files.filter(isVideo).length===1?files.find(isVideo):null);
    if(!chosen){$('cover-preview-status').textContent=say('Choose an image or a video timestamp to preview the cover.','Elige una imagen o un segundo del video para ver la portada.');return;}
    $('cover-preview-box').dataset.state='pending';
    $('cover-preview-status').textContent=say('Preparing cover preview','Preparando vista previa de la portada');
    framePending={id:frameSequence,path:chosen,second:cover?0:second,uploaded:!!cover};drainFrame();
  }
  async function show(path){
    const token=++sequence;pause();
    selected=path;video.removeAttribute('src');video.removeAttribute('poster');video.load();
    $('image-preview').hidden=true;$('image-preview').removeAttribute('src');video.hidden=true;$('use-current-frame').hidden=true;
    $('media-preview-info').textContent='';
    if(!path){onInfo(null);return;}
    const movie=isVideo(path);
    video.hidden=!movie;$('image-preview').hidden=movie;$('use-current-frame').hidden=!movie;
    if(movie){video.src=source(path);video.load();}else $('image-preview').src=source(path);
    try{
      const info=await engine('media_inspect',{path});if(token!==sequence)return;
      const shape=info.orientation==='vertical'?say('Vertical','Vertical'):info.orientation==='square'?say('Square','Cuadrado'):say('Horizontal','Horizontal');
      $('media-preview-info').textContent=shape+' · '+info.width+' × '+info.height+(movie?' · '+Math.floor(info.duration/60)+':'+String(Math.floor(info.duration%60)).padStart(2,'0'):'');
      if(movie)$('cover-second').max=Math.max(0,info.duration-.01).toFixed(2);
      onInfo(info);
      if(movie){
        const poster=await engine('media_frame',{path,second:0});
        if(token===sequence)video.poster=poster.image;
      }
    }catch(error){if(token===sequence){onInfo(null);$('media-preview-info').textContent=say('Preview unavailable for this file. Your selected file is kept.','No hay vista previa para este archivo. Se conserva tu selección.');}}
  }
  video.addEventListener('error',()=>{$('media-preview-info').textContent=say('This codec cannot play in this window. The file is still selected.','Este códec no se puede reproducir en esta ventana. El archivo sigue seleccionado.');});
  $('preview-file').onchange=()=>show($('preview-file').value);
  $('use-current-frame').onclick=()=>{if(Number.isFinite(video.currentTime)){pause();onFrame(Number(video.currentTime.toFixed(2)));}};
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
  window.addEventListener('blur',pause);
  return {
    pause,
    configure(callbacks){onFrame=callbacks.onFrame;onInfo=callbacks.onInfo;onCover=callbacks.onCover || (()=>{});},
    update(paths,image,timestamp,lang){
      language=lang;cover=image;second=timestamp;files=[...paths];
      $('preview-file').setAttribute('aria-label',say('Preview file','Archivo de vista previa'));
      $('image-preview').alt=say('Selected media','Archivo seleccionado');$('cover-preview').alt=say('Selected cover','Portada seleccionada');
      $('media-preview-pane').hidden=!files.length;$('preview-file').hidden=files.length<2;
      $('preview-file').replaceChildren(...files.map(path=>{const option=document.createElement('option');option.value=path;option.textContent=basename(path);return option;}));
      const path=files.includes(selected)?selected:files[0];$('preview-file').value=path || '';
      if(path!==selected || !path)show(path);
      const signature=JSON.stringify([files,cover,second,language]);
      if(signature!==coverSignature || $("cover-preview-box").dataset.state==='error'){coverSignature=signature;updateCover();}
    }
  };
})();
