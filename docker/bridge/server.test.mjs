import test from 'node:test';
import assert from 'node:assert/strict';
import {createBridge, validateAction} from './server.mjs';

test('action bounds and extra fields are rejected', () => {
  assert.equal(validateAction({type:'move',direction:'forward',ticks:20}),true);
  for (const a of [
    {type:'move',direction:'forward',ticks:21},
    {type:'move',direction:'forward',ticks:0},
    {type:'look',yaw:0,pitch:91},
    {type:'stop',code:'arbitrary'},
    {type:'command',command:'/gamemode creative'},
  ]) assert.equal(validateAction(a),false);
});

test('authentication, readiness, at-most-once dispatch and feedback', async t => {
  const token = 't'.repeat(32);
  const server = createBridge(token);
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = 'http://127.0.0.1:' + server.address().port;
  async function call(path, body, auth=true) {
    return fetch(base + path, {method:body ? 'POST':'GET',
      headers:auth ? {Authorization:'Bearer ' + token, 'Content-Type':'application/json'}:{},
      body:body ? JSON.stringify(body):undefined});
  }
  assert.equal((await call('/v1/observation',null,false)).status,401);
  assert.equal((await call('/v1/actions',{type:'stop'})).status,409);
  const observation = {protocol:1,session:'test-world',ready:true,busy:false,
    environment:{schema:1,available:true,terrain:{
      origin:[-4,62,-4],size:[9,6,9],order:'y,z,x',
      palette:[{id:'minecraft:air',air:true,collision:false,fluid:'empty',potentialHazard:false}],
      cells:Array(486).fill(0)},entities:[],target:{type:'miss'}}};
  await call('/v1/tick',observation);
  assert.deepEqual((await (await call('/v1/observation')).json()).observation.environment,observation.environment);
  assert.equal((await call('/v1/tick',{...observation,session:'other'})).status,409);
  const queued = await (await call('/v1/actions',{type:'move',direction:'forward',ticks:2})).json();
  assert.equal(queued.status,'queued');
  assert.equal((await call('/v1/actions',{type:'stop'})).status,409);
  const dispatch = await (await call('/v1/tick',observation)).json();
  assert.equal(dispatch.command.id,queued.id);
  assert.deepEqual(await (await call('/v1/tick',observation)).json(),{});
  await call('/v1/tick',{...observation,result:{id:queued.id,status:'completed'}});
  assert.equal((await (await call('/v1/actions/' + queued.id)).json()).status,'completed');
  const next = await (await call('/v1/actions',{type:'stop'})).json();
  await call('/v1/tick',{...observation,ready:false});
  assert.equal((await (await call('/v1/actions/' + next.id)).json()).status,'cancelled');
});

test('queued commands expire and cannot execute late', async t => {
  const server = createBridge('t'.repeat(32));
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = 'http://127.0.0.1:' + server.address().port;
  const headers = {Authorization:'Bearer ' + 't'.repeat(32),'Content-Type':'application/json'};
  const state = {protocol:1,session:'expire-world',ready:true,busy:false};
  const post = (path, body) => fetch(base+path,{method:'POST',headers,body:JSON.stringify(body)});
  await post('/v1/tick',state);
  const queued = await (await post('/v1/actions',{type:'stop'})).json();
  await new Promise(resolve => setTimeout(resolve,5100));
  assert.deepEqual(await (await post('/v1/tick',state)).json(),{});
  assert.equal((await (await fetch(base+'/v1/actions/'+queued.id,{headers})).json()).status,'expired');
});
