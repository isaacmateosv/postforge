// SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict');
const {patch,pmSignedMediaMatches}=require('../../patches/postiz/preserve-media.js');
const origin='https://postforge.example.test',path='/uploads/2026/11/10/synthetic_media_file_123456.mp4';
process.env.FRONTEND_URL=origin;
const signed=(expires=Math.floor(Date.now()/1000)+3600)=>origin+'/postforge-media/'+expires+'/'+'a'.repeat(64)+path;
test('a signed path for the exact same file survives normalization',()=>assert.equal(pmSignedMediaMatches(signed(),origin+path),true));
test('different files, foreign origins, expiry and extra URL fields are rejected',()=>{
 for(const [a,b] of [[signed(),origin+path.replace('123456','654321')],[signed().replace(origin,'https://foreign.example'),origin+path],
  [signed(1000000000),origin+path],[signed()+'?override=1',origin+path],[signed(),origin+path+'?x=1']])assert.equal(pmSignedMediaMatches(a,b),false);
});
test('the pinned patch is idempotent and fails on an unrecognized normalizer',()=>{
 const fixture="if (fresh?.status === 'ready' && fresh.path !== p.path) { return fresh; }";
 const result=patch(fixture);assert.match(result,/!pmSignedMediaMatches/);assert.equal(patch(result),result);
 assert.throws(()=>patch('changed upstream code'));
});
