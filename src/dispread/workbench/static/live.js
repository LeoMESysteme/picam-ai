// Live-Seite: zeigt LiveService.status() an und reicht Bedienschritte weiter.
// Entscheidungen fallen im Server (dispread.live), nie hier.

function cameraView(camera) {
  if (camera.stalled) return camera.error || 'Streamstillstand: kein neues Kamerabild';
  return camera.running ? `Kamera läuft, ${camera.frames} Bilder, ${camera.gaps} Lücken`
    : `Kamera aus: ${camera.error || '—'}`;
}

export function statusView(status) {
  if (status.reference?.restoring) {
    return {headline: 'Werte werden zurückgestellt …', cls: 'transition', detail: 'Gerät verbunden lassen.'};
  }
  const view = recordView(status);
  if (status.reader_tolerance && view.cls === 'valid') {
    view.detail = `erweiterte Toleranz ×${status.reader_tolerance.factor} – nicht validiert · ${view.detail}`;
  }
  if (status.test_run && status.state === 'running') {
    view.headline = `TESTLAUF · ${view.headline}`;
    // Vermutung nur zum aktuellen, verworfenen Bild: nie neben STALE oder VALID.
    const guess = status.run?.guess;
    if (guess && view.cls !== 'stale' && view.cls !== 'valid') {
      view.detail += `\nLeser-Vermutung (verworfen, nicht freigegeben): ${guess.text}` +
        `\nunsichere Zellen: ${guess.uncertain.length ? guess.uncertain.join(', ') : 'keine'}`;
    }
  }
  return view;
}

function recordView(status) {
  const run = status.run && status.run.latest;
  if (run) {
    const age = status.run.latest_age_s;
    const fresh = typeof age === 'number' && Number.isFinite(age) && age <= 0.5;
    const reasons = run.reject_reasons.map((reason) => {
      const key = reason.startsWith('tracking_lost:') ? reason.slice('tracking_lost:'.length) : reason;
      const label = status.tracking_reasons?.[key] || status.run.rejection_causes?.causes
        ?.find((cause) => cause.reason === reason)?.explanation;
      return label ? `${label} (${reason})` : reason;
    }).join(', ');
    if (status.test_run && run.status === 'valid' && fresh && status.state === 'running') {
      return {headline: 'UNREADABLE', cls: 'unreadable', detail: 'Testlauf: keine Wertfreigabe'};
    }
    if (status.state === 'running' && run.status === 'valid' && fresh) {
      return {headline: `${run.raw_text} ${run.unit}`, cls: 'valid', detail: `Bild ${run.frame_sequence}`};
    }
    const cls = !fresh || run.status === 'valid' ? 'stale' : run.status;
    if (run.reject_reasons[0]?.startsWith('tracking_lost:')) {
      return {headline: cls.toUpperCase(), cls,
        detail: (status.state === 'running' && trackingHintText(status.run.tracking_hint)) ||
          `Anzeige verloren — Kamera bewegt? Neu einrichten (${reasons})`};
    }
    if (cls === 'transition' && run.reject_reasons[0] === 'anzeige_wechselt') {
      return {headline: 'TRANSITION', cls, detail: `Wert wechselt (${reasons})`};
    }
    return {headline: cls.toUpperCase(), cls, detail: status.error || reasons};
  }
  if (status.run_block && ['setup_ready', 'confirmed', 'stopped'].includes(status.state)) {
    return {headline: 'Lauf gesperrt', cls: 'error', detail: status.run_block};
  }
  const setup = status.setup || {};
  const elapsed = typeof setup.elapsed_s === 'number' && Number.isFinite(setup.elapsed_s)
    ? ` (${setup.elapsed_s.toFixed(1)} s)` : '';
  const labels = {
    idle: 'Bereit zur Einrichtung', setup_running: `Einrichtung läuft: ${setup.step || ''}${elapsed}`,
    setup_ready: 'Vorschlag prüfen und bestätigen', setup_failed: 'Einrichtung abgebrochen',
    confirmed: 'Bestätigt – Lauf starten', running: 'Lauf startet …', stopped: 'Lauf beendet',
  };
  return {headline: labels[status.state] || status.state, cls: status.error ? 'error' : '', detail: status.error || setup.message || ''};
}

