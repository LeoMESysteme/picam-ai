// Live-Seite: zeigt LiveService.status() an und reicht Bedienschritte weiter.
// Entscheidungen fallen im Server (dispread.live), nie hier.

export function statusView(status) {
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
    return {headline: cls.toUpperCase(), cls, detail: status.error || reasons};
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
    $('error').textContent = status?.error || actionError;
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
    csrf = s.csrf;
    $('notice').textContent = s.release_notice;
    renderView(statusView(s));
    const cam = s.camera || {};
    $('camera').textContent = cam.running ? `Kamera läuft, ${cam.frames} Bilder, ${cam.gaps} Lücken`
      : `Kamera aus: ${cam.error || '—'}`;
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
  $('confirm').onclick = () => post('/live/confirm', {confirmed_by: $('confirmed-by').value,
    format_checked: $('format-checked').checked, acknowledge_warning: $('ack').checked});
  $('run-start').onclick = () => post('/live/run/start');
  $('run-stop').onclick = () => post('/live/run/stop');
  $('camera-start').onclick = () => post('/live/camera/start');
  setInterval(renderConnection, 500);
  tick();
}
