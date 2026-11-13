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
TEST_RELEASE_LINE = ('Testfreigabe – nicht abgenommen, keine Messfreigabe. Ungültige Werte werden ausgelassen; '
                     'GSVmulti zeigt dann den letzten Wert unmarkiert weiter.')
TEST_RELEASE_HINT = ('Der Pi-Bediener hat echte Werte ausdrücklich zum Test freigegeben. Das ist keine Abnahme '
                     'und kein Nachweis des GSVmulti-Empfangs.')
NO_PI = 'Kein Pi gekoppelt · Weg noch offen'
DIRECT_TITLE = 'UART direkt – Adapter noch offen'
NO_PI_WAY_SET = 'Kein Pi gekoppelt'
DIRECT_DUT_LINE = 'Die Brücke gibt in diesem Weg keine Werte weiter – Messfreigabe nicht durch die Brücke'
DIRECT_UNUSED = 'nicht benutzt'
DIRECT_UNUSED_SUB = 'UART direkt'
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
EXIT_KEEP, EXIT_QUIT, EXIT_CANCEL = 'Weiter übertragen', 'Beenden', 'Abbrechen'
REASON_DISCONNECT_FIRST = 'Erst Verbindung trennen'
REASON_TRANSMISSION_FIRST = 'Erst Übertragung beenden'
SWITCH_PI = 'Zu diesem Pi wechseln'
INFO_ABOUT = 'Über'
INFO_OPEN_SETTINGS = 'Einstellungen öffnen …'
DISCONNECT_TITLE = 'Verbindung trennen?'
DISCONNECT_TEXT = 'Die Verbindung zum Pi und die Übertragung an GSVmulti enden. Der Lauf auf dem Pi läuft weiter.'
JOURNAL_DETAILS = 'Begrenzt, Zugangsdaten werden nicht protokolliert.'

# ---- UX2: Kopf, Kacheln, Symbolleiste, Fenster
MODE_SHORT = {'uart_direct': 'UART direkt', 'uart_bridge': 'UART · Brücke', 'network': 'Netzwerk'}
MODE_ICON = {'uart_direct': 'plug_connected', 'uart_bridge': 'usb_stick', 'network': 'globe'}
MODE_NONE = 'Weg wählen'
MODE_TEXT = {
    'uart_direct': ('UART direkt', 'Das Pi-Kabel steckt am GSVmulti-PC, GSVmulti liest den Adapter direkt. '
                    'Die Brücke hilft nur beim Einrichten.'),
    'uart_bridge': ('UART über Brücke', 'Das Pi-Kabel steckt an diesem PC, die Brücke gibt die Werte an '
                    'GSVmulti weiter.'),
    'network': ('Netzwerk über Brücke', 'Der Pi ist über LAN oder Tailscale verbunden, verschlüsselt. '
                'Die Brücke gibt die Werte an GSVmulti weiter.'),
}


def baud_text(baud: int | None) -> str:
    """„<Rate> Baud, 8N1“ aus dem Kontext; ohne bekannte Rate nur „8N1“ (nie geraten)."""
    return f'{baud} Baud, 8N1' if baud else '8N1'


def mode_text(mode: str, ctx: UiContext | None = None) -> tuple[str, str]:
    """(Name, Erklärung) eines Wegs; Raten kommen aus dem Kontext, nie fest aus dem Text."""
    name, text = MODE_TEXT[mode]
    if ctx is not None:
        if mode == 'uart_bridge' and ctx.uart_baud:
            text += f' UART mit {ctx.uart_baud} Baud.'
        elif mode == 'uart_direct' and ctx.gsv_baud:
            text += f' GSVmulti liest mit {ctx.gsv_baud} Baud.'
    return name, text


CHIP_ICON = {'components': 'cube', 'uart': 'serial_port', 'pi': 'developer_board', 'output': 'arrow_export_ltr',
             'forward': 'arrow_forward', 'gsv': 'data_line'}
CHIP_HELP = {
    'components': 'Prüft, ob die Windows-Bausteine der Brücke vorhanden sind, vor allem das virtuelle Portpaar. '
                  'Sagt nichts über die Verbindung zum Pi oder den Empfang in GSVmulti.',
    'uart': 'Zeigt, ob der USB-Seriell-Adapter für einen UART-Weg steckt und bereit ist. Im Weg „Netzwerk“ wird '
            'er nicht gebraucht. Ein bereiter Adapter heißt nicht, dass der Pi antwortet.',
    'pi': 'Zeigt, ob die Brücke mit dem gekoppelten Pi verbunden ist und seine Identität geprüft hat. '
          'Verbunden heißt nicht, dass Werte weitergegeben werden.',
    'output': 'Zeigt, ob der Pi Werte zur Ausgabe freigibt. Die Brücke gibt selbst nichts frei und startet '
              'keine Messung.',
    'forward': 'Zeigt, ob der Windows-Port der Brückenseite geschriebene Werte angenommen hat. Weitergabe ist '
               'nicht Empfang: ob GSVmulti die Werte gelesen hat, belegt erst der Empfangstest.',
    'gsv': 'Zeigt, was über GSVmulti bekannt ist: einzustellen, von Hand bestätigt oder Empfang per Test belegt. '
           'Nur der Empfangstest belegt Empfang, und nur für genau diese Konfiguration.',
}
HEARTBEAT_ALIVE = 'Kontakt zum Pi – der Punkt pulsiert bei jedem Austausch. Das sagt nichts über die Weitergabe.'
HEARTBEAT_IDLE = 'Kein Kontakt zum Pi.'
HEARTBEAT_BUSY = 'Verbindung zum Pi wird aufgebaut …'
HEARTBEAT_RETRY = 'Keine Antwort – die Brücke versucht es automatisch erneut …'
SETTINGS = 'Einstellungen'
EXPORT_LOGS = 'Protokolle exportieren'
INFO = 'Info'
EXIT_TIP = 'Brücke beenden …'
PI_SWITCH_TIP = 'Pi wechseln'
PAIRED_TITLE = 'Gekoppelte Pi'
CURRENT_PI = 'aktuell gewählt'
COPY_TIP = 'Kopieren'
COPIED = 'Kopiert'
SAVED = 'Gespeichert'
EXPORT_LEAD = 'Das Paket enthält:'
EXPORT_NOTE = ('Die Protokolle halten fest, was die Brücke getan hat. Sie prüfen nichts und sind kein '
               'Gesundheitscheck. Messwerte und Zugangsdaten sind nicht enthalten.')
EXPORT_LOADING = 'Inhalt wird ermittelt …'
EXPORT_UNKNOWN = 'Inhalt nicht verfügbar – das Paket wird trotzdem vollständig gespeichert.'
EXPORT_SAVE = 'Speichern unter …'
EXPORT_SAVE_AGAIN = 'Erneut speichern …'
CLOSE = 'Schließen'
EXPORT_SAVING = 'Wird gespeichert …'
EXPORT_DONE = 'Protokolle gespeichert'
EXPORT_FAILED = 'Speichern fehlgeschlagen'
EXPORT_FAILED_TEXT = 'Wählen Sie einen anderen Ort und versuchen Sie es erneut.'
EXPORT_PATH = 'Datei'
OPEN_FOLDER = 'Ordner öffnen'
EXPORT_DIALOG = 'Protokolle speichern'
AUTO_CONNECT = 'Beim Start automatisch mit {pi} verbinden'
ICON_CREDIT = 'Symbole: Fluent UI System Icons, © Microsoft Corporation, MIT-Lizenz'

