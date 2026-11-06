"""Alle Oberflächentexte und die Abbildung Zustand -> (Wort, Ton, Unterzeile, Aktion).

Wahrheitsregeln (DESIGN.md): grün nur belegt; "Weitergabe" ist nie
GSVmulti-Empfang; "Empfang belegt" nur mit Testnachweis (ctx.receipt.proven);
ein Worker-Code oder output_ready=False wird nie von "Pi verbunden"
überstimmt; unbekannte Werte erscheinen als "Unbekannt", neutral.
"""
from __future__ import annotations

import re as _re
from dataclasses import dataclass

from dispread.bridge.types import BridgeEvent
from dispread_bridge_app.readiness import Readiness
from dispread_bridge_app.worker import WorkerStatus

from .port import JournalEntry, UiContext

APP_TITLE = 'GSVmulti-Brücke'
DUT_LOCK_LINE = 'DUT-Ausgabe gesperrt – die Brücke gibt keine Messwerte frei'
DUT_LOCK_DEFAULT_SEE = DUT_LOCK_LINE
NO_PI = 'Kein Pi gekoppelt · Weg noch offen'
SCREEN_READER = {'ok': 'Erfolg:', 'warn': 'Achtung:', 'err': 'Fehler:', 'info': 'Hinweis:',
                 'unclear': 'Unklar:', 'unused': 'Nicht benutzt:'}
STEPS = ('Komponenten', 'Pi koppeln', 'Verbinden', 'Session', 'Empfangstest')
LOCK_TITLE = 'Pi-Wechsel gesperrt'
LOCK_TEXT = ('Solange die Brücke an GSVmulti überträgt, bleibt der Pi festgelegt. '
             'Beenden Sie die Übertragung, um einen anderen Pi zu wählen.')
PI_SWITCH_NOTE = ('Nach dem Wechsel muss neu verbunden werden. '
                  'Ein Wechsel während der Übertragung ist nicht möglich.')
NO_FAULTS = 'Keine Störungen seit dem Start der Brücke.'
NO_EVENTS = 'Noch keine Ereignisse seit dem Start der Brücke.'
TRAY_HINT_TITLE = APP_TITLE
TRAY_HINT = ('Die Brücke läuft im Infobereich weiter. Dieser Hinweis erscheint nur einmal. '
             'Ein Klick auf das Symbol öffnet das Fenster.')
EXIT_TITLE = 'Brücke beenden?'
EXIT_TEXT_ACTIVE = 'Die Übertragung an GSVmulti endet. Der Lauf auf dem Pi läuft weiter.'
EXIT_TEXT_LOCKED = ('Die Verbindung zum Pi endet; es werden keine Werte übertragen. '
                    'Der Lauf auf dem Pi läuft weiter.')
EXIT_KEEP, EXIT_QUIT = 'Weiter übertragen', 'Beenden'
JOURNAL_DETAILS = 'Begrenzt, Zugangsdaten werden nicht protokolliert.'


@dataclass(frozen=True)
class Headline:
    text: str
    tone: str


@dataclass(frozen=True)
class ChipView:
    key: str
    name: str
    word: str
    tone: str
    sub: str = ''
    details: tuple[tuple[str, str], ...] = ()
    hint: str = ''


@dataclass(frozen=True)
class ActionBar:
    kind: str                       # ok | warn | err | info
    title: str
    text: str = ''
    buttons: tuple[tuple[str, str, bool], ...] = ()   # (Beschriftung, Aktions-ID, primär)

    @property
    def action_ids(self) -> tuple[str, ...]:
        return tuple(b[1] for b in self.buttons)


