import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const timeline = JSON.parse(fs.readFileSync(path.join(here, 'timeline.json'), 'utf8'));
const outDir = path.join(here, 'frames');
fs.rmSync(outDir, { recursive: true, force: true });
fs.mkdirSync(outDir, { recursive: true });

const port = process.env.CDP_PORT || '9223';
const target = await (await fetch(
  `http://127.0.0.1:${port}/json/new?` + encodeURIComponent('about:blank'),
  { method: 'PUT' },
)).json();

const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();

function send(method, params = {}) {
  const msgId = ++id;
  ws.send(JSON.stringify({ id: msgId, method, params }));
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(msgId); reject(new Error('timeout: ' + method)); }, 30000);
    pending.set(msgId, {
      resolve: (v) => { clearTimeout(timer); resolve(v); },
      reject: (e) => { clearTimeout(timer); reject(e); },
    });
  });
}

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(msg.error.message)); else resolve(msg.result);
  }
};

await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });

const W = 1280, H = 720;
await send('Page.enable');
await send('Page.navigate', { url: 'file:///' + path.join(here, 'terminal.html').replace(/\\/g, '/') });
await new Promise(r => setTimeout(r, 900));
await send('Emulation.setDeviceMetricsOverride', {
  width: W, height: H, deviceScaleFactor: 1, mobile: false, screenWidth: W, screenHeight: H,
});
await new Promise(r => setTimeout(r, 500));

const files = [];
for (let i = 0; i < timeline.length; i++) {
  const entry = timeline[i];
  await send('Runtime.evaluate', {
    expression: `window.addLine(${JSON.stringify(entry.cls)}, ${JSON.stringify(entry.text)})`,
    returnByValue: true,
  });
  await new Promise(r => setTimeout(r, 60));
  const { data } = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
  const name = String(i).padStart(4, '0') + '.png';
  fs.writeFileSync(path.join(outDir, name), Buffer.from(data, 'base64'));
  files.push({ name, duration: entry.hold });
  if (i % 10 === 0) console.log('frame', i, '/', timeline.length);
}

const list = files.map(f => `file '${f.name}'\nduration ${f.duration.toFixed(2)}`).join('\n');
fs.writeFileSync(path.join(outDir, 'list.txt'), list + `\nfile '${files.at(-1).name}'\n`);
console.log('frames written:', files.length, 'total', files.reduce((a, f) => a + f.duration, 0).toFixed(1) + 's');

ws.close();
await fetch(`http://127.0.0.1:${port}/json/close/` + target.id);
process.exit(0);
