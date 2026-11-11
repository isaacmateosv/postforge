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