WORKER_CODE_TEXT = {
    'unknown_invalidation': 'ungeklärte Auslieferung im Journal',
    'unknown_delivery': 'Ergebnis der letzten Weitergabe unklar',
    'audit_failed': 'Journal nicht schreibbar',
    'connection_failed': 'Verbindung abgebrochen',
    'blocked': 'Übertragung blockiert',
}
CONNECTION_CODE_TEXT = {
    'peer_invalid': ('Pi nicht bestätigt', 'Der antwortende Pi passt nicht zum Profil.'),
    'profile_invalid': ('Profil ungültig', 'Das Profil lässt sich nicht verwenden. Öffnen Sie ein neues Profil.'),
    'clock_or_certificate_invalid': ('Zertifikat oder Uhrzeit ungültig',
                                     'Prüfen Sie die Uhrzeit dieses PCs und das Profil.'),
    'selection_required': ('Auswahl nötig', 'Wählen Sie den Adapter oder Pi aus.'),
    'pairing_required': ('Pi nicht gekoppelt', 'Koppeln Sie den Pi mit einem Kopplungscode.'),
    'pairing_refused': ('Kopplung abgelehnt', 'Erzeugen Sie in der Werkbank einen neuen Code.'),
    'authentication_refused': ('Anmeldung abgelehnt', 'Der Zugang wurde widerrufen oder ist ungültig.'),
    'peer_refused': ('Pi lehnt die Verbindung ab', 'Prüfen Sie Profil und Zugang.'),
    'endpoint_unsupported': ('Adresse nicht unterstützt', 'Das Profil nennt keinen nutzbaren Weg.'),
    'endpoint_required': ('Adresse fehlt', 'Tragen Sie Adresse oder Namen manuell ein.'),
    'adapter_driver_unavailable': ('Adaptertreiber fehlt', 'Prüfen Sie die Komponenten.'),
    'adapter_unavailable': ('USB-Adapter nicht gefunden', 'Stecken Sie den Adapter an und prüfen Sie erneut.'),
    'credential_unavailable': ('Zugang nicht verfügbar', 'Koppeln Sie den Pi erneut.'),
    'components_unsupported': ('Komponenten nicht unterstützt', 'Prüfen Sie die Komponenten.'),
    'lease_unavailable': ('Pi ist belegt', 'Ein anderer Rechner überträgt gerade von diesem Pi.'),
    'connection_unavailable': ('Pi nicht erreichbar', 'Die Brücke versucht es erneut. Prüfen Sie Netz, Kabel und Pi-Dienst.'),
    'connection_lost': ('Verbindung unterbrochen', 'Die Brücke verbindet automatisch neu, ohne den Pi zu wechseln.'),
    'network_unavailable': ('Netzwerk nicht erreichbar', 'Prüfen Sie Netzwerk, VPN oder Tailscale.'),
    'uart_peer_unavailable': ('Pi am UART antwortet nicht', 'Prüfen Sie TX, RX, GND und den Pi-Dienst.'),
    'redirect_refused': ('Weiterleitung abgelehnt', 'Die Brücke folgt keiner Weiterleitung. Prüfen Sie die Adresse.'),
    'transport_write_uncertain': ('Senden unklar', 'Es ist offen, ob der Pi die Nachricht erhielt. Neu verbinden.'),
    'disconnected': ('Verbindung beendet', 'Verbinden Sie bei Bedarf erneut.'),
    'run_conflict': ('Lauf läuft bereits', 'Auf dem Pi läuft schon ein Lauf; es wurde keine Demo gestartet.'),
    'demo_unconfirmed': ('Demo nicht bestätigt', 'Der Pi hat den Demostart nicht bestätigt. Nichts wird wiederholt.'),
    'run_changed': ('Lauf gewechselt', 'Der Pi meldet einen anderen Lauf. Die Brücke liest neu.'),
    'stale_ack': ('Quittung veraltet', 'Eine Quittung passte nicht mehr zum Lauf. Sie wurde verworfen.'),
    'no_pending_poll': ('Interner Ablauf gestört', 'Verbinden Sie neu und exportieren Sie bei Wiederholung die Diagnose.'),
    'invalid_legacy_request': ('Interner Ablauf gestört', 'Verbinden Sie neu und exportieren Sie bei Wiederholung die Diagnose.'),
    'transport_unsupported': ('Weg nicht unterstützt', 'Wählen Sie Netzwerk oder UART.'),
    'windows_protection_required': ('Windows-Schutz fehlt', 'Zugangsdaten lassen sich ohne Windows-Schutz nicht speichern.'),
    'cancelled': ('Verbindung abgebrochen', 'Verbinden Sie bei Bedarf erneut.'),
}
# Bereitschaftswerte des Kerns (output / next_action): erklärender Satz + nächste Aktion
OUTPUT_TEXT = {
    'output_off': ('Auf dem Pi läuft keine Ausgabe.', 'Starten Sie dort einen Lauf; die Brücke startet keinen.'),
    'dut_release_blocked': ('Die DUT-Ausgabe ist gesperrt (Abnahme fehlt).', 'Nichts tun: es werden keine Messwerte an COM geschrieben.'),
    'peer_release_blocked': ('Der Pi meldet eine Sperre.', 'Ursache auf dem Pi klären; die Brücke deutet den Grund nicht.'),
    'run_ended': ('Der Lauf auf dem Pi ist beendet; die Verbindung besteht weiter.', 'Starten Sie bei Bedarf einen neuen Lauf auf dem Pi.'),
    'peer_output_unknown': ('Der Ausgabestand des Pi ist unbekannt.', 'Warten Sie auf die nächste Pi-Meldung oder verbinden Sie neu.'),
}
ERROR_TEXT = {
    'profile_invalid': ('Profil ungültig', 'Die Datei ist kein gültiges Pi-Profil. Laden Sie es in der Werkbank neu herunter.'),
    'profile_required': ('Profil fehlt', 'Öffnen Sie zuerst das Pi-Profil.'),
    'code_invalid': ('Code ungültig', 'Der Kopplungscode hat nicht das erwartete Format. Prüfen Sie die Eingabe.'),
    'fingerprint_unconfirmed': ('Fingerabdruck nicht bestätigt', 'Vergleichen Sie den Fingerabdruck mit der Werkbank und bestätigen Sie ihn.'),
    'pair_required': ('Pi nicht gekoppelt', 'Geben Sie den Kopplungscode ein und bestätigen Sie den Fingerabdruck.'),
    'portpair_required': ('Portpaar fehlt', 'Geben Sie das vorhandene Portpaar an (Schritt 1).'),
    'portpair_invalid': ('Portpaar ungültig', 'Wählen Sie zwei verschiedene, vorhandene COM-Ports.'),
    'transmission_active': ('Übertragung läuft', 'Beenden Sie zuerst die Übertragung.'),
    'demo_not_confirmed': ('Testsession nicht bestätigt', 'Bestätigen Sie die getrennte GSVmulti-Testsession.'),
    'not_connected': ('Nicht verbunden', 'Verbinden Sie zuerst den Pi.'),
    'connect_required': ('Nicht verbunden', 'Verbinden Sie zuerst den Pi.'),
    'session_unconfirmed': ('Session nicht bestätigt', 'Bestätigen Sie, dass Sie GSVmulti eingestellt haben.'),
    'automatic_export_blocked': ('Automatische Session noch nicht freigegeben', 'Stellen Sie GSVmulti von Hand ein.'),
    'endpoint_unsupported': ('Adresse nicht unterstützt', 'Erlaubt sind direkte https-Adressen ohne Proxy und Pfadpräfix.'),
}


def explain_code(code: str | None) -> tuple[str, str]:
    """Maschinencode -> (Erklärung, nächste Aktion); unbekannt -> „Unbekannt“ mit dem Code."""
    if code in CONNECTION_CODE_TEXT:
        return CONNECTION_CODE_TEXT[code]
    if code in ERROR_TEXT:
        return ERROR_TEXT[code]
    if code in OUTPUT_TEXT:
        return OUTPUT_TEXT[code]
    if code in WORKER_CODE_TEXT:
        return WORKER_CODE_TEXT[code], 'Diagnose exportieren und Ursache klären.'
    return 'Unbekannt', f'Code: {code}' if code else ''


def version_label(version: str | None) -> str:
    if not version:
        return ''
    return version if (version == 'Entwicklungsstand' or ' · ' in version) else f'Version {version}'

_TONE_OF_PEER = {'authenticated': 'ok', 'disconnected': 'info', 'backoff': 'err', 'connecting': 'info'}


NOT_SET = 'nicht festgelegt'


def _port(value):
    return value or NOT_SET


def _unknown(key, name):
    return ChipView(key, name, 'Unbekannt', 'info')


def _worker_active_failure(readiness: Readiness, worker: WorkerStatus | None) -> str | None:
    """Worker-Code, der jedes "verbunden" überstimmt."""
    if worker is not None and worker.code:
        return worker.code
    return None


