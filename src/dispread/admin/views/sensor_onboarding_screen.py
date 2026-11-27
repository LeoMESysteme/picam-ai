"""Bildschirm der Sensor-Einrichtung: Live-Checkliste, Protokoll, Fragen und Abbruch.

Der Ablauf läuft nicht hier, sondern im Prozess ``picam sensor onboard --run DIR`` (Orchestrierung, optional mit
KI-Agent). Die Konsole liest nur `events.jsonl` der Laufmappe (``RunDir.read_events``), zeigt die Schritte
(``STEPS``) als Checkliste, stellt ``question``-Ereignisse als Dialog und schreibt die Antwort mit
``RunDir.write_answer``. Abbruch schreibt ``cancel`` und beendet den Prozess nach einer Schonfrist.
"""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass

from rich.text import Text

from dispread.sensors.onboarding import STEPS, RunDir

from .. import probes, sensor_client
from ..ui import MUTED, SOFT, AskScreen, Choice, Confirmation, ConfirmScreen, InfoScreen
from ..widgets import SectionCard, badge, header, help_line
from .worker_screen import (
    ABORTED,
    DONE,
    FAILED,
    RUNNING,
    SKIPPED,
    WAITING,
    Step,
    WorkerScreen,
)

POLL_S = 0.15
CANCEL_GRACE_S = 8.0      # so lange darf der Prozess nach der cancel-Datei selbst aufräumen
DONE_GRACE_S = 5.0        # so lange darf er nach dem done-Ereignis noch auslaufen
STATE = {'waiting': WAITING, 'running': RUNNING, 'done': DONE, 'failed': FAILED, 'skipped': SKIPPED}


@dataclass
class Outcome:
    ok: bool
    message: str
    sensor_id: str | None = None
    cancelled: bool = False


