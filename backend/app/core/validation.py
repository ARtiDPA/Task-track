import re
from datetime import date, datetime, timedelta, timezone
MOSCOW = timezone(timedelta(hours=3))

def today():
    return datetime.now(MOSCOW).date().isoformat()


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Неверная дата')
    date.fromisoformat(value)
    if value > today():
        raise ValueError('Нельзя отмечать будущие дни')
    return value


def text_value(data, key, limit):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f'Неверное поле: {key}')
    return value.strip()


