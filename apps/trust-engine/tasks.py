import logging
import os
from celery import Celery
from shared import setup_logging
import trust_engine_core

setup_logging(service_name="trust-engine", level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("trust_engine")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("trust_engine", broker=REDIS_URL, backend=REDIS_URL)

@celery_app.task(name="tasks.evaluate_patch_trust")
def evaluate_patch_trust(patch: str, mutation_score: float) -> dict:
    logger.info("Evaluating patch trust score task...")
    result = trust_engine_core.evaluate_trust(patch, mutation_score)
    return result
