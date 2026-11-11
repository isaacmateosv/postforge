// SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function fixture() {
  const pending=[];
  const items=['settings','backup','confirm'].map(id=>({id,open:false,hidden:true,attributes:{},
    setAttribute(key,value){this.attributes[key]=value;},
    removeAttribute(key){delete this.attributes[key];},
    addEventListener(name,fn){this[name]=fn;},
    showModal(){this.open=true;},
    closeDialog(){this.open=false;pending.push(()=>this.close());}}));
  const order=[...items];
  const document={getElementById:id=>items.find(item=>item.id===id),querySelectorAll:()=>items,
    body:{prepend(item){order.splice(order.indexOf(item),1);order.unshift(item);}}};
  const window={};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../ui/dialogs.js'),'utf8'),{document,window});
  return {items,order,open:window.PostForgeDialogs.open,flush(){while(pending.length)pending.shift()();}};
}
test('the open dialog is visible and is the only accessible modal',()=>{
  const f=fixture();f.open('settings');
  assert.equal(f.items[0].hidden,false);
  assert.equal(f.items[0].attributes['aria-modal'],'true');
  assert.equal(f.items[1].attributes['aria-modal'],undefined);
});
test('Settings to Backup hides the closed dialog and exposes the new one',()=>{
  const f=fixture();f.open('settings');f.items[0].closeDialog();f.flush();f.open('backup');
  assert.equal(f.items[0].hidden,true);
  assert.equal(f.items[0].attributes['aria-modal'],undefined);
  assert.equal(f.items[1].hidden,false);
  assert.equal(f.items[1].attributes['aria-modal'],'true');
  assert.equal(f.order[0].id,'backup');
});
test('closing a nested confirmation restores modal accessibility to its parent',()=>{
  const f=fixture();f.open('backup');f.open('confirm');
  assert.equal(f.items[1].attributes['aria-modal'],undefined);
  f.items[2].closeDialog();f.flush();
  assert.equal(f.items[2].hidden,true);
  assert.equal(f.items[1].attributes['aria-modal'],'true');
});
test('a delayed close event cannot hide a reopened confirmation',()=>{
  const f=fixture();f.open('confirm');f.items[2].closeDialog();f.open('confirm');f.flush();
  assert.equal(f.items[2].open,true);
  assert.equal(f.items[2].hidden,false);
  assert.equal(f.items[2].attributes['aria-modal'],'true');
  f.items[2].closeDialog();f.flush();
  assert.equal(f.items[2].hidden,true);
});
