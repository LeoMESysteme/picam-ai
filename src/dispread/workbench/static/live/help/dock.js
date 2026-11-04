// Hilfe-Dock (Spec "Einarbeitung" 3): rechts, ersetzt den Inspektor bis zum
// Schliessen. Glossar aus glossar-de.json (Statuswoerter, Pruefungen,
// Markierungen, Bedienung) plus Gruende aus dem Status: tracking_reasons
// (fields.py REASONS, mit ?full=1 geliefert) und Lesegruende (cause_texts,
// sonst die explanation der gerade gemeldeten rejection_causes). Die Gruende
// werden nicht im Client gepflegt, sondern zur Laufzeit gesammelt.
//
// glossaryEntries und filterEntries sind rein (node-testbar); mountHelp baut
// das Dock.

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const capital = (text) => (text ? text[0].toUpperCase() + text.slice(1) : text);

// Suche ohne Gross/klein, Akzente und Umlaut-Schreibweise (ü = ue = u).
export function normalize(text) {
  return String(text ?? '').toLowerCase().replace(/ß/g, 'ss').normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/ae/g, 'a').replace(/oe/g, 'o').replace(/ue/g, 'u');
}

// Gruende aus dem Status, gesammelt ueber alle bisher gesehenen Status
// (seen: Map reason -> explanation, wird ergaenzt).
function causeTexts(status, seen) {
  for (const [reason, text] of Object.entries(status?.cause_texts || {})) {
    if (typeof text === 'string' && text) seen.set(reason, text);
  }
  for (const cause of status?.run?.rejection_causes?.causes || []) {
    if (cause && typeof cause.reason === 'string' && typeof cause.explanation === 'string' && cause.explanation) {
      if (!seen.has(cause.reason)) seen.set(cause.reason, cause.explanation);
    }
  }
  return seen;
}

// [{section, term, code, text, href}] in Anzeigereihenfolge.
export function glossaryEntries(glossary, status, {seenCauses = new Map(), seenTracking = new Map()} = {}) {
  const base = glossary?.wiki || '';
  const link = (anchor) => (anchor ? `${base}#${anchor}` : base);
  const entries = [];
  for (const section of glossary?.sections || []) {
    for (const entry of section.entries || []) {
      entries.push({section: section.title, term: entry.term, code: entry.code || '', text: entry.text,
        href: link(entry.anchor)});
    }
  }
  for (const [key, text] of Object.entries(status?.tracking_reasons || {})) {
    if (typeof text === 'string' && text) seenTracking.set(key, text);
  }
  const tracking = glossary?.reasons?.tracking || {title: 'Nachführungsgründe'};
  for (const [key, text] of seenTracking) {
    entries.push({section: tracking.title, term: capital(text), code: key, text, href: link(tracking.anchor)});
  }
  const causes = glossary?.reasons?.causes || {title: 'Lesegründe'};
  for (const [reason, text] of causeTexts(status, seenCauses)) {
    entries.push({section: causes.title, term: capital(text), code: reason, text, href: link(causes.anchor)});
  }
  return entries;
}

export function filterEntries(entries, query) {
  const q = normalize(query).trim();
  if (!q) return entries.slice();
  return entries.filter((e) => normalize(`${e.term} ${e.code} ${e.text}`).includes(q));
}

let glossaryPromise = null;
export function loadGlossary(fetchImpl = (...args) => fetch(...args)) {
  if (!glossaryPromise) {
    glossaryPromise = fetchImpl(new URL('./glossar-de.json', import.meta.url).href)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`Glossar: HTTP ${response.status}`))))
      .catch((error) => { glossaryPromise = null; throw error; });
  }
  return glossaryPromise;
}

const CLOSE_ICON = '<svg class="i" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>';