# ---- UX2 Runde 2: Prüfen, Moduswahl, Einstellungen, Session
CHECKING = 'Wird geprüft …'
CHECK_FAILED = 'Prüfung nicht möglich'
CHECK_FAILED_DETAIL = 'Erneut versuchen; bei Wiederholung die Protokolle exportieren.'
LEAVE_SETUP = 'Einrichtung verlassen'
RESCAN_TIP = 'Suche wiederholen'
RESCAN_PORTS_TIP = 'Ports neu einlesen'
MODES_TITLE = 'Weg wählen'
MODES_LEAD = 'Wie kommen die Werte vom Pi zu GSVmulti?'
MODE_ACTIVE = 'Aktiv'
MODE_SWITCH = 'Wechseln'
MODE_CANCEL = 'Abbrechen'
MODE_IS_ACTIVE = 'Dieser Weg ist bereits aktiv.'
MODE_UNCONFIGURED_HINT = 'Ein Wechsel startet die Einrichtung dieses Wegs.'
MODE_LOCKED_TITLE = 'Weg während der Übertragung gesperrt'
MODE_LOCKED_TEXT = 'Beenden Sie zuerst die Übertragung; dann lässt sich der Weg wechseln.'
MODE_LOADING = 'Wege werden gelesen …'
CHANGE_SETUP = 'Einrichtung erneut durchlaufen …'
NOT_SET_UP_TITLE = 'Nicht eingerichtet'
NOT_SET_UP_TEXT = 'Der gewählte Weg ist noch nicht fertig eingerichtet. Bis dahin überträgt die Brücke nichts.'
NOT_SET_UP_NO_WAY = 'Es ist noch kein Weg gewählt. Bis dahin überträgt die Brücke nichts.'
START_SETUP = 'Einrichtung starten'
SETTINGS_LOCKED = 'Während der Übertragung schreibgeschützt – Anzeige und Kopieren bleiben möglich.'
SETTINGS_LOCKED_SHORT = 'Schreibgeschützt, solange die Brücke überträgt'
SETTINGS_WAY = 'Weg'
SETTINGS_PI = 'Pi'
SETTINGS_PORTS = 'Ports'
SETTINGS_SESSION = 'GSVmulti-Session'
SETTINGS_LOGS = 'Protokolle'
SETTINGS_ABOUT = 'Über'
SETTINGS_CHOOSE_WAY = 'Weg wählen …'
SETTINGS_ENDPOINT = 'Endpunkt'
SETTINGS_TAKE_OVER = 'Übernehmen'
SETTINGS_PORTS_NOTE = ('Nach einer Änderung muss die GSVmulti-Session neu erzeugt oder bestätigt werden.')
SETTINGS_DIRECT_PI = ('Im Weg „UART direkt“ verbindet sich die Brücke nicht mit dem Pi; GSVmulti liest den '
                      'Adapter selbst.')
SETTINGS_LOGS_TEXT = 'Speichert, was die Brücke getan hat – ohne Messwerte und ohne Zugangsdaten.'
SETTINGS_LOGS_BUTTON = 'Protokolle exportieren …'
PORT_BRIDGE = 'Brückenseite (hier schreibt die Brücke)'
PORT_GSV = 'GSVmulti-Seite (hier hört GSVmulti)'
PORT_CHOOSE = 'Bitte wählen …'
ADAPTER = 'USB-Adapter'
NO_ADAPTER = 'Kein USB-Seriell-Adapter gefunden. Stecken Sie ihn an und suchen Sie erneut.'
NO_PORTS = 'Keine COM-Ports gefunden.'
SESSION_MAKE = 'Session-Datei erzeugen …'
SESSION_DIALOG = 'GSVmulti-Session speichern'
SESSION_SAVING = 'Session-Datei wird erzeugt …'
SESSION_DONE = 'Session-Datei erzeugt'
SESSION_PATH = 'Datei'
SESSION_PORT = 'Port in der Session'
SESSION_TEMPLATE = 'Vorlage'
SESSION_NOT_ACCEPTED = ('Nicht abgenommen – erst nach Öffnen in GSVmulti und dem Empfangstest belegt.')
SESSION_WHAT = ('Kopie der geprüften Session aus dem Testlauf vom 06.11.2026; geändert wird nur der Port. '
                'Vorhandene GSVmulti-Sessions bleiben unverändert.')
SESSION_HOWTO = ('In GSVmulti öffnen: GSVmulti starten, die erzeugte Datei (.ucf) als Session öffnen und '
                 'prüfen, dass der Kanal auf {port} steht. Ob GSVmulti die Werte empfängt, zeigt erst der '
                 'Empfangstest.')
SESSION_NO_PORT = 'Erst den Port festlegen (Portpaar oder USB-Adapter).'
SESSION_FAILED = 'Session-Datei nicht erzeugt'
SESSION_AGAIN = 'Neu erzeugen …'
RECORD_HIDDEN = ('In GSVmulti: Configure Recording → Advanced → ‚Record Hidden Channels‘ einschalten. Diese '
                 'Einstellung steht nicht in der Session-Datei; ohne sie fehlen die ausgeblendeten Kanäle '
                 '(Gültigkeit, Sequenz, Zeit) still in der Aufnahme. Kanal 1 hält bei Lesefehlern den letzten '
                 'Wert; auswerten nur Zeilen mit Gültigkeit 1.')
RECORD_HIDDEN_OK = 'Habe ich eingeschaltet'
AUTOSCALE_HINT = ('Für Kanal {channel} ‚Autoscale Y‘ ausschalten und Min/Max fest einstellen, damit der '
                  'Fehlwert vor dem ersten gültigen Wert die Skala nicht sprengt.')
SINGLE_CHANNEL_WARNING = ('Einkanal-Ausgabe: Bei Übergang (TRANSITION) und unlesbarer Anzeige (UNREADABLE) werden '
                          'keine Zeilen gesendet. GSVmulti zeichnet die Lücken nicht auf; Laufzeit und Zeitachse der '
                          'Aufnahme sind deshalb nicht genau.')


def gsv_channel(port: str | None) -> str | None:
    """GSVmulti-Kanalbezeichnung aus dem Port: COM8 -> „8_1“ (erster Kanal der Session)."""
    m = _re.fullmatch(r'COM(\d+)', port or '')
    return f'{m.group(1)}_1' if m else None


def autoscale_hint(port: str | None) -> str:
    ch = gsv_channel(port)
    return AUTOSCALE_HINT.format(channel=ch) if ch else ''


def single_channel_warning(ctx) -> str:
    """F3: nur bei Einkanal-Vorlage auf einem Brückenweg; unbekannte Kanalzahl -> nichts."""
    if getattr(ctx, 'session_channels', None) == 1 and ctx.route_mode in ('uart_bridge', 'network'):
        return SINGLE_CHANNEL_WARNING
    return ''
