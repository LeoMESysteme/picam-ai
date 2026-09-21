'use strict';
/* Geführter Datensatz-Sammelmodus - eigener Namespace, eigenes Polling.
 *
 * Bewusst getrennt von workbench.js: eigene csrf-Beschaffung, eigener
 * Zustand. Nur `DatasetCollection.toOriginalBox` ist absichtlich auf
 * `window` sichtbar - eine reine Geometriefunktion, die
 * tests/dataset_client.test.mjs ohne DOM-Umbau pruefen kann.
 *
 * Ablauf als drei Schritte (Geraet -> Situation -> Aufnahme), jeder
 * abgeschlossene Schritt klappt zu einer Einzeiler-Zusammenfassung zusammen -
 * siehe docs/status.md, Abschnitt "UX/Workflow des Sammelmodus vereinfachen".
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

  /* Reine Entscheidung: welche Situation ist nach Geraeteauswahl aktiv?
   * Bei genau einer vorhandenen Situation wird sie automatisch fortgesetzt
   * (Schritt 2 bleibt zugeklappt) - bei keiner oder mehreren muss der
   * Bediener bewusst waehlen. `groups` ist die vom Server gelieferte
   * device.groups-Struktur ({group_id: {change_note, ...}}).
   */
  function chooseInitialGroup(groups) {
    const entries = Object.entries(groups || {});
    if (entries.length !== 1) return null;
    const [groupId, g] = entries[0];
    return { group_id: groupId, change_note: g.change_note };
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function init() {
    if (typeof document === 'undefined') return; // im Node-Testharness nicht aufgerufen
    const $ = (id) => document.getElementById(id);
    let csrf = '';
    let devices = []; // aus dataset.device.list
    let device = null; // {id, revision, split, groups, ...}
    let group = null; // {group_id, device_id, change_note}
    let deviceStepExpanded = true;
    let groupStepExpanded = true;
    let capture = null; // {token, width, height}
    let dragStart = null;
    let selection = null; // {x,y,w,h} in Canvas-CSS-Pixeln
    let lastSavedSample = null; // zuletzt gespeicherte Probe, fuer "als Vertreter markieren"
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

    function deviceLabel(d) {
      return d.model ? `${d.name} (${d.model})` : d.name;
    }

    function populateDeviceSelect() {
      const select = $('dataset-device-select');
      const current = select.value;
      select.innerHTML =
        '<option value="">– Gerät wählen –</option>' +
        devices.map((d) => `<option value="${d.id}">${escapeHtml(deviceLabel(d))}</option>`).join('') +
        '<option value="__new__">+ neues Gerät anlegen</option>';
      if (devices.some((d) => d.id === current)) select.value = current;
    }

    function groupEntries() {
      return device ? Object.entries(device.groups) : [];
    }

    function populateGroupSelect() {
      const select = $('dataset-group-select');
      select.innerHTML =
        '<option value="">– keine –</option>' +
        groupEntries().map(([id, g]) => `<option value="${id}">${escapeHtml(g.change_note)}</option>`).join('');
    }

    function renderSteps() {
      const deviceDone = !!device && !deviceStepExpanded;
      $('dataset-step-device').classList.toggle('done', deviceDone);
      $('dataset-device-summary-text').textContent = device ? `Gerät: ${deviceLabel(device)} ✓` : '';

      $('dataset-step-group').hidden = !device;
      const groupDone = !!group && !groupStepExpanded;
      $('dataset-step-group').classList.toggle('done', groupDone);
      $('dataset-group-summary-text').textContent = group ? `Situation: ${group.change_note} ✓` : '';

      const ready = !!device && !!group;
      $('dataset-step-capture').hidden = !ready;
      $('dataset-capture-header').textContent = ready ? `Gerät: ${deviceLabel(device)} · Situation: ${group.change_note}` : '';
    }

    async function discardOpenCapture() {
      if (capture) {
        try {
          await op('dataset.discard', { token: capture.token });
        } catch (_) {
          /* Aufnahme war bereits abgelaufen/entfernt - kein Grund, den Schrittwechsel zu blockieren. */
        }
      }
      capture = null;
      selection = null;
      $('dataset-editor').hidden = true;
      $('dataset-similarity').hidden = true;
      lastSavedSample = null;
      $('dataset-representative').hidden = true;
    }

    async function afterDeviceChosen() {
      await discardOpenCapture();
      populateGroupSelect();
      const initial = chooseInitialGroup(device.groups);
      if (initial) {
        group = { ...initial, device_id: device.id };
        groupStepExpanded = false;
      } else {
        group = null;
        groupStepExpanded = true;
      }
      deviceStepExpanded = false;
      renderSteps();
    }

    $('dataset-device-select').onchange = () =>
      guarded(async () => {
        const value = $('dataset-device-select').value;
        if (value === '__new__') {
          $('dataset-device-new').hidden = false;
          return;
        }
        $('dataset-device-new').hidden = true;
        if (!value) return;
        device = devices.find((d) => d.id === value) || null;
        if (!device) return;
        await afterDeviceChosen();
      });

    $('dataset-device-create').onclick = () =>
      guarded(async () => {
        const payload = {
          name: $('dataset-device-input-name').value.trim(),
          model: $('dataset-device-input-model').value.trim() || null,
          family: $('dataset-device-input-family').value.trim(),
          technology: $('dataset-device-input-technology').value,
          split: $('dataset-device-input-split').value,
          identity_confirmed: $('dataset-device-input-confirm').checked,
          identity_evidence: $('dataset-device-input-evidence').value.trim(),
        };
        device = await op('dataset.device.create', payload);
        devices = devices.filter((d) => d.id !== device.id).concat(device);
        populateDeviceSelect();
        $('dataset-device-select').value = device.id;
        $('dataset-device-new').hidden = true;
        $('dataset-device-input-name').value = '';
        $('dataset-device-input-model').value = '';
        $('dataset-device-input-family').value = '';
        $('dataset-device-input-confirm').checked = false;
        $('dataset-device-input-evidence').value = '';
        note('Gerät angelegt: ' + device.name);
        await afterDeviceChosen();
      });

    $('dataset-device-change').onclick = () => {
      deviceStepExpanded = true;
      renderSteps();
    };

    $('dataset-group-continue').onclick = () =>
      guarded(async () => {
        const value = $('dataset-group-select').value;
        if (!value) throw new Error('Situation wählen');
        const g = device.groups[value];
        await discardOpenCapture();
        group = { group_id: value, device_id: device.id, change_note: g.change_note };
        groupStepExpanded = false;
        renderSteps();
      });

    $('dataset-group-begin').onclick = () =>
      guarded(async () => {
        if (!device) throw new Error('Zuerst ein Gerät anlegen oder wählen');
        const changeNote = $('dataset-group-input').value.trim();
        if (!changeNote) throw new Error('Was hat sich geändert? Bitte kurz beschreiben.');
        const created = await op('dataset.group.begin', { device_id: device.id, change_note: changeNote });
        device.groups[created.group_id] = { device_id: device.id, change_note: created.change_note };
        await discardOpenCapture();
        group = created;
        groupStepExpanded = false;
        $('dataset-group-input').value = '';
        note('Neue Situation eröffnet.');
        renderSteps();
      });

    $('dataset-group-change').onclick = () => {
      groupStepExpanded = true;
      renderSteps();
    };

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

    let pendingSaveArgs = null;

    function afterSave(sample) {
      note('Probe gespeichert: ' + sample.id);
      capture = null;
      selection = null;
      pendingSaveArgs = null;
      $('dataset-editor').hidden = true;
      $('dataset-similarity').hidden = true;
      $('dataset-expected-text').value = '';
      $('dataset-target-label').value = '';
      $('dataset-similarity-reason').value = '';
      showRepresentativeChoice(sample);
    }

    function showRepresentativeChoice(sample) {
      // Ohne ausdrueckliche Auswahl schliesst der Export eine ganze Situation
      // aus, sobald sie mehr als eine Probe hat (DatasetStore._export_locked,
      // Grund "group_without_selection") - dieser Knopf ist der einzige Weg,
      // das aus der Oberflaeche heraus zu setzen (Nutzerfund 2026-09-21).
      lastSavedSample = sample;
      $('dataset-representative').hidden = false;
      $('dataset-representative-info').textContent = sample.expected_text || sample.label_state;
      $('dataset-representative-mark').disabled = false;
      $('dataset-representative-mark').textContent = 'als Vertreter dieser Situation markieren';
    }

    $('dataset-representative-mark').onclick = () =>
      guarded(async () => {
        if (!lastSavedSample) return;
        const updated = await op('dataset.select', {
          sample_id: lastSavedSample.id,
          revision: lastSavedSample.metadata_revision,
        });
        lastSavedSample = updated;
        $('dataset-representative-mark').disabled = true;
        $('dataset-representative-mark').textContent = '✓ ist Vertreter dieser Situation';
        note('Als Vertreter der Situation markiert: ' + updated.id);
      });

    function buildSaveArgs() {
      if (!capture) throw new Error('Zuerst eine Aufnahme einfrieren');
      if (!selection || selection.w <= 0 || selection.h <= 0) throw new Error('Zielbox fehlt - Rechteck über der Zahlenzeile ziehen');
      const originalBox = toOriginalBox(
        selection,
        { width: canvas().clientWidth, height: canvas().clientHeight },
        { width: capture.width, height: capture.height }
      );
      const labelState = $('dataset-label-state').value;
      return {
        token: capture.token,
        bbox: [originalBox.x, originalBox.y, originalBox.w, originalBox.h],
        target_label: $('dataset-target-label').value.trim() || null,
        label_state: labelState,
        expected_text: labelState === 'readable' ? $('dataset-expected-text').value.trim() : null,
        conditions: conditionKeys(),
      };
    }

    $('dataset-save').onclick = () =>
      guarded(async () => {
        const args = buildSaveArgs();
        try {
          const sample = await op('dataset.save', args);
          afterSave(sample);
        } catch (error) {
          // Aehnlichkeitswarnung ist kein gewoehnlicher Fehler: Rohdaten und
          // Eingaben bleiben erhalten, der Bediener kann begruendet bestaetigen
          // statt neu anzufangen (Konzept, Aufgabe 5).
          if (/Ähnlich zu vorhandener Probe/.test(error.message)) {
            pendingSaveArgs = args;
            $('dataset-similarity').hidden = false;
            note(error.message, true);
            return;
          }
          throw error;
        }
      });

    $('dataset-similarity-confirm').onclick = () =>
      guarded(async () => {
        if (!pendingSaveArgs) return;
        const reason = $('dataset-similarity-reason').value.trim();
        if (!reason) throw new Error('Begründung fehlt');
        const sample = await op('dataset.save', {
          ...pendingSaveArgs,
          similarity_confirmed: true,
          similarity_reason: reason,
        });
        afterSave(sample);
      });
    $('dataset-similarity-cancel').onclick = () => {
      pendingSaveArgs = null;
      $('dataset-similarity').hidden = true;
      $('dataset-similarity-reason').value = '';
    };

    $('dataset-discard').onclick = () => guarded(discardOpenCapture);

    async function refreshSummary() {
      const summary = await op('dataset.summary');
      const overallGaps = summary.missing_conditions.overall;
      $('dataset-summary').textContent =
        `${summary.devices} Geräte · ${summary.samples} Proben · ${summary.independence_groups} Situationen · ` +
        `${summary.readable} lesbar · ${summary.unreadable} unlesbar · ${summary.uncertain_or_draft} unsicher/Entwurf` +
        (overallGaps.length ? ` · fehlend: ${overallGaps.join(', ')}` : '');
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
          devices = await op('dataset.device.list');
          populateDeviceSelect();
          await refreshSummary();
          renderSteps();
        }
      });

    renderSteps();
  }

  return { toOriginalBox, clampSelectionToImage, chooseInitialGroup, init };
})();

if (typeof window !== 'undefined') {
  window.DatasetCollection = DatasetCollection;
  if (typeof document !== 'undefined') DatasetCollection.init();
}
if (typeof module !== 'undefined') module.exports = DatasetCollection;