// dock: leerer Container im Dock rechts. Rueckgabe {open(), close(), toggle(),
// isOpen(), update(status)}. onToggle(open) meldet Oeffnen und Schliessen.
export function mountHelp(dock, status = null, {onToggle = () => {}, glossary = null} = {}) {
  dock.setAttribute('role', 'complementary');
  dock.setAttribute('aria-label', 'Hilfe');
  dock.classList.add('helpdock');
  dock.hidden = true;
  dock.innerHTML = `<div class="pt"><span>Hilfe · Glossar</span><span class="pa"><span data-part="count" class="mono"></span>` +
    `<button type="button" class="ghost x" data-part="close" aria-label="Hilfe schließen" title="Schließen (Esc)">${CLOSE_ICON}</button></span></div>` +
    '<div class="hsearch"><input type="search" data-part="search" aria-label="Begriff suchen" placeholder="Begriff suchen …" autocomplete="off" spellcheck="false"></div>' +
    '<div class="scroll gl" data-part="list"><p class="note pad">Glossar wird geladen …</p></div>';
  const q = (name) => dock.querySelector(`[data-part="${name}"]`);
  const seenCauses = new Map();
  const seenTracking = new Map();
  let data = glossary;
  let current = status;
  let entries = [];
  let signature = null;
  let before = null;

  function render() {
    if (!data) return;
    entries = glossaryEntries(data, current, {seenCauses, seenTracking});
    const next = JSON.stringify(entries.map((e) => [e.section, e.code, e.text]));
    if (next !== signature) {
      signature = next;
      const sections = [];
      for (const entry of entries) {
        if (sections.at(-1)?.title !== entry.section) sections.push({title: entry.section, items: []});
        sections.at(-1).items.push(entry);
      }
      q('list').innerHTML = sections.map((section) => `<section class="gl-sec" data-sec="${esc(section.title)}">` +
        `<h3 class="gl-h">${esc(section.title)}<span class="mono">${section.items.length}</span></h3>` +
        section.items.map((e) => `<article class="gl-entry" data-key="${esc(normalize(`${e.term} ${e.code} ${e.text}`))}">` +
          `<h4>${esc(e.term)}${e.code ? ` <span class="code mono">${esc(e.code)}</span>` : ''}</h4>` +
          `<p>${esc(e.text)}</p>` +
          `<a href="${esc(e.href)}" target="_blank" rel="noopener noreferrer">${esc(data.wiki_label || 'Wiki')}</a></article>`).join('') +
        '</section>').join('') + '<p class="note pad" data-part="empty" hidden>Kein Begriff gefunden.</p>';
    }
    filter();
  }

  function filter() {
    const query = normalize(q('search').value).trim();
    let shown = 0;
    for (const section of dock.querySelectorAll('.gl-sec')) {
      let any = false;
      for (const entry of section.querySelectorAll('.gl-entry')) {
        const hit = !query || entry.dataset.key.includes(query);
        entry.hidden = !hit;
        if (hit) { any = true; shown++; }
      }
      section.hidden = !any;
    }
    const empty = q('empty');
    if (empty) empty.hidden = shown > 0;
    q('count').textContent = query ? `${shown}/${entries.length}` : String(entries.length);
  }

  q('search').addEventListener('input', filter);
  q('close').addEventListener('click', () => api.close());
  dock.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    event.stopPropagation();
    if (q('search').value) { q('search').value = ''; filter(); } else api.close();
  });

  const api = {
    async open() {
      if (!dock.hidden) { q('search').focus(); return; }
      before = dock.ownerDocument.activeElement;
      dock.hidden = false;
      onToggle(true);
      q('search').focus();
      if (!data) {
        try { data = await loadGlossary(); } catch (error) {
          q('list').innerHTML = `<p class="note pad err-t">${esc(error.message)}</p>`;
          return;
        }
      }
      render();
    },
    close() {
      if (dock.hidden) return;
      dock.hidden = true;
      onToggle(false);
      if (before?.isConnected && typeof before.focus === 'function') before.focus();
    },
    toggle() { return dock.hidden ? api.open() : api.close(); },
    isOpen: () => !dock.hidden,
    update(next) {
      current = next;
      // Gruende auch bei geschlossenem Dock sammeln (gesehene Lesegruende bleiben).
      glossaryEntries(data || {}, next, {seenCauses, seenTracking});
      if (!dock.hidden) render();
    },
  };
  return api;
}
