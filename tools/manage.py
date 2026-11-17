"""Operator commands: bootstrap-admin, backup, restore, send-reminders.

Run from the project root. Account invitations and reminders are previews by
default; SMTP delivery happens only when explicitly configured by the operator.
"""
import argparse
import getpass
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app
from werkzeug.security import generate_password_hash


def backup_key(production=False):
    from cryptography.fernet import Fernet
    configured = os.environ.get('BETWEEN_BACKUP_KEY')
    if configured:
        return configured.encode('ascii')
    if production:
        raise ValueError('Set BETWEEN_BACKUP_KEY in a protected secret store before backing up production data.')
    keyfile = ROOT / 'instance' / 'backup.key'
    keyfile.parent.mkdir(parents=True, exist_ok=True)
    if not keyfile.exists():
        with keyfile.open('xb') as handle:
            handle.write(Fernet.generate_key())
        keyfile.chmod(0o600)
    return keyfile.read_bytes().strip()


def encrypted_backup(database, destination, key):
    from cryptography.fernet import Fernet
    database, destination = Path(database), Path(destination)
    if not database.is_file():
        raise ValueError('The database does not exist.')
    if destination.exists():
        raise ValueError('The backup destination already exists; choose a new filename.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='between-backup-', dir=destination.parent) as working:
        snapshot = Path(working) / 'snapshot.sqlite3'
        snapshot.touch(mode=0o600)
        with closing(sqlite3.connect(f'file:{database.as_posix()}?mode=ro', uri=True)) as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
            if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('The SQLite snapshot failed its integrity check.')
        encrypted = Fernet(key).encrypt(snapshot.read_bytes())
        with destination.open('xb') as handle:
            handle.write(encrypted)
        destination.chmod(0o600)
    return destination


def restore_backup(backup, destination, key):
    from cryptography.fernet import Fernet
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Restore uses a new file only. Stop the server and choose a fresh database filename.')
    raw = Fernet(key).decrypt(Path(backup).read_bytes())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='between-restore-', dir=destination.parent) as working:
        snapshot = Path(working) / 'snapshot.sqlite3'
        snapshot.touch(mode=0o600)
        snapshot.write_bytes(raw)
        with closing(sqlite3.connect(snapshot)) as connection:
            if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Restored data failed its SQLite integrity check.')
        # Exclusive creation prevents replacing a database that appeared meanwhile.
        with destination.open('xb') as handle:
            handle.write(raw)
        destination.chmod(0o600)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    admin = sub.add_parser('bootstrap-admin')
    admin.add_argument('--email', required=True)
    admin.add_argument('--name', required=True)
    backup = sub.add_parser('backup')
    backup.add_argument('--output', type=Path)
    restore = sub.add_parser('restore')
    restore.add_argument('--file', type=Path, required=True)
    restore.add_argument('--destination', type=Path, required=True)
    sub.add_parser('send-reminders')
    args = parser.parse_args()
    if args.command == 'restore':
        output = restore_backup(args.file, args.destination, backup_key(os.environ.get('BETWEEN_ENV') == 'production'))
        print('Restored to:', output, '\nStop the app before configuring it to use this restored database.')
        return
    app = create_app()
    database = app.config['DATABASE']
    if args.command == 'backup':
        output = args.output or ROOT / 'instance' / 'backups' / ('between-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3.fernet')
        print('Encrypted backup:', encrypted_backup(database, output, backup_key(app.config['PRODUCTION'])))
    elif args.command == 'bootstrap-admin':
        password = getpass.getpass('Administrator password (12+ characters): ')
        if len(password) < 12 or password != getpass.getpass('Repeat password: '):
            raise ValueError('Use matching passwords of at least 12 characters.')
        if '@' not in args.email or not args.name.strip():
            raise ValueError('Provide a valid email and name.')
        import secrets
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with sqlite3.connect(database) as conn:
            conn.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)', ('operator-' + secrets.token_hex(8), args.email.lower().strip(), generate_password_hash(password), args.name.strip(), 'administrator', 1, stamp))
            conn.execute('INSERT INTO audit(actor,action,target,detail,created) VALUES(?,?,?,?,?)', ('operator','Bootstrapped administrator',args.email.lower().strip(),'Local operator command',stamp))
        print('Administrator account created. No password was printed or emailed.')
    else:
        with app.app_context():
            print('Appointment reminders prepared:', app.extensions['workspace']['send_reminders']())
            print('Delivery mode:', app.config['MAIL_MODE'])


if __name__ == '__main__':
    main()