function trackingHintText(hint) {
  if (hint?.kind === 'anzeige_bewegt' && Number.isFinite(hint.shift_px) && Number.isFinite(hint.rotation_deg)) {
    const shift = Math.round(hint.shift_px).toLocaleString('de-DE');
    const rotation = Math.abs(hint.rotation_deg).toLocaleString('de-DE', {
      minimumFractionDigits: 1, maximumFractionDigits: 1});
    return `Anzeige hat sich bewegt (ca. ${shift} px (Ecken), ${rotation} Grad) – Werte werden nicht freigegeben. Bitte neu einrichten.`;
  }
  if (hint?.kind === 'rahmen_verdeckt') {
    return 'Rahmen verdeckt? Hand oder Gegenstand vom Rahmen nehmen. Werte werden nicht freigegeben.';
  }
  if (hint?.kind === 'unbekannt') {
    return 'Anzeige nicht sicher wiedergefunden. Bitte Sicht auf den Rahmen prüfen und bei Bedarf neu einrichten. Werte werden nicht freigegeben.';
  }
  return '';
}

export function connectionView(status, lastOkMs, nowMs, httpStatus) {
  if (httpStatus === null || httpStatus < 200 || httpStatus >= 300 ||
      lastOkMs === null || nowMs - lastOkMs > 1500) {
    return {headline: 'STALE', cls: 'stale', detail: httpStatus === 401
      ? 'Anmeldung abgelaufen' : 'Verbindung zur Werkbank verloren'};
  }
  return statusView(status);
}

