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
        const blocked=busy || result.needs_sync || !result.url;
        field.value=result.needs_sync?"":result.url || "";
        field.placeholder=result.needs_sync?placeholder:"";
        field.disabled=!!blocked;copy.disabled=!!blocked;
        if(changed)onURL(result.needs_sync?"":result.url);
        return true;
      },
      resolve(requested){
        if(!latest || latest.needs_sync || !latest.url)throw new Error("Synchronize the current URL before copying. / Sincroniza la URL actual antes de copiar.");
        const path=new URL(requested).pathname;
        if(path!=="/" && !/^\/integrations\/social\/(youtube|facebook|instagram|instagram-standalone|threads|tiktok)$/.test(path))throw new Error("Choose a public or callback link. / Elige un enlace público o de redirección.");
        return latest.url.replace(/\/$/,"")+(path==="/"?"":path);
      }
    };
  }
};
