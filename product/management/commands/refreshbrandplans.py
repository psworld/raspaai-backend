from django.core.management.base import BaseCommand, CommandError

from product.models import Brand

class Command(BaseCommand):
    help = 'Check the validity of brand plans. Change the is_active status of brands accordingly'
    
    def handle(self, *args, **options):
        try:
            # All the brands except raspaai own brands. Their username contains "raspaai" word.
            all_brands = Brand.objects.exclude(username__contains="raspaai")
            
            for brand in all_brands:
                brand.check_plans_validity()
        
            self.stdout.write(self.style.SUCCESS("Successfully refreshed brand plans"))
            
        except Shop.DoesNotExist:
            raise CommandError("No brands exist at the moment")