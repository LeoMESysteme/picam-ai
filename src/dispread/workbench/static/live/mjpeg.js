// MJPEG-Client fuer /live/preview.mjpg (multipart/x-mixed-replace).
// Bild und HUD kommen aus demselben Teil: der Aufrufer bekommt beide
// zusammen und zeichnet sie gemeinsam, damit das HUD deckungsgleich bleibt.

const CRLF2 = [13, 10, 13, 10];
const latin1 = new TextDecoder('latin1');

function indexOf(haystack, needle, from = 0) {
  const last = haystack.length - needle.length;
  outer: for (let i = Math.max(0, from); i <= last; i += 1) {
    for (let j = 0; j < needle.length; j += 1) if (haystack[i + j] !== needle[j]) continue outer;
    return i;
  }
  return -1;
}

function join(a, b) {
  if (!a.length) return b;
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

function parseHeaders(bytes) {
  const headers = new Map();
  for (const line of latin1.decode(bytes).split('\r\n')) {
    const colon = line.indexOf(':');
    if (colon > 0) headers.set(line.slice(0, colon).trim().toLowerCase(), line.slice(colon + 1).trim());
  }
  return headers;
}

// Zerlegt einen Byte-Strom in Teile. Kopfnamen sind klein geschrieben
// (`x-frame-sequence`, `x-hud`). Mit Content-Length zaehlt die Laenge, eine
// Grenzzeile im JPEG kann den Teil also nicht abschneiden; ohne Laenge
// endet der Rumpf vor der naechsten Grenze.
export async function* parseParts(chunks, boundary) {
  const delimiter = new TextEncoder().encode(`--${boundary}`);
  const next = new TextEncoder().encode(`\r\n--${boundary}`);
  let buf = new Uint8Array(0);
  let state = 'boundary';
  let headers = null;
  for await (const chunk of chunks) {
    buf = join(buf, chunk instanceof Uint8Array ? chunk : new Uint8Array(chunk));
    for (;;) {
      if (state === 'boundary') {
        const at = indexOf(buf, delimiter);
        if (at < 0) {
          // Nur so viel behalten, wie eine angeschnittene Grenze braucht.
          if (buf.length > delimiter.length) buf = buf.slice(buf.length - delimiter.length);
          break;
        }
        const after = at + delimiter.length;
        if (buf.length < after + 2) break;
        if (buf[after] === 45 && buf[after + 1] === 45) return; // "--frame--": Ende
        const eol = indexOf(buf, [13, 10], after);
        if (eol < 0) break;
        buf = buf.slice(eol + 2);
        state = 'headers';
      }
      if (state === 'headers') {
        // Teil ohne Kopfzeilen: Leerzeile direkt nach der Grenze.
        const end = buf[0] === 13 && buf[1] === 10 ? -2 : indexOf(buf, CRLF2);
        if (end === -1) break;
        headers = parseHeaders(buf.subarray(0, Math.max(0, end)));
        buf = buf.slice(end + 4);
        state = 'body';
      }
      if (state === 'body') {
        const length = Number.parseInt(headers.get('content-length'), 10);
        let body;
        if (Number.isFinite(length) && length >= 0) {
          if (buf.length < length) break;
          body = buf.slice(0, length);
          buf = buf.slice(length);
        } else {
          const end = indexOf(buf, next);
          if (end < 0) break;
          body = buf.slice(0, end);
          buf = buf.slice(end + 2);
        }
        state = 'boundary';
        yield {headers, body};
      }
    }
  }
}

async function* readerChunks(body) {
  if (body && typeof body.getReader === 'function') {
    const reader = body.getReader();
    try {
      for (;;) {
        const {done, value} = await reader.read();
        if (done) return;
        yield value;
      }
    } finally {
      reader.cancel().catch(() => {});
    }
  } else {
    yield* body; // AsyncIterable (Tests)
  }
}

const defaultSleep = (ms, signal) => new Promise((resolve) => {
  const timer = setTimeout(resolve, ms);
  signal?.addEventListener('abort', () => { clearTimeout(timer); resolve(); }, {once: true});
});

// Wie api.js: Fehler der Anzeige sichtbar machen (Konsole, pageerror).
function surfaceError(error) {
  if (typeof globalThis.reportError === 'function') globalThis.reportError(error);
  else setTimeout(() => { throw error; });
}

const defaultDecode = (bytes) => createImageBitmap(new Blob([bytes], {type: 'image/jpeg'}));

function headerOf(headers, name) {
  return typeof headers.get === 'function' ? headers.get(name) : headers[name];
}

// Haelt den Strom offen, bis `signal` abbricht. Nach jedem Abbruch (Server
// beendet nach 600 s, langsamer Client, Netzfehler) wird neu verbunden:
// 0,5 s, dann verdoppelt bis 5 s; ein empfangenes Bild setzt auf 0,5 s zurueck.
// onFrame bekommt {bitmap, hud, seq, capNs}; hud ist null, wenn X-Hud fehlt
// oder nicht lesbar ist. onState('verbindet'|'offen'|'getrennt') ist optional.
// Wirft onFrame, geht der Fehler an onError (Standard: reportError) und der
// Strom laeuft weiter.
export async function openPreview(url, onFrame, signal, deps = {}) {
  const fetchImpl = deps.fetchImpl || ((...args) => fetch(...args));
  const decode = deps.decode || defaultDecode;
  const sleep = deps.sleep || defaultSleep;
  const onState = deps.onState || (() => {});
  const onError = deps.onError || surfaceError;
  let failures = 0;
  while (!signal?.aborted) {
    let gotFrame = false;
    onState('verbindet');
    try {
      const response = await fetchImpl(url, {signal, cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const type = headerOf(response.headers, 'content-type') || '';
      const boundary = /boundary="?([^";]+)"?/i.exec(type)?.[1] || 'frame';
      onState('offen');
      for await (const part of parseParts(readerChunks(response.body), boundary)) {
        if (signal?.aborted) return;
        let hud = null;
        try { hud = JSON.parse(part.headers.get('x-hud') ?? 'null'); } catch { hud = null; }
        let bitmap;
        try { bitmap = await decode(part.body); } catch { continue; }
        if (signal?.aborted) { bitmap?.close?.(); return; }
        gotFrame = true;
        failures = 0;
        const seq = Number.parseInt(part.headers.get('x-frame-sequence'), 10);
        const capNs = part.headers.get('x-capture-ns') ?? null;
        try {
          onFrame({bitmap, hud, seq: Number.isFinite(seq) ? seq : null, capNs});
        } catch (error) {
          // Ein Anzeigefehler ist kein Stromabbruch: sichtbar machen, weiterlesen.
          onError(error);
        }
      }
    } catch {
      // Nur Abruf-, Strom- und Lesefehler: unten mit Wartezeit neu verbinden.
    }
    if (signal?.aborted) return;
    onState('getrennt');
    if (gotFrame) failures = 0;
    const delay = Math.min(5000, 500 * 2 ** failures);
    failures += 1;
    await sleep(delay, signal);
  }
}
