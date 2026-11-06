// Hinweise und der Dialog "Anzeige hat sich bewegt" (Spec "Meldungen").
// Nur "Anzeige hat sich bewegt" blockiert (Dialog); alles andere ist ein
// Hinweis unten rechts im Viewer. Texte: trackingHintText und statusView
// (woertlich aus der alten Live-Seite), Ueberschriften aus der Spec-Tabelle "Meldungen".
//
// watchAlerts(status, {client, viewer}) wertet jeden Statusabruf aus.
// createAlerts(deps) ist dieselbe Logik mit eingespeisten Hinweisen, Dialog,
// Speicher und Uhr (node-testbar).
//
// Dialog einmal je Verlust-Episode: Der Server meldet tracking_hint.since_s
// (Sekunden seit Beginn des Verlusts, waechst je Abruf). Eine Episode endet,
// wenn der Hinweis wegfaellt oder since_s zurueckspringt. "Weiter beobachten"
// (Esc) merkt sich die Episode in sessionStorage: {run, since_s, start, at}.
// Nach dem Neuladen gilt sie als dieselbe, wenn since_s gleich ist oder der
// Verlust vor dem Weglegen begann (start <= at). Ohne Speicher (privat,
// gesperrt) fragt die Seite nach dem Neuladen eben noch einmal.
import {openModal as defaultModal} from '../ui/modal.js';
import {closeToast as defaultClose, toast as defaultToast} from '../ui/toasts.js';
import {trackingHintText} from '../model.js';
import {checkLabel} from '../setup/checks.js';
import {runTitle} from './dock.js';
import {isCode, withoutCodes} from './result.js';

export const STORE_KEY = 'werkbank.anzeige-bewegt';
// Spec "Meldungen" (fields.py live_cause mit Umlauten und Halbgeviertstrich).
export const LOST_TITLE = 'Rahmenbereiche verdeckt oder verschoben – Kamera und Sicht prüfen';
export const STALL_TITLE = 'Streamstillstand: kein neues Kamerabild';
export const MOVED_TITLE = 'Anzeige hat sich bewegt';
const MOVED_ACTIONS = [
  {label: 'Weiter beobachten', value: 'weiter', escape: true, cls: 'ghost'},
  {label: 'Lauf stoppen', value: 'stopp', cls: 'danger', icon: 'stop'},
  // Ruling R28: beendet den Lauf (Dateien bleiben liegen) und startet die Einrichtung.
  {label: 'Lauf beenden und neu einrichten', value: 'neu', primary: true, icon: 'redo'},
];
// Spec "Meldungen", Zeile "Rahmen verdeckt": Text des Hinweises (trackingHintText, woertlich).
const COVERED_TEXT = trackingHintText({kind: 'rahmen_verdeckt'});
const WARN_ASK = 'Bitte im Bild prüfen und die Warnung zur Kenntnis nehmen.';
// Toleranz fuer "Verlust begann vor dem Weglegen" (Abrufabstand, Uhrsprung).
const START_SLACK_MS = 1500;

const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const pad = (n) => String(n).padStart(2, '0');
const clock = (ms) => { const d = new Date(ms); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };

function sessionStore() {
  try { return globalThis.sessionStorage ?? null; } catch { return null; }
}

