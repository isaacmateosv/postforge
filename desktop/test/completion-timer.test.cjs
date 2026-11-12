// SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test');const assert=require('node:assert/strict');
const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');
function timer(){
 const sandbox={window:{}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../ui/completion-timer.js'),'utf8'),sandbox);
 let tick,done=0,active=true,handle=0,cleared=0;const counts=[];
 const api=sandbox.window.PostForgeCompletionTimer.create({onTick:n=>counts.push(n),onDone:()=>done++,isActive:()=>active,schedule:fn=>{tick=fn;return ++handle;},cancel:()=>{tick=null;cleared++;}});
 return {api,counts,step(){tick?.();},pause(){active=false;},resume(){active=true;},get done(){return done;},get cleared(){return cleared;}};
}
test('returns once after eight visible active seconds',()=>{const t=timer();t.api.start();for(let i=0;i<8;i++)t.step();assert.equal(t.done,1);t.step();assert.equal(t.done,1);assert.deepEqual(t.counts,[8,7,6,5,4,3,2,1,0]);});
test('does not navigate while hidden or a dialog is open',()=>{const t=timer();t.api.start(2);t.pause();for(let i=0;i<20;i++)t.step();assert.equal(t.done,0);assert.deepEqual(t.counts,[2]);t.resume();t.step();t.step();assert.equal(t.done,1);});
test('interaction cancellation and restarting cannot leave a second timer',()=>{const t=timer();t.api.start(2);t.api.stop();t.step();assert.equal(t.done,0);t.api.start(3);t.step();t.api.start(1);assert.equal(t.cleared,2);t.step();assert.equal(t.done,1);});
test('pausing removes background wakeups and stop prevents later resume',()=>{const t=timer();t.api.start(2);t.step();t.api.pause();t.step();assert.equal(t.done,0);t.api.resume();t.step();assert.equal(t.done,1);t.api.resume();t.step();assert.equal(t.done,1);});
