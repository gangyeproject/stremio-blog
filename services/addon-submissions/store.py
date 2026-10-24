import contextlib
import hashlib
import json
import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY,
                    ticket_hash TEXT NOT NULL UNIQUE,
                    nonce TEXT NOT NULL UNIQUE,
                    ip_hash TEXT NOT NULL,
                    url_hash TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL,
                    manifest_id TEXT UNIQUE,
                    state TEXT NOT NULL DEFAULT 'queued',
                    message TEXT NOT NULL DEFAULT 'Waiting for automatic review.',
                    slug TEXT,
                    publication TEXT,
                    created REAL NOT NULL,
                    updated REAL NOT NULL,
                    next_attempt REAL NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    deploy_attempts INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS rate_limits (
                    bucket TEXT NOT NULL, identity TEXT NOT NULL,
                    window INTEGER NOT NULL, count INTEGER NOT NULL,
                    PRIMARY KEY(bucket, identity, window)
                );
            ''')

    @contextlib.contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def rate(self, bucket, identity, maximum, seconds):
        window = int(time.time() // seconds)
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT count FROM rate_limits WHERE bucket=? AND identity=? AND window=?',
                                     (bucket, identity, window)).fetchone()
            if row and row['count'] >= maximum:
                return False
            connection.execute('INSERT INTO rate_limits VALUES (?, ?, ?, 1) ON CONFLICT(bucket, identity, window) DO UPDATE SET count=count+1',
                               (bucket, identity, window))
            connection.execute('DELETE FROM rate_limits WHERE bucket=? AND window<?', (bucket, window - 2))
        return True

    def enqueue(self, payload, ip_hash, nonce, ticket):
        now = time.time()
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        url_hash = hashlib.sha256(payload['manifestUrl'].encode()).hexdigest()
        ticket_hash = hashlib.sha256(ticket.encode()).hexdigest()
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            existing = connection.execute('SELECT * FROM submissions WHERE nonce=?', (nonce,)).fetchone()
            if existing:
                return 'accepted' if existing['payload'] == encoded and existing['ip_hash'] == ip_hash else 'duplicate'
            counts = connection.execute('SELECT count(*) AS total, sum(ip_hash=?) AS mine FROM submissions WHERE created>?',
                                        (ip_hash, now - 86400)).fetchone()
            if counts['total'] >= 20 or (counts['mine'] or 0) >= 3:
                return 'limited'
            try:
                connection.execute('INSERT INTO submissions(ticket_hash, nonce, ip_hash, url_hash, payload, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                   (ticket_hash, nonce, ip_hash, url_hash, encoded, now, now))
            except sqlite3.IntegrityError:
                return 'duplicate'
        return 'accepted'

    def status(self, ticket):
        with self.connect() as connection:
            row = connection.execute('SELECT state,message,slug,updated FROM submissions WHERE ticket_hash=?',
                                     (hashlib.sha256(ticket.encode()).hexdigest(),)).fetchone()
        if not row:
            return None
        result = dict(row)
        result['url'] = f'https://stremioaddonmanager.org/blog/addons/{row["slug"]}' if row['state'] == 'published' else None
        result.pop('slug')
        return result

    def claim(self):
        now = time.time()
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute("UPDATE submissions SET state='retrying',next_attempt=?,updated=? WHERE state='reviewing' AND updated<?", (now, now, now - 900))
            row = connection.execute("SELECT * FROM submissions WHERE state IN ('queued','retrying','deploying') AND next_attempt<=? ORDER BY created LIMIT 1", (now,)).fetchone()
            if not row:
                return None
            if row['state'] != 'deploying':
                connection.execute("UPDATE submissions SET state='reviewing',message='Checking the manifest and reviewing your submission.',attempts=attempts+1,updated=? WHERE id=?", (now, row['id']))
            else:
                connection.execute('UPDATE submissions SET next_attempt=? WHERE id=?', (now + 300, row['id']))
            return dict(connection.execute('SELECT * FROM submissions WHERE id=?', (row['id'],)).fetchone())

    def update(self, identity, **values):
        allowed = {'state', 'message', 'slug', 'publication', 'next_attempt', 'deploy_attempts', 'manifest_id'}
        if not values or not set(values) <= allowed:
            raise ValueError('Unsupported database update')
        values['updated'] = time.time()
        with self.connect() as connection:
            connection.execute('UPDATE submissions SET ' + ','.join(f'{key}=?' for key in values) + ' WHERE id=?', (*values.values(), identity))

    def reserve_manifest(self, identity, manifest_id):
        try:
            self.update(identity, manifest_id=manifest_id.casefold())
            return True
        except sqlite3.IntegrityError:
            return False
