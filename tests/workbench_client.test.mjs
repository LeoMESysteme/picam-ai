/* Regressionstests fuer den Browserteil der Workbench (workbench.js).
 *
 * Gefahren wird der echte Auslieferungsstand der Datei in einem vm-Kontext
 * mit einem minimalen DOM-Ersatz - kein Framework, keine zusaetzliche
 * Abhaengigkeit (node_modules haelt nur Playwright). Geprueft wird
 * ausschliesslich beobachtbares Verhalten: was auf die Leinwand gezeichnet
 * wird und was an den Server geht. Die internen `let`-Variablen des Moduls
 * (u. a. `editing`) sind aus dem Kontext bewusst nicht erreichbar - ein Test
 * gegen sie wuerde die Umsetzung statt der Zusicherung pruefen.
 *
 * Aufruf (siehe tests/test_workbench_client.py):
 *     node tests/workbench_client.test.mjs <fixture.json>
 * Die Fixture liefert die Raster, die der SERVER aus `grid_geometry()`
 * rechnet - damit misst dieser Test gegen echte Serverdaten, nicht gegen in
 * JavaScript nachgebaute Rastermathematik.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const here = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = fs.readFileSync(
  path.join(here, '..', 'src', 'dispread', 'workbench', 'static', 'workbench.js'),
  'utf8',
);
const FIXTURE = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

const settle = async (rounds = 8) => {
  for (let i = 0; i < rounds; i++) await new Promise((resolve) => setImmediate(resolve));
};

/* --- minimaler DOM-Ersatz ------------------------------------------------ */
function element(id) {
  const node = {
    id,
    children: [],
    style: {},
    dataset: {},
    classList: { toggle() {}, add() {}, remove() {}, contains: () => false },
    hidden: false,
    className: '',
    textContent: '',
    title: '',
    value: '',
    disabled: false,
    ariaLabel: '',
    clientWidth: 640,
    clientHeight: 400,
    scrollHeight: 0,
    scrollTop: 0,
    append(...kids) { this.children.push(...kids); },
    replaceChildren(...kids) { this.children = kids; },
    querySelector() { return element(id + ':child'); },
    querySelectorAll() { return []; },
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 640, height: 400 }),
    getContext: () => ctx2d,
    focus() {}, select() {}, remove() {}, contains: () => false,
    setAttribute() {}, removeAttribute() {}, hasAttribute: () => false,
    setPointerCapture() {}, showPicker() {},
    get childElementCount() { return this.children.length; },
    get firstElementChild() { return this.children[0]; },
  };
  return node;
}
const ctx2d = {
  clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, closePath() {},
  stroke() {}, fill() {}, arc() {}, fillRect() {}, setLineDash() {},
  strokeStyle: '', fillStyle: '', lineWidth: 1,
};

/* --- Server-Ersatz ------------------------------------------------------- */
function makeServer() {
  return {
    sent: [],
    handlers: {},
    status: {
      csrf: 'token',
      sequence: 1,
      processing_fps: 10,
      live: true,
      mode: 'setup',
      profile: 'default',
      profiles: ['default'],
      simulated: true,
      dirty: false,
      conflict: false,
      error: null,
      stopped: false,
      logs: [],
      terminals: [{ id: 'shell-1', exit_code: null }],
      config: { role: 'main', layout: FIXTURE.committed.layout },
      ocr_grid: FIXTURE.committed.ocr_grid,
      reading: null,
      auto: { state: 'idle' },
      quality: {},
      observed: {},
      capabilities: {},
      focus: false,
      clip: { state: 'idle', frames: 0, dropped: 0, path: null, seconds_left: null },
      setup: { rows: [], actions: [] },
    },
  };
}

function load(server) {
  const nodes = new Map();
  const reply = (data) => ({
    ok: true, status: 200, json: async () => data, text: async () => JSON.stringify(data),
  });
  const context = {
    console,
    performance,
    AbortSignal,
    TextEncoder,
    setTimeout,
    clearTimeout,
    setInterval: () => 0,   // kein Dauer-Polling im Test - poll() wird gerufen
    clearInterval: () => {},
    location: { host: 'localhost', replace() {} },
    WebSocket: class { constructor() { this.readyState = 0; } close() {} send() {} },
    Terminal: class { constructor() { this.cols = 80; this.rows = 24; } loadAddon() {} open() {} write() {} reset() {} dispose() {} focus() {} onData() {} },
    FitAddon: { FitAddon: class { fit() {} } },
    ResizeObserver: class { observe() {} disconnect() {} },
    document: {
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, element(id));
        return nodes.get(id);
      },
      createElement: (tag) => element(tag),
      get activeElement() { return null; },
    },
    async fetch(url, options = {}) {
      const body = options.body ? JSON.parse(options.body) : null;
      if (url.startsWith('/status')) return reply(server.status);
      if (url === '/command') {
        server.sent.push(body);
        const handler = server.handlers[body.op];
        if (!handler) throw new Error('unerwarteter Befehl: ' + body.op);
        return reply(await handler(body.args));
      }
      if (url.startsWith('/terminals')) return reply([]);
      return reply({});
    },
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(SOURCE, context, { filename: 'workbench.js' });
  return context;
}

