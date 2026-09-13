import test from 'node:test';
import assert from 'node:assert/strict';
import {validateAction} from './server.mjs';
test('hotbar transfer requires bounded slots, counts and observed ids',()=>{
  const a={type:'move_hotbar',sourceSlot:9,hotbarSlot:0,expectedSource:'minecraft:wooden_pickaxe',expectedTarget:'minecraft:air',sourceCount:1,targetCount:0};
  assert.equal(validateAction(a),true);
  for(const c of [{sourceSlot:8},{sourceSlot:36},{hotbarSlot:9},{sourceCount:0},{targetCount:true},{expectedTarget:'bad'},{repeat:2}]) assert.equal(validateAction({...a,...c}),false);
});