def headline(readiness: Readiness, worker: WorkerStatus | None, ctx: UiContext) -> Headline:
    code = _worker_active_failure(readiness, worker)
    if code:
        return Headline(f'Übertragung gestoppt – {WORKER_CODE_TEXT.get(code, "Code " + code)}', 'err')
    if readiness.peer == 'authenticated' and readiness.output == 'ended' and not ctx.com_issue:
        return Headline('Verbunden – Lauf beendet', 'info')
    if ctx.com_issue and ctx.demo:
        word = {'busy': f'{ctx.bridge_port} belegt' if ctx.bridge_port else 'Port belegt', 'write_failed': 'Schreibfehler',
                'unclear': 'kein Nachweis'}.get(ctx.com_issue, 'unbekannt')
        lead = 'Weitergabe unklar' if ctx.com_issue == 'unclear' else 'Weitergabe gestört'
        return Headline(f'Demo: {lead} – {word}', 'warn')
    peer = readiness.peer
    if peer == 'backoff':
        n = f' in {ctx.retry_in_s} s' if ctx.retry_in_s is not None else ''
        return Headline(f'Pi antwortet nicht – Versuch{n}', 'err')
    if peer == 'authenticated':
        if worker is not None and not worker.output_ready and worker.state not in ('idle', 'starting', 'stopped'):
            return Headline('Verbunden – Übertragung nicht bereit', 'warn')
        if ctx.release and not ctx.dut_locked and not ctx.demo:
            return Headline(f'Verbunden – Lauf {ctx.run_id or "?"} wird übertragen', 'ok')
        if ctx.demo:
            return Headline('Verbunden – Demo läuft', 'warn')
        if ctx.waiting_for_run:
            return Headline('Verbunden – wartet auf einen Lauf auf dem Pi', 'info')
        if ctx.dut_locked:
            return Headline(f'Verbunden – Lauf {ctx.run_id} läuft, keine Werteausgabe'
                            if ctx.run_id else 'Verbunden – keine Werteausgabe', 'info')
        return Headline('Verbunden', 'info')
    if peer == 'disconnected':
        if readiness.next_action in CONNECTION_CODE_TEXT:
            return Headline(CONNECTION_CODE_TEXT[readiness.next_action][0], 'err')
        return Headline('Nicht verbunden – Pi ausgewählt' if ctx.pi_name else 'Nicht verbunden', 'info')
    if peer == 'connecting':
        return Headline('Verbindung wird aufgebaut …', 'info')
    return Headline('Unbekannt', 'info')


def head_title(ctx: UiContext) -> tuple[str, str]:
    """(Name, Weg); Name leer vor der Pi-Wahl."""
    if not ctx.pi_name:
        return NO_PI, ''
    return ctx.pi_name, ctx.route or ''


def dut_line(ctx: UiContext) -> tuple[str, str]:
    """Die Sperrzeile ist in jedem Zustand sichtbar."""
    if ctx.release and not ctx.dut_locked:
        return ctx.release, 'ok'
    return DUT_LOCK_LINE, 'warn'