RECORD_HIDDEN_GATE = 'Erst „Record Hidden Channels“ in GSVmulti einschalten und bestätigen'
# Werte, die als kopierbares Feld (Daten, Mono) erscheinen
TECH_FIELDS = frozenset({'Pi-ID', 'Endpunkt', 'TLS-Fingerabdruck (SHA-256)', 'Protokoll', 'Brückenseite',
                         'GSVmulti-Seite', 'Gegenport', 'App-Version', 'Version', 'Session', 'Portpaar', 'Code',
                         'Lauf-ID', 'USB-Adapter'})
EMPTY_VALUES = frozenset({'', '–', 'nicht festgelegt', 'nicht benutzt', 'offen', 'nicht nachgewiesen'})


_SHY = '\u00ad'
_HYPHEN = {w.replace('|', ''): w.replace('|', _SHY) for w in (
    'Test|freigabe', 'Weiter|gabe', 'Instal|liert', 'ein|gestellt', 'über|geben', 'an|genommen', 'aus|gelassen',
    'nach|gewiesen', 'ab|genommen', 'Kompo|nenten', 'Schreib|fehler', 'Frei|gegeben', 'Über|tragung', 'Ab|nahme')}


def hyphenate(text: str) -> str:
    """Weiche Trennstellen in langen Wörtern der Kacheln (schmale Fenster, 200 %); Anzeige, nie Screenreader."""
    return _re.sub(r'[A-Za-zÄÖÜäöüß]+', lambda m: _HYPHEN.get(m.group(0), m.group(0)), text)


def mode_view(ctx: UiContext) -> tuple[str, str | None, str]:
    """(Kurzname, Symbol, Tooltip) des Moduswahl-Knopfs."""
    mode = ctx.route_mode
    if mode is None and ctx.route:      # Controller ohne route_mode: aus dem Wegnamen ableiten
        mode = 'uart_bridge' if ctx.route.startswith('UART') else 'network' if ctx.route.startswith('Netz') else None
    if mode not in MODE_SHORT:
        return MODE_NONE, None, MODE_NONE
    tip = f'Weg: {MODE_TEXT[mode][0]}' + (f' ({ctx.route})' if ctx.route else '') + ' – Weg wählen'
    return MODE_SHORT[mode], MODE_ICON[mode], tip


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
    actions: tuple[tuple[str, str, bool, str], ...] = ()    # (Beschriftung, Aktions-ID, aktiv, Grund wenn inaktiv)
    warn: str = ''            # Achtung-Hinweis im Detailfenster (z. B. F3 Einkanal-Ausgabe)


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
    'peer_invalid': ('Pi nicht bestätigt', 'Unter dieser Adresse antwortet ein anderer Pi als im Profil. '
                     'Adresse oder Profil prüfen.'),
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
    'uart_timeout': ('Pi am UART antwortet nicht', 'Prüfen Sie TX, RX, GND und den Pi-Dienst.'),
    'uart_frame_invalid': ('UART-Nachricht gestört', 'Eine Nachricht kam unlesbar an. Die Brücke verbindet neu; bei Häufung Kabel und Masse prüfen.'),
    'uart_port_failed': ('USB-Adapter nicht lesbar', 'Prüfen Sie, ob der Adapter steckt.'),
    'uart_closed': ('UART-Verbindung beendet', 'Verbinden Sie bei Bedarf erneut.'),
    'redirect_refused': ('Weiterleitung abgelehnt', 'Die Brücke folgt keiner Weiterleitung. Prüfen Sie die Adresse.'),
    'transport_write_uncertain': ('Senden unklar', 'Es ist offen, ob der Pi die Nachricht erhielt. Neu verbinden.'),
    'disconnected': ('Verbindung beendet', 'Verbinden Sie bei Bedarf erneut.'),
    'run_conflict': ('Lauf läuft bereits', 'Auf dem Pi läuft schon ein Lauf; es wurde keine Demo gestartet.'),
    'demo_unconfirmed': ('Demo nicht bestätigt', 'Der Pi hat den Demostart nicht bestätigt. Nichts wird wiederholt.'),
    'run_changed': ('Lauf gewechselt', 'Der Pi meldet einen anderen Lauf. Die Brücke liest neu.'),
    'stale_ack': ('Quittung veraltet', 'Eine Quittung passte nicht mehr zum Lauf. Sie wurde verworfen.'),
    'no_pending_poll': ('Interner Ablauf gestört', 'Verbinden Sie neu und exportieren Sie bei Wiederholung die Protokolle.'),
    'invalid_legacy_request': ('Interner Ablauf gestört', 'Verbinden Sie neu und exportieren Sie bei Wiederholung die Protokolle.'),
    'transport_unsupported': ('Weg nicht unterstützt', 'Wählen Sie Netzwerk oder UART.'),
    'windows_protection_required': ('Windows-Schutz fehlt', 'Zugangsdaten lassen sich ohne Windows-Schutz nicht speichern.'),
    'cancelled': ('Verbindung abgebrochen', 'Verbinden Sie bei Bedarf erneut.'),
}
# Bereitschaftswerte des Kerns (output / next_action): erklärender Satz + nächste Aktion
RUN_ACTIVE_TITLE = 'Auf dem Pi läuft ein Messlauf.'
RUN_ACTIVE_TEXT = (
    'Der Empfangstest braucht einen Pi ohne Lauf: Lauf in der Werkbank stoppen, dann erneut starten. '
    'Während des Messlaufs bleibt die Ausgabe gesperrt – GSVmulti erhält dann absichtlich keine Werte.')
LOCKED_REASON = 'Während einer aktiven Verbindung nicht änderbar – erst trennen'
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
    'run_active': (RUN_ACTIVE_TITLE, RUN_ACTIVE_TEXT),
    'demo_rejected': (RUN_ACTIVE_TITLE, RUN_ACTIVE_TEXT),
    'mode_locked': ('Während der Übertragung gesperrt',
                    'Weg, Pi-Adresse und Adapter lassen sich erst nach dem Ende der Übertragung ändern.'),
    'adapter_required': ('USB-Adapter nicht bereit',
                         'Wählen Sie den Adapter und warten Sie, bis seine Prüfung bestanden ist.'),
    'session_required': ('Session-Datei fehlt',
                         'Erzeugen Sie die Session-Datei für den gewählten Port; danach geht es weiter.'),
    'session_port_invalid': ('Port für die Session ungültig',
                             'Erlaubt sind COM1 bis COM256. Legen Sie den Port neu fest.'),
    'session_write_failed': ('Session-Datei nicht gespeichert',
                             'Der Ort ist nicht beschreibbar. Wählen Sie einen anderen Ordner.'),
    'setup_changed': ('Einrichtung inzwischen geändert',
                      'Die Prüfung gehörte zu einer älteren Auswahl. Prüfen Sie die aktuelle Auswahl erneut.'),
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
        return WORKER_CODE_TEXT[code], 'Protokolle exportieren und Ursache klären.'
    return 'Unbekannt', f'Code: {code}' if code else ''


