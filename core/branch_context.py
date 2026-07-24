import threading

_thread_locals = threading.local()


def get_current_branch_code():
    return getattr(_thread_locals, 'branch_code', None)


def set_current_branch_code(code):
    _thread_locals.branch_code = code


def get_branch_db_alias(branch_code):
    if not branch_code:
        return 'default'
    return f'branch_{branch_code}'


def get_current_db_alias():
    branch_code = get_current_branch_code()
    return get_branch_db_alias(branch_code)
