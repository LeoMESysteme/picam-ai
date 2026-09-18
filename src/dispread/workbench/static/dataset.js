'use strict';
/* Geführter Datensatz-Sammelmodus - eigener Namespace, eigenes Polling.
 *
 * Bewusst getrennt von workbench.js: eigene csrf-Beschaffung, eigener
 * Zustand. Nur `DatasetCollection.toOriginalBox` ist absichtlich auf
 * `window` sichtbar - eine reine Geometriefunktion, die
 * tests/dataset_client.test.mjs ohne DOM-Umbau pruefen kann.
 */
const DatasetCollection = (function () {
  const CONDITIONS = [
    ['frontal', 'frontal'],
    ['angled', 'schräg'],
    ['distance', 'andere Entfernung'],
    ['digits', 'andere Ziffernzahl'],
    ['negative', 'negatives Vorzeichen'],
    ['decimal', 'andere Dezimalposition'],
    ['multiline', 'mehrere Zeilen'],
    ['reflection', 'Reflexion'],
    ['dim', 'schwache Anzeige'],
  ];

  /* Reine Geometrie: eine in CSS-Pixeln der sichtbaren (object-fit:contain)
   * Bilddarstellung gezogene Auswahl in Originalbildpixel umrechnen.
   * DPR-unabhaengig, solange `visibleSize` aus getBoundingClientRect()
   * kommt (CSS-Pixel) statt aus canvas.width/height (Backing-Store-Pixel).
   */
  function toOriginalBox(selection, visibleSize, originalSize) {
    const originalAspect = originalSize.width / originalSize.height;
    const visibleAspect = visibleSize.width / visibleSize.height;
    let renderedWidth, renderedHeight, offsetX, offsetY;
    if (originalAspect > visibleAspect) {
      renderedWidth = visibleSize.width;
      renderedHeight = visibleSize.width / originalAspect;
      offsetX = 0;
      offsetY = (visibleSize.height - renderedHeight) / 2;
    } else {
      renderedHeight = visibleSize.height;
      renderedWidth = visibleSize.height * originalAspect;
      offsetY = 0;
      offsetX = (visibleSize.width - renderedWidth) / 2;
    }
    const scale = originalSize.width / renderedWidth;
    return {
      x: (selection.x - offsetX) * scale,
      y: (selection.y - offsetY) * scale,
      w: selection.w * scale,
      h: selection.h * scale,
    };
  }

  function clampSelectionToImage(selection, visibleSize, originalSize) {
    const originalAspect = originalSize.width / originalSize.height;
    const visibleAspect = visibleSize.width / visibleSize.height;
    let renderedWidth, renderedHeight, offsetX, offsetY;
    if (originalAspect > visibleAspect) {
      renderedWidth = visibleSize.width;
      renderedHeight = visibleSize.width / originalAspect;
      offsetX = 0;
      offsetY = (visibleSize.height - renderedHeight) / 2;
    } else {
      renderedHeight = visibleSize.height;
      renderedWidth = visibleSize.height * originalAspect;
      offsetY = 0;
      offsetX = (visibleSize.width - renderedWidth) / 2;
    }
    const x = Math.max(offsetX, Math.min(offsetX + renderedWidth, selection.x));
    const y = Math.max(offsetY, Math.min(offsetY + renderedHeight, selection.y));
    const x2 = Math.max(offsetX, Math.min(offsetX + renderedWidth, selection.x + selection.w));
    const y2 = Math.max(offsetY, Math.min(offsetY + renderedHeight, selection.y + selection.h));
    return { x: Math.min(x, x2), y: Math.min(y, y2), w: Math.abs(x2 - x), h: Math.abs(y2 - y) };
  }

  function init() {
    if (typeof document === 'undefined') return; // im Node-Testharness nicht aufgerufen
    const $ = (id) => document.getElementById(id);
    let csrf = '';
    let device = null; // {id, revision, split, ...}
    let group = null; // {group_id, device_id, change_note}
    let capture = null; // {token, width, height}
    let dragStart = null;
    let selection = null; // {x,y,w,h} in Canvas-CSS-Pixeln
    let busy = false;

    async function api(path, method = 'GET', body) {
      const response = await fetch(path, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(10000),
      });
      if (response.status === 401) {
        location.replace('/login');
        throw new Error('Anmeldung erforderlich');
      }
      if (!response.ok) {
        let message = await response.text();
        try {
          message = JSON.parse(message).error || message;
        } catch (_) {
          /* Text bleibt wie er ist. */
        }
        throw new Error(message);
      }
      const type = response.headers.get('content-type') || '';
      return type.includes('application/json') ? response.json() : response;
    }
    async function op(name, args = {}) {
      return api('/command', 'POST', { op: name, args });
    }

    function note(message, isError) {
      const el = $('dataset-note');
      el.textContent = message;
      el.classList.toggle('error', !!isError);
    }

    async function refreshCsrf() {
      const status = await api('/status');
      csrf = status.csrf;
      return status;
    }

    async function guarded(fn) {
      if (busy) return;
      busy = true;
      try {
        await fn();
      } catch (error) {
        note(error.message, true);
      } finally {
        busy = false;
      }
    }

    function renderDeviceState() {
      $('dataset-device-name').textContent = device ? device.name : '(kein Gerät gewählt)';
      $('dataset-split').textContent = device ? device.split : '';
      $('dataset-group-note').textContent = group ? group.change_note : '(keine Situation)';
      $('dataset-capture-button').disabled = !device || !group;
    }

    $('dataset-device-create').onclick = () =>
      guarded(async () => {
        const payload = {
          name: $('dataset-device-input-name').value.trim(),
          model: $('dataset-device-input-model').value.trim() || null,
          family: $('dataset-device-input-family').value.trim(),
          technology: $('dataset-device-input-technology').value,
          split: $('dataset-device-input-split').value,
          identity_confirmed: $('dataset-device-input-confirm').checked,
        };
        device = await op('dataset.device.create', payload);
        group = null;
        note('Gerät angelegt: ' + device.name);
        renderDeviceState();
      });

    $('dataset-group-begin').onclick = () =>
      guarded(async () => {
        if (!device) throw new Error('Zuerst ein Gerät anlegen oder wählen');
        const changeNote = $('dataset-group-input').value.trim();
        if (!changeNote) throw new Error('Was hat sich geändert? Bitte kurz beschreiben.');
        group = await op('dataset.group.begin', { device_id: device.id, change_note: changeNote });
        $('dataset-group-input').value = '';
        note('Neue Situation eröffnet.');
        renderDeviceState();
      });

    function conditionKeys() {
      return [...$('dataset-conditions').querySelectorAll('input:checked')].map((el) => el.value);
    }

    function renderCanvas() {
      const canvas = $('dataset-canvas');
      const wrapper = $('dataset-viewport');
      canvas.width = wrapper.clientWidth;
      canvas.height = wrapper.clientHeight;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (selection) {
        ctx.strokeStyle = '#f0d080';
        ctx.lineWidth = 2;
        ctx.strokeRect(selection.x, selection.y, selection.w, selection.h);
      }
    }

    $('dataset-capture-button').onclick = () =>
      guarded(async () => {
        capture = await op('dataset.capture', { device_id: device.id, group_id: group.group_id });
        selection = null;
        const img = $('dataset-image');
        img.src = '/dataset/captures/' + capture.token + '.jpg?t=' + Date.now();
        $('dataset-editor').hidden = false;
        note('Aufnahme eingefroren. Zahlenzeile markieren und Wert eintragen.');
        renderCanvas();
      });

    const canvas = () => $('dataset-canvas');
    canvas().onpointerdown = (event) => {
      if (!capture) return;
      const rect = canvas().getBoundingClientRect();
      dragStart = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      canvas().setPointerCapture(event.pointerId);
    };
    canvas().onpointermove = (event) => {
      if (!dragStart) return;
      const rect = canvas().getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      selection = clampSelectionToImage(
        { x: Math.min(dragStart.x, x), y: Math.min(dragStart.y, y), w: Math.abs(x - dragStart.x), h: Math.abs(y - dragStart.y) },
        { width: canvas().clientWidth, height: canvas().clientHeight },
        { width: capture.width, height: capture.height }
      );
      renderCanvas();
    };
    canvas().onpointerup = () => {
      dragStart = null;
    };
    new ResizeObserver(renderCanvas).observe($('dataset-viewport'));

    function labelStateChanged() {
      const state = $('dataset-label-state').value;
      $('dataset-expected-text').disabled = state !== 'readable';
      if (state !== 'readable') $('dataset-expected-text').value = '';
    }
    $('dataset-label-state').onchange = labelStateChanged;
    labelStateChanged();

    $('dataset-save').onclick = () =>
      guarded(async () => {
        if (!capture) throw new Error('Zuerst eine Aufnahme einfrieren');
        if (!selection || selection.w <= 0 || selection.h <= 0) throw new Error('Zielbox fehlt - Rechteck über der Zahlenzeile ziehen');
        const originalBox = toOriginalBox(
          selection,
          { width: canvas().clientWidth, height: canvas().clientHeight },
          { width: capture.width, height: capture.height }
        );
        const labelState = $('dataset-label-state').value;
        const sample = await op('dataset.save', {
          token: capture.token,
          bbox: [originalBox.x, originalBox.y, originalBox.w, originalBox.h],
          target_label: $('dataset-target-label').value.trim() || null,
          label_state: labelState,
          expected_text: labelState === 'readable' ? $('dataset-expected-text').value.trim() : null,
          conditions: conditionKeys(),
        });
        note('Probe gespeichert: ' + sample.id);
        capture = null;
        selection = null;
        $('dataset-editor').hidden = true;
        $('dataset-expected-text').value = '';
        $('dataset-target-label').value = '';
        await refreshSummary();
      });

    $('dataset-discard').onclick = () =>
      guarded(async () => {
        if (capture) await op('dataset.discard', { token: capture.token });
        capture = null;
        selection = null;
        $('dataset-editor').hidden = true;
      });

    async function refreshSummary() {
      const summary = await op('dataset.summary');
      $('dataset-summary').textContent =
        `${summary.devices} Geräte · ${summary.samples} Proben · ${summary.independence_groups} Situationen · ` +
        `${summary.readable} lesbar · ${summary.unreadable} unlesbar · ${summary.uncertain_or_draft} unsicher/Entwurf`;
    }

    $('dataset-export').onclick = () =>
      guarded(async () => {
        const result = await op('dataset.export');
        const link = $('dataset-export-link');
        link.href = '/dataset/exports/' + result.export_id + '.zip';
        link.hidden = false;
        link.textContent = 'Export herunterladen (' + result.coverage.images + ' Bilder)';
        if (result.coverage.warnings.length) note('Export: ' + result.coverage.warnings.join('; '), true);
        else note('Export erstellt.');
      });

    for (const [value, label] of CONDITIONS) {
      const wrapper = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = value;
      wrapper.append(input, document.createTextNode(' ' + label));
      $('dataset-conditions').append(wrapper);
    }

    $('dataset-tab').onclick = () =>
      guarded(async () => {
        const entering = $('dataset').hidden;
        $('dataset').hidden = !entering;
        $('main').classList.toggle('dataset-mode', entering);
        if (entering) {
          await refreshCsrf();
          await refreshSummary();
          renderDeviceState();
        }
      });

    renderDeviceState();
  }

  return { toOriginalBox, clampSelectionToImage, init };
})();

if (typeof window !== 'undefined') {
  window.DatasetCollection = DatasetCollection;
  if (typeof document !== 'undefined') DatasetCollection.init();
}
if (typeof module !== 'undefined') module.exports = DatasetCollection;