def chips(readiness: Readiness, worker: WorkerStatus | None, ctx: UiContext) -> tuple[ChipView, ...]:
    code = _worker_active_failure(readiness, worker)
    peer_ok = readiness.peer == 'authenticated'
    pair = (f'{ctx.bridge_port} ↔ {ctx.gsv_port} (com0com)' if ctx.bridge_port and ctx.gsv_port else NOT_SET)
    ports = (('Brückenseite', _port(ctx.bridge_port)), ('GSVmulti-Seite', _port(ctx.gsv_port)))
    # Komponenten
    comp = {'ready': ChipView('components', 'Komponenten', 'Installiert', 'ok'),
            'missing': ChipView('components', 'Komponenten', 'Portpaar fehlt', 'err'),
            'restart': ChipView('components', 'Komponenten', 'Neustart nötig', 'warn'),
            'manual_pair': ChipView('components', 'Komponenten', 'Portpaar manuell', 'warn',
                                    'nicht von der App geprüft')
            }.get(readiness.components, _unknown('components', 'Komponenten'))
    comp = ChipView(comp.key, comp.name, comp.word, comp.tone, comp.sub,
                    (('Windows', '11, 64 Bit'), ('App-Version', ctx.version or '–'), ('Portpaar', pair)),
                    'Alle Systemkomponenten sind vorhanden. Das sagt nichts über Verbindung oder Empfang.'
                    if comp.tone == 'ok' else
                    'Das Portpaar wurde von Hand angegeben. Die App hat es weder angelegt noch geprüft.'
                    if readiness.components == 'manual_pair' else '')
    # UART
    uart = {'not_required': ChipView('uart', 'UART', 'nicht benutzt', 'unused'),
            'ready': ChipView('uart', 'UART', 'Adapter bereit', 'ok'),
            'unavailable': ChipView('uart', 'UART', 'Adapter fehlt', 'err'),
            'unknown': _unknown('uart', 'UART')}.get(readiness.adapter, _unknown('uart', 'UART'))
    uart = ChipView(uart.key, uart.name, uart.word, uart.tone, uart.sub,
                    (('Weg', ctx.route or 'offen'),
                     ('USB-Adapter', 'nicht benutzt' if uart.tone == 'unused' else uart.word)),
                    'Ein USB-Adapter wird nur im Weg „UART“ gebraucht.')
    # Pi
    if peer_ok and not code:
        pi = ChipView('pi', 'Pi', 'Verbunden', 'ok')
    elif peer_ok:
        pi = ChipView('pi', 'Pi', 'Verbunden', 'info', 'Übertragung gestoppt')
    elif readiness.peer == 'backoff':
        pi = ChipView('pi', 'Pi', 'Antwortet nicht', 'err')
    elif readiness.peer == 'disconnected':
        pi = ChipView('pi', 'Pi', 'Pi nicht verbunden', 'info')
    else:
        pi = _unknown('pi', 'Pi')
    pi = ChipView(pi.key, pi.name, pi.word, pi.tone, pi.sub,
                  (('Pi-ID', ctx.pi_id or '–'), ('Endpunkt', ctx.endpoint or '–'),
                   ('TLS-Fingerabdruck (SHA-256)', ctx.fingerprint or '–'),
                   ('Protokoll', ctx.protocol or '–'),
                   ('Letzte Meldung', ctx.last_report or '–'))
                  + ((('Code', readiness.next_action),) if readiness.next_action not in (
                      None, 'connect', 'reconnect', 'disconnected', 'output_off', 'run_ended', 'dut_release_blocked',
                      'peer_release_blocked') and readiness.next_action not in CONNECTION_CODE_TEXT else ()))
    # Ausgabe
    if code:
        out = ChipView('output', 'Ausgabe', 'Blockiert', 'err', WORKER_CODE_TEXT.get(code, code))
    elif not peer_ok:
        out = ChipView('output', 'Ausgabe', 'Unbekannt', 'info',
                       '' if readiness.peer == 'disconnected' and not ctx.pi_name else 'solange der Pi nicht antwortet')
        out = ChipView(out.key, out.name, out.word, out.tone, '')
    elif ctx.waiting_for_run:
        out = ChipView('output', 'Ausgabe', 'Wartet auf Lauf', 'info')
    elif readiness.output == 'ended':
        out = ChipView('output', 'Ausgabe', 'Lauf beendet', 'info', 'Verbindung besteht weiter')
    elif readiness.output == 'blocked':
        out = (ChipView('output', 'Ausgabe', 'DUT gesperrt', 'warn') if readiness.next_action == 'dut_release_blocked'
               else ChipView('output', 'Ausgabe', 'Gesperrt (Pi)', 'warn', 'Sperrgrund vom Pi'))
    elif readiness.output == 'output_off':
        out = ChipView('output', 'Ausgabe', 'Keine Ausgabe', 'info', 'auf dem Pi läuft kein Lauf')
    elif readiness.output == 'unavailable' and not ctx.demo:
        out = ChipView('output', 'Ausgabe', 'Unbekannt', 'info')
    elif ctx.demo:
        out = ChipView('output', 'Ausgabe', 'Demo-Werte', 'warn')
    elif ctx.release and not ctx.dut_locked:
        out = ChipView('output', 'Ausgabe', 'Freigegeben', 'ok')
    elif ctx.dut_locked:
        out = ChipView('output', 'Ausgabe', 'DUT gesperrt', 'warn')
    else:
        out = _unknown('output', 'Ausgabe')
    hints = {'Freigegeben': 'Dieser Zustand existiert erst nach der Windows-Abnahme.',
             'Wartet auf Lauf': 'Die Brücke startet keinen Lauf.',
             'DUT gesperrt': 'Die Brücke gibt nichts frei und startet keine Messung.',
             'Demo-Werte': 'Nicht für Kalibrierungen verwenden.'}
    hints.update({'Lauf beendet': OUTPUT_TEXT['run_ended'][0] + ' ' + OUTPUT_TEXT['run_ended'][1],
                  'Gesperrt (Pi)': OUTPUT_TEXT['peer_release_blocked'][0] + ' ' + OUTPUT_TEXT['peer_release_blocked'][1],
                  'Keine Ausgabe': OUTPUT_TEXT['output_off'][0] + ' ' + OUTPUT_TEXT['output_off'][1]})
    odetails = (('Ausgabe', out.word),) + ((('Code', readiness.next_action),) if out.word == 'Unbekannt'
                                           and readiness.next_action else ())
    out = ChipView(out.key, out.name, out.word, out.tone, out.sub, odetails, hints.get(out.word, ''))
    # Weitergabe
    if code:
        fw = ChipView('forward', 'Weitergabe', 'Gestoppt', 'err', WORKER_CODE_TEXT.get(code, code))
    elif ctx.com_issue and ctx.demo:
        word = {'busy': 'Port belegt', 'write_failed': 'Schreibfehler', 'unclear': 'Ergebnis unklar'}.get(
            ctx.com_issue, 'Unbekannt')
        fw = ChipView('forward', 'Weitergabe', word, 'warn' if ctx.com_issue != 'unclear' else 'unclear',
                      f'{ctx.bridge_port} (Brückenseite)' if ctx.bridge_port else 'Brückenseite')
    elif not peer_ok:
        fw = ChipView('forward', 'Weitergabe', 'Keine Weitergabe',  'info',
                      'Pi antwortet nicht' if readiness.peer == 'backoff' else '')
    elif ctx.waiting_for_run:
        fw = ChipView('forward', 'Weitergabe', 'Keine Weitergabe', 'info', 'kein Lauf')
    elif readiness.com == 'driver_ready' and (ctx.demo or (ctx.release and not ctx.dut_locked)):
        fw = ChipView('forward', 'Weitergabe', 'Bestätigt', 'info', 'vom Port angenommen'
                      if not ctx.demo else 'Demo-Werte vom Port angenommen')
    elif ctx.dut_locked:
        fw = ChipView('forward', 'Weitergabe', 'Keine Weitergabe', 'info', 'DUT-Ausgabe gesperrt')
    else:
        fw = _unknown('forward', 'Weitergabe')
    fw = ChipView(fw.key, fw.name, fw.word, fw.tone, fw.sub,
                  ports + (('Letzte Quittung', ctx.last_ack),),
                  '„Bestätigt“ heißt: der Windows-Port hat die Daten angenommen.'
                  if fw.word == 'Bestätigt' else
                  'Solange die DUT-Ausgabe gesperrt ist, schreibt die Brücke keine Messwerte an COM.')
    # GSVmulti: grün nur mit Testnachweis
    if ctx.receipt is not None and ctx.receipt.proven:
        gsv = ChipView('gsv', 'GSVmulti', 'Empfang belegt', 'ok', ctx.receipt.label)
        ghint = ('Der Test war eine Demo mit synthetischen Werten und gilt nur für genau diese '
                 'Konfiguration. Die Weitergabe von Messwerten bleibt gesperrt.' if ctx.receipt.demo else
                 'Gilt nur für genau diese Testdatei und Konfiguration.')
    elif ctx.session_confirmed:
        gsv = ChipView('gsv', 'GSVmulti', 'Übernahme bestätigt', 'info', 'Empfang nicht nachgewiesen')
        ghint = 'Nur der Empfangstest belegt Empfang. Der laufende Betrieb zeigt nur die COM-Weitergabe.'
    else:
        gsv = ChipView('gsv', 'GSVmulti', 'Kanal einstellen', 'info',
                       f'{ctx.gsv_port} · 115200 8N1 in GSVmulti' if ctx.gsv_port else 'Portpaar festlegen')
        ghint = ('Stellen Sie GSVmulti auf den Port der GSVmulti-Seite ein und bestätigen Sie das in der Einrichtung. '
                 'Nur der Empfangstest belegt Empfang.')
    gsv = ChipView(gsv.key, gsv.name, gsv.word, gsv.tone, gsv.sub,
                   (('Session', ctx.session_name or '–'),
                    ('Empfangsnachweis', ctx.receipt.label if ctx.receipt and ctx.receipt.proven
                     else 'nicht nachgewiesen')), ghint)
    return (comp, uart, pi, out, fw, gsv)


