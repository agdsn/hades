from collections import OrderedDict
from datetime import timedelta

# Hades options

HADES_REAUTHENTICATION_INTERVAL = timedelta(seconds=300)
HADES_RETENTION_INTERVAL = timedelta(days=1)
HADES_CONTACT_ADDRESSES = OrderedDict([
    ("Support", "support@wh2.tu-dresden.de"),
    ("Abuse",   "abuse@wh2.tu-dresden.de"),
    ("Finance", "finanzen@wh2.tu-dresden.de"),
])

# Flask options
BABEL_DEFAULT_LOCALE = 'de_DE'
BABEL_DEFAULT_TIMEZONE = 'Europe/Berlin'
SQLALCHEMY_DATABASE_URI = 'postgresql:///radius'
DEBUG = True

# Celery options
CELERY_ENABLE_UTC = True
CELERY_CREATE_MISSING_QUEUES = True
CELERY_WORKER_DIRECT = True
CELERYBEAT_SCHEDULE = {
    'refresh': {
        'task': 'hades.agent.refresh',
        'schedule': timedelta(minutes=5),
    },
    'delete-old': {
        'task': 'hades.agent.delete_old',
        'schedule': timedelta(minutes=5),
    },
}
