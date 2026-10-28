/* The same verified, lazy file transport serves the wiki and the original explorer. */
(function () {
  "use strict";
  const root = new URL("sessions/", document.currentScript.src);
  async function json(url, signal) {
    const response = await fetch(url, { signal, credentials: "same-origin", redirect: "error" });
    if (!response.ok || !(response.headers.get("content-type") || "").includes("json")) {
      throw new Error("Archiv nicht erreichbar. Bitte Anmeldung prüfen und die Seite neu laden.");
    }
    return response.json();
  }
  function member(path) {
    if (typeof path !== "string" || !/^[A-Za-z0-9_./-]+$/.test(path) || path.startsWith("/") || path.split("/").some(p => p === ".." || p === "." || !p)) {
      throw new Error("Ungültiger Archivpfad.");
    }
    const url = new URL(path, root);
    if (url.origin !== root.origin || !url.href.startsWith(root.href)) throw new Error("Fremder Archivpfad.");
    return url;
  }
  async function digest(bytes, expected) {
    if (!/^[a-f0-9]{64}$/.test(expected || "")) throw new Error("Prüfsumme fehlt.");
    const result = await crypto.subtle.digest("SHA-256", bytes);
    const actual = Array.from(new Uint8Array(result), b => b.toString(16).padStart(2, "0")).join("");
    if (actual !== expected) throw new Error("Prüfsumme stimmt nicht. Datei wird nicht verwendet.");
  }
  async function catalog(signal) {
    const data = await json(new URL("catalog.json", root), signal);
    if (data.schema !== "sessions/1" || data.stats_version !== "sessions-stats/1" || !Array.isArray(data.runs) || !Array.isArray(data.groups)) throw new Error("Unbekanntes Archivformat.");
    return data;
  }
  async function manifest(run, signal) {
    const data = await json(member(run.manifest), signal);
    if (data.schema !== "session-files/1" || data.id !== run.id || !Array.isArray(data.files)) throw new Error("Manifest passt nicht zur Session.");
    return data;
  }
  function file(entry, signal) {
    if (!globalThis.DecompressionStream) throw new Error("Dieser Browser kann das Archiv nicht entpacken. Die komprimierten Dateiteile stehen in der Dateiliste zum Download bereit.");
    if (typeof entry.name !== "string" || /[/\\]/.test(entry.name) || !Number.isSafeInteger(entry.size) || entry.size < 0 || !Array.isArray(entry.parts)) throw new Error("Ungültige Dateibeschreibung.");
    async function* blocks() {
      let total = 0;
      for (const part of entry.parts) {
        if (!Number.isSafeInteger(part.size) || part.size < 0 || part.size > 25 * 1024 * 1024 || !Number.isSafeInteger(part.raw_size) || part.raw_size < 0 || part.raw_size > 8 * 1024 * 1024) throw new Error("Ungültige Blockgröße.");
        const response = await fetch(member(part.path), { signal, credentials: "same-origin", redirect: "error" });
        if (!response.ok || response.headers.get("content-encoding")) throw new Error("Dateiteil nicht unverändert erreichbar. Bitte Anmeldung prüfen.");
        const packed = await response.arrayBuffer();
        if (packed.byteLength !== part.size) throw new Error("Dateiteil unvollständig.");
        await digest(packed, part.sha256);
        const stream = new Blob([packed]).stream().pipeThrough(new DecompressionStream("gzip"));
        const reader = stream.getReader();
        const pieces = []; let size = 0;
        try {
          for (;;) {
            const { value, done } = await reader.read(); if (done) break;
            size += value.byteLength;
            if (size > part.raw_size) throw new Error("Entpackter Dateiteil größer als angekündigt.");
            pieces.push(value);
          }
        } finally { await reader.cancel().catch(() => {}); }
        if (size !== part.raw_size) throw new Error("Entpackter Dateiteil unvollständig.");
        const raw = new Uint8Array(size); let offset = 0;
        for (const piece of pieces) { raw.set(piece, offset); offset += piece.byteLength; }
        await digest(raw, part.raw_sha256);
        total += size; yield raw;
      }
      if (total !== entry.size) throw new Error("Originalgröße stimmt nicht.");
    }
    return { name: entry.name, size: entry.size, stream() {
      const iterator = blocks();
      return new ReadableStream({ async pull(controller) {
        try { const { value, done } = await iterator.next(); if (done) controller.close(); else controller.enqueue(value); }
        catch (error) { controller.error(error); }
      }, async cancel() { await iterator.return(); } });
    } };
  }
  async function download(entry, signal) {
    const source = file(entry, signal);
    const blob = await new Response(source.stream()).blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = entry.name; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }
  const warnings = {
    "missing-profile": "Profil fehlt im Archiv.", "missing-confirmation": "Bestätigung fehlt im Archiv.",
    "unreadable-records": "Messdatei nicht lesbar; keine auswertbaren Beobachtungen.",
    "frame-count-mismatch": "Frameanzahl weicht von der Session-Zusammenfassung ab.",
    "tracking-count-mismatch": "Dokumentierte Trackingverluste und Auditgründe stimmen nicht überein.",
    "no-records": "Keine auswertbaren Datensätze.", "capture-time-unavailable": "Aufnahmezeitbasis nicht auswertbar; keine Leserate.",
    "invalid-record-lines": "Einige Zeilen konnten nicht ausgewertet werden; Originaldatei bleibt unverändert.",
    "reader-tolerance-unvalidated": "Erhöhte Lesetoleranz; nicht validiert.",
    "unvalidated-reader-tolerance": "Erhöhte Lesetoleranz; nicht validiert.",
  };
  window.SessionFiles = { catalog, manifest, file, download, member, warning: code => warnings[code] || code };
})();
