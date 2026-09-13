import test from 'node:test';
import assert from 'node:assert/strict';
import {createBridge,validateAction} from './server.mjs';
test('workbench tools and coordinates are bounded',()=>{
  const a={type:'craft_workbench',recipe:'wooden_pickaxe',x:0,y:64,z:0};
  assert.equal(validateAction(a),true);
  for(const recipe of ['stone_pickaxe','stone_axe','stone_sword','stone_shovel','stone_hoe']) assert.equal(validateAction({...a,recipe}),true);
  for(const c of [{recipe:'diamond_pickaxe'},{x:true},{y:320},{count:4}]) assert.equal(validateAction({...a,...c}),false);
});
test('workbench execution outlives opening but has a fixed deadline',async t=>{
  let now=1000;const server=createBridge('t'.repeat(32),()=>now);
  await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(()=>new Promise(r=>server.close(r)));
  const call=(p,b)=>fetch('http://127.0.0.1:'+server.address().port+p,{method:b?'POST':'GET',headers:{Authorization:'Bearer '+'t'.repeat(32),'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});
  const state={protocol:1,session:'workbench',ready:true,busy:false};
  const action={type:'craft_workbench',recipe:'wooden_pickaxe',x:0,y:64,z:0};
  await call('/v1/tick',state);assert.equal((await call('/v1/actions',action)).status,409);
  state.capabilities=['craft_workbench'];await call('/v1/tick',state);
  assert.equal((await call('/v1/actions',{...action,recipe:'stone_pickaxe'})).status,409);
  state.capabilities.push('stone_tools');await call('/v1/tick',state);
  action.recipe='stone_pickaxe';
  const queued=await (await call('/v1/actions',action)).json();await call('/v1/tick',state);
  for(let i=0;i<5;i++){now+=3000;await call('/v1/tick',{...state,busy:true});}
  assert.equal((await (await call('/v1/actions/'+queued.id)).json()).status,'running');
  now+=3100;assert.equal((await (await call('/v1/actions/'+queued.id)).json()).status,'expired');
});
