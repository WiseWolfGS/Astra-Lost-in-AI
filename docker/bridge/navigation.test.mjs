import test from 'node:test';
import assert from 'node:assert/strict';
import {createBridge,validateAction} from './server.mjs';

test('approach and collect have bounded strict contracts',()=>{
  assert.equal(validateAction({type:'approach',x:1,y:70,z:2,timeoutTicks:200}),true);
  assert.equal(validateAction({type:'collect',entityId:5,timeoutTicks:200}),true);
  for(const change of [{entityId:-1},{entityId:1.5},{entityId:true},{entityId:2147483648},
    {timeoutTicks:201},{timeoutTicks:0},{item:'extra'}])
    assert.equal(validateAction({type:'collect',entityId:5,timeoutTicks:200,...change}),false);
});

test('navigation requires capability and preserves pickup evidence past five seconds',async t=>{
  let now=10000;
  const server=createBridge('t'.repeat(32),()=>now);
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(()=>new Promise(resolve=>server.close(resolve)));
  const base='http://127.0.0.1:'+server.address().port;
  const call=(path,body)=>fetch(base+path,{method:body?'POST':'GET',
    headers:{Authorization:'Bearer '+'t'.repeat(32),'Content-Type':'application/json'},
    body:body?JSON.stringify(body):undefined});
  const state={protocol:1,session:'nav',ready:true,busy:false,capabilities:['mine']};
  const action={type:'collect',entityId:5,timeoutTicks:200};
  await call('/v1/tick',state);
  assert.equal((await call('/v1/actions',action)).status,409);
  state.capabilities=['approach','collect'];
  await call('/v1/tick',state);
  const queued=await (await call('/v1/actions',action)).json();
  assert.deepEqual((await (await call('/v1/tick',state)).json()).command.action,action);
  for(let i=0;i<2;i++){
    now+=4000;
    await call('/v1/tick',{...state,busy:true});
  }
  assert.equal((await (await call('/v1/actions/'+queued.id)).json()).status,'running');
  const details={pickupPacketCount:1,inventoryDelta:1,verifiedCollectedCount:1};
  await call('/v1/tick',{...state,result:{id:queued.id,status:'completed',reason:'pickup_verified',details}});
  assert.deepEqual((await (await call('/v1/actions/'+queued.id)).json()).details,details);
});
