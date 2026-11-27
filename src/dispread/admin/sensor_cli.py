"""JSON-Kommandos fuer Sensorpakete und deren Onboarding."""

from __future__ import annotations

import argparse
import json
import math
import os
import stat
import sys
import tempfile
import time
import uuid
from pathlib import Path

from dispread.sensors import local_root, registry_with_errors
from dispread.sensors import tools as sensor
from dispread.sensors.formats import derive_display
from dispread.sensors.onboarding import (
    QUESTION_KINDS,
    STEP_KEYS,
    STEP_STATES,
    OnboardingCancelled,
    RunDir,
    slugify,
)


def add_commands(parser: argparse.ArgumentParser) -> None:
    subs = parser.add_subparsers(dest='sensor_command', required=True)
    for name, help_text in (
        ('list', 'Sensorpakete auflisten'), ('agents', 'KI-Assistenten prüfen'),
        ('ports', 'Serielle Anschlüsse auflisten'), ('sniff', 'Seriell passiv mitlesen'),
        ('capture', 'Standbild aufnehmen'), ('step', 'Schritt melden'), ('log', 'Meldung protokollieren'),
        ('ask', 'Bediener über die Laufmappe fragen'), ('propose', 'Vorläufiges Paket erzeugen'),
        ('check', 'Paket und gegebenenfalls Standbild prüfen'), ('activate', 'Aktiven Sensor setzen'),
        ('onboard', 'Einrichtung über die Laufmappe ausführen'),
    ):
        cmd = subs.add_parser(name, help=help_text)
        if name in ('capture', 'step', 'log', 'ask', 'propose', 'check', 'onboard'):
            cmd.add_argument('--run', type=Path, required=name != 'check')
        if name in ('propose', 'check', 'activate'):
            cmd.add_argument('--id', required=True)
        if name in ('capture', 'onboard'):
            cmd.add_argument('--source', help='Alternative Bildquelle, z. B. synthetic://')
        if name == 'capture':
            cmd.add_argument('--confirmed', action='store_true',
                             help='Bestätigtes Referenzbild samt Profil aus /live übernehmen')
        if name == 'sniff':
            cmd.add_argument('--port', required=True)
            cmd.add_argument('--bauds', default=sensor.DEFAULT_BAUDS)
            cmd.add_argument('--seconds', default=3.0, type=float)
        elif name == 'step':
            cmd.add_argument('--key', required=True, choices=STEP_KEYS)
            cmd.add_argument('--state', required=True, choices=STEP_STATES)
            cmd.add_argument('--detail')
        elif name == 'log':
            cmd.add_argument('--text', required=True)
        elif name == 'ask':
            cmd.add_argument('--kind', choices=QUESTION_KINDS, required=True)
            cmd.add_argument('--prompt', required=True)
            cmd.add_argument('--option', action='append', default=[], metavar='LABEL=WERT')
            cmd.add_argument('--timeout', default=sensor.DEFAULT_TIMEOUT, type=float)
        elif name == 'propose':
            for key in ('example', 'unit', 'sign-chars', 'display-name', 'serial-port'):
                cmd.add_argument(f'--{key}')
            cmd.add_argument('--digits', type=int)
            cmd.add_argument('--serial-baud', type=int)
        elif name == 'activate':
            cmd.add_argument('--accept-provisional', action='store_true')
        elif name == 'onboard':
            cmd.add_argument('--assistant', choices=('claude', 'codex', 'none'))


def _ask(run, kind, prompt, *, options=None, timeout=sensor.DEFAULT_TIMEOUT):
    sensor.check_cancel(run)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Frage braucht ein positives, endliches Zeitlimit')
    value = run.ask(uuid.uuid4().hex, kind, prompt, options=options, timeout_s=timeout)
    sensor.check_cancel(run)
    if kind == 'confirm' and type(value) is not bool:
        raise ValueError('Antwort auf Bestätigung muss true oder false sein')
    if kind == 'text' and not isinstance(value, str):
        raise ValueError('Textantwort fehlt')
    if kind == 'choice' and (not isinstance(value, str) or value not in {item['value'] for item in options}):
        raise ValueError('Antwort steht nicht zur Auswahl')
    return value


def _options(values):
    options = []
    for item in values:
        label, sep, value = item.partition('=')
        if not sep or not label or not value:
            raise ValueError('Option im Format label=value angeben')
        options.append({'label': label, 'value': value})
    return options


def _proposal_args(args):
    return {key: getattr(args, key) for key in
            ('example', 'unit', 'sign_chars', 'digits', 'display_name', 'serial_port', 'serial_baud')}


