import test from 'node:test';
import assert from 'node:assert/strict';
import {createBridge} from './server.mjs';

async function setup(t, capabilities=['mine','cancel']) {
  let clock=10000;
  const token='t'.repeat(32), server=createBridge(token,()=>clock);
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(()=>new Promise(resolve=>server.close(resolve)));
  const base='http://127.0.0.1:'+server.address().port;
  const call=(path,body,auth=true)=>fetch(base+path,{method:body===undefined?'GET':'POST',
    headers:{'Content-Type':'application/json',...(auth?{Authorization:'Bearer '+token}:{})},
    body:body===undefined?undefined:JSON.stringify(body)});
  const state={protocol:1,session:'world',ready:true,busy:false,capabilities};
  await call('/v1/tick',state);
  const queue=async()=> (await call('/v1/actions',{type:'mine',x:1,y:70,z:2,timeoutTicks:200})).json();
  const get=async id=> (await call('/v1/actions/'+id)).json();
  const cancel=async id=>call('/v1/actions/'+id+'/cancel',{});
  return {call,state,queue,get,cancel,advance(ms){clock+=ms;}};
}

test('queued cancellation removes action and retries cannot cancel its successor',async t=>{
  const {call,state,queue,cancel,get}=await setup(t);
  const {id}=await queue();
  assert.equal((await cancel(id)).status,200);
  assert.equal((await get(id)).confirmation,'never_dispatched');
  assert.equal((await get(id)).cancelConfirmed,true);
  assert.deepEqual(await (await call('/v1/tick',state)).json(),{});
  const next=await queue();
  await cancel(id);
  assert.equal((await (await call('/v1/tick',state)).json()).command.id,next.id);
});

test('running cancel bypasses busy queue, repeats until client confirms input release',async t=>{
  const {call,state,queue,cancel,get}=await setup(t);
  const {id}=await queue();
  await call('/v1/tick',state);
  const busy={...state,busy:true,activeAction:{id,type:'mine'}};
  await call('/v1/tick',busy);
  assert.equal((await cancel(id)).status,202);
  assert.equal((await get(id)).status,'cancelling');
  assert.equal((await get(id)).cancelConfirmed,false);
  for(let i=0;i<2;i++) assert.deepEqual(await (await call('/v1/tick',busy)).json(),{cancel:{id,session:'world'}});
  assert.equal((await call('/v1/actions',{type:'stop'})).status,409);
  await call('/v1/tick',{...state,result:{id,status:'cancelled',reason:'cancel_requested',details:{inputsReleased:true}}});
  assert.equal((await get(id)).cancelConfirmed,true);
  assert.equal((await get(id)).status,'cancelled');
});

test('unready or forged unrelated feedback is not cancellation confirmation',async t=>{
  const {call,state,queue,cancel,get}=await setup(t);
  const {id}=await queue(); await call('/v1/tick',state); await cancel(id);
  await call('/v1/tick',{...state,ready:false,busy:true,result:{id:'unrelated',status:'cancelled',details:{inputsReleased:true}}});
  assert.equal((await get(id)).status,'cancelling');
  await call('/v1/tick',{...state,result:{id,status:'cancelled'}});
  assert.equal((await get(id)).cancelConfirmed,false);
});

test('completion winning the race remains completed',async t=>{
  const {call,state,queue,cancel,get}=await setup(t);
  const {id}=await queue(); await call('/v1/tick',state); await cancel(id);
  await call('/v1/tick',{...state,result:{id,status:'completed',reason:'block_change_observed'}});
  assert.equal((await get(id)).status,'completed');
  assert.equal((await get(id)).cancelConfirmed,false);
  assert.equal((await (await cancel(id)).json()).status,'completed');
});

test('repeated cancellation cannot extend deadline or claim success on disconnect',async t=>{
  const {call,state,queue,cancel,get,advance}=await setup(t);
  const {id}=await queue(); await call('/v1/tick',state); await cancel(id);
  advance(4000); await call('/v1/tick',{...state,busy:true}); await cancel(id);
  advance(1001);
  assert.equal((await get(id)).reason,'cancel_ack_timeout');
  assert.equal((await get(id)).cancelConfirmed,false);
  assert.deepEqual(await (await call('/v1/tick',{...state,session:'new-world'})).json(),{error:'another client is connected'});
});

test('late feedback after expiry cannot overwrite the terminal result',async t=>{
  const {call,state,queue,cancel,get,advance}=await setup(t);
  const {id}=await queue(); await call('/v1/tick',state); await cancel(id); advance(5001);
  await call('/v1/tick',{...state,result:{id,status:'cancelled',details:{inputsReleased:true}}});
  assert.equal((await get(id)).status,'expired');
  assert.equal((await get(id)).cancelConfirmed,false);
});

test('legacy client fails explicitly for running cancel but queued cancel still works',async t=>{
  const {call,state,queue,cancel}=await setup(t,['mine']);
  const first=await queue(); assert.equal((await cancel(first.id)).status,200);
  const next=await queue(); await call('/v1/tick',state);
  assert.equal((await cancel(next.id)).status,409);
});

test('cancellation requires auth, known id and empty body',async t=>{
  const {call,queue}=await setup(t); const {id}=await queue();
  assert.equal((await call('/v1/actions/'+id+'/cancel',{},false)).status,401);
  assert.equal((await call('/v1/actions/'+id+'/cancel',{all:true})).status,400);
  assert.equal((await call('/v1/actions/00000000-0000-0000-0000-000000000000/cancel',{})).status,404);
});
