from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from home.models import SkincareProfile


class Command(BaseCommand):
    help = "Create missing SkincareProfile records for existing users."

    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.all()
        created_count = 0
        for user in users:
            profile, created = SkincareProfile.objects.get_or_create(user=user)
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created_count} missing SkincareProfile(s)."))
