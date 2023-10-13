from django.core.management.base import BaseCommand, CommandError
from versatileimagefield.image_warmer import VersatileImageFieldWarmer
from product.models import ProductImage

class Command(BaseCommand):
    help = 'Create or check thumbnails of products'
    
    def handle(self, *args, **options):
        # All product thumbs. Thumbs have position = 0
        all_thumbs = ProductImage.objects.filter(position=0)
        
        img_warmer = VersatileImageFieldWarmer(instance_or_queryset=all_thumbs, rendition_key_set='product_image', image_attr='image', verbose=True)
        done, failed = img_warmer.warm()
        
        if done:
            self.stdout.write(self.style.SUCCESS(f'Successfully warmed {done} thumbs.'))
            
        if failed:
            raise CommandError(f'Failed to warm {failed} thumbs')