import test from 'node:test';
import assert from 'node:assert/strict';
import {createBridge,validateAction} from './server.mjs';

const mine = {type:'mine',x:1,y:70,z:2,timeoutTicks:200};
async function setup(t, capabilities=['mine']) {
  let now=10000;
  const server=createBridge('t'.repeat(32),()=>now);
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(()=>new Promise(resolve=>server.close(resolve)));
  const base='http://127.0.0.1:'+server.address().port;
  const call=(path,body)=>fetch(base+path,{method:body?'POST':'GET',
    headers:{Authorization:'Bearer '+'t'.repeat(32),'Content-Type':'application/json'},
    body:body?JSON.stringify(body):undefined});
  const state={protocol:1,session:'mining-world',ready:true,busy:false,capabilities};
  await call('/v1/tick',state);
  return {call,state,advance(ms){now+=ms;}};
}

test('mining coordinates, budgets and properties are bounded',()=>{
  assert.equal(validateAction(mine),true);
  for(const update of [{x:1.5},{x:true},{x:30000000},{y:320},{y:-65},{timeoutTicks:19},
    {timeoutTicks:201},{timeoutTicks:40.5},{unexpected:true}])
    assert.equal(validateAction({...mine,...update}),false);
});

test('old clients cannot receive mining commands',async t=>{
  const {call}=await setup(t,[]);
  assert.equal((await call('/v1/actions',mine)).status,409);
});

test('mining survives the old five second limit but has a hard deadline',async t=>{
  const {call,state,advance}=await setup(t);
  const {id}=await (await call('/v1/actions',mine)).json();
  assert.equal((await (await call('/v1/tick',state)).json()).command.id,id);
  for(let i=0;i<3;i++){
    advance(4000);
    const response=await (await call('/v1/tick',{...state,busy:true,
      activeAction:{id,type:'mine',phase:'breaking',elapsedTicks:(i+1)*40}})).json();
    assert.deepEqual(response,{});
    assert.equal((await (await call('/v1/actions/'+id)).json()).status,'running');
  }
  advance(2001);
  assert.equal((await (await call('/v1/actions/'+id)).json()).status,'expired');
});

test('terminal mining evidence survives transport without implying item collection',async t=>{
  const {call,state}=await setup(t);
  const {id}=await (await call('/v1/actions',mine)).json();
  await call('/v1/tick',state);
  const details={blockChanged:true,inventoryDelta:{},collectionGuaranteed:false};
  await call('/v1/tick',{...state,result:{id,status:'completed',reason:'block_change_observed',details}});
  assert.deepEqual(await (await call('/v1/actions/'+id)).json(),
    {id,status:'completed',reason:'block_change_observed',details});
});

test('client timeout is terminal and disconnected mining expires promptly',async t=>{
  const {call,state,advance}=await setup(t);
  const first=await (await call('/v1/actions',mine)).json();
  await call('/v1/tick',state);
  await call('/v1/tick',{...state,result:{id:first.id,status:'timed_out',reason:'tick_timeout'}});
  assert.equal((await (await call('/v1/actions/'+first.id)).json()).status,'timed_out');
  const second=await (await call('/v1/actions',mine)).json();
  await call('/v1/tick',state);
  advance(5001);
  assert.equal((await (await call('/v1/actions/'+second.id)).json()).status,'expired');
});