function readStore(storage) {
  try {
    const raw = storage?.getItem(STORE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function writeStore(storage, value) {
  try { storage?.setItem(STORE_KEY, JSON.stringify(value)); } catch { /* ohne Speicher: nur fuer diese Seite */ }
}

const runKeyOf = (status) => (['running', 'stopped'].includes(status?.state) ? `${status.session_id}|${status.run?.dir}` : null);
const markKeyOf = (mark) => (mark ? `${mark.number ?? ''}|${mark.received_at_utc}|${mark.text}` : null);

// Wie effectState (model.js): nur ein frischer Datensatz (<= 0,5 s) belegt den
// Verlust; bei Stillstand oder Verbindungsluecke steht der Hinweis nicht daneben.
function freshLatest(status) {
  const age = status?.run?.latest_age_s;
  return typeof age === 'number' && Number.isFinite(age) && age <= 0.5;
}

function lostOf(status) {
  if (status?.state !== 'running') return null;
  const hint = status.run?.tracking_hint || null;
  const lost = (status.run?.latest?.reject_reasons || []).some((r) => r.startsWith('tracking_lost:'));
  if (!hint && !lost) return null;
  // Ohne Hinweis des Servers (nur tracking_lost:*) gilt der Spec-Text fuer "Rahmen verdeckt".
  return {hint, fresh: freshLatest(status), text: trackingHintText(hint) || COVERED_TEXT};
}

// "Raster: Raster am Rand knapp. Bitte im Bild pruefen …" bzw. "Pruefung Raster. …":
// Wort der Pruefung wie im Glossar, Grund nur als Klartext (eine Kennung faellt weg).
export function warningText(status) {
  const setup = status.setup || {};
  const parts = Object.entries(setup.checks || {}).filter(([, v]) => v === 'WARNUNG').map(([key]) => {
    const reason = withoutCodes(setup.check_reasons?.[key] || '').trim();
    return reason && !isCode(reason) ? `${checkLabel(key)}: ${reason}` : `Prüfung ${checkLabel(key)}`;
  });
  return parts.length ? `${parts.join('; ')}. ${WARN_ASK}` : WARN_ASK;
}

const DEFAULTS = {toast: defaultToast, closeToast: defaultClose, openModal: defaultModal, wallNow: () => Date.now(), run: {}};

export function createAlerts(initial = {}) {
  // Abhaengigkeiten sind austauschbar (setDeps): der Uebungslauf (Aufgabe 11)
  // ersetzt Status und Bedienschritte im Client; ein Dialog-Knopf nimmt immer
  // die gerade gueltigen, damit der Uebungslauf nie an den Server sendet.
  const deps = {...DEFAULTS, storage: sessionStore()};
  const setDeps = (next = {}) => {
    for (const [key, value] of Object.entries(next)) if (value !== undefined) deps[key] = value;
  };
  setDeps(initial);
  const toast = (opts) => deps.toast(opts);
  const closeToast = (key) => deps.closeToast(key);
  const openModal = (opts) => deps.openModal(opts);
  const wallNow = () => deps.wallNow();
  let prev = null;
  let episode = null; // {run, since, start, modal}
  let lostDismissed = false;
  let lostShown = false;
  let stalledShown = false;
  let warned = null;
  let latest = null;

  function sameStored(runKey, since, start) {
    const stored = readStore(deps.storage);
    if (!stored || stored.run !== runKey) return false;
    return stored.since === since || (finite(stored.at) && start <= stored.at + START_SLACK_MS);
  }

  async function choose(value, ep) {
    if (value === 'weiter') {
      writeStore(deps.storage, {run: ep.run, since: ep.since, start: ep.start, at: wallNow()});
      ep.dismissed = true;
      update(latest, {replay: true});
      return;
    }
    if (value === 'stopp' || value === 'neu') {
      ep.dismissed = true;
      // Erst beim Klick nachschlagen: die dann gueltige Quelle (echt oder Uebung).
      const stopped = latest?.state === 'running' ? await deps.run.stop?.() : {ok: true};
      if (value === 'neu' && stopped?.ok) await deps.run.setup?.();
    }
  }

  function moved(status, runKey) {
    const hint = status?.state === 'running' && status.run?.tracking_hint?.kind === 'anzeige_bewegt'
      ? status.run.tracking_hint : null;
    if (!hint) {
      if (episode?.modal && !episode.answered) episode.modal.close?.(null);
      episode = null;
      return;
    }
    const since = finite(hint.since_s) ? hint.since_s : 0;
    const start = wallNow() - since * 1000;
    const continues = episode && episode.run === runKey && since >= episode.since - 1;
    if (continues) {
      episode.since = Math.max(episode.since, since);
      return;
    }
    if (episode?.modal && !episode.answered) episode.modal.close?.(null);
    episode = {run: runKey, since, start, dismissed: sameStored(runKey, since, start)};
    if (episode.dismissed) return;
    const ep = episode;
    const text = `${trackingHintText(hint)}\n\nSeit ${clock(start)} sind alle Datensätze Unlesbar (anzeige_bewegt).`;
    ep.modal = openModal({title: MOVED_TITLE, text, tone: 'err', actions: MOVED_ACTIONS});
    Promise.resolve(ep.modal).then((value) => {
      ep.answered = true;
      if (value !== null && value !== undefined) return choose(value, ep);
      return undefined;
    });
  }

  // Rahmen verdeckt / Nachfuehrung verloren: stehender Hinweis bis zur Erholung.
  // Bei "Anzeige bewegt" erst nach dem Weglegen des Dialogs (Erinnerung).
  function lost(status) {
    const info = lostOf(status);
    const movedOpen = info?.hint?.kind === 'anzeige_bewegt' && !episode?.dismissed;
    if (!info || !info.fresh || movedOpen) {
      if (lostShown) closeToast('nachfuehrung');
      lostShown = false;
      // Weggelegt bleibt weggelegt, bis der Verlust wirklich endet (nicht nur veraltet).
      if (!info) lostDismissed = false;
      return;
    }
    if (lostDismissed) return;
    lostShown = true;
    toast({level: 'err', title: LOST_TITLE, text: info.text, sticky: true, key: 'nachfuehrung',
      onClose: (reason) => { if (reason === 'user') lostDismissed = true; lostShown = false; }});
  }

  function update(status, {replay = false} = {}) {
    if (!status) return;
    latest = status;
    const runKey = runKeyOf(status);
    moved(status, runKey);
    lost(status);
    if (replay) return;

    const stalled = Boolean(status.camera?.stalled);
    if (stalled && !stalledShown) {
      toast({level: 'err', title: STALL_TITLE, text: 'Datensätze werden als Veraltet geführt.', key: 'stillstand'});
    } else if (!stalled && stalledShown) closeToast('stillstand');
    stalledShown = stalled;

    if (status.state === 'setup_ready' && status.setup?.overall === 'WARNUNG') {
      const key = status.session_id;
      if (warned !== key) {
        warned = key;
        toast({level: 'warn', title: 'Vorschlag mit WARNUNG', text: warningText(status), key: 'vorschlag'});
      }
    }

    // Uebergaenge nur zwischen zwei gesehenen Abrufen: ein Neuladen meldet nichts nach.
    if (prev) {
      const title = runTitle(status);
      if (prev.state !== 'running' && status.state === 'running') {
        toast({level: 'info', title: `${status.test_run ? 'Testlauf' : title} gestartet`,
          text: `Ablage ${status.session_id}/${status.run?.dir || ''}`, key: 'lauf'});
      }
      if (prev.state === 'running' && status.state === 'stopped') {
        const reason = status.run?.summary?.end_reason;
        toast({level: 'info', title: `${title} gestoppt`, text: reason ? `Endgrund ${reason}` : '', key: 'lauf'});
      }
      const sameRun = runKey && runKey === runKeyOf(prev) && status.state === 'running';
      const step = status.reference?.schedule_step;
      if (sameRun && step && step.index !== prev.reference?.schedule_step?.index) {
        toast({level: 'info', title: `Werteplan: set norm ${step.factor}`, text: 'Sprung wird nicht geglättet.', key: 'werteplan'});
      }
      const mark = markKeyOf(status.last_mark);
      if (sameRun && mark && mark !== markKeyOf(prev.last_mark)) {
        toast({level: 'info', title: 'Ereignis markiert', text: status.last_mark.text, key: 'marke'});
      }
    }
    prev = status;
  }

  return {update, setDeps, episode: () => episode};
}

const watchers = new WeakMap();
export function watchAlerts(status, deps = {}) {
  const owner = deps.client || watchAlerts;
  let watcher = watchers.get(owner);
  if (!watcher) {
    watcher = createAlerts(deps);
    watchers.set(owner, watcher);
  } else watcher.setDeps(deps);
  watcher.update(status);
  return watcher;
}
