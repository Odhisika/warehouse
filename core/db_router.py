from django.conf import settings

BRANCH_APPS = {'inventory', 'receiving', 'dispatch', 'returns', 'transfers', 'reports', 'invoicing', 'fleet'}
SHARED_APPS = {'core', 'auth', 'contenttypes', 'sessions', 'messages', 'admin', 'staticfiles'}


def register_branch_db(branch_code):
    alias = f'branch_{branch_code}'
    if alias not in settings.DATABASES:
        db_path = settings.BRANCH_DB_DIR / f'{branch_code}.sqlite3'
        settings.DATABASES[alias] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(db_path),
            'OPTIONS': {},
            'AUTOCOMMIT': True,
            'ATOMIC_REQUESTS': False,
            'TIME_ZONE': None,
            'CONN_MAX_AGE': 0,
            'CONN_HEALTH_CHECKS': False,
            'TEST': {'MIRROR': None, 'NAME': None},
        }


class BranchAwareRouter:

    def db_for_read(self, model, **hints):
        app_label = model._meta.app_label
        if app_label in BRANCH_APPS:
            from core.branch_context import get_current_db_alias
            alias = get_current_db_alias()
            if alias != 'default':
                register_branch_db(alias.replace('branch_', ''))
            return alias
        return 'default'

    def db_for_write(self, model, **hints):
        app_label = model._meta.app_label
        if app_label in BRANCH_APPS:
            from core.branch_context import get_current_db_alias
            alias = get_current_db_alias()
            if alias != 'default':
                register_branch_db(alias.replace('branch_', ''))
            return alias
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)
        if db1 == db2:
            return True
        app1 = obj1.__class__._meta.app_label
        app2 = obj2.__class__._meta.app_label
        if app1 in SHARED_APPS or app2 in SHARED_APPS:
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in BRANCH_APPS:
            return db.startswith('branch_')
        return db == 'default'
