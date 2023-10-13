from django.core.management.base import BaseCommand, CommandError

from shop.models import Shop

class Command(BaseCommand):
    help = 'Check the validity of shop plans. Change the is_active status of shops accordingly'
    
    def handle(self, *args, **options):
        try:
            all_shops = Shop.objects.all()
            
            for shop in all_shops:
                shop.check_plans_validity()
        
            self.stdout.write(self.style.SUCCESS("Successfully refreshed shop plans"))
            
        except Shop.DoesNotExist:
            raise CommandError("No shops exist at the moment")