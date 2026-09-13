import http from 'node:http';
import { randomUUID, timingSafeEqual } from 'node:crypto';
import { pathToFileURL } from 'node:url';

export function validateAction(a) {
  if (!a || typeof a !== 'object' || Array.isArray(a)) return false;
  const keys = Object.keys(a).sort().join(',');
  if (a.type === 'stop') return keys === 'type';
  if (a.type === 'move_hotbar') return keys === 'expectedSource,expectedTarget,hotbarSlot,sourceCount,sourceSlot,targetCount,type' &&
    Number.isInteger(a.sourceSlot) && a.sourceSlot>=9 && a.sourceSlot<=35 &&
    Number.isInteger(a.hotbarSlot) && a.hotbarSlot>=0 && a.hotbarSlot<=8 &&
    Number.isInteger(a.sourceCount) && a.sourceCount>=1 && a.sourceCount<=64 &&
    Number.isInteger(a.targetCount) && a.targetCount>=0 && a.targetCount<=64 &&
    [a.expectedSource,a.expectedTarget].every(v=>typeof v==='string' && v.length<=128 && /^[a-z0-9_.-]+:[a-z0-9_./-]+$/.test(v));
  if (a.type === 'craft_workbench') return keys === 'recipe,type,x,y,z' &&
    ['x','y','z'].every(k=>Number.isInteger(a[k])) && Math.abs(a.x)<=29999999 && Math.abs(a.z)<=29999999 &&
    a.y>=-64 && a.y<=319 && ['wooden_pickaxe','wooden_axe','wooden_sword','wooden_shovel','wooden_hoe'].includes(a.recipe);
  if (a.type === 'place_workbench') return keys === 'expectedSupport,type,x,y,z' &&
    ['x','y','z'].every(k=>Number.isInteger(a[k])) && Math.abs(a.x)<=29999999 && Math.abs(a.z)<=29999999 &&
    a.y>=-64 && a.y<=318 && ['minecraft:dirt','minecraft:grass_block','minecraft:stone','minecraft:cobblestone'].includes(a.expectedSupport);
  if (a.type === 'craft') return keys === 'recipe,type' &&
    ['oak_planks','spruce_planks','birch_planks','jungle_planks','acacia_planks',
     'dark_oak_planks','mangrove_planks','cherry_planks','stick','crafting_table'].includes(a.recipe);
  if (a.type === 'select_hotbar') return keys === 'expectedItem,slot,type' &&
    Number.isInteger(a.slot) && a.slot >= 0 && a.slot <= 8 &&
    typeof a.expectedItem === 'string' && a.expectedItem.length <= 128 &&
    /^[a-z0-9_.-]+:[a-z0-9_./-]+$/.test(a.expectedItem);
  if (a.type === 'collect') return keys === 'entityId,timeoutTicks,type' &&
    Number.isInteger(a.entityId) && a.entityId >= 0 && a.entityId <= 2147483647 &&
    Number.isInteger(a.timeoutTicks) && a.timeoutTicks >= 20 && a.timeoutTicks <= 200;
  if (a.type === 'mine' || a.type === 'approach') return keys === 'timeoutTicks,type,x,y,z' &&
    ['x','y','z'].every(k=>Number.isInteger(a[k])) &&
    Math.abs(a.x) <= 29999999 && Math.abs(a.z) <= 29999999 && a.y >= -64 && a.y <= 319 &&
    Number.isInteger(a.timeoutTicks) && a.timeoutTicks >= 20 && a.timeoutTicks <= 200;
  if (a.type === 'move') return keys === 'direction,ticks,type' &&
    ['forward','back','left','right','jump'].includes(a.direction) &&
    Number.isInteger(a.ticks) && a.ticks >= 1 && a.ticks <= 20;
  return a.type === 'look' && keys === 'pitch,type,yaw' &&
    Number.isFinite(a.yaw) && Math.abs(a.yaw) <= 180 &&
    Number.isFinite(a.pitch) && Math.abs(a.pitch) <= 90;
}
export function createBridge(token, now = Date.now) {
  if (!token || token.length < 32) throw new Error('BRIDGE_TOKEN must have at least 32 characters');
  let observation = null, seenAt = 0, session = null, pending = null;
  const results = new Map();
  function remember(id, status, feedback = {}) {
    results.set(id, {...feedback, id, status});
    if (results.size > 200) results.delete(results.keys().next().value);
  }
  function expire() {
    if (pending && (now() > pending.expiresAt || (pending.delivered && now()-seenAt > 5000))) {
      remember(pending.id, 'expired', pending.cancelRequested ?
        {reason:'cancel_ack_timeout', cancelRequested:true, cancelConfirmed:false} : {}); pending = null;
    }
  }
  return http.createServer(async (req, res) => {
    const send = (status, body) => {
      res.writeHead(status, {'Content-Type':'application/json', 'Cache-Control':'no-store'});
      res.end(JSON.stringify(body));
    };
    if (req.method === 'GET' && req.url === '/health') return send(200, {ok:true, protocol:1});
    const actual = Buffer.from(req.headers.authorization || '');
    const expected = Buffer.from('Bearer ' + token);
    if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) return send(401,{error:'unauthorized'});
    expire();
    try {
      let body = {};
      if (req.method === 'POST') {
        let data = '';
        for await (const part of req) {
          data += part;
          if (Buffer.byteLength(data) > 65536) return send(413,{error:'body too large'});
        }
        body = JSON.parse(data);
      }
      if (req.method === 'POST' && req.url === '/v1/tick') {
        if (body.protocol !== 1 || typeof body.session !== 'string' ||
            typeof body.ready !== 'boolean' || typeof body.busy !== 'boolean')
          return send(400,{error:'invalid observation'});
        if (session && session !== body.session && now()-seenAt < 5000)
          return send(409,{error:'another client is connected'});
        if (session !== body.session && pending) {
          remember(pending.id,'cancelled',{reason:'session_changed',cancelConfirmed:false}); pending = null;
        }
        session = body.session; observation = body; seenAt = now();
        if (pending && body.result?.id === pending.id &&
            ['completed','cancelled','rejected','timed_out'].includes(body.result.status)) {
          const feedback = {};
          if (typeof body.result.reason === 'string') feedback.reason = body.result.reason.slice(0,128);
          if (body.result.details && typeof body.result.details === 'object' &&
              !Array.isArray(body.result.details) && Buffer.byteLength(JSON.stringify(body.result.details)) <= 8192)
            feedback.details = body.result.details;
          if (pending.cancelRequested) {
            feedback.cancelRequested = true;
            feedback.cancelConfirmed = body.result.status === 'cancelled' &&
              body.result.details?.inputsReleased === true;
          }
          remember(pending.id, body.result.status, feedback); pending = null;
        }
        // A not-ready observation is not proof that a delivered action released
        // its inputs. Wait for that action's terminal feedback or expiry.
        if (!body.ready && pending && !pending.delivered) {
          remember(pending.id,'cancelled',{reason:'not_ready_before_dispatch'}); pending = null;
        }
        if (pending?.delivered && body.activeAction?.id === pending.id &&
            Buffer.byteLength(JSON.stringify(body.activeAction)) <= 2048)
          remember(pending.id,pending.cancelRequested ? 'cancelling' : 'running',
            {progress:body.activeAction,...(pending.cancelRequested ? {cancelRequested:true,cancelConfirmed:false} : {})});
        if (pending?.cancelRequested) return send(200,{cancel:{id:pending.id,session}});
        let command = undefined;
        if (pending && !pending.delivered && body.ready && !body.busy) {
          pending.delivered = true;
          pending.expiresAt = now() + (pending.action.type === 'craft_workbench' ? 18000 : ['craft','place_workbench','move_hotbar'].includes(pending.action.type) ? 14000 : ['mine','approach','collect'].includes(pending.action.type) ? pending.action.timeoutTicks*50+4000 : 5000);
          remember(pending.id,'running');
          command = {id:pending.id, action:pending.action};
        }
        return send(200, command ? {command} : {});
      }
      if (req.method === 'GET' && req.url === '/v1/observation') {
        return send(200,{connected: observation !== null && now()-seenAt < 5000, observedAt:seenAt, observation});
      }
      if (req.method === 'POST' && req.url === '/v1/actions') {
        if (!validateAction(body)) return send(400,{error:'invalid action'});
        if (!observation?.ready || now()-seenAt > 5000) return send(409,{error:'Minecraft not ready'});
        if (['mine','approach','collect','select_hotbar','craft','place_workbench','craft_workbench','move_hotbar'].includes(body.type) && !observation.capabilities?.includes(body.type))
          return send(409,{error:'Minecraft client upgrade required for '+body.type});
        if (pending || observation.busy) return send(409,{error:'action already in progress'});
        const id = randomUUID();
        pending = {id, action:body, expiresAt:now()+5000, delivered:false};
        remember(id,'queued');
        return send(202,{id,status:'queued'});
      }
      const cancelMatch = /^\/v1\/actions\/([a-f0-9-]{36})\/cancel$/.exec(req.url);
      if (req.method === 'POST' && cancelMatch) {
        if (!body || Array.isArray(body) || typeof body !== 'object' || Object.keys(body).length)
          return send(400,{error:'cancel body must be empty'});
        const id = cancelMatch[1], existing = results.get(id);
        if (!existing) return send(404,{error:'unknown action'});
        if (pending?.id !== id) return send(200,existing); // Terminal, idempotent; never touch another action.
        if (!pending.delivered) {
          remember(id,'cancelled',{reason:'cancelled_before_dispatch',cancelRequested:true,
            cancelConfirmed:true,confirmation:'never_dispatched'});
          pending = null;
          return send(200,results.get(id));
        }
        if (!observation.capabilities?.includes('cancel')) return send(409,{error:'Minecraft client upgrade required for cancel'});
        if (!pending.cancelRequested) {
          pending.cancelRequested = true;
          pending.expiresAt = Math.min(pending.expiresAt,now()+5000);
          remember(id,'cancelling',{cancelRequested:true,cancelConfirmed:false});
        }
        return send(202,results.get(id));
      }
      if (req.method === 'GET' && req.url.startsWith('/v1/actions/')) {
        const result = results.get(req.url.slice('/v1/actions/'.length));
        return send(result ? 200 : 404, result || {error:'unknown action'});
      }
      return send(404,{error:'not found'});
    } catch { return send(400,{error:'invalid request'}); }
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  createBridge(process.env.BRIDGE_TOKEN).listen(8765,'0.0.0.0',()=>console.log('Astra bridge listening on 8765'));
}
