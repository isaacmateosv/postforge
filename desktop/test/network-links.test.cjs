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
  assert.throws(()=>f.links.resolve('https://old.example.org'),/Use the detected link/);
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

test('unreachable links cannot be copied or mistaken for a healthy login',()=>{
  const f=fixture();f.links.update(status('https://down.example.org',1,{reachable:false}));
  assert.equal(f.copy.disabled,true);assert.throws(()=>f.links.resolve('https://down.example.org'),/Check public access/);
});
function guidance(){const window={};vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../ui/network-links.js'),'utf8'),{window,URL});return window.PostForgeNetworkGuidance;}
test('link guidance offers sync only for a detected change, and opens only verified links',()=>{
  for(const lang of ['en','es']){
    const guide=guidance();
    const changed=guide.describe({needs_sync:true,reachable:true},lang);assert.equal(changed.sync,true);assert.equal(changed.open,false);
    const outage=guide.describe({needs_sync:false,reachable:false},lang);assert.equal(outage.sync,false);assert.equal(outage.open,false);
    const ready=guide.describe({needs_sync:false,reachable:true},lang);assert.equal(ready.open,true);assert.equal(ready.sync,false);
    assert.match(ready.detail,lang==='es'?/no exige reconectarla/:/not a reason to reconnect/);
  }
});
test('normal access and automatic token renewal never prompt unnecessary reconnection',()=>{
  const guide=guidance();assert.equal(guide.account({state:'connected'}),'none');assert.equal(guide.account({state:'renewal'}),'renew');assert.equal(guide.account({state:'reconnect'}),'reconnect');assert.equal(guide.account({state:'paused'}),'manage');
});
test('opening Postiz routes outages and changed origins into repair instead of opening the browser',async()=>{
  const code=fs.readFileSync(require('node:path').join(__dirname,'../ui/app.js'),'utf8');
  for(const checked of [null,{reachable:false},{reachable:true,needs_sync:true},{reachable:true,needs_sync:false}]){
    const calls=[],context={state:{networkBusy:false},document:{querySelector:()=>null},networkCheck:async()=>checked,openDialog:id=>calls.push(id),invoke:async cmd=>calls.push(cmd)};
    vm.createContext(context);vm.runInContext(code.slice(code.indexOf('async function openVerifiedPostiz('),code.indexOf('async function reconnectAccount(')),context);
    await context.openVerifiedPostiz();assert.deepEqual(calls,checked?.reachable&&!checked?.needs_sync?['open_calendar']:['network-dialog']);
  }
});

test('Use detected link keeps the active provider even while advanced fields are being edited',async()=>{
  const f=applyFixture({url:'https://new.example.org',reachable:true,needs_sync:false});
  f.state.network={url:'https://old.example.org',needs_sync:true,provider:'trycloudflare'};
  f.$('network-provider').value='cloudflare';let request;
  f.context.engine=async(op,payload)=>{if(op==='network_apply')request=payload;return {};};
  await f.context.networkApply(false,true);assert.equal(request.provider,'trycloudflare');assert.equal(request.rotate,false);
});
