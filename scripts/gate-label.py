#!/usr/bin/env python3
"""Offline-Gate fuer eine `sync-record.py`-Aufzeichnung - Task F aus
docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md.

Aufruf:

    ./.venv/bin/python scripts/gate-label.py \\
        --recording var/diagnostics/lauf1 \\
        --guard-margin-ms 250 --max-gap-ms 700 \\
        --output var/diagnostics/lauf1/proposal.json

Zweck: entscheidet, offline, welche Bilder einer Aufzeichnung einen Sollwert
aus dem seriellen Strom bekommen duerfen. Legt KEINE Datensatzproben an -
das ist eine spaetere, getrennte Aufgabe mit Menschenbeteiligung
(`DatasetStore` wird hier nicht einmal importiert). Ergebnis ist ein
Bericht auf stdout und eine Vorschlagsdatei (JSON).

Reiner Diagnosecode, Stil an `dataset-benchmark.py`/`sync-record.py`
angelehnt.

## Die Gate-Regel

Modellherleitung: siehe Plan, Abschnitt "Der Kern: das Schutzintervall". Ein
Lauf gleicher Telegrammzeichenketten von Telegramm i bis j (naechstes
ABWEICHENDES Telegramm: j+1) zeigt seinen Wert sicher waehrend
`[t_i + M, t_{j+1} - M)` - UNTERE Grenze eingeschlossen, OBERE Grenze
ausgeschlossen (Festlegung, siehe unten). Exakte Zeichenkettengleichheit,
keine Toleranz (Festlegung 1 des Plans).

`--guard-margin-ms` (M) und `--max-gap-ms` haben ABSICHTLICH keinen
Vorgabewert. Beides sind offene Messgroessen/Festlegungen
(M: Task B des Plans; max-gap-ms: Schwelle fuer Telegrammluecken, noch
unbegruendet) - ein erfundener Default wuerde eine Zahl vortaeuschen, die
niemand gemessen hat.

## Vier Ablehnungsgruende (siehe Aufgabenbeschreibung, alle vier gezaehlt)

1. **Wertwechsel im Fenster** (`wertwechsel_im_fenster`): Bild faellt in den
   `+-M`-Randbereich um einen echten Telegrammwechsel. Enthaelt auch den
   Randbereich VOR dem allerersten Lauf (`[t_min, t_min+M)`) - strukturell
   derselbe Schutzmechanismus (unbekannter Uebergang), auch wenn dort kein
   tatsaechlicher Wertwechsel bekannt ist, weil nichts davor liegt.
2. **Ausserhalb des Telegrammbereichs** (`ausserhalb_telegrammbereich`):
   Bildzeitstempel < erstes Telegramm oder > letztes Telegramm ueberhaupt.
   Ueber diese Zeit ist nichts bekannt, es wird nicht extrapoliert.
3. **Letzter Lauf ohne Folgetelegramm** (`letzter_lauf_ohne_folgetelegramm`):
   der ALLERLETZTE Lauf des Stroms hat kein abweichendes Folgetelegramm -
   sein Ende ist unbekannt. Er wird konservativ mit dem Zeitstempel seines
   letzten TELEGRAMMS abgeschlossen (`[t_i + M, t_j - M)`), nicht mit einer
   unterstellten Dauer. Bilder danach (bis zum letzten Telegramm) fallen in
   diesen Ablehnungsgrund.
4. **Telegrammluecke** (`telegrammluecke`): der Abstand zwischen zwei
   aufeinanderfolgenden Telegrammen desselben Laufs uebersteigt
   `--max-gap-ms`. Entscheidung (dokumentiert wie verlangt): der Lauf wird
   an der Luecke GETEILT, nicht komplett verworfen - das ist die genauere
   Loesung, weil nur die tatsaechlich unsichere Stelle (in der ein anderer,
   nie angekommener Wert gestanden haben kann) verworfen wird, waehrend der
   Rest des Laufs weiter nutzbar bleibt. Der Teil VOR der Luecke schliesst
   konservativ mit seinem letzten Telegramm ab (wie Fall 3, da sein "Ende"
   durch die Luecke ebenso unbekannt ist), der Teil NACH der Luecke beginnt
   normal ab seinem ersten Telegramm.

## Fenstergrenzen: geschlossen/offen

`[t_i + M, t_{j+1} - M)` wird woertlich als Halboffen gelesen: die UNTERE
Grenze ist eingeschlossen (ein Bild GENAU bei `t_i + M` darf gelabelt
werden), die OBERE Grenze ist ausgeschlossen (ein Bild GENAU bei
`t_{j+1} - M` wird abgelehnt). Halboffen ist die einzige Form, die keinen
Zeitpunkt zwei benachbarten Fenstern gleichzeitig zuordnet - EIN Zeitpunkt
gehoert also nie zu zwei Fenstern. WELCHE der beiden Seiten geschlossen ist,
ist eine Festlegung, keine Notwendigkeit; hier: unten zu, oben auf, wie die
Klammerschreibweise des Plans es bereits vorgibt.

## Woher `label_origin_detail` kommt

`_SERIAL_ASCII_DETAIL_REQUIRED` aus `src/dispread/workbench/datasets.py`
(NUR gelesen, nicht importiert - dieses Skript legt keine Proben an und
haengt damit nicht von `DatasetStore` ab) legt die Pflichtschluessel fest:
`source_port`, `guard_margin_ms`, `plateau_start_ns`, `plateau_end_ns`,
`telegram_count`. Namen hier bewusst identisch uebernommen.

`plateau_start_ns`/`plateau_end_ns` sind die Zeitstempel des ERSTEN und
LETZTEN Telegramms, die den labelnden (Teil-)Lauf tragen (das Plateau der
Zeichenkette selbst) - NICHT das bereits um M geschrumpfte sichere Fenster.
`guard_margin_ms` (M) steht daneben, damit sich das sichere Fenster bei
Bedarf aus beidem rekonstruieren laesst. `telegram_count` ist die Anzahl
Telegramme GENAU dieses Teillaufs (nach einem etwaigen Luecken-Split), nicht
des gesamten Rohlaufs.

`source_port` kommt aus `session.json` der Aufzeichnung (`sync-record.py`
schreibt dort das `port`-Feld) - nicht erraten, sondern aus derselben
Aufzeichnung gelesen. Ueber `--source-port` laesst es sich uebersteuern,
falls keine `session.json` vorliegt.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MS_TO_NS = 1_000_000

REASON_VALUE_CHANGE = "wertwechsel_im_fenster"
REASON_OUTSIDE_RANGE = "ausserhalb_telegrammbereich"
REASON_TAIL_UNKNOWN = "letzter_lauf_ohne_folgetelegramm"
REASON_GAP = "telegrammluecke"
REASON_NO_TELEGRAMS = "keine_telegramme"

_REASON_LABELS = {
    REASON_VALUE_CHANGE: "Wertwechsel im Fenster",
    REASON_OUTSIDE_RANGE: "ausserhalb Telegrammbereich (vor erstem/nach letztem Telegramm)",
    REASON_TAIL_UNKNOWN: "letzter Lauf ohne Folge-Telegramm",
    REASON_GAP: "Telegrammluecke",
    REASON_NO_TELEGRAMS: "keine Telegramme in der Aufzeichnung",
}

#: Fuehrender numerischer Teil eines GSV-Telegramms wie "+0.46776 mV/V" ->
#: "+0.46776". Rein informativ fuer die Vorschlagsdatei - fuer die
#: Gate-Entscheidung selbst zaehlt ausschliesslich die exakte Zeichenkette
#: (Festlegung 1 des Plans), nie der geparste numerische Wert.
_NUMBER_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?")

#: Name der Normalisierung in `label_normalization` - siehe
#: `telegram_to_display_text()`. Versioniert (Suffix `_v1`), falls die Regel
#: sich spaeter aendert (z.B. wenn negative Normierung einmal verifiziert
#: wird) und alte Vorschlagsdateien unterscheidbar bleiben sollen.
LABEL_NORMALIZATION = "gsv2as_leading_zero_v1"


def telegram_to_display_text(telegram: str) -> str:
    """Bildet den ASCII-Telegrammtext des GSV-2AS auf den Text ab, den das
    Anzeigeglas tatsaechlich zeigt (OQ-41, gemessen ueber 15 Normierungs-
    faktoren, siehe docs/VALIDATION.md 2026-09-23).

    Befund: das Geraet unterdrueckt auf dem Glas genau EINE fuehrende Null
    direkt nach dem Vorzeichen, wenn danach eine weitere Ziffer folgt (Werte
    >= 1, z.B. Telegramm "+01.8290 mV/V" -> Glas "+1.8290 mV/V" - die
    Leerzelle selbst wird hier NICHT nachgebildet, siehe unten). Bei Werten
    < 1 (z.B. "+0.60965") ist diese Null die Einerstelle vor dem Punkt und
    steht auf beiden Seiten - sie wird NICHT entfernt, weil ihr nicht die
    Ziffer '.' folgt, sondern eine tatsaechliche Ziffer waere die Bedingung;
    hier folgt '.', also bleibt die Regel unwirksam.

    Regel (Nutzerentscheidung, keine Toleranz/Rundung - reiner Zeichenketten-
    Zuschnitt): genau eine '0' unmittelbar nach dem Vorzeichenzeichen wird
    entfernt, wenn auf sie selbst eine Ziffer (nicht '.') folgt. Alles
    andere - Vorzeichen, Dezimalpunkt, restliche Ziffern, Einheitensuffix
    wie " mV/V" - bleibt unveraendert. Das Glas zeigt an der Stelle der
    entfernten Null eine LEERE Zelle (8 Zellen im Zahlenblock bleiben
    bestehen), keine echte Verkuerzung - diese Funktion bildet aber nur den
    fuer den Textvergleich/Label relevanten Zeicheninhalt ab, nicht die
    Zellengeometrie.

    Fehlendes Vorzeichen (erstes Zeichen weder '+' noch '-'): defensiv
    dieselbe Regel ab Position 0 anwenden, statt zu verwerfen. Begruendung:
    das GSV-2AS-Protokoll liefert im Normalbetrieb IMMER ein Vorzeichen
    (siehe Konzept/OQ-37-Messungen); ein fehlendes Vorzeichen deutet auf
    Kappung/Uebertragungsfehler hin, bei dem ein Verwerfen des ganzen
    Telegramms ohnehin an anderer Stelle (Syntaxregel, §7) passieren sollte -
    diese Funktion ist kein Ersatz fuer eine Syntaxpruefung und soll auf
    unerwarteter Eingabe nicht zusaetzlich raten, sondern nur mechanisch
    dieselbe, klar spezifizierte Regel anwenden.

    ACHTUNG negative Werte: die Regel wird auf ein fuehrendes '-' rein
    mechanisch genauso angewendet wie auf '+' (dieselbe Position). Das ist
    NICHT gemessen/verifiziert - negative Normierung existiert laut
    Anleitung erst ab Firmware 1.5.06, das gemessene Geraet hat 1.3.07, die
    Vorzeichenstelle '-' ist an diesem Geraet nie erreichbar (siehe
    CLAUDE.md/OQ-37/docs/VALIDATION.md). Diese Funktion darf NICHT als Beleg
    dafuer gelesen werden, dass negative Telegramme korrekt behandelt
    werden.
    """
    if not telegram:
        return telegram
    if telegram[0] in "+-":
        sign, rest = telegram[0], telegram[1:]
    else:
        sign, rest = "", telegram
    if len(rest) >= 2 and rest[0] == "0" and rest[1].isdigit():
        rest = rest[1:]
    return sign + rest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Wertet eine sync-record.py-Aufzeichnung offline aus und "
            "bestimmt, welche Bilder einen Sollwert aus dem seriellen "
            "Strom bekommen duerfen. Schreibt keine Datensatzproben."
        )
    )
    parser.add_argument(
        "--recording",
        type=Path,
        required=True,
        help="Verzeichnis einer sync-record.py-Aufzeichnung (serial.jsonl, frames.jsonl, session.json)",
    )
    parser.add_argument(
        "--guard-margin-ms",
        type=float,
        required=True,
        help="M in Millisekunden - Messgroesse aus Task B, KEIN Vorgabewert",
    )
    parser.add_argument(
        "--max-gap-ms",
        type=float,
        required=True,
        help="Schwelle fuer Telegrammluecken in Millisekunden - KEIN Vorgabewert, siehe docstring",
    )
    parser.add_argument("--output", type=Path, required=True, help="Zielpfad der Vorschlagsdatei (JSON)")
    parser.add_argument(
        "--source-port",
        default=None,
        help="Ueberschreibt den Port aus session.json (falls keine session.json vorliegt)",
    )
    return parser.parse_args(argv)


# --- Eingabe -----------------------------------------------------------------


def load_serial(path: Path) -> list[tuple[int, str]]:
    """`(t_ns, text)`, aufsteigend sortiert. `t_boot` in serial.jsonl ist
    Sekunden (float, CLOCK_BOOTTIME, wie von sync-record.py geschrieben)."""
    records: list[tuple[int, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        t_ns = round(float(obj["t_boot"]) * 1e9)
        records.append((t_ns, str(obj["text"])))
    records.sort(key=lambda r: r[0])
    return records


def load_frames(path: Path) -> list[tuple[str, int]]:
    """`(dateiname, capture_timestamp_ns)` - `capture_timestamp.value_ns` ist
    bereits Nanosekunden derselben CLOCK_BOOTTIME-Domaene (Timestamp.to_dict())."""
    frames: list[tuple[str, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        t_ns = int(obj["capture_timestamp"]["value_ns"])
        frames.append((str(obj["file"]), t_ns))
    return frames


def load_source_port(recording: Path, override: str | None) -> str:
    if override:
        return override
    session_path = recording / "session.json"
    if not session_path.is_file():
        raise SystemExit(
            f"Fehler: {session_path} fehlt und --source-port wurde nicht angegeben - "
            "der Port ist Pflichtfeld in label_origin_detail und wird nicht erraten."
        )
    session = json.loads(session_path.read_text(encoding="utf-8"))
    port = session.get("port")
    if not port:
        raise SystemExit(f"Fehler: {session_path} enthaelt kein 'port'-Feld.")
    return str(port)


def extract_numeric_text(text: str) -> str | None:
    match = _NUMBER_RE.match(text.strip())
    return match.group(0) if match else None


# --- Fensterbau ----------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    lo_ns: int
    hi_ns: int
    text: str
    plateau_start_ns: int
    plateau_end_ns: int
    telegram_count: int
    #: Grund, warum dieses Fenster hier endet - bestimmt den Ablehnungsgrund
    #: von Bildern, die zwischen diesem Fenster und dem naechsten liegen.
    tag_right: str  # "value_change" | "gap" | "tail_unknown"


#: Plateau-/Gleichheitserkennung (Laufgruppierung) laeuft bewusst auf dem
#: ROHEN Telegrammtext, nicht auf `telegram_to_display_text(...)`. Fuer die
#: Gleichheitsfrage ("zwei Telegramme derselbe Zeichenkette?") ist das
#: aequivalent, WEIL die Abbildung innerhalb eines festen Telegrammformats
#: injektiv ist (sie entfernt hoechstens eine Ziffer an einer durch das
#: Vorzeichen fest bestimmten Position - zwei verschiedene Rohtexte
#: DESSELBEN Formats koennen also nie auf denselben normalisierten Text
#: fallen). Der Rohtext bleibt trotzdem die Grundlage, weil er das ist, was
#: tatsaechlich auf der Leitung ankam - die Normalisierung ist reine
#: Aufbereitung fuer das Label (Vergleich mit dem Anzeigeglas), keine
#: Aenderung an der Gate-Entscheidung selbst.
def _group_raw_runs(telegrams: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    runs: list[list[tuple[int, str]]] = []
    current = [telegrams[0]]
    for t_ns, text in telegrams[1:]:
        if text == current[-1][1]:
            current.append((t_ns, text))
        else:
            runs.append(current)
            current = [(t_ns, text)]
    runs.append(current)
    return runs


def _split_on_gaps(run: list[tuple[int, str]], max_gap_ns: int) -> list[list[tuple[int, str]]]:
    subruns: list[list[tuple[int, str]]] = []
    current = [run[0]]
    # Absichtlich kein `strict=True`: `run[1:]` ist per Konstruktion um genau
    # ein Element kuerzer als `run` (paarweise Nachbarn ablaufen).
    for prev, nxt in zip(run, run[1:], strict=False):
        if nxt[0] - prev[0] > max_gap_ns:
            subruns.append(current)
            current = [nxt]
        else:
            current.append(nxt)
    subruns.append(current)
    return subruns


def build_windows(telegrams: list[tuple[int, str]], guard_margin_ns: int, max_gap_ns: int) -> list[Window]:
    if not telegrams:
        return []
    raw_runs = _group_raw_runs(telegrams)
    n_runs = len(raw_runs)
    windows: list[Window] = []
    for run_idx, run in enumerate(raw_runs):
        subruns = _split_on_gaps(run, max_gap_ns)
        n_sub = len(subruns)
        for sub_idx, sub in enumerate(subruns):
            t_first = sub[0][0]
            t_last = sub[-1][0]
            text = sub[0][1]
            lo_ns = t_first + guard_margin_ns
            is_last_subrun = sub_idx == n_sub - 1
            if not is_last_subrun:
                # Luecke folgt innerhalb desselben Rohlaufs: konservativ mit
                # dem letzten Telegramm DIESES Teillaufs abschliessen - der
                # Teil, der die Luecke ueberspannt, ist nicht vertrauenswuerdig.
                hi_ns = t_last - guard_margin_ns
                tag = "gap"
            elif run_idx < n_runs - 1:
                # Letzter Teillauf eines Rohlaufs, dem ein ABWEICHENDER
                # Rohlauf folgt. Der Abstand zum naechsten Telegramm
                # (Anfang des Folgelaufs) ist selbst eine Telegrammluecke
                # im Sinne von --max-gap-ms, wenn er zu gross ist - eine
                # Luecke GENAU an einem Wertwechsel ist der gefaehrlichste
                # Fall (siehe Aufgabenbeschreibung, "der subtile und
                # wichtigste"): mehrere echte Zwischenwerte koennten
                # unbemerkt verloren gegangen sein, bevor B ankam. Deshalb
                # NICHT die normale t_{j+1}-Regel anwenden, sondern wie bei
                # einer Luecke konservativ mit dem letzten TELEGRAMM dieses
                # Teillaufs abschliessen.
                next_first_ns = raw_runs[run_idx + 1][0][0]
                if next_first_ns - t_last > max_gap_ns:
                    hi_ns = t_last - guard_margin_ns
                    tag = "gap"
                else:
                    hi_ns = next_first_ns - guard_margin_ns
                    tag = "value_change"
            else:
                # Der allerletzte Rohlauf des ganzen Stroms: kein
                # Folgetelegramm bekannt (Fall 3) - konservativ mit dem
                # letzten TELEGRAMM dieses Teillaufs abschliessen.
                hi_ns = t_last - guard_margin_ns
                tag = "tail_unknown"
            windows.append(
                Window(
                    lo_ns=lo_ns,
                    hi_ns=hi_ns,
                    text=text,
                    plateau_start_ns=t_first,
                    plateau_end_ns=t_last,
                    telegram_count=len(sub),
                    tag_right=tag,
                )
            )
    return windows


_TAG_TO_REASON = {
    "gap": REASON_GAP,
    "value_change": REASON_VALUE_CHANGE,
    "tail_unknown": REASON_TAIL_UNKNOWN,
}


def classify(t_ns: int, telegrams: list[tuple[int, str]], windows: list[Window]) -> tuple[Window | None, str | None]:
    """`(fenster, ablehnungsgrund)` - genau eines von beiden ist nicht `None`."""
    if not telegrams:
        return None, REASON_NO_TELEGRAMS
    t_min = telegrams[0][0]
    t_max = telegrams[-1][0]
    if t_ns < t_min or t_ns > t_max:
        return None, REASON_OUTSIDE_RANGE
    for idx, window in enumerate(windows):
        if window.lo_ns <= t_ns < window.hi_ns:
            return window, None
        if t_ns < window.lo_ns:
            if idx == 0:
                # Randbereich vor dem allerersten Fenster: derselbe
                # Schutzmechanismus wie ein Wertwechsel (siehe docstring).
                return None, REASON_VALUE_CHANGE
            reason = _TAG_TO_REASON[windows[idx - 1].tag_right]
            return None, reason
    # t liegt hinter dem letzten Fenster, aber innerhalb [t_min, t_max].
    return None, REASON_TAIL_UNKNOWN


# --- Hauptablauf ---------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    recording: Path = args.recording
    serial_path = recording / "serial.jsonl"
    frames_path = recording / "frames.jsonl"
    frames_dir = recording / "frames"

    if not serial_path.is_file():
        print(f"Fehler: {serial_path} fehlt.", file=sys.stderr)
        return 1
    if not frames_path.is_file():
        print(f"Fehler: {frames_path} fehlt.", file=sys.stderr)
        return 1

    guard_margin_ns = round(args.guard_margin_ms * MS_TO_NS)
    max_gap_ns = round(args.max_gap_ms * MS_TO_NS)
    source_port = load_source_port(recording, args.source_port)

    telegrams = load_serial(serial_path)
    frames = load_frames(frames_path)
    windows = build_windows(telegrams, guard_margin_ns, max_gap_ns)

    labeled: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    text_counts: Counter[str] = Counter()

    for filename, t_ns in frames:
        window, reason = classify(t_ns, telegrams, windows)
        if window is None:
            reject_counts[reason or REASON_NO_TELEGRAMS] += 1
            continue
        image_path = str(frames_dir / filename)
        numeric_text = extract_numeric_text(window.text)
        label_text = telegram_to_display_text(window.text)
        labeled.append(
            {
                "image_path": image_path,
                "telegram_text": window.text,
                "label_text": label_text,
                "label_normalization": LABEL_NORMALIZATION,
                "numeric_text": numeric_text,
                "label_origin_detail": {
                    "source_port": source_port,
                    "guard_margin_ms": args.guard_margin_ms,
                    "plateau_start_ns": window.plateau_start_ns,
                    "plateau_end_ns": window.plateau_end_ns,
                    "telegram_count": window.telegram_count,
                },
            }
        )
        text_counts[window.text] += 1

    total = len(frames)
    rejected_total = sum(reject_counts.values())
    unparseable_numeric = sum(1 for entry in labeled if entry["numeric_text"] is None)

    print("=== gate-label: Bericht ===")
    print(f"Aufzeichnung: {recording}")
    print(f"M (--guard-margin-ms): {args.guard_margin_ms}  --max-gap-ms: {args.max_gap_ms}")
    print(f"Telegramme: {len(telegrams)}  Bilder gesamt: {total}")
    print(f"Gelabelt: {len(labeled)}  Abgelehnt: {rejected_total}")
    print("Ablehnungen je Grund:")
    for reason_key in (REASON_VALUE_CHANGE, REASON_OUTSIDE_RANGE, REASON_TAIL_UNKNOWN, REASON_GAP, REASON_NO_TELEGRAMS):
        count = reject_counts.get(reason_key, 0)
        print(f"  {_REASON_LABELS[reason_key]}: {count}")
    if unparseable_numeric:
        print(
            f"WARNUNG: bei {unparseable_numeric} gelabelten Bildern liess sich kein "
            "fuehrender Zahlenteil aus dem Telegrammtext extrahieren (numeric_text=null) "
            "- Label steht trotzdem (exakte Zeichenkettengleichheit zaehlt), aber das "
            "ist ein Formatbefund."
        )
    print()
    print(f"Verschiedene Zeichenketten unter den gelabelten Bildern: {len(text_counts)}  <-- wichtiger als die Bilderzahl")
    print("Verteilung Bilder je Zeichenkette:")
    for text, count in sorted(text_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {text!r}: {count}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    proposal = {
        "recording": str(recording),
        "guard_margin_ms": args.guard_margin_ms,
        "max_gap_ms": args.max_gap_ms,
        "images": labeled,
    }
    args.output.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nVorschlagsdatei geschrieben: {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
