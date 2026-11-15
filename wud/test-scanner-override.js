/* Run via docker exec -i wud-wud-1 node < test-scanner-override.js */
'use strict';
const fs = require('fs');
const assert = require('node:assert/strict');
const scanner = fs.readFileSync('/home/node/app/dist/watchers/providers/docker/Docker.js', 'utf8');
const start = scanner.indexOf('async findNewVersion(');
const end = scanner.indexOf('\n    /**', start);
const method = scanner.slice(start, end).trim();
const sha = n => 'sha256:' + String(n).repeat(64);
const log = {debug(){},info(){},warn(){},error(){}};
function fixture(opts={}) {
  const calls=[];
  const registry={
    shouldWatchDigest:()=>true,
    getImageManifestDigest:async(image,ref)=>{
      calls.push(ref || 'candidate');
      if (!ref) {if(opts.candidateError) throw opts.candidateError; return {version:2,digest:sha(2)};}
      if(opts.historicalAvailable) return {digest:sha(1)};
      throw Object.assign(new Error('historical manifest missing'),{response:{status:opts.status || 404}});
    },
    callRegistry:async()=>{if(opts.manifestFailure)throw new Error('candidate unavailable');return {config:{digest:opts.invalidConfig?'invalid':opts.sameConfig?sha(3):sha(4)}};},
    getImageConfig:async()=>({created:'2026-11-12T01:27:10.886Z'})
  };
  const object=new Function('getRegistry','getTagCandidates','label_1','storeContainer',`return ({${method}});`)(()=>registry,()=>[],{wudWatchDigest:'wud.watch.digest'},{getContainer:()=>undefined});
  object.configuration={watchdigestdefault:true};object.log=log;
  object.dockerApi={getImage:()=>({inspect:async()=>({Id:opts.wrongLocal?sha(9):sha(3)})})};
  const c={id:'fixture',labels:{},image:{id:sha(3),registry:{name:opts.otherRegistry?'hub.public':'ghcr.public',url:'https://ghcr.io/v2'},name:opts.otherImage?'other/image':'berriai/litellm',tag:{value:'main-stable',semver:false},digest:{watch:true,repo:sha(1),value:sha(5)}}};
  return {object,c,calls};
}
async function run() {
 let count=0;
 for(const opts of [{},{sameConfig:true},{historicalAvailable:true}]) {
  const f=fixture(opts),r=await f.object.findNewVersion(f.c,log);
  assert.equal(r.digest,sha(2));assert.equal(f.c.image.digest.value,opts.sameConfig?sha(2):sha(1));count++;
 }
 for(const opts of [{status:401},{status:403},{status:429},{status:500},{otherRegistry:true},{otherImage:true},{candidateError:new Error('candidate 404')},{manifestFailure:true},{invalidConfig:true},{wrongLocal:true}]) {
  const f=fixture(opts);await assert.rejects(()=>f.object.findNewVersion(f.c,log));count++;
 }
 const {validate}=require('/home/node/app/dist/model/container.js');
 const base={id:'test',name:'test',watcher:'vm',delay:'48h',image:{id:sha(3),registry:{name:'ghcr.public',url:'https://ghcr.io/v2'},name:'berriai/litellm',tag:{value:'main-stable'},digest:{watch:true,value:sha(1)},architecture:'amd64',os:'linux'},result:{tag:'main-stable',digest:sha(2),created:'2026-11-12T00:00:00.000Z'}};
 const created=Date.parse(base.result.created),now=Date.now;
 try {
  for(const [age,cooling,available] of [[0,true,false],[48*3600000-1,true,false],[48*3600000,false,true],[49*3600000,false,true]]) {
   Date.now=()=>created+age;const c=validate(JSON.parse(JSON.stringify(base)));
   assert.equal(c.isCoolingDown,cooling);assert.equal(c.updateAvailable,available);assert.equal(c.coolingDownUntil,created+48*3600000);count++;
  }
  const missing=JSON.parse(JSON.stringify(base));delete missing.result.created;const c=validate(missing);assert.equal(c.isCoolingDown,false);assert.equal(c.updateAvailable,true);count++;
  // Invalid timestamps are rejected by validation. Persisted corruption can bypass validation;
  // the actual getter must still be documented as fail-open for invalid created values.
  const invalid=validate(JSON.parse(JSON.stringify(base)));invalid.result.created='invalid';assert.equal(invalid.isCoolingDown,false);assert.equal(invalid.updateAvailable,true);count++;
  const unchanged=JSON.parse(JSON.stringify(base));unchanged.result.digest=sha(1);Date.now=()=>created;assert.equal(validate(unchanged).isCoolingDown,false);count++;
 } finally {Date.now=now;}
 console.log(JSON.stringify({testsPassed:count,registryCases:13,cooldownCases:7,candidateTimestamp:base.result.created}));
}
run().catch(e=>{console.error(e);process.exitCode=1;});
