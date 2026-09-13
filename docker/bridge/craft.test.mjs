import test from 'node:test';
import assert from 'node:assert/strict';
import {createBridge,validateAction} from './server.mjs';
test('craft recipe allowlist is bounded to a single request',()=>{
  assert.equal(validateAction({type:'craft',recipe:'crafting_table'}),true);
  assert.equal(validateAction({type:'craft',recipe:'diamond_sword'}),false);
  assert.equal(validateAction({type:'craft',recipe:'stick',count:64}),false);
});
test('craft requires capability and keeps its longer execution deadline',async t=>{
  let clock=1000;
  const server=createBridge('t'.repeat(32),()=>clock);
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  t.after(()=>new Promise(r=>server.close(r)));
  const call=(p,b)=>fetch('http://127.0.0.1:'+server.address().port+p,{method:b?'POST':'GET',
    headers:{Authorization:'Bearer '+'t'.repeat(32),'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});
  const state={protocol:1,session:'craft',ready:true,busy:false};
  await call('/v1/tick',state);
  assert.equal((await call('/v1/actions',{type:'craft',recipe:'stick'})).status,409);
  state.capabilities=['craft','cancel'];
  await call('/v1/tick',state);
  const action=await (await call('/v1/actions',{type:'craft',recipe:'stick'})).json();
  await call('/v1/tick',state);
  for(let i=0;i<3;i++){clock+=3000;await call('/v1/tick',{...state,busy:true});}
  assert.equal((await (await call('/v1/actions/'+action.id)).json()).status,'running');
  await call('/v1/actions/'+action.id+'/cancel',{});
  const cancel=await (await call('/v1/tick',{...state,busy:true})).json();
  assert.equal(cancel.cancel.id,action.id);
  await call('/v1/tick',{...state,result:{id:action.id,status:'cancelled',details:{inputsReleased:true,pendingChangesPossible:true}}});
  const result=await (await call('/v1/actions/'+action.id)).json();
  assert.equal(result.cancelConfirmed,true);
  assert.equal(result.details.pendingChangesPossible,true);
});
