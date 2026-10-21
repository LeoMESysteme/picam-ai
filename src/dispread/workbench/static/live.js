// Live-Seite: zeigt LiveService.status() an und reicht Bedienschritte weiter.
// Entscheidungen fallen im Server (dispread.live), nie hier.

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
    const reasons = run.reject_reasons.join(', ');
    if (status.state === 'running' && run.status === 'valid' && fresh) {
      return {headline: `${run.raw_text} ${run.unit}`, cls: 'valid', detail: `Bild ${run.frame_sequence}`};
    }
    const cls = !fresh || run.status === 'valid' ? 'stale' : run.status;
    if (run.reject_reasons[0]?.startsWith('tracking_lost:')) {
      return {headline: cls.toUpperCase(), cls,
        detail: `Anzeige verloren — Kamera bewegt? Neu einrichten (${reasons})`};
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
  };
  const renderView = (view) => {
    $('headline').textContent = view.headline;
    $('headline').className = `value ${view.cls}`;
    $('detail').textContent = view.detail;
  };
  const renderConnection = () => renderView(connectionView(lastStatus, lastOkMs,
    performance.now(), httpStatus));
  const render = (s) => {
    if (s.session_id !== lastStatus?.session_id) {
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
    renderView(statusView(s));
    const cam = s.camera || {};
    $('camera').textContent = cam.running ? `Kamera läuft, ${cam.frames} Bilder, ${cam.gaps} Lücken`
      : `Kamera aus: ${cam.error || '—'}`;
    $('reference-status').textContent = s.reference?.restoring ? 'Werte werden zurückgestellt …'
      : s.reference?.error ? s.reference.error
      : s.reference?.enabled ? `Referenz: ${s.reference.lines} Telegramme`
      : `ohne Referenz: ${s.reference?.reason || 'nicht gestartet'}`;
    renderError(s);
    $('setup-state').textContent = s.setup?.overall ? `Gesamturteil: ${s.setup.overall}` : '';
    $('overlays').replaceChildren(...(s.setup?.overlays || []).map((name) => {
      const img = document.createElement('img');
      img.src = `/live/setup/${name}.png?${s.session_id}`;
      img.alt = name;
      return img;
    }));
    $('confirm-box').hidden = s.state !== 'setup_ready';
    $('ack-label').hidden = !(s.setup && s.setup.overall === 'WARNUNG');
  };
  const tick = async () => {
    try {
      const response = await fetch('/live/status');
      httpStatus = response.status;
      if (response.ok) {
        const status = await response.json();
        render(status);
        lastStatus = status;
        lastOkMs = performance.now();
      } else {
        renderConnection();
      }
    } catch {
      httpStatus = null;
      renderConnection();
    } finally {
      $('preview').src = `/live/preview.jpg?${Date.now()}`;
      setTimeout(tick, 500);
    }
  };
  $('setup').onclick = () => post('/live/setup', {cell_text: $('cell-text').value || null});
  $('confirm').onclick = () => post('/live/confirm', {session_id: lastStatus?.session_id, confirmed_by: $('confirmed-by').value,
    format_checked: $('format-checked').checked, acknowledge_warning: $('ack').checked,
    use_tolerance: $('use-tolerance').checked});
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
      reference: $('reference-enabled').checked, norm_schedule: schedule || null});
  };
  $('run-stop').onclick = () => post('/live/run/stop');
  $('camera-start').onclick = () => post('/live/camera/start');
  setInterval(renderConnection, 500);
  tick();
}