def action_bar(readiness: Readiness, worker: WorkerStatus | None, ctx: UiContext) -> ActionBar | None:
    """Genau eine nächste Aktion, höchstens zwei Knöpfe."""
    code = _worker_active_failure(readiness, worker)
    if code:
        return ActionBar('err', f'Übertragung gestoppt – {WORKER_CODE_TEXT.get(code, code)}',
                         'Die Brücke schreibt nichts mehr an COM. Diagnose exportieren und Ursache klären; '
                         'danach neu verbinden.', (('Diagnose exportieren', 'export_diagnostics', True),))
    notice = (ctx.setup.data.get('notice') if ctx.setup is not None else None)
    if notice:
        title, text = explain_code(notice)
        return ActionBar('err', title, text)
    if ctx.com_issue and ctx.demo:
        p = ctx.bridge_port or 'Port'
        g = f'GSVmulti hört auf {ctx.gsv_port}' if ctx.gsv_port else 'GSVmulti-Port nicht festgelegt'
        return {
            'busy': ActionBar('warn', f'{p} (Brückenseite) belegt – {g}',
                              'Ein anderes Programm hält ' + p + '. Es wurde nichts gesendet. '
                              'Schließen Sie es und prüfen Sie erneut.', (('Erneut prüfen', 'recheck', True),)),
            'write_failed': ActionBar('warn', f'Schreibfehler auf {p} (Brückenseite)',
                                      'Der Port hat den Wert nicht vollständig angenommen. Er wird nicht '
                                      'erneut gesendet; es geht mit dem nächsten zulässigen Wert weiter.'),
            'unclear': ActionBar('warn', f'Ergebnis unklar auf {p} (Brückenseite)',
                                 'Keine Bestätigung vom Port nach dem Schreiben. Ob GSVmulti den Wert erhalten '
                                 'hat, ist offen. Nicht wiederholt, im Journal vermerkt.'),
        }.get(ctx.com_issue)
    peer = readiness.peer
    if peer == 'backoff':
        t = f'Keine Antwort vom Pi seit {ctx.last_report}' if ctx.last_report else 'Keine Antwort vom Pi'
        return ActionBar('err', t, 'Mögliche Ursachen: Pi-Dienst, Netzwerk oder Strom des Pi. Wiederholung nach '
                         '1, 2, 4, 8 s, dann alle 8 s. „Nicht mehr versuchen“ stoppt das automatische '
                         'Wiederverbinden.', (('Nicht mehr versuchen', 'stop_retry', False),
                                              ('Erneut versuchen', 'reconnect', True)))
    if peer == 'disconnected':
        na = readiness.next_action
        if readiness.adapter == 'unavailable' or na == 'adapter_unavailable':
            return ActionBar('err', 'USB-Adapter nicht gefunden',
                             'Stecken Sie den USB-Seriell-Adapter an und prüfen Sie erneut.',
                             (('Erneut prüfen', 'recheck_adapter', True),))
        if na == 'pairing_required':
            return ActionBar('warn', 'Pi nicht gekoppelt', CONNECTION_CODE_TEXT[na][1],
                             (('Pi koppeln', 'goto_pairing', True),))
        if na in CONNECTION_CODE_TEXT:
            return ActionBar('err', CONNECTION_CODE_TEXT[na][0], CONNECTION_CODE_TEXT[na][1],
                             (('Erneut versuchen', 'reconnect', True),))
        if na not in (None, 'connect', 'reconnect', 'disconnected', 'adapter_unavailable'):
            title, text = explain_code(na)
            return ActionBar('info', title, text, (('Erneut versuchen', 'reconnect', True),))
        if ctx.pi_name:
            return ActionBar('info', 'Es läuft keine Übertragung',
                             'Ein Pi-Wechsel ist jetzt möglich. Verbinden Sie danach neu.',
                             (('Verbinden', 'connect', True),))
        return None
    if peer == 'authenticated':
        if ctx.waiting_for_run:
            return ActionBar('info', 'Wartet auf einen Lauf', 'Starten Sie den Lauf auf dem Pi. '
                             'Die Brücke startet keinen Lauf.')
    return None


def event_entry(event: BridgeEvent, ctx: UiContext | None = None, now: str = '') -> JournalEntry:
    """BridgeEvent -> Journalzeile. Keine Rohdetails (Zugangsdaten) übernehmen."""
    if event.kind == 'connection':
        title = {'authenticated': 'Pi verbunden (Identität geprüft)', 'backoff': 'Pi antwortet nicht',
                 'disconnected': 'Verbindung beendet'}.get(event.code or '')
        if title is None and event.code in CONNECTION_CODE_TEXT:
            return JournalEntry(now, CONNECTION_CODE_TEXT[event.code][0], tone='err', fault=True)
        title = title or 'Verbindungsereignis'
        bad = event.code in ('backoff',)
        return JournalEntry(now, title, tone='err' if bad else 'info', fault=bad)
    if event.kind in ('blocked', 'audit_failed', 'connection_failed'):
        return JournalEntry(now, f'Übertragung gestoppt – {WORKER_CODE_TEXT.get(event.code or event.kind, event.kind)}',
                            'keine weiteren Werte an COM', tone='err', fault=True)
    if event.kind == 'started':
        return JournalEntry(now, 'Übertragung gestartet', 'Demo · Werte sind synthetisch', tone='info')
    if event.kind == 'stopped':
        return JournalEntry(now, 'Übertragung beendet', tone='info')
    if event.kind == 'exchange':
        outcome = (event.detail or {}).get('outcome')
        if outcome in ('unknown', 'stopped'):
            return JournalEntry(now, 'Weitergabe unklar', 'nicht wiederholt', tone='warn', fault=True)
        return JournalEntry(now, 'Weitergabe', str(outcome or ''), tone='info')
    return JournalEntry(now, 'Ereignis', event.kind, tone='info')