def version_label(version: str | None) -> str:
    if not version:
        return ''
    return version if (version == 'Entwicklungsstand' or ' · ' in version) else f'Version {version}'

_TONE_OF_PEER = {'authenticated': 'ok', 'disconnected': 'info', 'backoff': 'err', 'connecting': 'info'}


NOT_SET = 'nicht festgelegt'
BACKOFF_DETAIL = ('Mögliche Ursachen: Pi-Dienst, Netzwerk oder Strom des Pi. Wiederholung nach 1, 2, 4, 8 s, dann '
                  'alle 8 s. „Automatik stoppen“ beendet das automatische Wiederverbinden.')
RUN_LOCK_SENTENCE = ('GSVmulti erhält absichtlich keine Messwerte – die DUT-Ausgabe ist gesperrt '
                     '(Windows-Abnahme fehlt). Das ist kein Fehler.')
_CLOCK = _re.compile(r'^\d\d:\d\d:\d\d$')


def _port(value):
    return value or NOT_SET


def _unknown(key, name):
    return ChipView(key, name, 'Unbekannt', 'info')


def _in_locked_run(peer_ok: bool, ctx: UiContext) -> bool:
    return bool(peer_ok and ctx.run_id and ctx.dut_locked and not ctx.demo and not ctx.waiting_for_run
                and not ctx.test_release)


def _test_release(readiness: Readiness) -> bool:
    return readiness.peer == 'authenticated' and readiness.output == 'test_release'


def _values(n: int) -> str:
    return f'{n} {"Wert" if n == 1 else "Werte"}'


def _worker_active_failure(readiness: Readiness, worker: WorkerStatus | None) -> str | None:
    """Worker-Code, der jedes "verbunden" überstimmt."""
    if worker is not None and worker.code:
        return worker.code
    return None


def _direct_adapter(ctx: UiContext) -> tuple[str, str]:
    """(Zustandstext, Ton) des Adapters im direkten Weg; „steckt“ belegt nur USB-Präsenz."""
    port = ctx.adapter_port or 'Adapter'
    if ctx.adapter_present is None:
        return 'Adapterzustand unbekannt', 'info'
    if ctx.adapter_present:
        return f'Adapter {port} steckt', 'ok'
    return f'Adapter {port} fehlt', 'warn'


def headline(readiness: Readiness, worker: WorkerStatus | None, ctx: UiContext) -> Headline:
    if ctx.route_mode == 'uart_direct':
        text, tone = _direct_adapter(ctx)
        return Headline(f'UART direkt – {text}', tone)
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
        if _test_release(readiness):
            return Headline(f'Verbunden – Lauf {ctx.run_id or "?"}, Testfreigabe aktiv', 'warn')
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
    if ctx.route_mode == 'uart_direct':
        # Direkter Weg: kein gekoppelter Pi, die Brücke kennt nur den Adapter.
        return (f'USB-Adapter {ctx.adapter_port}' if ctx.adapter_port else DIRECT_TITLE), ''
    if not ctx.pi_name:
        return (NO_PI if ctx.route_mode is None else NO_PI_WAY_SET), ''
    return ctx.pi_name, ctx.route or ''


