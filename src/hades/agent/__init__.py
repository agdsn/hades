"""Hades AMQP API agent"""

import celery
import celery.signals

import hades.config
from . import tasks


def create_app(config: hades.config.Config) -> celery.Celery:
    app = celery.Celery(__package__)
    for obj in tasks.__dict__.values():
        if isinstance(obj, tasks.Task):
            app.register_task(obj)
    celery.signals.worker_process_init.connect(tasks.setup_engine)
    app.config_from_object(config.of_type(hades.config.CeleryOption))
    return app