# ---------------------------------------------------------------- Einrichtung
FP_PROFILE = '{fingerprint}'
FP_OTHER = '{peer_fingerprint}'
UART_WIRING = ('115200 Baud, 8N1, kein Handshake. TX des Adapters an RX des Pi, RX des Adapters an TX des Pi, '
               'GND an GND. VCC, CTS und RTS bleiben frei.')
_INV = ('statusrows', 'Bestandsaufnahme', (('Windows', 'Windows 11, 64 Bit – unterstützt', 'ok'),
                                           ('Brücke', '{version}', 'info')))
_PROFILE = ('card', 'Profil geladen', (('Anzeigename', '{pi_name}'), ('Pi-ID', '{pi_id}')))
_WAY = ('radios', 'way', (('Netzwerk', 'LAN oder Tailscale, verschlüsselt', True),
                          ('UART (USB-Adapter)', 'Direktverbindung, unverschlüsselt', False)))
_WAY_U = ('radios', 'way', (('Netzwerk', 'LAN oder Tailscale, verschlüsselt', False),
                            ('UART (USB-Adapter)', 'Direktverbindung, unverschlüsselt', True)))
_PORTS = ('card', 'Portpaar', (('Brückenseite', '{bridge_port}'), ('Gegenport für GSVmulti', '{gsv_port}')))
_TEST_INFO = ('info', 'warn', 'Synthetischer Test – getrennte GSVmulti-Testsession verwenden',
              'Die Testwerte sind künstlich und dürfen nicht in einer Kalibriermessung landen.', ())
_NEXT = 'Weiter'


def _s(step, lead, blocks, nxt=_NEXT, ready=False, back=True, header=None):
    """Ein Einrichtungszustand: Schritt, Leitsatz, Blöcke, Fuß."""
    return dict(step=step, lead=lead, blocks=tuple(blocks), next=nxt, ready=ready, back=back, header=header)


