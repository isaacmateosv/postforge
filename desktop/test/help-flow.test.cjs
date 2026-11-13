// SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function element(tag='div') {return {tagName:tag.toUpperCase(),textContent:'',children:[],attrs:{},hidden:false,open:false,
 append(...items){this.children.push(...items);this.lastElementChild=this.children.at(-1);},replaceChildren(){this.children=[];},
 setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,v){this[k]=v;},close(){this.open=false;}};}
function fixture(engine) {
 const nodes=new Map(),handlers={},state={language:'en'};
 const $=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};
 const context={state,$,text:(en,es)=>state.language==='es'?es:en,friendlyError:String,
  document:{createElement:element},engine,openDialog:id=>{$(id).open=true;},bind:(id,fn)=>{handlers[id]=fn;}};
 const source=fs.readFileSync(path.join(__dirname,'../ui/app.js'),'utf8');vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('let helpRequest=0;'),source.indexOf('async function loadOptions()')),context);
 return {...context,handlers};
}
test('Help opens directly and loads each bundled English/Spanish guide',async()=>{
 const calls=[];const f=fixture(async(op,payload)=>{calls.push(payload);return {markdown:fs.readFileSync(path.join(__dirname,'../../docs/help',`${payload.technical?'technical':'quick'}-${payload.language}.md`),'utf8')};});
 for(const language of ['en','es'])for(const technical of [false,true]) {
  f.state.language=language;await f.help(technical);
  assert.equal(f.$('help-dialog').open,true);assert.equal(f.$('help-body').children[0].children[0].tagName,'H1');
  assert.equal(f.$('help-feedback').textContent,'');assert.equal(f.$('help-body').attrs['aria-busy'],'false');
 }
 assert.equal(calls.length,4);
});
test('guide failure is visible in Help and retry succeeds',async()=>{
 let fails=true;const f=fixture(async()=>{if(fails)throw Error('Missing guide');return {markdown:'# Recovered'};});
 await f.help();assert.match(f.$('help-feedback').textContent,/Missing guide/);assert.equal(f.$('help-retry').hidden,false);
 fails=false;await f.handlers['help-retry']();assert.equal(f.$('help-retry').hidden,true);assert.equal(f.$('help-feedback').textContent,'');
});
test('switching guides rejects an older response; closing does not reopen Help',async()=>{
 const pending=[];const f=fixture(()=>new Promise(resolve=>pending.push(resolve)));
 const first=f.help(false),second=f.help(true);
 pending[1]({markdown:'# Technical'});await second;pending[0]({markdown:'# Old quick'});await first;
 assert.equal(f.$('help-body').children[0].children[0].textContent,'Technical');
 const third=f.help(false);f.handlers['help-close']();pending[2]({markdown:'# Closed'});await third;
 assert.equal(f.$('help-dialog').open,false);assert.equal(f.$('help-body').children.length,0);
});