if (typeof document !== 'undefined') {
  let csrf = '';
  let regionBusy = false;
  let refreshSequence = 0;
  let trackingReasons = null;
  let fullStatusReceived = false;
  let actionError = '';
  let lastStatus = null;
  let lastOkMs = null;
  let httpStatus = null;
  const $ = (id) => document.getElementById(id);
  const renderError = (status = lastStatus) => {
    $('error').textContent = [status?.error, actionError].filter(Boolean).join('\n');
  };
  const post = async (path, body) => {
    const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json',
      'X-CSRF-Token': csrf}, body: JSON.stringify(body || {})});
    const data = await response.json().catch(() => ({}));
    actionError = response.ok ? '' : data.error || response.statusText;
    renderError();
    return response.ok;
  };
  const renderView = (view) => {
    $('headline').textContent = view.headline;
    $('headline').className = `value ${view.cls}`;
    $('detail').textContent = view.detail;
  };
  const renderConnection = () => renderView(connectionView(lastStatus, lastOkMs,
    performance.now(), httpStatus));
  const render = (s) => {
    if (s.session_id !== lastStatus?.session_id ||
        s.setup?.proposal_revision !== lastStatus?.setup?.proposal_revision) {
      $('confirmed-by').value = '';
      $('format-checked').checked = false;
      $('ack').checked = false;
      $('use-tolerance').checked = false;
      $('test-override').checked = false;
    }
    $('run-block').hidden = !s.run_block;
    $('run-block-reason').textContent = s.run_block || '';
    $('test-override-box').hidden = !s.run_block;
    $('test-banner').hidden = !s.test_run;
    $('tolerance-banner').hidden = !s.reader_tolerance;
    $('tolerance-banner').textContent = s.reader_tolerance
      ? `Angepasste Lesetoleranz ×${s.reader_tolerance.factor}: Werte nur in dieser Aufstellung gegen Referenz geprüft, nicht validiert.` : '';
    const metrics = s.setup?.gegenlesen?.metrics || {};
    const tolerance = metrics.tolerance;
    $('proposal-hint').hidden = !(s.state === 'setup_ready' && metrics.hinweis);
    $('proposal-hint').textContent = metrics.hinweis ? `Hinweis: ${metrics.hinweis}` : '';
    $('tolerance-label').hidden = !tolerance?.possible;
    $('tolerance-text').textContent = tolerance?.possible
      ? `Angepasste Toleranz ×${tolerance.factor} verwenden – Lesung nur in dieser Aufstellung gegen den Referenzwert geprüft, nicht validiert` : '';
    if (!tolerance?.possible) $('use-tolerance').checked = false;
    $('proposal-block').hidden = !(s.run_block && s.state === 'setup_ready');
    $('proposal-block').textContent = tolerance?.possible
      ? 'Achtung: Der strikte Lauf ist gesperrt. Angepasste Toleranz kann ausdrücklich gewählt werden; sonst ist nur ein Testlauf möglich.'
      : 'Achtung: Mit diesem Vorschlag ist der Lauf gesperrt (siehe unten). Bestätigen ist möglich, ein Lauf nur als Testlauf.';
    $('run-start').disabled = Boolean(s.run_block && !$('test-override').checked);
    csrf = s.csrf;
    $('notice').textContent = s.release_notice;
    const storage = s.storage;
    $('storage-status').textContent = storage?.free_bytes == null
      ? storage?.message || 'Speicherplatz nicht verfuegbar'
      : `${storage.level === 'error' ? 'Speicher knapp: ' : storage.level === 'warn' ? 'Warnung: unter 5 GB frei. ' : ''}` +
        `SD-Speicher: ${(storage.free_bytes / 1e9).toFixed(2).replace('.', ',')} GB frei`;
    $('storage-status').className = storage?.level === 'ok' ? '' : storage?.level === 'warn' ? 'transition' : 'error';
    renderView(statusView(s));
    const causes = s.state === 'running' ? s.run?.rejection_causes : null;
    $('recent-causes').hidden = !(causes?.frames && causes.causes?.length);
    $('recent-causes-list').replaceChildren(...(causes?.causes || []).map(cause => {
      const item = document.createElement('li');
      item.textContent = `${cause.explanation} · ${Math.round(100 * cause.fraction)} % der Bilder`;
      return item;
    }));
    $('recent-causes-limit').textContent = causes?.limited ? 'Fenster wegen hoher Bildrate begrenzt' : '';
    const cam = s.camera || {};
    $('camera').textContent = cameraView(cam);
    $('reference-status').textContent = s.reference?.restoring ? 'Werte werden zurückgestellt …'
      : s.reference?.error ? s.reference.error
      : s.reference?.enabled ? `Referenz: ${s.reference.lines} Telegramme`
      : `ohne Referenz: ${s.reference?.reason || 'nicht gestartet'}`;
    const diag = s.diagnostics;
    $('diagnostics-enabled').disabled = s.state === 'running';
    $('diagnostics-status').textContent = (diag?.enabled
      ? `Diagnose: ${diag.saved} Bilder, ${(diag.bytes / 1e6).toFixed(1)} MB; Queue verworfen: ${diag.dropped_queue}, ` +
        `Limit verworfen: ${diag.dropped_limit}, RAM verworfen: ${diag.dropped_memory ?? 0}, ` +
        `Markenbilder verworfen: ${diag.dropped_mark_rate ?? 0}, Schreibfehler: ${diag.write_errors}`
      : `Diagnose aus: ${diag?.reason || 'nicht gestartet'}`) +
      (s.diagnose_kopie ? ' · Diagnose wird kopiert …' : '') +
      (diag?.first_error ? ` · ${diag.first_error} · RAM-Ablage: ${diag.staging || '—'}` : '') +
      (diag?.copied ? ' · Kopie gesichert' : '') +
      (s.diagnostic_leftovers || []).map(item => ` · Verbliebene RAM-Ablage: ${item.path} (` +
        `${item.bytes == null ? 'Größe unbekannt' : (item.bytes / 1e6).toFixed(1) + ' MB'})`).join('');
    $('mark-box').hidden = s.state !== 'running';
    $('last-mark').textContent = s.last_mark
      ? `Letzte Marke (Meldezeit): ${s.last_mark.received_at_utc} · ${s.last_mark.text}` : '';
    renderError(s);
    $('setup-state').textContent = s.setup?.overall ? `Gesamturteil: ${s.setup.overall}` : '';
    $('setup-checks').textContent = Object.entries(s.setup?.checks || {}).map(([name, status]) => {
      const label = name === 'nachfuehrung' ? 'Nachführung' : name;
      const reason = s.setup?.check_reasons?.[name];
      return `${label}: ${status ?? 'nicht geprüft'}${reason ? ` – ${reason}` : ''}`;
    }).join('\n');
    const mode = s.run?.tracking?.mode ?? s.profile?.tracking_mode;
    $('tracking-mode').textContent = mode === 'rahmenbereiche' ? 'Nachführung: Rahmenbereiche'
      : mode === 'ecc_alt' ? 'Nachführung: alt (ECC, inhaltsabhängig) – neu einrichten empfohlen'
      : mode === 'injiziert' ? 'Nachführung: injiziert' : '';
    const editable = s.state === 'setup_ready' && s.setup?.proposal_revision != null;
    $('region-editor').hidden = !editable;
    $('region-add').disabled = !editable || regionBusy;
    $('confirm').disabled = regionBusy;
    if (s.session_id !== lastStatus?.session_id || !editable) $('edit-regions').checked = false;
    $('region-selection').textContent = `Auswahl: ${s.setup?.auswahl || 'automatisch'}`;
    const regions = s.setup?.regions || [];
    if (s.setup?.proposal_revision !== lastStatus?.setup?.proposal_revision || s.state !== lastStatus?.state) {
      $('region-list').replaceChildren(...regions.map((region, index) => {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = `Bereich ${index + 1} entfernen (${region.centre.join(', ')})`;
        button.disabled = !editable;
        button.onclick = () => editRegions([], [index], s.setup.proposal_revision);
        item.append(button);
        return item;
      }));
    }
    const reasons = {im_zeichenbereich: 'im Zeichenbereich', ausserhalb_rahmenband: 'außerhalb des Rahmenbands',
      am_bildrand: 'am Bildrand', zu_wenig_struktur: 'zu wenig zweidimensionale Struktur',
      mehrdeutig: 'mehrdeutige Struktur', zu_nah: 'zu nah an einem anderen Bereich'};
    $('region-results').textContent = (s.setup?.centre_results || []).map(result => {
      const requested = result.requested_centre || result.centre;
      const used = result.used_centre === undefined ? result.centre : result.used_centre;
      return `${requested.join(',')} (verwendet: ${used ? used.join(',') : 'kein Mittelpunkt'}): ` +
        `${result.ok ? 'geeignet' : reasons[result.reason] || result.reason}`;
    }).join('\n');
    // Bilder und fokussierte Entfernen-Schaltflaechen zwischen Statuspolls erhalten.
    if (s.session_id !== lastStatus?.session_id || s.setup?.proposal_revision !== lastStatus?.setup?.proposal_revision ||
        JSON.stringify(s.setup?.overlays) !== JSON.stringify(lastStatus?.setup?.overlays)) {
      $('overlays').replaceChildren(...(s.setup?.overlays || []).map((name) => {
        const img = document.createElement('img');
        img.src = `/live/setup/${name}.png?${s.session_id}&${s.setup?.proposal_revision ?? ''}`;
        img.alt = name;
        if (name === 'overlay_source') {
          img.className = $('edit-regions').checked ? 'region-editing' : '';
          img.onclick = (event) => {
            if (!$('edit-regions').checked || !img.naturalWidth || !img.naturalHeight) return;
            const box = img.getBoundingClientRect();
            const x = Math.floor((event.clientX - box.left) * img.naturalWidth / box.width);
            const y = Math.floor((event.clientY - box.top) * img.naturalHeight / box.height);
            const index = regions.findIndex(region => Math.abs(x - region.centre[0]) <= region.size / 2 &&
              Math.abs(y - region.centre[1]) <= region.size / 2);
            return editRegions(index < 0 ? [[x, y]] : [], index < 0 ? [] : [index], s.setup.proposal_revision);
          };
        }
        return img;
      }));
    }
    $('confirm-box').hidden = s.state !== 'setup_ready';
    $('ack-label').hidden = !(s.setup && s.setup.overall === 'WARNUNG');
  };
  const refresh = async () => {
    const sequence = ++refreshSequence;
    try {
      const response = await fetch(fullStatusReceived ? '/live/status' : '/live/status?full=1');
      httpStatus = response.status;
      if (response.ok) {
        const status = await response.json();
        if (sequence !== refreshSequence) return;
        fullStatusReceived = true;
        if (status.tracking_reasons) trackingReasons = status.tracking_reasons;
        status.tracking_reasons = trackingReasons;
        render(status);
        lastStatus = status;
        lastOkMs = performance.now();
      } else {
        renderConnection();
      }
    } catch {
      httpStatus = null;
      renderConnection();
    }
  };
  const tick = async () => {
    try { await refresh(); } finally {
      $('preview').src = `/live/preview.jpg?${Date.now()}`;
      setTimeout(tick, 500);
    }
  };
  const editRegions = async (add, remove, revision) => {
    if (regionBusy || lastStatus?.state !== 'setup_ready') return;
    regionBusy = true;
    $('region-add').disabled = true;
    $('confirm').disabled = true;
    try {
      if (await post('/live/setup/regions', {proposal_revision: revision, add, remove})) await refresh();
    } catch {
      actionError = 'Bereichsänderung nicht bestätigt – Verbindung prüfen und erneut versuchen.';
      renderError();
    } finally {
      regionBusy = false;
      $('region-add').disabled = lastStatus?.state !== 'setup_ready';
      $('confirm').disabled = false;
    }
  };
  $('edit-regions').onchange = () => {
    for (const img of $('overlays').children) {
      if (img.alt === 'overlay_source') img.className = $('edit-regions').checked ? 'region-editing' : '';
    }
  };
  $('region-add').onclick = () => {
    const text = $('region-coordinates').value.trim();
    if (!/^-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?$/.test(text)) {
      actionError = 'Koordinaten als x,y eingeben, zum Beispiel 320,240.';
      renderError();
      return;
    }
    return editRegions([text.split(',').map(Number)], [], lastStatus?.setup?.proposal_revision);
  };
  $('setup').onclick = () => post('/live/setup', {cell_text: $('cell-text').value || null});
  $('confirm').onclick = () => post('/live/confirm', {session_id: lastStatus?.session_id, confirmed_by: $('confirmed-by').value,
    format_checked: $('format-checked').checked, acknowledge_warning: $('ack').checked,
    use_tolerance: $('use-tolerance').checked,
    ...(lastStatus?.setup?.proposal_revision != null ? {proposal_revision: lastStatus.setup.proposal_revision} : {})});
  $('test-override').onchange = () => {
    $('run-start').disabled = Boolean(lastStatus?.run_block && !$('test-override').checked);
  };
  $('run-start').onclick = () => {
    const override = Boolean(lastStatus?.run_block && $('test-override').checked);
    if (lastStatus?.run_block && !override) return;
    if (override && !window.confirm('TESTLAUF starten?\n\nDie Lesesperre wird übergangen. Angezeigte Vermutungen und Werte sind nicht freigegeben und dürfen nicht für Messungen verwendet werden. Der Lauf wird als Testlauf gekennzeichnet (TESTLAUF.json).')) return;
    // Jeder Testlauf braucht einen neuen Haken.
    if (override) $('test-override').checked = false;
    const schedule = $('norm-schedule').value.trim();
    if (schedule && !$('reference-enabled').checked) {
      actionError = 'Werteplan braucht Referenzaufzeichnung';
      renderError();
      return;
    }
    if (schedule && !window.confirm('Werteplan anwenden? Der Plan schreibt in den RAM des GSV-2AS. Beim Stoppen werden die Ausgangswerte zurückgestellt und geprüft. Gerät verbunden lassen.')) return;
    return post('/live/run/start', {test_override: override,
      reference: $('reference-enabled').checked, norm_schedule: schedule || null,
      diagnostics: $('diagnostics-enabled').checked});
  };
  $('run-stop').onclick = () => post('/live/run/stop');
  $('run-mark').onclick = () => post('/live/run/mark', {text: $('mark-text').value});
  $('camera-start').onclick = () => post('/live/camera/start');
  setInterval(renderConnection, 500);
  tick();
}
