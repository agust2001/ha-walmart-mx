"""Constantes de la integración Walmart México."""

from datetime import timedelta

DOMAIN = "walmart_mx"

CONF_PRODUCT_ID = "product_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 6 * 60  # minutos
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 24 * 60

# Cuántos cambios de precio se guardan en el historial de cada producto
MAX_HISTORY = 100

EVENT_PRICE_CHANGED = f"{DOMAIN}_price_changed"

STORAGE_VERSION = 1


def scan_interval(minutes: int | None) -> timedelta:
    return timedelta(minutes=max(minutes or DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL))
