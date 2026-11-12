// SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');
function media(){
 const nodes={};const node=id=>nodes[id]??=( {dataset:{},hidden:true,value:'',textContent:'',pause(){},load(){},removeAttribute(){},setAttribute(){},addEventListener(){},replaceChildren(){}} );
 const jobs=[],events=[];const sandbox={window:{__TAURI__:{core:{invoke:(op,data)=>new Promise((resolve,reject)=>jobs.push({op,data,resolve,reject})),convertFileSrc:x=>x}},addEventListener(){}},document:{getElementById:node,addEventListener(){},createElement:()=>({})}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../ui/media-preview.js'),'utf8'),sandbox);
 const api=sandbox.window.PostForgeMedia;api.configure({onFrame(){},onInfo(){},onCover:x=>events.push(x)});
 return {api,node,jobs,events};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
test('cover success appears only after its preview succeeds, and unchanged renders reuse it',async()=>{
 const m=media();m.api.update([], '/synthetic-cover.jpg', null,'en');assert.equal(m.node('cover-preview-box').dataset.state,'pending');assert.equal(m.events.length,0);
 m.jobs[0].resolve({image:'data:image/png;base64,synthetic',second:0});await flush();assert.equal(m.node('cover-preview-box').dataset.state,'ready');assert.match(m.node('cover-preview-status').textContent,/Cover ready/);assert.equal(m.events[0].state,'ready');
 m.api.update([], '/synthetic-cover.jpg', null,'en');assert.equal(m.jobs.length,1);
});
test('an old preview cannot confirm a replacement cover; failures are visible',async()=>{
 const m=media();m.api.update([], '/old.jpg',null,'es');m.api.update([], '/new.jpg',null,'es');m.jobs[0].resolve({image:'old',second:0});await flush();assert.equal(m.events.length,0);
 m.jobs[1].reject(new Error('Cannot preview / No se puede mostrar'));await flush();assert.equal(m.node('cover-preview-box').dataset.state,'error');assert.equal(m.node('cover-preview').hidden,true);assert.equal(m.events[0].state,'error');
 m.api.update([], '/new.jpg',null,'es');assert.equal(m.jobs.length,3);m.jobs[2].resolve({image:'new',second:0});await flush();assert.match(m.node('cover-preview-status').textContent,/Portada lista/);
});
