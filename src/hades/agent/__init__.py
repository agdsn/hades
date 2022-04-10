"""Hades AMQP API agent"""

import celery

import hades.config.loader
from . import tasks


def create_app(config: hades.config.loader.Config) -> celery.Celery:
    app = celery.Celery(__package__)
    for obj in tasks.__dict__.values():
        if isinstance(obj, tasks.Task):
            app.register_task(obj)
    app.config_from_object(config.of_type(hades.config.CeleryOption))
    return app