def dut_line(ctx: UiContext) -> tuple[str, str]:
    """Die Sperrzeile ist in jedem Zustand sichtbar."""
    if ctx.route_mode == 'uart_direct':
        return DIRECT_DUT_LINE, 'info'
    if ctx.test_release:
        return TEST_RELEASE_LINE, 'warn'
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
            'manual_pair': ChipView('components', 'Komponenten',
                                    f'Portpaar {ctx.bridge_port} ↔ {ctx.gsv_port}' if ctx.bridge_port and ctx.gsv_port
                                    else 'Portpaar manuell',
                                    'warn' if ctx.com_issue == 'busy' else 'info', 'nicht von der App geprüft')
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
                      'peer_release_blocked') and readiness.next_action not in CONNECTION_CODE_TEXT else ()),
                  BACKOFF_DETAIL if readiness.peer == 'backoff' else '')
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
    elif _test_release(readiness):
        out = ChipView('output', 'Ausgabe', 'Testfreigabe', 'warn', 'nicht abgenommen')
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
    hints = {'Testfreigabe': TEST_RELEASE_HINT, 'Freigegeben': 'Dieser Zustand existiert erst nach der Windows-Abnahme.',
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
    elif _test_release(readiness) and readiness.com == 'driver_ready':
        extra = f' · {ctx.omitted} ausgelassen (ungültig/veraltet)' if ctx.omitted else ''
        fw = ChipView('forward', 'Weitergabe',
                      f'{_values(ctx.forwarded)} an {ctx.bridge_port or "den Port"} übergeben', 'warn',
                      'vom Port angenommen' + extra)
    elif readiness.com == 'driver_ready' and (ctx.demo or (ctx.release and not ctx.dut_locked)):
        fw = ChipView('forward', 'Weitergabe', 'Bestätigt', 'info', 'vom Port angenommen'
                      if not ctx.demo else 'Demo-Werte vom Port angenommen')
    elif ctx.dut_locked:
        fw = ChipView('forward', 'Weitergabe', 'Keine Weitergabe', 'info', 'DUT-Ausgabe gesperrt')
    else:
        fw = _unknown('forward', 'Weitergabe')
    fw = ChipView(fw.key, fw.name, fw.word, fw.tone, fw.sub,
                  ports + (('Letzte Quittung', ctx.last_ack),)
                  + ((('Ausgelassen (ungültig/veraltet)', str(ctx.omitted)),) if _test_release(readiness) else ()),
                  '„Bestätigt“ heißt: der Windows-Port hat die Daten angenommen.'
                  if fw.word == 'Bestätigt' else
                  'Übergeben heißt: der Windows-Port hat die Daten angenommen – nicht, dass GSVmulti sie empfangen hat.'
                  if _test_release(readiness) else
                  'Solange die DUT-Ausgabe gesperrt ist, schreibt die Brücke keine Messwerte an COM.')
    # GSVmulti: grün nur mit Testnachweis
    if ctx.receipt is not None and ctx.receipt.proven:
        gsv = ChipView('gsv', 'GSVmulti', 'Empfang belegt', 'ok', ctx.receipt.label)
        ghint = ('Der Test war eine Demo mit synthetischen Werten und gilt nur für genau diese '
                 'Konfiguration. Die Weitergabe von Messwerten bleibt gesperrt.' if ctx.receipt.demo else
                 'Gilt nur für genau diese Testdatei und Konfiguration.')
    elif ctx.session_confirmed:
        gsv = ChipView('gsv', 'GSVmulti', 'Von Hand eingestellt', 'info',
                       'erhält im Lauf keine Werte' if _in_locked_run(peer_ok, ctx) else 'Empfang nicht nachgewiesen')
        ghint = 'Nur der Empfangstest belegt Empfang. Der laufende Betrieb zeigt nur die COM-Weitergabe.'
    else:
        gsv = ChipView('gsv', 'GSVmulti', 'Kanal einstellen', 'info',
                       'erhält im Lauf keine Werte' if _in_locked_run(peer_ok, ctx) else
                       f'{ctx.gsv_port} · {baud_text(ctx.gsv_baud).replace(" Baud,", "")} in GSVmulti'
                       if ctx.gsv_port else 'Portpaar festlegen')
        ghint = ('Stellen Sie GSVmulti auf den Port der GSVmulti-Seite ein und bestätigen Sie das in der Einrichtung. '
                 'Nur der Empfangstest belegt Empfang.')
    gsv = ChipView(gsv.key, gsv.name, gsv.word, gsv.tone, gsv.sub,
                   (('Session', ctx.session_name or '–'),
                    ('Empfangsnachweis', ctx.receipt.label if ctx.receipt and ctx.receipt.proven
                     else 'nicht nachgewiesen')), ghint, warn=single_channel_warning(ctx))
    if ctx.route_mode == 'uart_direct':
        return (comp, _direct_uart(ctx)) + tuple(
            ChipView(k, n, DIRECT_UNUSED, 'unused', DIRECT_UNUSED_SUB, (('Weg', 'UART direkt'),),
                     'Im Weg „UART direkt“ überträgt die Brücke nichts; dieser Punkt wird nicht benutzt.')
            for k, n in (('pi', 'Pi'), ('output', 'Ausgabe'), ('forward', 'Weitergabe'))) + (
            ChipView(gsv.key, gsv.name, gsv.word, gsv.tone, 'Empfang nicht nachgewiesen' if gsv.tone != 'ok'
                     else gsv.sub, gsv.details, gsv.hint, warn=''),)
    return (comp, uart, pi, out, fw, gsv)


def _direct_uart(ctx: UiContext) -> ChipView:
    port = ctx.adapter_port or 'USB-Adapter'
    if ctx.adapter_present is None:
        word, tone, sub = 'Adapterzustand unbekannt', 'info', ''
    elif ctx.adapter_present:
        word, tone, sub = 'Adapter steckt', 'ok', port
    else:
        word, tone, sub = 'Adapter fehlt', 'warn', port
    return ChipView('uart', 'UART', word, tone, sub, (('Weg', 'UART direkt'), ('USB-Adapter', f'{port}: {word}')),
                    'Zeigt nur, ob der USB-Seriell-Adapter am PC steckt. Ob GSVmulti Werte erhält, zeigt nur GSVmulti.')


def action_bar(readiness: Readiness, worker: WorkerStatus | None, ctx: UiContext,
               configured: bool | None = None) -> ActionBar | None:
    """Genau eine nächste Aktion, höchstens zwei Knöpfe. ``configured=False``: Weg nicht fertig eingerichtet."""
    code = _worker_active_failure(readiness, worker)
    if code:
        return ActionBar('err', f'Übertragung gestoppt – {WORKER_CODE_TEXT.get(code, code)}',
                         'Die Brücke schreibt nichts mehr an COM. Protokolle exportieren und Ursache klären; '
                         'danach neu verbinden.', (('Protokolle exportieren', 'export_diagnostics', True),))
    if ctx.route_mode == 'uart_direct':
        if ctx.adapter_present is False:
            return ActionBar('warn', f'Adapter {ctx.adapter_port or ""} fehlt – einstecken'.replace('  ', ' '), '',
                             (('Weg wählen', 'open_modes', False),))
        return ActionBar('info', f'GSVmulti liest {ctx.adapter_port or "den Adapter"} direkt.',
                         'Die Brücke überträgt in diesem Weg nichts; ob Werte ankommen, zeigt nur GSVmulti.')
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
    if peer not in ('authenticated', 'connecting', 'backoff') and (configured is False or (
            ctx.route_mode is None and configured is not None)):
        return ActionBar('info', NOT_SET_UP_TITLE, NOT_SET_UP_NO_WAY if ctx.route_mode is None else NOT_SET_UP_TEXT,
                         ((START_SETUP, 'start_setup', True),))
    if peer == 'backoff':
        t = f'Keine Antwort vom Pi seit {ctx.last_report}' if ctx.last_report else 'Keine Antwort vom Pi'
        return ActionBar('err', t, 'Die Brücke versucht es automatisch weiter; Details stehen beim Pi.',
                         (('Automatik stoppen', 'stop_retry', False), ('Erneut versuchen', 'reconnect', True)))
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
            return ActionBar('info', 'Nicht verbunden.', '',
                             ((f'Mit {ctx.pi_name} verbinden', 'connect', True),))
        return None
    if peer == 'authenticated':
        if ctx.waiting_for_run:
            return ActionBar('info', 'Wartet auf einen Lauf', 'Starten Sie den Lauf auf dem Pi. '
                             'Die Brücke startet keinen Lauf.')
        if _in_locked_run(True, ctx):
            life = (f' Letzte Antwort vom Pi: {ctx.last_report}.' if _CLOCK.match(ctx.last_report or '') else '')
            return ActionBar('info', f'Lauf {ctx.run_id} läuft.', RUN_LOCK_SENTENCE + life)
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
        if outcome == 'omitted':
            return JournalEntry(now, 'Wert ausgelassen', 'ungültig oder veraltet – nichts an COM geschrieben', tone='warn')
        if outcome == 'idle':
            return JournalEntry(now, 'Wartet auf Messlauf', 'kein Wert vorhanden', tone='info')
        if outcome == 'ended':
            return JournalEntry(now, 'Messlauf beendet', tone='info')
        return JournalEntry(now, 'Weitergabe', str(outcome or ''), tone='info')
    return JournalEntry(now, 'Ereignis', event.kind, tone='info')


# ---------------------------------------------------------------- Einrichtung
FP_PROFILE = '{fingerprint}'
FP_OTHER = '{peer_fingerprint}'
UART_WIRING = ('{uart_line}, kein Handshake. TX des Adapters an RX des Pi, RX des Adapters an TX des Pi, '
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
_AUTO = ('check_dyn', 'Beim Start automatisch mit {pi_name} verbinden', 'auto_connect', 'auto_connect')


STEPS_DIRECT = ('Adapter', 'Verdrahtung', 'Session', 'Fertig')
STEP_SETS = {'bridge': STEPS, 'direct': STEPS_DIRECT}


GATE_CHECK_RUNNING = 'Die Prüfung läuft noch – bitte kurz warten'
GATE_NO_ADAPTER = 'Erst einen USB-Adapter wählen'
GATE_ADAPTER_MISSING = 'Erst den Adapter einstecken – er fehlt'


def _s(step, lead, blocks, nxt=_NEXT, ready=False, back=True, header=None, gate=None, steps='bridge'):
    """Ein Einrichtungszustand: Schritt, Leitsatz, Blöcke, Fuß. ``gate``: (Pflichtfeld, Grund) für „Weiter“.

    Pflichtfeld: Name eines Hakens, ``ports`` (beide Ports gewählt), ``check:<feld>`` (bestandene Prüfung)
    oder ``data:<schlüssel>`` (Wert im Controllerzustand vorhanden)."""
    return dict(step=step, lead=lead, blocks=tuple(blocks), next=nxt, ready=ready, back=back, header=header,
                gate=gate, next_action='next', freeze=False, steps=STEP_SETS[steps])


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
        ('portpair_dyn',),
        ('button', 'Portpaar übernehmen', 'set_port_pair', True)], back=False,
        gate=('ports', 'Erst beide COM-Ports wählen (zwei verschiedene)')),
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
                                                           'Manuell, nicht von der App geprüft.'),)),
        ('button', 'Portpaar ändern', 'change_pair', False)],
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
        ('button', 'Code übernehmen', 'pair', True),
        ('gate_hint', 'pair', 'Erst Fingerabdruck bestätigen und Code eingeben')],
        gate=('pair', 'Erst Fingerabdruck bestätigen und einen gültigen Code eingeben')),
    'E2exp': _s(2, 'Schritt 2 von 5: Pi koppeln.', [
        ('info', 'err', 'Code abgelaufen – in der Werkbank einen neuen erzeugen',
         'Der Kopplungscode war 5 Minuten gültig. Es wurde nichts gekoppelt. Geben Sie den neuen Code ein.', (('Neuen Code eingeben', 'new_code', True),)), _PROFILE]),
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
                                  ('Zugang', 'Gilt nur für diesen PC und ist in der Werkbank widerrufbar.'))),
        ('button', 'Anderes Profil öffnen …', 'open_profile', False)],
        ready=True),
    'E3': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        _WAY,
        ('radios_dyn', 'found', 'Adresse aus dem Profil und gefundene Pi im Netz'),
        ('text', 'Ein gefundener Name ist kein Identitätsnachweis. Erst die Prüfung gegen das Profil bestätigt den Pi.'),
        ('entry', 'Adresse oder Name manuell eintragen',
         'Tailscale wird nur benutzt, wenn Sie hier den Tailscale-Namen oder die Adresse eintragen. Ohne Tailscale '
         'braucht es ein gemeinsames Netz oder die VPN-Route Ihrer IT.')], nxt='Verbinden', ready=True,
        gate=('clear:endpoint', 'Erst die Adresse korrigieren – die Prüfung ist fehlgeschlagen')),
    'E3err': _s(3, 'Schritt 3 von 5: Verbindung herstellen.', [
        ('error_code', 'code', 'Verbindung nicht möglich')], nxt='Verbinden'),
    'E3uart': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        _WAY_U,
        ('radios_dyn', 'adapter', 'USB-Adapter'),
        ('card', 'Verdrahtung', (('', UART_WIRING),))], nxt='Verbinden', ready=True, header='uart',
        gate=('clear:adapter', 'Erst einen Adapter wählen und seine Prüfung bestehen')),
    'E3uart2': _s(3, 'Schritt 3 von 5: Weg zum Pi wählen.', [
        ('info', 'warn', 'Zwei gleiche Adapter – Auswahl nötig',
         'Die Adapter lassen sich nur am USB-Anschluss unterscheiden. Wählen Sie den Adapter, der am Pi hängt.', ()),
        _WAY_U,
        ('radios_dyn', 'adapter', 'USB-Adapter'),
        ('card', 'Verdrahtung', (('', UART_WIRING),))], nxt='Verbinden', header='uart',
        gate=('clear:adapter', 'Erst einen Adapter wählen und seine Prüfung bestehen')),
    'E3ok': _s(3, 'Schritt 3 von 5: Pi verbunden.', [
        ('info', 'ok', 'Pi verbunden (Identität geprüft)',
         'Der Pi hat seine Identität belegt; der Fingerabdruck passt zum Profil. Das ist noch keine Messfreigabe.', ()),
        ('card', '', (('Weg', 'Netzwerk (LAN)'), ('Endpunkt', '{endpoint}'),
                      ('Protokoll', '{protocol}')))], ready=True),
    'E3fail': _s(3, 'Schritt 3 von 5: Verbindung herstellen.', [
        ('info', 'err', 'Adapter erkannt, Pi antwortet nicht',
         'Der USB-Adapter ist da, aber der Pi hat nicht geantwortet. Mögliche Ursachen:', (('Erneut versuchen', 'reconnect', True),)),
        ('bullets', ('Der Pi-Dienst läuft nicht.', 'TX, RX oder GND sind nicht richtig verbunden.',
                     'Die Parameter stimmen nicht ({uart_line}).')),
        ('card', '', (('Adapter', 'USB-Seriell-Adapter · COM6'), ('USB-Ort', 'Port 3'),
                      ('Parameter', '{uart_line}, kein Handshake')))], header='uart'),
    'E4locked': _s(4, 'Schritt 4 von 5: GSVmulti-Session.', [
        ('session', 'gsv_port'),
        ('card', 'In GSVmulti einstellen – ohne Session-Datei', (
            ('Gerät', 'UserDef (benutzerdefiniert)'), ('COM-Port', '{gsv_port}'), ('Übertragung', '{gsv_line}'),
            ('Kanäle', '{channels_line}'),
            ('Präfix', '%'), ('Einheit', 'mV/V'), ('Frequenz', '10 Hz'))),
        ('text', 'Muster: Session aus dem Testlauf vom 06.11.2026 (nur Port anpassen).'),
        ('text', 'Legen Sie eine neue Testsession an und speichern Sie sie unter eigenem Namen.'),
        ('text', 'Ob GSVmulti die Einstellungen übernimmt, belegt erst der Empfangstest.'),
        ('check_dyn', 'Session in GSVmulti geöffnet bzw. Kanal auf {gsv_port}, {gsv_line} eingestellt.',
         'session_ok', 'session_confirmed')],
        nxt='Weiter', gate=('session_ok', 'Erst bestätigen, dass GSVmulti eingestellt ist')),
    'E4': _s(4, 'Schritt 4 von 5: GSVmulti-Session erzeugen.', [
        _PORTS, ('text', 'Die Session verweist auf {gsv_port}. Vorhandene GSVmulti-Sessions bleiben unverändert.'),
        ('button', 'Session erzeugen', 'export_session', True)]),
    'E4ok': _s(4, 'Schritt 4 von 5: Session in GSVmulti öffnen.', [
        ('info', 'info', 'Sessiondatei erzeugt: {session_name}',
         'Die Datei allein belegt nicht, dass GSVmulti die Einstellungen übernommen hat.',
         (('Ordner öffnen', 'open_folder', False), ('In GSVmulti öffnen', 'open_in_gsv', True))),
        ('card', 'In GSVmulti: Datei › Öffnen …', (('', 'Die erzeugte Datei auswählen.'),)),
        ('text', 'Hier bestätigen, dass die Session geöffnet ist.'),
        ('check_dyn', 'Ich habe die Session in GSVmulti geöffnet.', 'session_ok', 'session_confirmed')],
        gate=('session_ok', 'Erst bestätigen, dass die Session in GSVmulti geöffnet ist')),
    'E4unk': _s(4, 'Schritt 4 von 5: GSVmulti manuell einrichten.', [
        ('info', 'warn', 'GSVmulti-Version unbekannt – Automatik gesperrt',
         'Für diese Version gibt es keine geprüfte Vorlage. Es wird keine Sessiondatei erzeugt. '
         'Die manuelle Anleitung ist eingeschränkt.', ()),
        ('card', 'Manuelle Anleitung (eingeschränkt)', (('', 'Stellen Sie in GSVmulti selbst ein:'),
                                                       ('Port', '{gsv_port}'), ('Übertragung', '{gsv_line}'),
                                                       ('Format', '8N1, kein Handshake'))),
        ('text', 'Die Menüführung Ihrer GSVmulti-Version ist nicht geprüft. Ob GSVmulti die Einstellungen '
                 'übernimmt, belegt erst der Empfangstest.'),
        ('check_dyn', 'Ich habe GSVmulti so eingestellt.', 'session_ok', 'session_confirmed')],
        gate=('session_ok', 'Erst bestätigen, dass GSVmulti eingestellt ist')),
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
    'E5busy': _s(5, 'Schritt 5 von 5: Empfang prüfen.', [
        ('info', 'warn', RUN_ACTIVE_TITLE, RUN_ACTIVE_TEXT, ()),
        ('text', 'Diese Ansicht aktualisiert sich selbst, sobald der Lauf endet.'),
        _AUTO], nxt='Ohne Test beenden'),
    'E5done': _s(5, 'Schritt 5 von 5: Test gesendet.', [
        _TEST_INFO,
        ('info', 'warn', 'Empfang nicht nachgewiesen – Werte in GSVmulti selbst prüfen',
         '{written} synthetische Werte wurden an den COM-Port übergeben. Ob GSVmulti sie empfangen hat, prüft die '
         'Brücke nicht (Testdateivergleich noch nicht verfügbar). Vergleichen Sie die Aufzeichnung der '
         'Testsession in GSVmulti selbst.', ()), _AUTO], nxt='Fertig', ready=True),
    'E5short': _s(5, 'Schritt 5 von 5: Test unvollständig.', [
        ('info', 'err', 'Unvollständig: {written} von {count} Werten übergeben',
         '{missing} Werte kamen nicht bis zum COM-Port. Protokolle exportieren und den Test wiederholen.',
         (('Protokolle exportieren', 'export_diagnostics', True),)),
        ('check', 'Ich verwende eine getrennte GSVmulti-Testsession.', 'test_session_ok'),
        ('button', 'Test wiederholen', 'start_demo_check', True), _AUTO], nxt='Fertig', ready=True),
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
                 'COM-Weitergabe bleibt eine eigene Aussage.'), _AUTO], nxt='Fertig', ready=True),
    'E5bad': _s(5, 'Schritt 5 von 5: Empfang nicht belegt.', [
        ('info', 'err', 'Abweichung: 598/600',
         'Zwei Werte der Testdatei stimmen nicht mit dem Test überein. Der Empfang ist für diese Datei nicht belegt.',
         (('Test wiederholen', 'start_demo_check', True),)),
        ('card', 'Fehlende Werte', (('Nr. 211', 'fehlt in der Testdatei'), ('Nr. 212', 'fehlt in der Testdatei')))]),
    # ---- UART direkt (Einrichtungshelfer, kein Worker, keine Kopplung)
    'D1': _s(1, 'Schritt 1 von 4: USB-Seriell-Adapter wählen.', [
        ('text', 'Das Kabel vom Pi steckt über einen USB-Seriell-Adapter an diesem PC. GSVmulti liest den Adapter '
                 'später selbst; die Brücke überträgt in diesem Weg nichts.'),
        ('adapter_pick', 'USB-Adapter')], ready=True, back=False, steps='direct',
        gate=('check:adapter', 'Erst einen Adapter wählen und seine Prüfung abwarten')),
    'D2': _s(2, 'Schritt 2 von 4: Verdrahtung prüfen.', [
        ('adapter_state',),
        ('card', 'Verdrahtung', (('Übertragung', '{gsv_line}, kein Handshake – wie in der GSVmulti-Session'),
                                 ('Leitungen', 'TX des Adapters an RX des Pi, RX des Adapters an TX des Pi, GND an '
                                               'GND. VCC, CTS und RTS bleiben frei.'))),
        ('text', 'Die Brücke prüft die Verdrahtung nicht. Ob Werte ankommen, zeigt erst GSVmulti.')],
        ready=True, steps='direct'),
    'D3': _s(3, 'Schritt 3 von 4: GSVmulti-Session erzeugen.', [
        ('session', 'adapter_port')], ready=True, steps='direct',
        gate=('data:session_path', 'Erst die Session-Datei für diesen Adapter erzeugen')),
    'D4': _s(4, 'Schritt 4 von 4: Fertig.', [
        ('info', 'info', 'Weg „UART direkt“ eingerichtet ({adapter_port})',
         'Öffnen Sie die erzeugte Session in GSVmulti; GSVmulti liest den Adapter dann selbst. Die Brücke zeigt '
         'danach nur, ob der Adapter steckt; die Werte laufen an ihr vorbei. Ob Werte ankommen, zeigt erst '
         'GSVmulti.', ()),
        ('adapter_state',),
        ('session', 'adapter_port')], nxt='Fertig', ready=True, steps='direct'),
}


