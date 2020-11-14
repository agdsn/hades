"""Hades agent celery app"""
from celery import Celery

app = Celery("hades.agent")
