"""Reloj centralizado del sistema (fuente única de verdad temporal).

Contexto:
- `datetime.utcnow()` está deprecado desde Python 3.12 y es confuso
  (produce datetimes "naive" sin advertirlo explícitamente).
- Las columnas `DateTime` del proyecto (models/migraciones) almacenan
  timestamps **naive en UTC** (filas existentes incluidas).

Por lo tanto, `utc_now()` devuelve la hora actual UTC como datetime
**naive**: coherente con las filas ya guardadas, sin deprecaciones y
sin errores al comparar naive vs. aware.

Uso:
    from src.core.datetime_utils import utc_now
    expires_at = utc_now() + timedelta(hours=24)
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Hora actual en UTC como datetime naive (equivalente moderno de utcnow)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
