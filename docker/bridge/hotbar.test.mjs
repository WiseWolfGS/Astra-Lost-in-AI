import test from 'node:test';
import assert from 'node:assert/strict';
import {createBridge,validateAction} from './server.mjs';

test('hotbar selection accepts only bounded slots and explicit item ids',()=>{
  const action={type:'select_hotbar',slot:0,expectedItem:'minecraft:air'};
  assert.equal(validateAction(action),true);
  assert.equal(validateAction({...action,slot:8}),true);
  for(const slot of [-1,9,true,'0',1.5]) assert.equal(validateAction({...action,slot}),false);
  for(const expectedItem of ['',null,'air','minecraft:bad item','a:'.padEnd(129,'b')])
    assert.equal(validateAction({...action,expectedItem}),false);
  assert.equal(validateAction({...action,extra:1}),false);
});

test('legacy capability blocks hotbar action and feedback remains client evidence',async t=>{
  const server=createBridge('t'.repeat(32));
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(()=>new Promise(resolve=>server.close(resolve)));
  const base='http://127.0.0.1:'+server.address().port;
  const call=(path,body)=>fetch(base+path,{method:body?'POST':'GET',
    headers:{Authorization:'Bearer '+'t'.repeat(32),'Content-Type':'application/json'},
    body:body?JSON.stringify(body):undefined});
  const state={protocol:1,session:'hotbar-test',ready:true,busy:false};
  const action={type:'select_hotbar',slot:8,expectedItem:'minecraft:air'};
  await call('/v1/tick',state);
  assert.equal((await call('/v1/actions',action)).status,409);
  state.capabilities=['select_hotbar'];
  await call('/v1/tick',state);
  const queued=await (await call('/v1/actions',action)).json();
  const dispatch=await (await call('/v1/tick',state)).json();
  assert.deepEqual(dispatch.command.action,action);
  await call('/v1/tick',{...state,result:{id:queued.id,status:'completed',reason:'hotbar_selected',
    details:{selectedSlot:8,packetSent:true,serverConfirmed:false,verification:'client_selection'}}});
  const result=await (await call('/v1/actions/'+queued.id)).json();
  assert.equal(result.reason,'hotbar_selected');
  assert.equal(result.details.serverConfirmed,false);
});
