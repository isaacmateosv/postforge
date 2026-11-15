// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
"use strict";
window.PostForgeNetworkLinks={
  create({field,copy,onURL}){
    let latest=null,language=null;
    return {
      update(result,{busy=false,lang="en",placeholder=""}={}){
        if(latest && Number(result.checked_at || 0)<Number(latest.checked_at || 0))return false;
        const changed=!latest || latest.url!==result.url || latest.needs_sync!==result.needs_sync || language!==lang;
        latest=result;language=lang;
        const blocked=busy || result.needs_sync || !result.url || result.reachable===false;
        field.value=result.needs_sync?"":result.url || "";
        field.placeholder=result.needs_sync?placeholder:"";
        field.disabled=!!blocked;copy.disabled=!!blocked;
        if(changed)onURL(result.needs_sync?"":result.url);
        return true;
      },
      resolve(requested){
        if(!latest || latest.needs_sync || !latest.url)throw new Error("Use the detected link before copying. / Usa el enlace detectado antes de copiar.");
        if(latest.reachable===false)throw new Error("Check public access before copying this link. / Comprueba el acceso público antes de copiar este enlace.");
        const path=new URL(requested).pathname;
        if(path!=="/" && !/^\/integrations\/social\/(youtube|facebook|instagram|instagram-standalone|threads|tiktok)$/.test(path))throw new Error("Choose a public or callback link. / Elige un enlace público o de redirección.");
        return latest.url.replace(/\/$/,"")+(path==="/"?"":path);
      }
    };
  }
};

// Keep everyday access separate from developer configuration and social login.
window.PostForgeNetworkGuidance={
  describe(result,lang="en"){
    const es=lang==="es",pick=(en,spanish)=>es?spanish:en;
    if(result.needs_sync)return {kind:"changed",sync:true,open:false,title:pick("A new temporary link was found","Se encontró un enlace temporal nuevo"),detail:pick("Update PostForge to use the detected link. Your social accounts are not automatically signed out. Do not request another random link.","Actualiza PostForge para usar el enlace detectado. Este cambio no cierra automáticamente las sesiones de tus redes. No pidas otro enlace aleatorio.")};
    if(!result.reachable)return {kind:"unavailable",sync:false,open:false,title:pick("Postiz’s public link could not be reached","No se pudo acceder al enlace público de Postiz"),detail:pick("Check again after confirming Docker and your internet connection are running. This does not mean your social accounts need reconnecting. Changing the link is an advanced recovery step.","Confirma que Docker esté en ejecución y que tengas internet; luego vuelve a comprobar. Esto no significa que debas reconectar tus redes. Cambiar el enlace es una medida avanzada de recuperación.")};
    return {kind:"ready",sync:false,open:true,title:pick("✓ Your Postiz link is ready","✓ Tu enlace de Postiz está listo"),detail:pick("Open Postiz or copy this link. Keep using it while it works. Reconnect a social account only when Connections asks you to; a changed link alone is not a reason to reconnect.","Abre Postiz o copia este enlace. Sigue usándolo mientras funcione. Reconecta una red solo cuando Conexiones lo indique; cambiar de enlace no exige reconectarla.")};
  },
  account(item){return item.state==="reconnect"?"reconnect":item.state==="renewal"?"renew":item.state==="paused"?"manage":"none";}
};