/* --- Hilfen fuer die Szenarien ------------------------------------------- */
const frozen = () => ({
  id: 'frame-1',
  width: 960,
  height: 720,
  roi: [0.2, 0.3, 0.6, 0.3],
  quad: [[0.2, 0.3], [0.8, 0.3], [0.8, 0.6], [0.2, 0.6]],
  candidates: [],
  ocr_box: [0.15, 0.15, 0.7, 0.7],
  ocr_grid: FIXTURE.committed.ocr_grid,
});
const proposal = (extra = {}) => ({
  matched: true,
  layout: FIXTURE.proposed.layout,
  ocr_grid: FIXTURE.proposed.ocr_grid,
  ocr_box: [0.12, 0.14, 0.75, 0.72],
  separation: 0.31,
  runner_up: 0.12,
  flat_optimum: false,
  evaluated: 120,
  reason: null,
  preview: { raw_text: '012.3', value: 12.3 },
  ...extra,
});

/** Zeichnet neu und liefert die dabei gezeichneten Rasterzellen. */
function drawnCells(context) {
  const boxes = [];
  const original = context.gridBox;
  context.gridBox = (box, colour, width) => { boxes.push(box); return original(box, colour, width); };
  try { context.draw(); } finally { context.gridBox = original; }
  return boxes;
}

async function bisStufeOcr(context, server) {
  server.handlers.freeze = async () => frozen();
  server.handlers['ocr.suggest'] = async () => ({ ocr_box: [0.15, 0.15, 0.7, 0.7] });
  await context.freeze();
  await context.confirmRoi();
}

const layoutRows = () => ({
  rows: [
    {
      key: 'layout.digits', label: 'stellen', kind: 'number', op: 'layout.set', arg: 'digits',
      min: 1, max: 8, step: 1, value: 4, integer: true, presets: [], hint: '', disabled: false,
    },
    {
      key: 'layout.polarity', label: 'polaritaet', kind: 'choice', value: 'bright_on_dark',
      hint: '', disabled: false,
      options: [
        { value: 'bright_on_dark', label: 'LED', ops: [['layout.set', { key: 'polarity', value: 'bright_on_dark' }]] },
        { value: 'dark_on_bright', label: 'LCD', ops: [['layout.set', { key: 'polarity', value: 'dark_on_bright' }]] },
      ],
    },
  ],
  actions: [],
});

/* --- Testlauf ------------------------------------------------------------ */
const failures = [];
async function test(name, fn) {
  try { await fn(); process.stdout.write(`ok   ${name}\n`); }
  catch (error) { failures.push(name); process.stdout.write(`FAIL ${name}\n${error.stack}\n`); }
}

const committedCells = FIXTURE.committed.ocr_grid.cells;
const proposedCells = FIXTURE.proposed.ocr_grid.cells;
assert.notDeepEqual(committedCells, proposedCells, 'Fixture taugt nicht: beide Raster sind gleich');

await test('R1: Vorschau zeigt das vorgeschlagene Raster und ueberlebt Statusabfragen', async () => {
  const server = makeServer();
  const context = load(server);
  await settle();
  await bisStufeOcr(context, server);

  server.handlers['layout.autofit'] = async () => proposal();
  await context.runAutofit('12,3');

  // Mehrere Statusabfragen mit dem UEBERNOMMENEN Raster - genau der Fall, in
  // dem die Vorschau frueher wieder auf das alte Raster zurueckfiel.
  for (let i = 0; i < 3; i++) { await context.poll(); await settle(2); }

  const gezeichnet = drawnCells(context);
  assert.equal(gezeichnet.length, proposedCells.length + 1, 'Ziffernzellen + Vorzeichenzelle erwartet');
  assert.deepEqual(gezeichnet.slice(0, proposedCells.length), proposedCells);
  assert.deepEqual(gezeichnet[proposedCells.length], FIXTURE.proposed.ocr_grid.sign);
  assert.notDeepEqual(gezeichnet.slice(0, committedCells.length), committedCells);

  // ... und bestaetigt wird genau dieses Raster.
  server.handlers['layout.set_many'] = async () => ({});
  server.handlers.roi = async () => ({});
  await context.confirmOcr();
  await settle();

  const setMany = server.sent.filter((entry) => entry.op === 'layout.set_many');
  assert.equal(setMany.length, 1);
  assert.deepEqual(setMany[0].args.values, FIXTURE.proposed.layout);
  const roi = server.sent.filter((entry) => entry.op === 'roi');
  assert.equal(roi.length, 1);
  assert.deepEqual(roi[0].args.ocr_box, [0.12, 0.14, 0.75, 0.72], 'der vorgeschlagene Rahmen wird mitbestaetigt');
});

