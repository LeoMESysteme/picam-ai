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
    return {headline: cls.toUpperCase(), cls, detail: status.error || reasons};
  }
  const labels = {
    idle: 'Bereit zur Einrichtung', setup_running: `Einrichtung läuft: ${status.step || ''}`,
    setup_ready: 'Vorschlag prüfen und bestätigen', setup_failed: 'Einrichtung abgebrochen',
    confirmed: 'Bestätigt – Lauf starten', running: 'Lauf startet …', stopped: 'Lauf beendet',
  };
  return {headline: labels[status.state] || status.state, cls: status.error ? 'error' : '', detail: status.error || ''};
}

if (typeof document !== 'undefined') {
  let csrf = '';
  const $ = (id) => document.getElementById(id);
  const post = async (path, body) => {
    const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json',
      'X-CSRF-Token': csrf}, body: JSON.stringify(body || {})});
    const data = await response.json().catch(() => ({}));
    $('error').textContent = response.ok ? '' : (data.error || response.statusText);
  };
  const render = (s) => {
    csrf = s.csrf;
    $('notice').textContent = s.release_notice;
    const view = statusView(s);
    $('headline').textContent = view.headline;
    $('headline').className = `value ${view.cls}`;
    $('detail').textContent = view.detail;
    const cam = s.camera || {};
    $('camera').textContent = cam.running ? `Kamera läuft, ${cam.frames} Bilder, ${cam.gaps} Lücken`
      : `Kamera aus: ${cam.error || '—'}`;
    $('setup-state').textContent = s.setup ? `Gesamturteil: ${s.setup.overall}` : '';
    $('overlays').replaceChildren(...(s.setup ? s.setup.overlays : []).map((name) => {
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
      if (response.ok) render(await response.json());
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
  tick();
}
