// SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(){
  const window={};vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../ui/network-links.js'),'utf8'),{window,URL});
  const field={},copy={},origins=[];
  return {field,copy,origins,links:window.PostForgeNetworkLinks.create({field,copy,onURL:url=>origins.push(url)})};
}
const status=(url,checked_at,extra={})=>({url,checked_at,needs_sync:false,...extra});
test('a changed backend URL refreshes the field and callback origin together',()=>{
  const f=fixture();f.links.update(status('https://old.example.org',1));f.links.update(status('https://current.example.org',2));
  assert.equal(f.field.value,'https://current.example.org');assert.equal(f.origins.at(-1),'https://current.example.org');assert.equal(f.copy.disabled,false);
  assert.equal(f.links.resolve('https://old.example.org'),'https://current.example.org');
  assert.equal(f.links.resolve('https://old.example.org/integrations/social/youtube'),'https://current.example.org/integrations/social/youtube');
});
test('an older response cannot replace a newer URL',()=>{
  const f=fixture();f.links.update(status('https://current.example.org',2));
  assert.equal(f.links.update(status('https://old.example.org',1)),false);assert.equal(f.field.value,'https://current.example.org');
});
test('a restarted connector requiring synchronization cannot expose stale copy links',()=>{
  const f=fixture();f.links.update(status('https://old.example.org',1));f.links.update(status('https://old.example.org',2,{needs_sync:true,discovered_url:'https://new.example.org'}));
  assert.equal(f.field.value,'');assert.equal(f.copy.disabled,true);assert.equal(f.field.disabled,true);assert.equal(f.origins.at(-1),'');
  assert.throws(()=>f.links.resolve('https://old.example.org'),/Synchronize/);
});
test('unchanged polling preserves callback focus while a language change refreshes labels',()=>{
  const f=fixture();f.links.update(status('https://current.example.org',1),{lang:'en'});f.links.update(status('https://current.example.org',2),{lang:'en'});
  assert.equal(f.origins.length,1);f.links.update(status('https://current.example.org',3),{lang:'es'});assert.equal(f.origins.length,2);
});

function applyFixture(checked){
  const code=fs.readFileSync(require('node:path').join(__dirname,'../ui/app.js'),'utf8'),nodes=new Map();
  const $=id=>{if(!nodes.has(id))nodes.set(id,{value:'trycloudflare',textContent:'',disabled:false});return nodes.get(id);};
  const review={plan:{public_origin:'https://old.example.org'},caption:'Keep my edits'};
  const state={history:[review],selected:0,network:{url:'https://old.example.org'}};
  const context={state,$,current:()=>state.history[0],text:en=>en,modal:async()=>true,engine:async()=>({}),networkCheck:async()=>{state.network=checked;return checked;},networkCallbacks(){},friendlyError:String,document:{querySelectorAll:()=>[]},networkLinkView:{update(){}}};
  vm.createContext(context);
  vm.runInContext(code.slice(code.indexOf('function reviewNeedsNetworkRefresh('),code.indexOf('function updateVersionControls(')),context);
  vm.runInContext(code.slice(code.indexOf('async function networkApply('),code.indexOf('bind("network-open"')),context);
  return {context,state,review,$};
}
test('synchronization keeps caption history and requires a fresh review for a changed origin',async()=>{
  const f=applyFixture({url:'https://new.example.org',reachable:true,needs_sync:false});await f.context.networkApply();
  assert.equal(f.state.history[0],f.review);assert.equal(f.review.caption,'Keep my edits');
  assert.match(f.$('network-result').textContent,/caption is kept.*fresh review/);
  assert.equal(f.context.reviewNeedsNetworkRefresh(f.review.plan,f.state.network),true);
});
test('apply never claims public verification when the follow-up check fails or still needs sync',async()=>{
  for(const checked of [null,{reachable:false},{reachable:true,needs_sync:true}]){
    const f=applyFixture(checked);await f.context.networkApply();assert.doesNotMatch(f.$('network-result').textContent,/✓ Public access verified/);
  }
});
