"""Linux-PAM, kurzlebige Websessions; kein Passwortspeicher."""

import secrets
import time
from collections import defaultdict, deque


def authenticate(password):
    import PAM

    def conversation(_auth, queries, _data):
        replies = []
        for _prompt, kind in queries:
            if kind == PAM.PAM_PROMPT_ECHO_OFF:
                replies.append((password, 0))
            elif kind == PAM.PAM_PROMPT_ECHO_ON:
                replies.append(("me-systeme", 0))
            elif kind in (PAM.PAM_ERROR_MSG, PAM.PAM_TEXT_INFO):
                replies.append(("", 0))
            else:
                raise ValueError("Nicht unterstuetzte PAM-Abfrage")
        return replies

    try:
        handle = PAM.pam()
        handle.start("login", "me-systeme", conversation)
        handle.authenticate()
        handle.acct_mgmt()
        return True
    except PAM.error:
        return False


class Sessions:
    def __init__(self):
        self.sessions = {}
        self.attempts = defaultdict(deque)

    def allow_attempt(self, remote):
        now = time.monotonic()
        # Bounded map even when remote addresses are varied.
        if len(self.attempts) > 1000:
            self.attempts.clear()
        attempts = self.attempts[remote]
        while attempts and now - attempts[0] > 60:
            attempts.popleft()
        if len(attempts) >= 5:
            return False
        attempts.append(now)
        return True

    def create(self):
        now = time.monotonic()
        self.sessions = {k: v for k, v in self.sessions.items() if now - v["created"] < 8 * 3600}
        if len(self.sessions) >= 32:
            del self.sessions[next(iter(self.sessions))]
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {"created": now, "csrf": secrets.token_urlsafe(32)}
        return token

    def get(self, token):
        session = self.sessions.get(token)
        if session and time.monotonic() - session["created"] < 8 * 3600:
            return session
        self.sessions.pop(token, None)
        return None
