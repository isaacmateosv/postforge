// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
// Backport the reply-button wire-format correction described in Evolution 2.4:
// https://github.com/evolution-foundation/evolution-api/releases
// Keep the pinned 2.3.7 service, status sender, database and linked session unchanged.
// Run AFTER status-receipts.js, which restores the image original at each boot.
const fs=require('fs');
const MARK='/*pm-interactive-replies*/';
function patch(source){
  if(source.includes(MARK))return source;
  const start=source.indexOf('async sendMessage('), end=source.indexOf('async sendMessageWithTyping(',start);
  if(start<0 || end<start)throw new Error('Unsupported Evolution sendMessage implementation');
  let body=source.slice(start,end);
  const anchor=/(\w+)\.viewOnceMessage\)\{(?=(?:let|const|var) \w+=\(0,\w+\.generateWAMessageFromContent\))/g;
  const matches=[...body.matchAll(anchor)];
  const relay=/this\.client\.relayMessage\((\w+),(\w+),\{messageId:(\w+)\}\)/g;
  const relays=[...body.matchAll(relay)];
  if(matches.length!==1 || relays.length!==1 || matches[0][1]!==relays[0][2])throw new Error('Unrecognized Evolution reply relay');
  const message=matches[0][1];
  // Scope the change to native reply controls; media, PIX, calls and status sends stay intact.
  body=body.replace(anchor,original=>original+MARK+
    `const pmFlow=${message}.viewOnceMessage?.message?.interactiveMessage;`+
    `if(pmFlow?.nativeFlowMessage?.buttons?.length&&pmFlow.nativeFlowMessage.buttons.every(pmButton=>pmButton.name==="quick_reply")){${message}={interactiveMessage:pmFlow};}`);
  body=body.replace(relay,(_whole,to,msg,id)=>
    `this.client.relayMessage(${to},${msg},{messageId:${id},...(${msg}.interactiveMessage?{additionalNodes:[{tag:"biz",attrs:{},content:[{tag:"interactive",attrs:{type:"native_flow",v:"1"},content:[{tag:"native_flow",attrs:{v:"9",name:"mixed"}}]}]}]}:{})})`);
  return source.slice(0,start)+body+source.slice(end);
}
if(require.main===module){
  const file=process.env.PM_INTERACTIVE_PATCH_FILE || '/evolution/dist/main.js';
  try{const original=fs.readFileSync(file,'utf8'),result=patch(original);if(result!==original)fs.writeFileSync(file,result);console.log('pm-interactive-replies: ready');}
  catch(error){console.warn('pm-interactive-replies: skipped; unsupported provider format. Text commands remain available.');}
}
module.exports={patch};
