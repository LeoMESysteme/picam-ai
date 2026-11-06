"""Alle Oberflächentexte und die Abbildung Zustand -> (Wort, Ton, Unterzeile, Aktion).

Wahrheitsregeln (DESIGN.md): grün nur belegt; "Weitergabe" ist nie
GSVmulti-Empfang; "Empfang belegt" nur mit Testnachweis (ctx.receipt.proven);
ein Worker-Code oder output_ready=False wird nie von "Pi verbunden"
überstimmt; unbekannte Werte erscheinen als "Unbekannt", neutral.
"""
from __future__ import annotations

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
}

_TONE_OF_PEER = {'authenticated': 'ok', 'disconnected': 'info', 'backoff': 'err', 'connecting': 'info'}


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
    if ctx.com_issue and ctx.demo:
        word = {'busy': f'{ctx.bridge_port} belegt', 'write_failed': 'Schreibfehler',
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
    pair = f'COM4 ↔ COM5 (com0com)'.replace('COM4', ctx.bridge_port).replace('COM5', ctx.gsv_port)
    ports = (('Brückenseite', ctx.bridge_port), ('GSVmulti-Seite', ctx.gsv_port))
    # Komponenten
    comp = {'ready': ChipView('components', 'Komponenten', 'Installiert', 'ok'),
            'missing': ChipView('components', 'Komponenten', 'Portpaar fehlt', 'err'),
            'restart': ChipView('components', 'Komponenten', 'Neustart nötig', 'warn')
            }.get(readiness.components, _unknown('components', 'Komponenten'))
    comp = ChipView(comp.key, comp.name, comp.word, comp.tone, comp.sub,
                    (('Windows', '11, 64 Bit'), ('App-Version', ctx.version), ('Portpaar', pair)),
                    'Alle Systemkomponenten sind vorhanden. Das sagt nichts über Verbindung oder Empfang.'
                    if comp.tone == 'ok' else '')
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
                   ('Protokoll', ctx.protocol),
                   ('Letzte Meldung', ctx.last_report or '–')))
    # Ausgabe
    if code:
        out = ChipView('output', 'Ausgabe', 'Blockiert', 'err', WORKER_CODE_TEXT.get(code, code))
    elif not peer_ok:
        out = ChipView('output', 'Ausgabe', 'Unbekannt', 'info',
                       '' if readiness.peer == 'disconnected' and not ctx.pi_name else 'solange der Pi nicht antwortet')
        out = ChipView(out.key, out.name, out.word, out.tone, '')
    elif ctx.waiting_for_run:
        out = ChipView('output', 'Ausgabe', 'Wartet auf Lauf', 'info')
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
    out = ChipView(out.key, out.name, out.word, out.tone, out.sub,
                   (('Ausgabe', out.word),), hints.get(out.word, ''))
    # Weitergabe
    if code:
        fw = ChipView('forward', 'Weitergabe', 'Gestoppt', 'err', WORKER_CODE_TEXT.get(code, code))
    elif ctx.com_issue and ctx.demo:
        word = {'busy': 'Port belegt', 'write_failed': 'Schreibfehler', 'unclear': 'Ergebnis unklar'}.get(
            ctx.com_issue, 'Unbekannt')
        fw = ChipView('forward', 'Weitergabe', word, 'warn' if ctx.com_issue != 'unclear' else 'unclear',
                      f'{ctx.bridge_port} (Brückenseite)')
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
        gsv = ChipView('gsv', 'GSVmulti', 'Noch nicht gekoppelt', 'info', 'Empfang nicht nachgewiesen')
        ghint = 'Nur der Empfangstest belegt Empfang.'
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
    if ctx.com_issue and ctx.demo:
        p = ctx.bridge_port
        return {
            'busy': ActionBar('warn', f'{p} (Brückenseite) belegt – GSVmulti hört auf {ctx.gsv_port}',
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
FP_PROFILE = 'a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de'
FP_OTHER = 'a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 55e0 1b6c 9a46 3f02'
UART_WIRING = ('115200 Baud, 8N1, kein Handshake. TX des Adapters an RX des Pi, RX des Adapters an TX des Pi, '
               'GND an GND. VCC, CTS und RTS bleiben frei.')
_INV = ('card', 'Bestandsaufnahme', (('Windows 11, 64 Bit', 'Unterstützte Windows-Version'),
                                     ('Brücke 0.1.0.dev0', 'Installiert')))
_PROFILE = ('card', 'Profil geladen', (('Anzeigename', 'Prüfstand 2'), ('Pi-ID', 'pi-4b7e09c1')))
_WAY = ('radios', 'way', (('Netzwerk', 'LAN oder Tailscale, verschlüsselt', True),
                          ('UART (USB-Adapter)', 'Direktverbindung, unverschlüsselt', False)))
_WAY_U = ('radios', 'way', (('Netzwerk', 'LAN oder Tailscale, verschlüsselt', False),
                            ('UART (USB-Adapter)', 'Direktverbindung, unverschlüsselt', True)))
_PORTS = ('card', 'Portpaar', (('Brückenseite', 'COM4'), ('Gegenport für GSVmulti', 'COM5')))
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
        ('text', 'Die Brücke legt das Portpaar einmalig an. Windows fragt dafür nach der Administratorfreigabe. '
                 'Es wird nichts verändert, was bereits vorhanden ist.'),
        ('button', 'Portpaar einrichten (Administratorfreigabe)', 'install', True)], back=False),
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
    'E1ok': _s(1, 'Schritt 1 von 5: Komponenten sind bereit.', [
        _INV, ('card', 'Portpaar eingerichtet', (('', 'Brückenseite COM4 · GSVmulti-Seite COM5. '
                                                      'Selbsttest in beide Richtungen bestanden.'),))],
        ready=True, back=False),
    'E2': _s(2, 'Schritt 2 von 5: Pi-Profil öffnen.', [
        ('drop', 'Profil hierher ziehen', 'Datei „pi.dispread“', 'Profil öffnen …', 'open_profile'),
        ('text', 'Laden Sie das Profil in der Werkbank herunter (Brücke einrichten › Profil). Öffnen allein '
                 'gibt noch nichts frei: Kopplung und Ausgabe folgen getrennt.')], header='nopi'),
    'E2b': _s(2, 'Schritt 2 von 5: Pi koppeln.', [
        ('card', 'Profil geladen', (('Anzeigename', 'Prüfstand 2'), ('Pi-ID', 'pi-4b7e09c1'))),
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
        ('card', 'Pi gekoppelt', (('Anzeigename', 'Prüfstand 2'), ('Pi-ID', 'pi-4b7e09c1'),
                                  ('Zugang', 'Gilt nur für diesen PC und ist in der Werkbank widerrufbar.')))],
        ready=True),
    'E3': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        _WAY,
        ('radios', 'found', (('prüfstand2.local', '192.168.10.24 · gefunden per mDNS', True, 'Unbestätigt'),
                             ('pi-labor-b.local', '192.168.10.37 · gefunden per mDNS', False, 'Unbestätigt')),
         'Gefundene Pi im Netz'),
        ('text', 'Ein gefundener Name ist kein Identitätsnachweis. Erst die Prüfung gegen das Profil bestätigt den Pi.'),
        ('entry', 'Adresse oder Name manuell eintragen',
         'Tailscale wird nur benutzt, wenn Sie hier den Tailscale-Namen oder die Adresse eintragen. Ohne Tailscale '
         'braucht es ein gemeinsames Netz oder die VPN-Route Ihrer IT.'),
        ('button', 'Suche wiederholen', 'rescan', False)], nxt='Verbinden', ready=True),
    'E3uart': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        _WAY_U,
        ('radios', 'adapter', (('USB-Seriell-Adapter · COM6', 'USB-Ort: Port 3', True),), 'USB-Adapter'),
        ('card', 'Verdrahtung', (('', UART_WIRING),))], nxt='Verbinden', ready=True, header='uart'),
    'E3uart2': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        ('info', 'warn', 'Zwei gleiche Adapter – Auswahl nötig',
         'Die Adapter lassen sich nur am USB-Anschluss unterscheiden. Wählen Sie den Adapter, der am Pi hängt.', ()),
        _WAY_U,
        ('radios', 'adapter', (('USB-Seriell-Adapter · COM6', 'USB-Ort: Port 3 (Hub 1)', False),
                               ('USB-Seriell-Adapter · COM7', 'USB-Ort: Port 4 (Hub 1)', False)), 'USB-Adapter'),
        ('card', 'Verdrahtung', (('', UART_WIRING),))], nxt='Verbinden', header='uart'),
    'E3ok': _s(3, 'Schritt 3 von 5: Pi verbunden.', [
        ('info', 'ok', 'Pi verbunden (Identität geprüft)',
         'Der Pi hat seine Identität belegt; der Fingerabdruck passt zum Profil. Das ist noch keine Messfreigabe.', ()),
        ('card', '', (('Weg', 'Netzwerk (LAN)'), ('Endpunkt', 'wss://192.168.10.24 (Beispiel)'),
                      ('Protokoll', 'Version 2')))], ready=True),
    'E3fail': _s(3, 'Schritt 3 von 5: Verbindung herstellen.', [
        ('info', 'err', 'Adapter erkannt, Pi antwortet nicht',
         'Der USB-Adapter ist da, aber der Pi hat nicht geantwortet. Mögliche Ursachen:', (('Erneut versuchen', 'reconnect', True),)),
        ('bullets', ('Der Pi-Dienst läuft nicht.', 'TX, RX oder GND sind nicht richtig verbunden.',
                     'Die Parameter stimmen nicht (115200 Baud, 8N1).')),
        ('card', '', (('Adapter', 'USB-Seriell-Adapter · COM6'), ('USB-Ort', 'Port 3'),
                      ('Parameter', '115200 Baud, 8N1, kein Handshake')))], header='uart'),
    'E4': _s(4, 'Schritt 4 von 5: GSVmulti-Session erzeugen.', [
        _PORTS, ('text', 'Die Session verweist auf COM5. Vorhandene GSVmulti-Sessions bleiben unverändert.'),
        ('button', 'Session erzeugen', 'export_session', True)]),
    'E4ok': _s(4, 'Schritt 4 von 5: Session in GSVmulti öffnen.', [
        ('info', 'info', 'Sessiondatei erzeugt: GSVmulti_Prüfstand2_COM5.ucf',
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
                                                       ('Port', 'COM5'), ('Baudrate', '115200'),
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
        ('progress', 'Test läuft', '312 von 600 Werten gesendet (10 Hz, synthetisch)', 52),
        ('button', 'Abbrechen', 'cancel_test', False)]),
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
        ('fp', 'SHA-256', '9f2c 41ab 07d3 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de'),
        ('text', 'Im Betrieb zeigt die Brücke danach „Empfang belegt“ nur für diese Konfiguration; die '
                 'COM-Weitergabe bleibt eine eigene Aussage.')], nxt='Fertig', ready=True),
    'E5bad': _s(5, 'Schritt 5 von 5: Empfang nicht belegt.', [
        ('info', 'err', 'Abweichung: 598/600',
         'Zwei Werte der Testdatei stimmen nicht mit dem Test überein. Der Empfang ist für diese Datei nicht belegt.',
         (('Test wiederholen', 'start_demo_check', True),)),
        ('card', 'Fehlende Werte', (('Nr. 211', 'fehlt in der Testdatei'), ('Nr. 212', 'fehlt in der Testdatei')))]),
}
