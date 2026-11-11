// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
// Preserve a gateway link only when it points to the exact same normalized file.
const fs=require('node:fs');
function pmSignedMediaMatches(supplied,current) {
  try {
    const base=new URL(process.env.FRONTEND_URL),a=new URL(supplied),b=new URL(current);
    const match=a.pathname.match(/^\/postforge-media\/([0-9]{10})\/[a-f0-9]{64}(\/uploads\/[0-9]{4}\/[0-9]{2}\/[0-9]{2}\/[A-Za-z0-9_-]{20,100}\.(?:mp4|jpe?g|png|webp))$/);
    const now=Math.floor(Date.now()/1000);
    return !!(match && a.origin===base.origin && b.origin===base.origin && !a.username && !a.password && !a.search && !a.hash &&
      b.pathname===match[2] && !b.search && !b.hash && Number(match[1])>now && Number(match[1])-now<=32*86400);
  }catch{return false;}
}
function patch(source) {
  if(source.includes('function pmSignedMediaMatches('))return source;
  const old="fresh?.status === 'ready' && fresh.path !== p.path";
  if(!source.includes(old))throw new Error('Pinned Postiz media normalizer changed; signed-media patch was not applied.');
  return source.replace(old,old+' && !pmSignedMediaMatches(p.path, fresh.path)')+'\n'+pmSignedMediaMatches.toString()+'\n';
}
if(require.main===module){
  for(const app of ['backend','orchestrator']){
    const file='/app/apps/'+app+'/dist/libraries/nestjs-libraries/src/database/prisma/posts/posts.service.js';
    fs.writeFileSync(file,patch(fs.readFileSync(file,'utf8')));
  }
  console.log('[pm-patch] signed media: preserving file-scoped gateway paths');
}
module.exports={patch,pmSignedMediaMatches};
