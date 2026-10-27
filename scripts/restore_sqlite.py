"""Import a PostgreSQL JSON export into a new, empty Ritmo SQLite database."""
import json
import sqlite3
from pathlib import Path

from backend.app.persistence.store import Store


def quote(value):
    return '"' + value.replace('"', '""') + '"'


def main():
    directory = Path('/app/data')
    target = directory / 'ritmo.sqlite3'
    if target.exists():
        raise SystemExit('Refusing to overwrite an existing database')
    source = json.loads((directory / 'postgres-export.json').read_text())
    schema = json.loads((directory / 'postgres-schema.json').read_text())
    Store(target)
    db = sqlite3.connect(target)
    db.execute('PRAGMA foreign_keys=OFF')
    with db:
        for table, rows in source.items():
            columns = [c for c in schema if c['table_name'] == table]
            types = {c['column_name']: ('INTEGER' if c['data_type'] in ('integer', 'bigint', 'boolean', 'smallint') else 'TEXT') for c in columns}
            existing = {r[1] for r in db.execute(f'PRAGMA table_info({quote(table)})')}
            if not existing:
                definitions = ','.join(f'{quote(k)} {v}' for k, v in types.items())
                db.execute(f'CREATE TABLE {quote(table)} ({definitions})')
            else:
                for name in set(types) - existing:
                    db.execute(f'ALTER TABLE {quote(table)} ADD COLUMN {quote(name)} {types[name]}')
            if db.execute(f'SELECT count(*) FROM {quote(table)}').fetchone()[0]:
                raise ValueError(f'Target table is not empty: {table}')
            for row in rows:
                names = list(row)
                values = [json.dumps(row[k], ensure_ascii=False) if isinstance(row[k], (dict, list)) else row[k] for k in names]
                db.execute(f'INSERT INTO {quote(table)} ({",".join(map(quote,names))}) VALUES ({",".join("?" for _ in names)})', values)
            actual = [dict(zip([c[0] for c in cursor.description], r)) for cursor in [db.execute(f'SELECT * FROM {quote(table)}')] for r in cursor.fetchall()]
            assert len(actual) == len(rows), table
            for original, restored in zip(rows, actual):
                for key, value in original.items():
                    expected = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                    assert restored[key] == expected, (table, key)
            print(f'{table}: {len(rows)} rows verified')
        violations = db.execute('PRAGMA foreign_key_check').fetchall()
        assert not violations, violations
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    db.close()
    print(f'Restored and verified {sum(map(len, source.values()))} rows in {len(source)} tables')


if __name__ == '__main__':
    main()
