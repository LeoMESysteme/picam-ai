// Hinweise und der Dialog "Anzeige hat sich bewegt" (Spec "Meldungen").
// Nur "Anzeige hat sich bewegt" blockiert (Dialog); alles andere ist ein
// Hinweis unten rechts im Viewer. Texte: trackingHintText und statusView
// (woertlich aus live.js), Ueberschriften aus der Spec-Tabelle "Meldungen".
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
import {statusView, trackingHintText} from '../model.js';
import {runTitle} from './dock.js';

export const STORE_KEY = 'werkbank.anzeige-bewegt';
// Spec "Meldungen" (fields.py live_cause mit Umlauten und Halbgeviertstrich).
export const LOST_TITLE = 'Rahmenbereiche verdeckt oder verschoben – Kamera und Sicht prüfen';
export const STALL_TITLE = 'Streamstillstand: kein neues Kamerabild';
export const MOVED_TITLE = 'Anzeige hat sich bewegt';
const MOVED_ACTIONS = [
  {label: 'Weiter beobachten', value: 'weiter', escape: true, cls: 'ghost'},
  {label: 'Lauf stoppen', value: 'stopp', cls: 'danger', icon: 'stop'},
  {label: 'Neu einrichten', value: 'neu', primary: true, icon: 'redo'},
];
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

function lostOf(status) {
  if (status?.state !== 'running') return null;
  const hint = status.run?.tracking_hint || null;
  const lost = (status.run?.latest?.reject_reasons || []).some((r) => r.startsWith('tracking_lost:'));
  if (!hint && !lost) return null;
  return {hint, text: trackingHintText(hint) || statusView(status).detail};
}

function warningWhy(status) {
  const setup = status.setup || {};
  return Object.entries(setup.checks || {}).filter(([, v]) => v === 'WARNUNG')
    .map(([k]) => setup.check_reasons?.[k] || k).join(', ');
}

export function createAlerts({toast = defaultToast, closeToast = defaultClose, openModal = defaultModal,
  storage = sessionStore(), wallNow = () => Date.now(), run = {}} = {}) {
  let prev = null;
  let episode = null; // {run, since, start, modal}
  let lostDismissed = false;
  let lostShown = false;
  let stalledShown = false;
  let warned = null;
  let latest = null;

  function sameStored(runKey, since, start) {
    const stored = readStore(storage);
    if (!stored || stored.run !== runKey) return false;
    return stored.since === since || (finite(stored.at) && start <= stored.at + START_SLACK_MS);
  }

  async function choose(value, ep) {
    if (value === 'weiter') {
      writeStore(storage, {run: ep.run, since: ep.since, start: ep.start, at: wallNow()});
      ep.dismissed = true;
      update(latest, {replay: true});
      return;
    }
    if (value === 'stopp' || value === 'neu') {
      ep.dismissed = true;
      const stopped = latest?.state === 'running' ? await run.stop?.() : {ok: true};
      if (value === 'neu' && stopped?.ok) await run.setup?.();
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
    if (!info || movedOpen) {
      if (lostShown) closeToast('nachfuehrung');
      lostShown = false;
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
        const why = warningWhy(status);
        toast({level: 'warn', title: 'Vorschlag mit WARNUNG', text: why, key: 'vorschlag'});
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

  return {update, episode: () => episode};
}

const watchers = new WeakMap();
export function watchAlerts(status, deps = {}) {
  const owner = deps.client || watchAlerts;
  let watcher = watchers.get(owner);
  if (!watcher) {
    watcher = createAlerts(deps);
    watchers.set(owner, watcher);
  }
  watcher.update(status);
  return watcher;
}
