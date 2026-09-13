import test from 'node:test';
import assert from 'node:assert/strict';
import {validateAction} from './server.mjs';
test('workbench placement restricts ground, height and input shape',()=>{
  const action={type:'place_workbench',x:0,y:64,z:0,expectedSupport:'minecraft:dirt'};
  assert.equal(validateAction(action),true);
  for(const changes of [{y:319},{x:true},{expectedSupport:'minecraft:chest'},{repeat:2},{z:30000000}])
    assert.equal(validateAction({...action,...changes}),false);
});