class SensorOnboardingScreen(WorkerScreen):
    TITLE_ICON = 'setup'
    GROUP = 'sensor-onboarding'
    ASK_DANGER = False

    def __init__(self, instance, run_dir: RunDir, assistant: str = 'none'):
        super().__init__(instance, 'Sensor einrichten')
        self.run_dir = run_dir
        self.assistant = assistant
        self.steps = [Step(key, label) for key, label in STEPS]
        self._outcome: Outcome | None = None
        self.phase = 'running'   # Checkliste sofort zeigen (keine Vorprüfung/Rückfrage vor dem Lauf)

    # ------------------------------------------------------------ Worker-Thread
    def run_job(self, console) -> None:
        proc = sensor_client.start_onboard(self.run_dir, self.assistant, self.instance)
        state = {'seq': 0, 'done': None}

        def drain() -> None:
            for event in self.run_dir.read_events(state['seq']):
                state['seq'] = max(state['seq'], int(event.get('seq', state['seq'])))
                if event.get('type') == 'question':
                    self.handle_question(event)
                elif event.get('type') == 'done':
                    state['done'] = event
                    self.thread_call(self.apply_event, event)
                else:
                    self.thread_call(self.apply_event, event)

        cancel_at = done_at = killed_at = None
        while not self.gone.is_set():
            drain()
            code = proc.poll()
            if code is not None:
                drain()
                break
            now = time.monotonic()
            if self.cancel_event.is_set() and cancel_at is None:
                self.run_dir.request_cancel()
                cancel_at = now
            if state['done'] is not None and done_at is None:
                done_at = now
            overdue = ((cancel_at is not None and now - cancel_at > CANCEL_GRACE_S)
                       or (done_at is not None and now - done_at > DONE_GRACE_S))
            if overdue and killed_at is None:
                sensor_client.stop_process(proc)
                killed_at = now
            elif killed_at is not None and now - killed_at > 3.0:
                sensor_client.stop_process(proc, kill=True)
                killed_at = now
            time.sleep(POLL_S)
        else:
            sensor_client.stop_process(proc)
            return
        done = state['done']
        if done is not None:
            self._outcome = Outcome(bool(done.get('ok')), str(done.get('message', '')), done.get('sensor_id'),
                                    cancelled=not done.get('ok') and cancel_at is not None)
        elif cancel_at is not None:
            self._outcome = Outcome(False, 'Einrichtung abgebrochen; nichts übernommen.', cancelled=True)
        else:
            self._outcome = Outcome(False, f'Der Einrichtungsprozess endete ohne Ergebnis (Exit {code}). '
                                           f'Einzelheiten: {self.run_dir.path / "onboard.log"}')

    def collect_result(self, console, failure):
        if self._outcome is not None:
            return self._outcome
        return Outcome(False, failure or 'Einrichtung ohne Ergebnis beendet.')

    def handle_question(self, event: dict) -> None:
        """Frage als Dialog zeigen (UI-Thread), im Worker auf die Antwort warten und sie schreiben."""
        future: concurrent.futures.Future = concurrent.futures.Future()
        if not self.thread_call(self.open_dialog, event, future):
            return
        while not self.gone.is_set():
            try:
                answer = future.result(timeout=0.2)
                break
            except concurrent.futures.TimeoutError:
                continue
        else:
            return
        qid = str(event.get('id'))
        if answer is None:  # Esc im Dialog: Einrichtung abbrechen, nichts raten
            self.thread_call(self.log_line, 'Frage nicht beantwortet: Einrichtung wird abgebrochen.', True)
            self.cancel_event.set()
            self.thread_call(self.mark_cancel)
            return
        value_ = answer[0]
        try:
            self.run_dir.write_answer(qid, value_)
        except (OSError, ValueError) as error:
            self.thread_call(self.log_line, f'Antwort nicht geschrieben: {error}', True)

    # ------------------------------------------------------------ Hooks (UI-Thread)
    def mark_cancel(self) -> None:
        self.cancel_requested = True
        self.update_view()

    def open_dialog(self, event: dict, future: concurrent.futures.Future) -> None:
        kind, prompt = event.get('kind'), str(event.get('prompt', ''))
        default = event.get('default')

        def done(result, convert=lambda x: x) -> None:
            if not future.done():
                future.set_result(None if result is None else (convert(result),))

        if kind == 'choice':
            options = event.get('options') or []
            choices = [Choice(str(o.get('label')), str(i), primary=i == 0) for i, o in enumerate(options)]
            screen = InfoScreen('Frage zur Einrichtung', [prompt], choices)
            self.app.push_screen(screen, callback=lambda r: done(r, lambda i: options[int(i)].get('value')))
        elif kind == 'confirm':
            screen = ConfirmScreen(Confirmation('Bitte bestätigen', [prompt], [], 'Ja'))
            self.app.push_screen(screen, callback=lambda r: done(bool(r), bool))
        else:
            screen = AskScreen('Eingabe zur Einrichtung', [prompt], value='' if default is None else str(default))
            self.app.push_screen(screen, callback=lambda r: done(r))

    def apply_event(self, event: dict) -> None:
        kind = event.get('type')
        if kind == 'step':
            step = next((s for s in self.steps if s.key == event.get('key')), None)
            if step is None:
                return
            step.state = STATE.get(event.get('state'), WAITING)
            detail = event.get('detail')
            if detail:
                self.log_line(f'{step.label}: {detail}')
            elif step.state in (RUNNING, FAILED):
                self.log_line(step.label)
        elif kind == 'log':
            self.log_line(str(event.get('text', '')))
        elif kind == 'error':
            self.log_line(str(event.get('text', '')), True)
            step = next((s for s in self.steps if s.key == event.get('step')), None)
            if step is not None:
                step.state = FAILED
        elif kind == 'answer':
            self.log_line('Antwort übernommen.')
        self.update_view()

    def finish_steps(self, result: Outcome) -> None:
        for step in self.steps:
            if step.state == RUNNING:
                step.state = DONE if result.ok else (ABORTED if result.cancelled else FAILED)
            elif step.state == WAITING:
                step.state = SKIPPED

    def result_badge(self, result: Outcome) -> tuple[str, str]:
        if result.ok:
            return probes.OK, 'angelegt'
        return (probes.WARN, 'abgebrochen') if result.cancelled else (probes.FAIL, 'Fehler')

    def after_finished(self, result: Outcome) -> None:
        level, word = self.result_badge(result)
        self.app.message(level, f'Sensor einrichten: {word}.')

    def cancel_confirmation(self) -> Confirmation:
        return Confirmation(
            'Einrichtung abbrechen?',
            ['Der Prozess bekommt die Abbruchmarke und beendet sich; ein schon angelegtes vorläufiges '
             'Sensorpaket bleibt bestehen, aktiv gesetzt wird nichts mehr.'], [], 'Abbruch anfordern', danger=True)

    def hint_text(self) -> str:
        if self.finished:
            return 'Esc oder Enter schließt.'
        if self.cancel_requested:
            return 'Abbruch angefordert: der Prozess räumt auf und endet.'
        return 'Esc bricht die Einrichtung ab (nach Rückfrage).'

    # ------------------------------------------------------------ Anzeige
    def draw_result(self) -> None:
        card = self.query_one('#kal-result', SectionCard)
        result = self.result
        card.display = result is not None
        if result is None:
            return
        width = self._width(card)
        level, word = self.result_badge(result)
        paragraphs: list[tuple[str, str]] = []
        if result.ok:
            active = any(s.key == 'aktivieren' and s.state == DONE for s in self.steps)
            name = result.sensor_id or self.run_dir.request().get('name', 'Sensor')
            if active:
                text = (f'Sensor {name} vorläufig angelegt und aktiv – jetzt in der Werkbank '
                        f'{self.instance.url or "/live"} einrichten und Lauf starten.')
            else:
                text = (f'Sensor {name} vorläufig angelegt, aber noch nicht aktiv – im Tab Sensoren „Als aktiv '
                        f'setzen“, danach in der Werkbank {self.instance.url or "/live"} einrichten.')
            paragraphs.append(('Nächster Schritt', text))
        if result.message:
            paragraphs.append(('Meldung', result.message))
        paragraphs.append(('Laufmappe', str(self.run_dir.path)))
        hint = help_line('Werte dieses Sensors sind vorläufig markiert, bis ein Mensch das Paket prüft.') \
            if result.ok else None
        body = Text('\n').join(Text.assemble((f'{label}: ', MUTED), (text, SOFT)) for label, text in paragraphs)
        card.show(header('values', 'Ergebnis', badge(level, word), width), body, hint)

    def step_extras(self, width: int, running) -> list:
        return [Text(f'Assistent: {self.assistant}', style=SOFT)] if self.assistant != 'none' else []
