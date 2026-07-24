import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from core.models import UserProfile, Branch

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Branch)
def migrate_branch_database(sender, instance, created, **kwargs):
    if not created:
        return
    from core.db_router import register_branch_db
    from django.core.management import call_command
    register_branch_db(instance.code)
    alias = f'branch_{instance.code}'
    try:
        call_command('migrate', database=alias, interactive=False, verbosity=0)
        logger.info(f'Branch database migrated: {alias}')
    except Exception as e:
        logger.error(f'Failed to migrate branch database {alias}: {e}')
