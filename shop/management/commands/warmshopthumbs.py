from django.core.management.base import BaseCommand, CommandError
from versatileimagefield.image_warmer import VersatileImageFieldWarmer
from shop.models import Shop

class Command(BaseCommand):
    help = 'Create or check thumbnails of shop hero_image'
    
    def handle(self, *args, **options):
        all_shops = Shop.objects.all()
        
        img_warmer = VersatileImageFieldWarmer(instance_or_queryset=all_shops, rendition_key_set='hero_image', image_attr='hero_image', verbose=True)
        done, failed = img_warmer.warm()
        
        if done:
            self.stdout.write(self.style.SUCCESS(f'Successfully warmed {done} thumbs.'))
            
        if failed:
            raise CommandError(f'Failed to warm {failed} thumbs')