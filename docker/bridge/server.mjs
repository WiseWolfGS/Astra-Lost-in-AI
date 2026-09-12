import http from 'node:http';
import { randomUUID, timingSafeEqual } from 'node:crypto';
import { pathToFileURL } from 'node:url';

export function validateAction(a) {
  if (!a || typeof a !== 'object' || Array.isArray(a)) return false;
  const keys = Object.keys(a).sort().join(',');
  if (a.type === 'stop') return keys === 'type';
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
      remember(pending.id, 'expired'); pending = null;
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
          remember(pending.id,'cancelled'); pending = null;
        }
        session = body.session; observation = body; seenAt = now();
        if (pending && body.result?.id === pending.id &&
            ['completed','cancelled','rejected','timed_out'].includes(body.result.status)) {
          const feedback = {};
          if (typeof body.result.reason === 'string') feedback.reason = body.result.reason.slice(0,128);
          if (body.result.details && typeof body.result.details === 'object' &&
              !Array.isArray(body.result.details) && Buffer.byteLength(JSON.stringify(body.result.details)) <= 8192)
            feedback.details = body.result.details;
          remember(pending.id, body.result.status, feedback); pending = null;
        }
        if (!body.ready && pending) { remember(pending.id,'cancelled'); pending = null; }
        if (pending?.delivered && body.activeAction?.id === pending.id &&
            Buffer.byteLength(JSON.stringify(body.activeAction)) <= 2048)
          remember(pending.id,'running',{progress:body.activeAction});
        let command = undefined;
        if (pending && !pending.delivered && body.ready && !body.busy) {
          pending.delivered = true;
          pending.expiresAt = now() + (['mine','approach','collect'].includes(pending.action.type) ? pending.action.timeoutTicks*50+4000 : 5000);
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
        if (['mine','approach','collect'].includes(body.type) && !observation.capabilities?.includes(body.type))
          return send(409,{error:'Minecraft client upgrade required for '+body.type});
        if (pending || observation.busy) return send(409,{error:'action already in progress'});
        const id = randomUUID();
        pending = {id, action:body, expiresAt:now()+5000, delivered:false};
        remember(id,'queued');
        return send(202,{id,status:'queued'});
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
