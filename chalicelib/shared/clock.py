from datetime import datetime, timedelta, timezone

# Brasil não tem horário de verão desde 2019; evita depender de tzdata no Lambda
BRASILIA = timezone(timedelta(hours=-3), 'BRT')


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