SETUP: dict[str, dict] = {
    'E1': _s(1, 'Schritt 1 von 5: Komponenten prüfen.', [
        _INV,
        ('info', 'warn', 'COM-Portpaar fehlt',
         'Für GSVmulti wird ein virtuelles Portpaar (com0com) mit freien COM-Namen benötigt.', ()),
        ('text', 'Die Brücke legt kein Portpaar an und ändert keines. Sie prüft nur, ob eines vorhanden ist; '
                 'andernfalls geben Sie ein vorhandenes Portpaar ausdrücklich an.'),
        ('button', 'Portpaar prüfen', 'install', True),
        ('button', 'Vorhandenes Portpaar angeben', 'manual_pair', False)], back=False),
    'E1manual': _s(1, 'Schritt 1 von 5: Vorhandenes Portpaar angeben.', [
        ('info', 'warn', 'Portpaar manuell – nicht von der App geprüft',
         'Die App legt kein Portpaar an und ändert keines. Wählen Sie zwei verschiedene, bereits vorhandene '
         'COM-Ports, die zusammen ein Paar bilden (Brückenseite und GSVmulti-Seite).', ()),
        ('radios_dyn', 'bridge_port', 'Brückenseite (hier schreibt die Brücke)'),
        ('radios_dyn', 'gsv_port', 'GSVmulti-Seite (hier hört GSVmulti)'),
        ('button', 'Portpaar übernehmen', 'set_port_pair', True)], back=False),
    'E1uac': _s(1, 'Schritt 1 von 5: Komponenten prüfen.', [
        ('info', 'err', 'IT-Freigabe erforderlich',
         'Windows hat die Administratorfreigabe nicht erteilt. Die Brücke ändert ohne Freigabe nichts. Bitten Sie '
         'Ihre IT, das Portpaar einzurichten; danach genügt „Erneut prüfen“.', (('Erneut prüfen', 'recheck', True),)),
        _INV, ('card', 'COM-Portpaar fehlt', (('', 'Einrichtung nicht möglich ohne Administratorfreigabe.'),))],
        back=False),
    'E1restart': _s(1, 'Schritt 1 von 5: Komponenten prüfen.', [
        ('info', 'warn', 'Neustart nötig',
         'Windows muss neu starten, damit das Portpaar nutzbar wird. Die Einrichtung wird danach bei Schritt 1 '
         'fortgesetzt. Speichern Sie vorher offene Arbeit in anderen Programmen.',
         (('Später', 'later', False), ('Jetzt neu starten', 'restart', True))),
        _INV, ('card', 'COM-Portpaar eingerichtet', (('', 'Wird erst nach dem Neustart nutzbar.'),))], back=False),
    'E1ok': _s(1, 'Schritt 1 von 5: Portpaar festgelegt.', [
        _INV, ('card', 'Portpaar manuell angegeben', (('', 'Brückenseite {bridge_port} · GSVmulti-Seite {gsv_port}. '
                                                           'Manuell, nicht von der App geprüft.'),))],
        ready=True, back=False),
    'E2': _s(2, 'Schritt 2 von 5: Pi-Profil öffnen.', [
        ('drop', 'Profil hierher ziehen', 'Datei „pi.dispread“', 'Profil öffnen …', 'open_profile'),
        ('text', 'Laden Sie das Profil in der Werkbank herunter (Brücke einrichten › Profil). Öffnen allein '
                 'gibt noch nichts frei: Kopplung und Ausgabe folgen getrennt.')], header='nopi'),
    'E2b': _s(2, 'Schritt 2 von 5: Pi koppeln.', [
        ('card', 'Profil geladen', (('Anzeigename', '{pi_name}'), ('Pi-ID', '{pi_id}'))),
        ('fp', 'Fingerabdruck (SHA-256)', FP_PROFILE),
        ('text', 'Vergleichen Sie den Fingerabdruck mit der Werkbank (Brücke einrichten › Profil).'),
        ('check', 'Der Fingerabdruck stimmt mit der Werkbank überein.', 'fp_ok'),
        ('code', 'Kopplungscode', 'Der Code ist 5 Minuten gültig und nur einmal verwendbar.'),
        ('button', 'Koppeln', 'pair', True)]),
    'E2exp': _s(2, 'Schritt 2 von 5: Pi koppeln.', [
        ('info', 'err', 'Code abgelaufen',
         'Der Kopplungscode war 5 Minuten gültig. Es wurde nichts gekoppelt. Erzeugen Sie in der Werkbank '
         'einen neuen Code und geben Sie ihn ein.', (('Neuen Code eingeben', 'new_code', True),)), _PROFILE]),
    'E2bad': _s(2, 'Schritt 2 von 5: Pi koppeln.', [
        ('info', 'err', 'Fingerabdruck stimmt nicht – falsches Gerät',
         'Der Pi, der geantwortet hat, ist nicht der Pi aus dem Profil. Es wurde nichts gekoppelt und nichts '
         'gesendet. Prüfen Sie, ob Profil und Pi zusammengehören.',
         (('Anderes Profil öffnen', 'open_profile', True),)),
        ('card', 'Fingerabdrücke im Vergleich', ()),
        ('fp', 'Im Profil', FP_PROFILE),
        ('fpdiff', 'Beim antwortenden Gerät (fett unterstrichen = abweichend)', FP_OTHER, FP_PROFILE)]),
    'E2ok': _s(2, 'Schritt 2 von 5: Pi ist gekoppelt.', [
        ('card', 'Pi gekoppelt', (('Anzeigename', '{pi_name}'), ('Pi-ID', '{pi_id}'),
                                  ('Zugang', 'Gilt nur für diesen PC und ist in der Werkbank widerrufbar.')))],
        ready=True),
    'E3': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        _WAY,
        ('radios_dyn', 'found', 'Adresse aus dem Profil und gefundene Pi im Netz'),
        ('text', 'Ein gefundener Name ist kein Identitätsnachweis. Erst die Prüfung gegen das Profil bestätigt den Pi.'),
        ('entry', 'Adresse oder Name manuell eintragen',
         'Tailscale wird nur benutzt, wenn Sie hier den Tailscale-Namen oder die Adresse eintragen. Ohne Tailscale '
         'braucht es ein gemeinsames Netz oder die VPN-Route Ihrer IT.'),
        ('button', 'Suche wiederholen', 'rescan', False)], nxt='Verbinden', ready=True),
    'E3err': _s(3, 'Schritt 3 von 5: Verbindung herstellen.', [
        ('error_code', 'code', 'Verbindung nicht möglich')], nxt='Verbinden'),
    'E3uart': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        _WAY_U,
        ('radios_dyn', 'adapter', 'USB-Adapter'),
        ('card', 'Verdrahtung', (('', UART_WIRING),))], nxt='Verbinden', ready=True, header='uart'),
    'E3uart2': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        ('info', 'warn', 'Zwei gleiche Adapter – Auswahl nötig',
         'Die Adapter lassen sich nur am USB-Anschluss unterscheiden. Wählen Sie den Adapter, der am Pi hängt.', ()),
        _WAY_U,
        ('radios_dyn', 'adapter', 'USB-Adapter'),
        ('card', 'Verdrahtung', (('', UART_WIRING),))], nxt='Verbinden', header='uart'),
    'E3ok': _s(3, 'Schritt 3 von 5: Pi verbunden.', [
        ('info', 'ok', 'Pi verbunden (Identität geprüft)',
         'Der Pi hat seine Identität belegt; der Fingerabdruck passt zum Profil. Das ist noch keine Messfreigabe.', ()),
        ('card', '', (('Weg', 'Netzwerk (LAN)'), ('Endpunkt', '{endpoint}'),
                      ('Protokoll', '{protocol}')))], ready=True),
    'E3fail': _s(3, 'Schritt 3 von 5: Verbindung herstellen.', [
        ('info', 'err', 'Adapter erkannt, Pi antwortet nicht',
         'Der USB-Adapter ist da, aber der Pi hat nicht geantwortet. Mögliche Ursachen:', (('Erneut versuchen', 'reconnect', True),)),
        ('bullets', ('Der Pi-Dienst läuft nicht.', 'TX, RX oder GND sind nicht richtig verbunden.',
                     'Die Parameter stimmen nicht (115200 Baud, 8N1).')),
        ('card', '', (('Adapter', 'USB-Seriell-Adapter · COM6'), ('USB-Ort', 'Port 3'),
                      ('Parameter', '115200 Baud, 8N1, kein Handshake')))], header='uart'),
    'E4locked': _s(4, 'Schritt 4 von 5: GSVmulti manuell einrichten.', [
        ('info', 'warn', 'Automatische Session noch nicht freigegeben',
         'Es wird keine Sessiondatei erzeugt. Stellen Sie GSVmulti von Hand ein.', ()),
        ('card', 'In GSVmulti selbst einstellen', (('', 'In GSVmulti den Kanal auf {gsv_port} 115200 8N1 einstellen.'),
                                                  ('Port', '{gsv_port}'), ('Baudrate', '115200'),
                                                  ('Format', '8N1, kein Handshake'))),
        ('text', 'Ob GSVmulti die Einstellungen übernimmt, belegt erst der Empfangstest.'),
        ('check_dyn', 'Ich habe GSVmulti so eingestellt.', 'session_ok', 'session_confirmed')], nxt='Weiter'),
    'E4': _s(4, 'Schritt 4 von 5: GSVmulti-Session erzeugen.', [
        _PORTS, ('text', 'Die Session verweist auf {gsv_port}. Vorhandene GSVmulti-Sessions bleiben unverändert.'),
        ('button', 'Session erzeugen', 'export_session', True)]),
    'E4ok': _s(4, 'Schritt 4 von 5: Session in GSVmulti öffnen.', [
        ('info', 'info', 'Sessiondatei erzeugt: {session_name}',
         'Die Datei allein belegt nicht, dass GSVmulti die Einstellungen übernommen hat.',
         (('Ordner öffnen', 'open_folder', False), ('In GSVmulti öffnen', 'open_in_gsv', True))),
        ('card', 'In GSVmulti: Datei › Öffnen …', (('', 'Die erzeugte Datei auswählen.'),)),
        ('text', 'Hier bestätigen, dass die Session geöffnet ist.'),
        ('check', 'Ich habe die Session in GSVmulti geöffnet.', 'session_ok')]),
    'E4unk': _s(4, 'Schritt 4 von 5: GSVmulti manuell einrichten.', [
        ('info', 'warn', 'GSVmulti-Version unbekannt – Automatik gesperrt',
         'Für diese Version gibt es keine geprüfte Vorlage. Es wird keine Sessiondatei erzeugt. '
         'Die manuelle Anleitung ist eingeschränkt.', ()),
        ('card', 'Manuelle Anleitung (eingeschränkt)', (('', 'Stellen Sie in GSVmulti selbst ein:'),
                                                       ('Port', '{gsv_port}'), ('Baudrate', '115200'),
                                                       ('Format', '8N1, kein Handshake'))),
        ('text', 'Die Menüführung Ihrer GSVmulti-Version ist nicht geprüft. Ob GSVmulti die Einstellungen '
                 'übernimmt, belegt erst der Empfangstest.'),
        ('check', 'Ich habe GSVmulti so eingestellt.', 'session_ok')]),
    'E5': _s(5, 'Schritt 5 von 5: Empfang prüfen.', [
        _TEST_INFO,
        ('text', 'Die Brücke sendet 600 synthetische Werte mit 10 Hz (etwa 60 s). GSVmulti zeichnet sie in der '
                 'Testsession auf.'),
        ('check', 'Ich verwende eine getrennte GSVmulti-Testsession.', 'test_session_ok'),
        ('button', 'Test starten', 'start_demo_check', True)]),
    'E5run': _s(5, 'Schritt 5 von 5: Empfang prüfen.', [
        _TEST_INFO,
        ('progress', 'Test läuft', '{progress_text}', '{progress_value}'),
        ('text', 'Der Test lässt sich nicht abbrechen; der Pi beendet ihn nach der eingestellten Anzahl Werte.')],
        back=False),
    'E5done': _s(5, 'Schritt 5 von 5: Test gesendet.', [
        _TEST_INFO,
        ('info', 'warn', 'Empfang nicht nachgewiesen – Werte in GSVmulti selbst prüfen',
         '{written} synthetische Werte wurden an den COM-Port übergeben. Ob GSVmulti sie empfangen hat, prüft die '
         'Brücke nicht (Testdateivergleich noch nicht verfügbar). Vergleichen Sie die Aufzeichnung der '
         'Testsession in GSVmulti selbst.', ())], nxt='Fertig', ready=True),
    'E5file': _s(5, 'Schritt 5 von 5: Empfang prüfen.', [
        _TEST_INFO,
        ('info', 'info', 'Testdatei auswählen',
         'Der Test ist gesendet. Speichern Sie die Aufzeichnung in GSVmulti und wählen Sie die originale Datei '
         'aus. Die Brücke vergleicht jeden Wert und die Reihenfolge.',
         (('Testdatei auswählen …', 'choose_test_file', True),))]),
    'E5ok': _s(5, 'Empfang belegt für diese Testdatei und Konfiguration', [
        ('info', 'ok', '600/600 Werte stimmen überein',
         'Der Vergleich gilt nur für die ausgewählte Testdatei und diese Konfiguration, nicht für spätere Läufe.', ()),
        ('card', '', (('Datei', 'GSVmulti_Test_Prüfstand2.txt'), ('Test', '14:02, synthetisch'),
                      ('Werte', '600 von 600'))),
        ('fp', 'SHA-256', '{test_sha256}'),
        ('text', 'Im Betrieb zeigt die Brücke danach „Empfang belegt“ nur für diese Konfiguration; die '
                 'COM-Weitergabe bleibt eine eigene Aussage.')], nxt='Fertig', ready=True),
    'E5bad': _s(5, 'Schritt 5 von 5: Empfang nicht belegt.', [
        ('info', 'err', 'Abweichung: 598/600',
         'Zwei Werte der Testdatei stimmen nicht mit dem Test überein. Der Empfang ist für diese Datei nicht belegt.',
         (('Test wiederholen', 'start_demo_check', True),)),
        ('card', 'Fehlende Werte', (('Nr. 211', 'fehlt in der Testdatei'), ('Nr. 212', 'fehlt in der Testdatei')))]),
}


