from django.core.management.base import BaseCommand
from django.core.management import call_command
from core.db_router import register_branch_db, BRANCH_APPS


class Command(BaseCommand):
    help = 'Run migrations on all branch databases'

    def handle(self, *args, **options):
        from core.models import Branch

        branches = Branch.objects.filter(status='active')
        if not branches.exists():
            self.stdout.write(self.style.WARNING('No active branches found'))
            return

        for branch in branches:
            alias = f'branch_{branch.code}'
            register_branch_db(branch.code)
            self.stdout.write(f'Migrating {branch.name} ({alias})...')
            call_command('migrate', database=alias, interactive=False)
            self.stdout.write(self.style.SUCCESS(f'  Done'))

        self.stdout.write(self.style.SUCCESS('All branch migrations complete'))
