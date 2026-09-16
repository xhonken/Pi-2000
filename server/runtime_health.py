"""Startup identity and leased draining for existing long-lived processes."""
from contextlib import contextmanager
import os
import secrets
import time
from aiohttp import web
import build_info


class RuntimeIdentity:
    def __init__(self, component, identity=None):
        self.component = component
        self.loaded = dict(identity if identity is not None else build_info.installed())
        self.instance = secrets.token_hex(16)
        self.started = time.time()
        self.inflight = 0
        self.lease = ''
        self.deadline = 0

    @property
    def draining(self):
        return bool(self.lease and time.monotonic() < self.deadline)

    def admit(self):
        if self.draining:
            raise web.HTTPServiceUnavailable(text='This service is waiting for an update. Existing work remains available; try new work after maintenance.')

    @contextmanager
    def operation(self):
        self.admit()
        self.inflight += 1
        try: yield
        finally: self.inflight -= 1

    def control(self, data):
        action, token = data.get('action'), data.get('lease')
        if action == 'status': return
        if not isinstance(token, str) or not 16 <= len(token) <= 128:
            raise web.HTTPBadRequest(text='A maintenance lease is required.')
        if action == 'drain':
            if self.draining and token != self.lease:
                raise web.HTTPConflict(text='Another maintenance operation owns this service.')
            self.lease = token
            self.deadline = time.monotonic() + 120
        elif action == 'resume':
            if token != self.lease:
                raise web.HTTPConflict(text='Maintenance lease does not match.')
            self.lease = ''; self.deadline = 0
        else:
            raise web.HTTPBadRequest(text='Unknown maintenance action.')

    def report(self, work=None):
        work = dict(work or {})
        work['inflight'] = self.inflight
        return {'component': self.component, 'protocol': 1, 'loaded': self.loaded,
                'instance': self.instance, 'pid': os.getpid(), 'started': self.started,
                'draining': self.draining, 'work': work, 'busy': any(work.values())}


def compare(report, installed):
    if not isinstance(report, dict) or report.get('protocol') != 1 or not isinstance(report.get('loaded'), dict):
        return {'state': 'unknown', 'message': 'Running version unavailable; upgrade requires a planned maintenance window.'}
    pending = report['loaded'].get('build') != installed.get('build')
    return {**report, 'pending_update': pending,
            'state': 'draining' if report['draining'] else 'pending' if pending else 'current'}
