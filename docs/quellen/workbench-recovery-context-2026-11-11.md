# Wiederherstellungskontext für Workbench und EXE

[Archiv](workbench-recovery-context-2026-11-11.zip),
[SHA-256](workbench-recovery-context-2026-11-11.sha256).
Ergänzt den [kritischen Auftrag](../WORKBENCH_BLOCKER.md).

## Kandidatenstände erhalten

Von `bruecke-ui` (`8335abf`) und `bruecke-ux` (`2c5be9b`) liegen jeweils
committeter Quellstand, binärfähiger Git-Patch der relevanten getrackten
Dateien und zusätzliche neue Source-/Testdateien vor. Metadaten nennen
Umfang, HEAD und Sicherungszeit. Patch vor/nach Sicherung unverändert.
Dies sind ungeprüfte Arbeitskandidaten, keine ausgerollten oder abgenommenen
Fixes. Andere lokale Änderungen beim Weiterarbeiten erhalten.

Wiederaufbau auf vollständigem Checkout des jeweiligen HEAD: Patch mit
`git apply --check` prüfen und anwenden, danach `untracked/` relativ zum
Checkout übernehmen. Fremde Änderungen vorher sichern.

Für vollständig offline verfügbaren **Code** enthält der Tar den Unterordner
`source/`. Dort nur die enthaltenen Code-/Testpfade des Patches anwenden:

```bash
git apply --check --include='src/**' --include='tests/**' --include='windows/**' /pfad/zum/tracked.patch
git apply --include='src/**' --include='tests/**' --include='windows/**' /pfad/zum/tracked.patch
```

Die Code-Patches beider Kandidaten wurden gegen die jeweils frisch
entpackten Quellen erfolgreich geprüft. Der vollständige Patch enthält
zusätzlich Dokuänderungen, deren Basisdateien im Teilquellpaket fehlen;
dafür vollständigen Checkout verwenden. Kein vollständiger Git-Checkout,
keine getestete Funktionsfreigabe und kein ausgerollter Dienststand.

## Passive Versionsbeobachtung

`passive-capture/` enthält lesende Statusbeobachtungen und nach Inhalts-Hash
abgelegte Versionen vorhandener Setup-Dateien. Der Beobachter öffnete keine
Kamera und änderte keinen Servicezustand. Herkunft und beobachtete Dateizeit
stehen in `file-versions.jsonl`; diese FILE_MTIME ist keine Sensorzeit.
Auch dieses Verfahren erhält nur tatsächlich auf Platte geschriebene Bilder,
keine nachträglich erzeugten Rohbilder oder verlorenen Stabilitätsproben.

Aktuelle bestätigte Referenzen und deren ausführbares Offline-Rezept liegen
im [separaten Regressionspaket](workbench-positive-regression-2026-11-11.md).
