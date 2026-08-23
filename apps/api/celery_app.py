import os
import sys

# Ensure all internal packages and apps/api are in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
api_dir = os.path.join(root_dir, "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

packages_dir = os.path.join(root_dir, "packages")
if os.path.isdir(packages_dir):
    for pkg in os.listdir(packages_dir):
        pkg_path = os.path.join(packages_dir, pkg)
        if os.path.isdir(pkg_path) and pkg_path not in sys.path:
            sys.path.insert(0, pkg_path)

import kombu.transport.redis
_orig_connparams = kombu.transport.redis.Channel._connparams
def _patched_connparams(self, asynchronous=False):
    params = _orig_connparams(self, asynchronous=asynchronous)
    params["protocol"] = 2
    return params
kombu.transport.redis.Channel._connparams = _patched_connparams

from celery import Celery
from config import settings

celery_app = Celery(
    "recovery_paas",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_transport_options={"protocol": 2},
    result_backend_transport_options={"protocol": 2},
)


