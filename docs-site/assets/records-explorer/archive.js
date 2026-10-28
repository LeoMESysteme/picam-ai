/* Published sessions use the existing parser, cursors, zoom and A/B views. */
(function () {
  "use strict";
  const abort = new AbortController();
  window.addEventListener("pagehide", () => abort.abort(), { once: true });
  const params = new URLSearchParams(location.search);
  const context = document.createElement("aside"); context.className = "archive-context"; context.hidden = true;
  context.style.cssText = "padding:10px 20px;border-bottom:1px solid var(--line);font:13px var(--sans);color:var(--ink-2);white-space:pre-line";
  document.querySelector(".bar").after(context);
  const originalView = setView;
  setView = function (view) {
    originalView(view);
    const lines = [];
    for (const [tag, record] of Object.entries(FILES)) {
      if (!record) continue;
      const run = record.sessionContext;
      if (run) {
        lines.push(`${tag}: ${run.id} · ${run.device_id} · Start (UTC): ${run.started_at_utc || "unbekannt"}`);
        if (run.test_run) lines.push(`${tag}: TESTLAUF – nicht für Messungen verwenden. Aufgezeichnetes VALID ist kein Richtigkeitsnachweis.`);
        for (const warning of run.warnings || []) lines.push(`${tag}: ${window.SessionFiles.warning(warning)}`);
      } else lines.push(`${tag}: Lokale Einzeldatei ohne Session-Metadaten; Testlauf und Toleranzstatus unbekannt.`);
      if (!record.timeBearing) lines.push(`${tag}: Keine belastbare Aufnahmezeitbasis. Die Achse zeigt den Frameindex; keine Dauer oder Leserate ableiten.`);
    }
    lines.push("A/B wird relativ ausgerichtet; keine physikalische Synchronität nachgewiesen. Konfidenz ist keine Fehlerwahrscheinlichkeit.");
    context.textContent = lines.join("\n"); context.hidden = !FILES.A;
  };
  async function open(run, slot) {
    const manifest = await window.SessionFiles.manifest(run, abort.signal);
    const entry = manifest.files.find(file => file.name === "records.jsonl");
    if (!entry) throw new Error("Diese Session enthält keine lesbare records.jsonl. Hinweise und übrige Dateien stehen in der Wiki-Dateiliste.");
    const file = window.SessionFiles.file(entry, abort.signal); file.sessionContext = run;
    await loadFile(file, slot);
    if (!FILES[slot]) throw new Error("Session konnte nicht ausgewertet werden.");
  }
  async function start() {
    if (!params.get("a")) return;
    const catalog = await window.SessionFiles.catalog(abort.signal);
    const find = id => { const run = catalog.runs.find(row => row.id === id); if (!run) throw new Error("Session nicht im veröffentlichten Archiv gefunden."); return run; };
    await open(find(params.get("a")), "A");
    if (params.get("b")) await open(find(params.get("b")), "B");
  }
  // The transport is deferred in the head; all original synchronous UI setup
  // has completed by DOMContentLoaded. Local file mode still works offline.
  window.addEventListener("DOMContentLoaded", () => start().catch(error => {
    if (abort.signal.aborted) return;
    context.hidden = false; context.textContent = error.message;
    document.getElementById("introError").textContent = error.message;
    document.getElementById("introError").hidden = false;
  }), { once: true });
})();
