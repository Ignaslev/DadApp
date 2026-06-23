import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create a timestamped SQLite database backup.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default=None,
            help='Directory for backups. Defaults to <project>/backups.',
        )
        parser.add_argument(
            '--keep',
            type=int,
            default=30,
            help='Keep the newest N backups in the output directory. Use 0 to keep all.',
        )

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if db.get('ENGINE') != 'django.db.backends.sqlite3':
            raise CommandError('backup_db currently supports SQLite only.')

        source_name = str(db['NAME'])
        source_is_uri = source_name.startswith('file:')
        source_path = Path(source_name) if not source_is_uri else None
        if source_path is not None and not source_path.exists():
            raise CommandError(f'Database not found: {source_path}')

        output_dir = Path(options['output']) if options['output'] else settings.BASE_DIR / 'backups'
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target_path = output_dir / f'db-{stamp}.sqlite3'

        if source_is_uri:
            source = sqlite3.connect(source_name, uri=True)
        else:
            source = sqlite3.connect(f'file:{source_path.as_posix()}?mode=ro', uri=True)
        try:
            target = sqlite3.connect(target_path)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()

        keep = options['keep']
        if keep > 0:
            backups = sorted(output_dir.glob('db-*.sqlite3'), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_backup in backups[keep:]:
                old_backup.unlink()

        self.stdout.write(self.style.SUCCESS(f'Backup created: {target_path}'))