def _confirm_format(run, example, unit, sign_chars=None, digits=None, *, timeout=sensor.DEFAULT_TIMEOUT):
    display = derive_display(example, unit, sign_chars, digits)
    roles = [''] * display.cells
    labels = {'sign': 'V', 'number': 'Z', 'separator': 'T', 'unit': 'E', 'blank': 'L'}
    for name, label in labels.items():
        for cell in getattr(display.roles, name):
            roles[cell] = label
    digits_text = str(display.format.digits)
    if display.format.min_digits is not None:
        digits_text = f'{display.format.min_digits}–{digits_text}'
    run.step('format', 'done', f'{digits_text} Ziffern, Einheit {unit}')
    run.step('bestaetigung', 'running')
    polarity = _ask(run, 'choice', 'Wie sehen die Zeichen auf der Anzeige aus?', options=[
        {'label': 'Dunkle Zeichen auf hellem Grund (z. B. schwarz auf grau/grün)', 'value': 'dark_on_light'},
        {'label': 'Helle Zeichen auf dunklem oder farbigem Grund (z. B. weiß auf blau)', 'value': 'bright_on_dark'},
    ], timeout=timeout)
    if polarity != 'dark_on_light':
        message = ('Anzeigen mit hellen Zeichen auf dunklem/farbigem Grund liest picam noch nicht '
                   '(Leser und Vorlagen kennen nur dunkle Zeichen). Ausbau folgt, siehe OQ-84.')
        run.step('bestaetigung', 'failed', message)
        raise OnboardingCancelled(message)
    prompt = (f'Anzeigebeispiel und Format bestätigen?\n|{example.ljust(16)}|\n|{"".join(roles)}|\n'
              f'V Vorzeichen, Z Zahl, T Trennung, E Einheit, L Leerzelle. {digits_text} Ziffern, Einheit: {unit}')
    if not _ask(run, 'confirm', prompt, timeout=timeout):
        run.step('bestaetigung', 'failed', 'Format abgelehnt')
        raise OnboardingCancelled('Format vom Bediener abgelehnt')
    run.step('bestaetigung', 'done')


def _confirm_activation(run, instance, sensor_id, *, timeout=sensor.DEFAULT_TIMEOUT):
    run.step('aktivieren', 'running')
    if not _ask(run, 'confirm', f'Vorläufiges Paket {sensor_id} als aktiven Sensor setzen?', timeout=timeout):
        run.step('aktivieren', 'skipped', 'Bediener hat die Aktivierung abgelehnt')
        return None
    try:
        result = sensor.activate(instance, sensor_id, True)
    except (ValueError, OSError) as error:
        run.step('aktivieren', 'failed', str(error))
        raise
    run.step('aktivieren', 'done', result['message'])
    return result


def _run_none(run, instance, data, source):
    run.step('werkzeug', 'skipped', 'Ohne KI-Assistent')
    port = data['connection'].get('port')
    run.step('anschluss', 'done' if port else 'skipped', port or 'Kein Port angegeben')
    if port:
        run.step('schnittstelle', 'running')
        findings = sensor.sniff(port, run=run, instance=instance)
        (run.work_dir / 'sniff.json').write_text(json.dumps(findings, ensure_ascii=False) + '\n', encoding='utf-8')
        run.step('schnittstelle', 'done', 'Passiver Empfang protokolliert')
    else:
        run.step('schnittstelle', 'skipped')
    run.step('kamera', 'running')
    try:
        capture = sensor.capture(run, instance, source)
    except OnboardingCancelled:
        raise
    except Exception as error:  # Kamera fehlt/belegt: Lauf geht ohne Standbild weiter
        # Das Standbild dient nur der Vorschau und Probelesung; die Einrichtung
        # mit Kamera folgt ohnehin in /live. Ohne Bild prueft check statisch.
        run.step('kamera', 'skipped', f'Kein Standbild: {error}. Einrichtung später in /live.')
    else:
        run.step('kamera', 'done', capture['path'])
    run.step('format', 'running')
    example = data.get('example')
    if not example:
        example = _ask(run, 'text', 'Anzeigezeichen einschließlich Leerzellen und Einheit eingeben')
    _confirm_format(run, example, data['unit'])
    sensor_id = slugify(data['name'])
    if len(sensor_id) < 2:
        sensor_id = f'sensor-{sensor_id}'
    result = sensor.propose(run, instance, sensor_id, example=example)
    if not sensor.check(instance, sensor_id, run)['ok']:
        raise ValueError('Probelesung fehlgeschlagen')
    activated = _confirm_activation(run, instance, sensor_id)
    return {**result, 'activated': activated is not None,
            'message': activated['message'] if activated else 'Vorläufiges Paket gespeichert.'}