_TOKEN = _re.compile(r'\{([a-z_0-9]+)\}')


def fill(obj, mapping):
    """Platzhalter {name} aus dem Kontext ersetzen; fehlender Wert -> „–“, nie ein Beispielwert."""
    if isinstance(obj, str):
        return _TOKEN.sub(lambda m: str(mapping.get(m.group(1)) or '–'), obj)
    if isinstance(obj, (tuple, list)):
        return tuple(fill(o, mapping) for o in obj)
    return obj


STEP3_SELECT = ('E3', 'E3uart', 'E3uart2')
UNVERIFIED_PAIR = ('Portpaar von Hand wählen',
                   'Automatische Prüfung ist in dieser Version nicht verfügbar – wählen Sie Ihr Paar '
                   '(z. B. com0com COM7 ↔ COM8). Die App legt kein Portpaar an und ändert keines.')
RESUMED_LEAD = 'Schritt 3 von 5: Verbindung neu herstellen (Ihr Fortschritt bis hier ist gespeichert).'
# Fehlercode -> (Aktionsbeschriftung, Aktions-ID); alles andere: „Erneut versuchen“
CODE_ACTION = {'pairing_refused': ('Neuen Code eingeben', 'new_code'),
               'pairing_required': ('Neuen Code eingeben', 'new_code'),
               'peer_invalid': ('Anderes Profil öffnen', 'open_profile'),
               'profile_invalid': ('Anderes Profil öffnen', 'open_profile')}