await test('R1: Verwerfen zeigt wieder das uebernommene Raster', async () => {
  const server = makeServer();
  const context = load(server);
  await settle();
  await bisStufeOcr(context, server);
  server.handlers['layout.autofit'] = async () => proposal();
  await context.runAutofit('12,3');
  assert.deepEqual(drawnCells(context).slice(0, proposedCells.length), proposedCells);

  context.toggleEdit('ocr');   // Geometrie bearbeiten verwirft den Vorschlag
  assert.deepEqual(drawnCells(context).slice(0, committedCells.length), committedCells);

  server.handlers.roi = async () => ({});
  await context.confirmOcr();
  await settle();
  assert.equal(server.sent.filter((entry) => entry.op === 'layout.set_many').length, 0);
});

await test('R1: fehlgeschlagener Autofit laesst das uebernommene Raster stehen', async () => {
  const server = makeServer();
  const context = load(server);
  await settle();
  await bisStufeOcr(context, server);

  server.handlers['layout.autofit'] = async () => ({ matched: false, reason: 'kein Treffer' });
  await context.runAutofit('99,9');
  assert.deepEqual(drawnCells(context).slice(0, committedCells.length), committedCells);

  server.handlers['layout.autofit'] = async () => { throw new Error('Serverfehler'); };
  await context.runAutofit('99,9');
  assert.deepEqual(drawnCells(context).slice(0, committedCells.length), committedCells);

  server.handlers.roi = async () => ({});
  await context.confirmOcr();
  await settle();
  assert.equal(server.sent.filter((entry) => entry.op === 'layout.set_many').length, 0);
});

await test('R8a: Handaenderung in der Einstelltabelle sticht den Autofit-Vorschlag', async () => {
  for (const [beschreibung, aendern] of [
    ['Zahlenfeld', (context) => context.apply('layout.digits', '5')],
    ['Auswahlfeld (Polaritaet)', (context) => context.apply('layout.polarity', 'dark_on_bright')],
  ]) {
    const server = makeServer();
    server.status.setup = layoutRows();
    const context = load(server);
    await settle();
    await context.poll();          // Einstelltabelle aufbauen
    await bisStufeOcr(context, server);
    server.handlers['layout.autofit'] = async () => proposal();
    await context.runAutofit('12,3');
    assert.deepEqual(
      drawnCells(context).slice(0, proposedCells.length), proposedCells,
      beschreibung + ': Vorschau muss zuerst den Vorschlag zeigen',
    );

    server.handlers['layout.set'] = async () => ({});
    await aendern(context);
    await settle();

    assert.deepEqual(
      drawnCells(context).slice(0, committedCells.length), committedCells,
      beschreibung + ': nach der Handaenderung gilt wieder das uebernommene Raster',
    );
    server.handlers.roi = async () => ({});
    await context.confirmOcr();
    await settle();
    assert.equal(
      server.sent.filter((entry) => entry.op === 'layout.set_many').length, 0,
      beschreibung + ': das alte Vorschlagsraster darf nicht nachtraeglich gesendet werden',
    );
    assert.equal(server.sent.filter((entry) => entry.op === 'layout.set').length, 1);
  }
});

await test('R8a: eine spaet eintreffende Autofit-Antwort ueberholt die Handaenderung nicht', async () => {
  const server = makeServer();
  server.status.setup = layoutRows();
  const context = load(server);
  await settle();
  await context.poll();
  await bisStufeOcr(context, server);

  let freigeben;
  const unterwegs = new Promise((resolve) => { freigeben = resolve; });
  server.handlers['layout.autofit'] = async () => { await unterwegs; return proposal(); };
  server.handlers['layout.set'] = async () => ({});

  const autofit = context.runAutofit('12,3');   // absichtlich nicht abgewartet
  await settle();
  await context.apply('layout.digits', '5');    // Bediener tippt waehrenddessen
  freigeben();
  await autofit;
  await settle();

  assert.deepEqual(
    drawnCells(context).slice(0, committedCells.length), committedCells,
    'die spaete Antwort darf die Vorschau nicht uebernehmen',
  );
  server.handlers.roi = async () => ({});
  await context.confirmOcr();
  await settle();
  assert.equal(server.sent.filter((entry) => entry.op === 'layout.set_many').length, 0);
});

if (failures.length) {
  process.stdout.write(`\n${failures.length} fehlgeschlagen: ${failures.join(', ')}\n`);
  process.exit(1);
}
process.stdout.write('\nalle Browsertests bestanden\n');