class _AgentTools:
    """Reicht ausschließlich Sensorkommandos für diese Laufmappe an die Instanz."""

    def __init__(self, run, instance, data, source):
        self.run = run
        self.instance = instance
        self.data = data
        self.source = source
        self.proposal = None
        self.checked = False
        self.activation = None
        self.activation_declined = False
        self.parser = argparse.ArgumentParser(prog='picam sensor')
        add_commands(self.parser)

    def execute(self, argv, deadline):
        if not isinstance(argv, list) or not all(isinstance(arg, str) for arg in argv) or argv[:1] != ['sensor']:
            raise ValueError('Erwartet picam sensor …')
        try:
            args = self.parser.parse_args(argv[1:])
        except SystemExit as error:
            raise ValueError('Sensor-Werkzeugaufruf ist ungültig') from error
        cmd = args.sensor_command
        if cmd == 'onboard' or getattr(args, 'source', None) is not None:
            raise ValueError('Dieser Aufruf ist während des Agentenlaufs nicht verfügbar')
        if getattr(args, 'run', None) is not None and args.run.resolve() != self.run.path.resolve():
            raise ValueError('Diese Aktion gehört zur aktuellen Laufmappe')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Zeitlimit des KI-Assistenten erreicht')
        if cmd == 'ask':
            args.timeout = min(args.timeout, remaining)
        if cmd == 'capture':
            args.source = self.source
        if cmd == 'sniff':
            configured = self.data['connection'].get('port')
            if args.port not in {configured, *(entry['port'] for entry in sensor.ports())}:
                raise ValueError('Port fehlt in der Anschlussliste')
            args.seconds = min(args.seconds, remaining / len(args.bauds.split(',')))
        if cmd == 'propose':
            if self.proposal is not None:
                raise ValueError('Für diesen Lauf wurde bereits ein Paket erzeugt')
            kwargs = _proposal_args(args)
            _confirm_format(self.run, kwargs['example'] if kwargs['example'] is not None else self.data.get('example'),
                            kwargs['unit'] if kwargs['unit'] is not None else self.data['unit'],
                            kwargs['sign_chars'], kwargs['digits'], timeout=remaining)
            self.proposal = sensor.propose(self.run, self.instance, args.id, **kwargs)
            return self.proposal, 0
        if cmd in ('check', 'activate'):
            if self.proposal is None or args.id != self.proposal['sensor_id']:
                raise ValueError('Bitte zuerst ein Paket in diesem Lauf erzeugen')
            if cmd == 'check':
                result = sensor.check(self.instance, args.id, self.run)
                self.checked = result['ok']
                return result, 0 if self.checked else 1
            if not self.checked or not args.accept_provisional:
                raise ValueError('Aktivierung braucht erfolgreiche Prüfung und --accept-provisional')
            if self.activation is not None:
                return self.activation, 0
            if self.activation_declined:
                raise OnboardingCancelled('Aktivierung vom Bediener bereits abgelehnt')
            self.activation = _confirm_activation(self.run, self.instance, args.id, timeout=remaining)
            if self.activation is None:
                self.activation_declined = True
                raise OnboardingCancelled('Aktivierung vom Bediener abgelehnt')
            return self.activation, 0
        if cmd == 'log':
            return self.run.log(args.text, 'agent'), 0
        return dispatch(args, self.instance, run=self.run), 0

    def serve(self, deadline):
        rpc = self.run.path / '.agent' / 'rpc'
        for pending in sorted(rpc.glob('*.request')):
            key = pending.stem
            if len(key) != 32 or any(char not in '0123456789abcdef' for char in key):
                continue
            try:
                fd = os.open(pending, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as request:
                    if not stat.S_ISREG(os.fstat(request.fileno()).st_mode):
                        raise ValueError('Werkzeuganfrage muss eine Datei sein')
                    argv = json.loads(request.read(32768))
                value, code = self.execute(argv, deadline)
                result = {'value': value, 'code': code}
            except (OSError, ValueError, RuntimeError) as error:
                result = {'error': str(error), 'code': 3 if isinstance(error, OnboardingCancelled) else 2}
            pending.unlink(missing_ok=True)
            with tempfile.NamedTemporaryFile('w', dir=rpc, delete=False, encoding='utf-8') as tmp:
                json.dump(result, tmp, ensure_ascii=False)
            Path(tmp.name).replace(rpc / f'{key}.response')


def _run_ai(run, instance, data, name, source):
    from dispread.sensors import agent

    run.step('werkzeug', 'running')
    found = next(item for item in agent.detect() if item['name'] == name)
    if not found['installed'] or found['logged_in'] is False:
        raise ValueError(f'{name}: Assistent fehlt oder Anmeldung erforderlich')
    run.step('werkzeug', 'done', found['version'])
    tools = _AgentTools(run, instance, data, source)
    code = agent.run_agent(run, name, tools.serve)
    if tools.proposal is None:
        log = next((event['text'] for event in reversed(run.read_events())
                    if event['type'] == 'log' and event['source'] == 'agent'), None)
        detail = f' Letzte Meldung: {log}' if log else ''
        raise ValueError(f'{name} beendet (Exit {code}), kein Sensorpaket erzeugt.{detail}')
    message = (tools.activation['message'] if tools.activation else
               f'Vorläufiges Paket gespeichert. {name} beendet (Exit {code}).')
    return {**tools.proposal, 'activated': tools.activation is not None, 'message': message}


def _onboard(run, instance, args):
    try:
        sensor.check_cancel(run)
        run.step('anfrage', 'running')
        data = sensor.request_data(run)
        assistant = args.assistant or data.get('assistant', 'none')
        if assistant not in ('none', 'claude', 'codex'):
            raise ValueError('Unbekannter KI-Assistent')
        run.step('anfrage', 'done')
        result = (_run_none(run, instance, data, args.source) if assistant == 'none'
                  else _run_ai(run, instance, data, assistant, args.source))
        sensor.check_cancel(run)
    except (ValueError, OSError, RuntimeError, KeyError, KeyboardInterrupt, ImportError) as error:
        running = {event['key']: event['state'] for event in run.read_events() if event['type'] == 'step'}
        step = next((key for key in reversed(STEP_KEYS) if running.get(key) == 'running'), None)
        message = str(error) or 'Onboarding abgebrochen'
        if step is not None:
            run.step(step, 'failed', message)
        run.error(message, step)
        run.done(False, message)
        raise
    if not any(event['type'] == 'done' for event in run.read_events()):
        run.done(True, result['message'], result['sensor_id'])
    return {**result, 'ok': True}


def dispatch(args, instance, *, run=None):
    cmd = args.sensor_command
    if run is None and getattr(args, 'run', None) is not None:
        run = RunDir.open(args.run.absolute())
    if cmd != 'onboard':
        sensor.check_cancel(run)
    if cmd == 'list':
        registry, errors = registry_with_errors(instance=instance)
        return [{'id': item.id, 'display_name': item.display_name, 'manufacturer': item.manufacturer,
                 'status': item.status, 'aliases': item.aliases, 'unit': item.unit, 'version': item.version,
                 'local': item.directory.parent == local_root(instance), 'directory': str(item.directory),
                 'active': item.id == instance.sensor} for item in registry.values()] + [
                    {'id': '', 'error': error} for error in errors]
    if cmd == 'agents':
        from dispread.sensors.agent import detect

        return detect()
    if cmd == 'ports':
        return sensor.ports()
    if cmd == 'sniff':
        return sensor.sniff(args.port, args.bauds, args.seconds, run=run, instance=instance)
    if cmd == 'capture':
        return sensor.capture(run, instance, args.source, confirmed=args.confirmed)
    if cmd == 'step':
        return run.step(args.key, args.state, args.detail)
    if cmd == 'log':
        return run.log(args.text)
    if cmd == 'ask':
        return {'value': _ask(run, args.kind, args.prompt, options=_options(args.option), timeout=args.timeout)}
    if cmd == 'propose':
        return sensor.propose(run, instance, args.id, **_proposal_args(args))
    if cmd == 'check':
        return sensor.check(instance, args.id, run)
    if cmd == 'activate':
        return sensor.activate(instance, args.id, args.accept_provisional)
    return _onboard(run, instance, args)


def main(args, instance) -> int:
    try:
        result = dispatch(args, instance)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 1 if isinstance(result, dict) and result.get('ok') is False else 0
    except OnboardingCancelled as error:
        print(f'picam sensor: {error}', file=sys.stderr)
        return 3
    except (ValueError, OSError, RuntimeError, KeyError, ImportError) as error:
        print(f'picam sensor: {error}', file=sys.stderr)
        return 2