def _clock_text(seconds: int) -> str:
    return f'{seconds // 60}:{seconds % 60:02d}'


def _step3_head(ctx, data) -> tuple[list, dict]:
    """Leisten oberhalb der Wegwahl (Fehler, Backoff, Aufbau, Codehinweis) und Fußänderungen."""
    pre, foot = [], {}
    if data.get('connecting'):
        pre.append(('progress_busy', f'Verbindung zu {ctx.pi_name or "Pi"} wird aufgebaut …',
                    'Das kann einige Sekunden dauern. Mit „Abbrechen“ stoppen Sie den Versuch.'))
        foot.update(next='Abbrechen', next_action='cancel_connect', ready=False, back=False, freeze=True)
    elif data.get('backoff'):
        n = f' in {ctx.retry_in_s} s' if ctx.retry_in_s is not None else ' läuft'
        pre.append(('livebar', 'err', f'Pi antwortet nicht – nächster Versuch{n}',
                    'Die Brücke versucht es automatisch weiter.',
                    (('Automatik stoppen', 'stop_retry', False), ('Erneut versuchen', 'reconnect', True))))
        foot.update(next=None)
    elif data.get('code'):
        title, text = explain_code(data['code'])
        label, aid = CODE_ACTION.get(data['code'], ('Erneut versuchen', 'reconnect'))
        pre.append(('info', 'err', title, text, ((label, aid, True),)))
        if aid in ('reconnect', 'new_code'):
            foot.update(next=None)
    if ctx.code_remaining_s is not None and not data.get('code'):
        pre.append(('livebar', 'info',
                    f'Code gespeichert – gekoppelt wird beim Verbinden, jetzt gleich '
                    f'(Code noch {_clock_text(ctx.code_remaining_s)} gültig).', '', ()))
    return pre, foot