_TOKEN = _re.compile(r'\{([a-z_0-9]+)\}')


def fill(obj, mapping):
    """Platzhalter {name} aus dem Kontext ersetzen; fehlender Wert -> „–“, nie ein Beispielwert."""
    if isinstance(obj, str):
        return _TOKEN.sub(lambda m: str(mapping.get(m.group(1)) or '–'), obj)
    if isinstance(obj, (tuple, list)):
        return tuple(fill(o, mapping) for o in obj)
    return obj


def setup_spec(ctx):
    """SETUP-Zustand mit Werten aus ctx (und ctx.setup.data) gefüllt."""
    m = dict(bridge_port=ctx.bridge_port, gsv_port=ctx.gsv_port, version=ctx.version, protocol=ctx.protocol,
             pi_name=ctx.pi_name, pi_id=ctx.pi_id, endpoint=ctx.endpoint, fingerprint=ctx.fingerprint,
             session_name=ctx.session_name)
    data = ctx.setup.data
    m.update({k: v for k, v in data.items() if isinstance(v, (str, int, float))})
    spec = dict(SETUP[ctx.setup.variant])
    blocks = []
    for blk in spec['blocks']:
        kind = blk[0]
        if kind == 'radios_dyn':
            name, heading = blk[1], blk[2]
            items = data.get({'found': 'found_items', 'adapter': 'adapter_items'}.get(name, 'ports_' + name))
            if items is None:
                items = tuple((p, 'vorhandener COM-Port', p == (ctx.bridge_port if name == 'bridge_port' else
                                                              ctx.gsv_port)) for p in data.get('ports', ()))
            if not items:
                blocks.append(('text', EMPTY_CHOICE.get(name, 'Keine Einträge gefunden.')))
            else:
                blocks.append(('radios', name, tuple(items), heading))
        elif kind == 'check_dyn':
            blocks.append(('check', blk[1], blk[2], bool(data.get(blk[3]))))
        elif kind == 'error_code':
            title, text = explain_code(data.get('code'))
            blocks.append(('info', 'err', title if title != 'Unbekannt' else 'Unbekannt',
                           text, (('Erneut versuchen', 'reconnect', True),)))
        else:
            blocks.append(blk)
    blocks = fill(tuple(blocks), m)
    if data.get('notice'):
        title, text = explain_code(data['notice'])
        blocks = (('info', 'err', title, text, ()),) + blocks
    spec['blocks'] = blocks
    return spec


EMPTY_CHOICE = {'found': 'Keine Adresse im Profil und nichts gefunden. Tragen Sie unten eine Adresse ein.',
                'adapter': 'Kein unterstützter USB-Seriell-Adapter gefunden. Stecken Sie ihn an und suchen Sie erneut.',
                'bridge_port': 'Keine COM-Ports gefunden.', 'gsv_port': ''}
