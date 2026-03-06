from django.db.backends.signals import connection_created


def enable_sqlite_wal_mode(sender, connection, **kwargs):
    """
    Enable WAL (Write-Ahead Logging) mode for SQLite.
    This allows concurrent reads while a write is happening.
    Also sets a busy timeout so queries wait instead of failing.
    """
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA busy_timeout=20000;')   # 20 second timeout
        cursor.execute('PRAGMA synchronous=NORMAL;')   # Faster writes
        cursor.execute('PRAGMA foreign_keys=ON;')      # Enforce FK constraints


connection_created.connect(enable_sqlite_wal_mode)