def channels_text(channels):
    """Kanäle laut Session-Vorlage (eine Quelle mit Export und Empfangstest)."""
    if channels == 4:
        return '4 – Wert; gültig; Takt; Zeit (3 ausgeblendet, „Record Hidden Channels“ an)'
    if channels == 1:
        return '1 – ein Wertestrom'
    return 'laut Session-Vorlage'


def setup_spec(ctx, locked=False):
    """SETUP-Zustand mit Werten aus ctx (und ctx.setup.data) gefüllt."""
    m = dict(bridge_port=ctx.bridge_port, gsv_port=ctx.gsv_port, version=ctx.version, protocol=ctx.protocol,
             pi_name=ctx.pi_name, pi_id=ctx.pi_id, endpoint=ctx.endpoint, fingerprint=ctx.fingerprint,
             session_name=ctx.session_name, adapter_port=ctx.adapter_port,
             uart_line=baud_text(ctx.uart_baud), gsv_line=baud_text(ctx.gsv_baud),
             channels_line=channels_text(ctx.session_channels))
    data = ctx.setup.data
    if data.get('gsv_baud') and not ctx.gsv_baud:
        m['gsv_line'] = baud_text(data['gsv_baud'])
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
            if not items and name not in RESCAN_LISTS:
                blocks.append(('text', EMPTY_CHOICE.get(name, 'Keine Einträge gefunden.')))
            else:
                blocks.append(('radios', name, tuple(items), heading))
        elif kind == 'portpair_dyn':
            ports = tuple(data.get('ports', ()))
            cur_b = ctx.bridge_port if ctx.bridge_port in ports else None
            cur_g = ctx.gsv_port if ctx.gsv_port in ports else None
            blocks.append(('portpair', ports, cur_b, cur_g))
        elif kind == 'combo_dyn':
            name, heading = blk[1], blk[2]
            ports = tuple(data.get('ports', ()))
            current = ctx.bridge_port if name == 'bridge_port' else ctx.gsv_port
            if not ports:
                blocks.append(('text', EMPTY_CHOICE.get(name, 'Keine COM-Ports gefunden.')))
            else:
                blocks.append(('combo', name, heading, ports, current if current in ports else None))
        elif kind == 'check_dyn':
            blocks.append(('check', blk[1], blk[2], bool(data.get(blk[3]))))
        elif kind == 'session':
            port = data.get(blk[1]) or getattr(ctx, blk[1], None)
            path = data.get('session_path') if 'session_path' in data else None
            name = path.replace('\\', '/').rsplit('/', 1)[-1] if path else ctx.session_name
            blocks.append(('session', port, name, path))
        elif kind == 'adapter_pick':
            items = tuple(data.get('adapter_items') or ())
            blocks.append(('adapter_pick', blk[1], items, ctx.adapter_port or data.get('adapter_port')))
        elif kind == 'adapter_state':
            port = ctx.adapter_port or data.get('adapter_port')
            present = data.get('adapter_present', ctx.adapter_present)
            if port is None:
                blocks.append(('statusrows', 'USB-Adapter', (('Adapter', 'nicht gewählt', 'warn'),)))
            else:
                word, tone = ({True: ('steckt', 'ok'), False: ('fehlt – Adapter einstecken', 'err')}
                              .get(present, ('Präsenz unbekannt', 'info')))
                blocks.append(('statusrows', 'USB-Adapter', ((port, word, tone),)))
                if present is False and ctx.setup.variant == 'D2':
                    spec['gate'] = ('blocked', GATE_ADAPTER_MISSING)
            if port is None and ctx.setup.variant == 'D2':
                spec['gate'] = ('blocked', GATE_NO_ADAPTER)
        elif kind == 'error_code':
            title, text = explain_code(data.get('code'))
            blocks.append(('info', 'err', title if title != 'Unbekannt' else 'Unbekannt',
                           text, (('Erneut versuchen', 'reconnect', True),)))
        else:
            blocks.append(blk)
    if ctx.setup.variant == 'E1manual' and data.get('unverified'):
        blocks[0] = ('info', 'warn', *UNVERIFIED_PAIR, ())
    blocks = list(fill(tuple(blocks), m))
    gate = spec.get('gate')
    if gate is not None and gate[0].startswith('data:'):
        spec['gate'] = None if data.get(gate[0][5:]) else ('blocked', gate[1])
    if ctx.setup.variant in ('E3uart', 'E3uart2') and not (data.get('adapter_items')
                                                          and (ctx.adapter_port or data.get('adapter_port'))):
        spec['gate'] = ('blocked', GATE_NO_ADAPTER)
    if ctx.setup.variant in STEP3_SELECT:
        pre, foot = _step3_head(ctx, data)
        blocks = pre + blocks
        spec.update(foot)
        if data.get('resumed'):
            spec['lead'] = RESUMED_LEAD
    blocks = tuple(blocks)
    if data.get('notice'):
        title, text = explain_code(data['notice'])
        blocks = (('info', 'err', title, text, ()),) + blocks
    if locked and spec['step'] <= 3:
        blocks = (('info', 'info', LOCKED_REASON, 'Beenden Sie die Verbindung, um Pi, Weg oder Portpaar zu ändern.',
                   (('Verbindung trennen', 'disconnect', True),)),) + blocks
    spec['blocks'] = blocks
    return spec


RESCAN_LISTS = ('found', 'adapter')      # Listen mit Symbolknopf „Suche wiederholen“ daneben
EMPTY_CHOICE = {'found': 'Keine Adresse im Profil und nichts gefunden. Tragen Sie unten eine Adresse ein.',
                'adapter': 'Kein unterstützter USB-Seriell-Adapter gefunden. Stecken Sie ihn an und suchen Sie erneut.',
                'bridge_port': 'Keine COM-Ports gefunden.', 'gsv_port': ''}
