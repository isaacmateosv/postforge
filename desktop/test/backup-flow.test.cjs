// SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function fixture({failure=false}={}) {
  const elements=new Map(),handlers={},calls=[],state={language:'en'},focus=[];
  const $=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',hidden:false,dataset:{},checked:false,attrs:{},
    setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,f){this[k]=f;},focus(){focus.push(id);},close(){}});return elements.get(id);};
  const context={state,$,window:{},text:(en,es)=>state.language==='es'?es:en,openDialog(){},updateTray(){},
    friendlyError:String,fromSettings:fn=>fn(),checkUpdates(){},modal:async()=>true,
    bind:(id,fn)=>{handlers[id]=fn;},document:{querySelectorAll:()=>[...elements.values()]},
    setTimeout:fn=>fn(),invoke:async(command,args)=>{calls.push({command,args});return '/private/test.pfbackup';},
    engine:async(operation,payload)=>{calls.push({operation,payload});
      if(operation==='backup_start')return {id:'a'.repeat(32)};
      if(failure)return {state:'error',error:'Wrong passphrase or damaged backup.'};
      return {state:'done',percent:100,result:{fingerprint:'b'.repeat(64),rows:224,media_files:72,gateway:true,telegram:true}};
    }};
  const source=fs.readFileSync(path.join(__dirname,'../ui/app.js'),'utf8');
  vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function backupSetMode('),source.indexOf('if (window.__TAURI__?.event) {',source.indexOf('function backupSetMode('))),context);
  return {...context,handlers,calls,focus};
}
test('Restore opens a file workflow and clears misleading export success',()=>{
  const f=fixture();f.$('backup-stage').textContent='Complete';f.$('backup-result').textContent='Old backup';f.state.backupPath='/old/folder';
  f.handlers['backup-import-open']();
  assert.equal(f.$('backup-mode').value,'inspect');assert.equal(f.state.backupPath,null);
  assert.equal(f.$('backup-result').textContent,'');assert.equal(f.$('backup-stage').textContent,'');
  assert.equal(f.$('backup-pick').textContent,'Choose backup file');assert.equal(f.$('backup-confirm-row').hidden,true);
  assert.equal(f.$('backup-inspect-mode').attrs['aria-pressed'],'true');
});
test('backup selection picks a file and Enter inspects without restoring',async()=>{
  const f=fixture();f.backupSetMode('inspect');await f.handlers['backup-pick']();
  assert.equal(f.calls[0].command,'backup_location');assert.equal(f.calls[0].args.restore,true);
  assert.equal(f.focus.at(-1),'backup-password');f.$('backup-password').value='test passphrase';
  f.$('backup-password').keydown({key:'Enter',preventDefault(){}});
  // Let the async polling continuation finish.
  for(let i=0;i<12;i++)await Promise.resolve();
  const request=f.calls.find(call=>call.operation==='backup_start');
  assert.equal(request.payload.action,'inspect');assert.equal(request.payload.file,'/private/test.pfbackup');
  assert.equal(f.$('backup-restore').hidden,false);assert.ok(f.$('backup-result').textContent.includes('224'));
  assert.equal(f.calls.filter(call=>call.payload?.action==='restore').length,0);
});
test('wrong passphrase is visible and controls recover for retry',async()=>{
  const f=fixture({failure:true});f.backupSetMode('inspect');f.state.backupPath='/private/test.pfbackup';f.$('backup-password').value='test passphrase';
  await f.backupRun('inspect');
  assert.match(f.$('backup-stage').textContent,/Wrong passphrase/);assert.equal(f.$('backup-stage').dataset.error,'true');
  assert.equal(f.$('backup-progress').hidden,true);assert.equal(f.state.backupBusy,false);assert.equal(f.$('backup-start').disabled,false);
});
test('export uses a folder, moves Enter to confirmation and ignores repeated submission',async()=>{
  const f=fixture();f.backupSetMode('export');await f.handlers['backup-pick']();
  assert.equal(f.calls[0].args.restore,false);f.$('backup-password').keydown({key:'Enter',preventDefault(){}});
  assert.equal(f.focus.at(-1),'backup-confirm');assert.equal(f.calls.filter(call=>call.operation==='backup_start').length,0);
  f.state.backupBusy=true;f.handlers['backup-inspect-mode']();assert.equal(f.$('backup-mode').value,'export');
  await f.backupRun('export');assert.equal(f.calls.filter(call=>call.operation==='backup_start').length,0);
});
test('restore cannot start before inspection and the old-host confirmation',async()=>{
  const f=fixture();f.backupSetMode('inspect');f.state.backupPath='/private/test.pfbackup';f.$('backup-password').value='test passphrase';
  await f.backupRun('restore');assert.equal(f.calls.length,0);assert.match(f.$('backup-stage').textContent,/previous host/);
});
