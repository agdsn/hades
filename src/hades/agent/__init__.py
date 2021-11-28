"""Hades AMQP API agent"""

import celery

from . import tasks


def create_app() -> celery.Celery:
    app = celery.Celery(__package__)
    for obj in tasks.__dict__.values():
        if isinstance(obj, tasks.Task):
            app.register_task(obj)
    return app
