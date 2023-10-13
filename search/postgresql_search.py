from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

from shop.models import ShopProduct, Combo, Shop
from product.models import Product

def shop_product_search(phrase, coords, km=5, shops=False):
    name_sim = TrigramSimilarity("title", phrase)
    ft_in_description = Q(description__search=phrase)
    name_sim_filter = Q(name_sim__gt=0.1)
    matching_products = Product.objects.annotate(name_sim=name_sim).filter(
        (name_sim_filter | ft_in_description)
    )
    
    if matching_products.count() == 0:
        return []
    
    else:
        lat = coords['lat']
        lng = coords['lng']
        ref_location = Point(lng, lat, srid=4326)

        nearby_shops = shops if shops else Shop.objects.filter(location__dwithin=(ref_location, D(km=km)), is_active=True)
        
        if nearby_shops.count() == 0:
            return []
        
        nearby_shop_products = ShopProduct.objects.filter(shop__in=nearby_shops)
        
        filtered_shop_products = nearby_shop_products.filter(product__in=matching_products)
        ordered_shop_products = filtered_shop_products.order_by('offered_price')

        return ordered_shop_products

# first filtering nearby shops and then phrase filtering
# def shop_product_search(phrase, coords, km=5, shops=False):
    # name_sim = TrigramSimilarity("product__title", phrase)
    # ft_in_description = Q(product__description__search=phrase)
    # lat = coords['lat']
    # lng = coords['lng']
    # ref_location = Point(lng, lat, srid=4326)

    # nearby_shops = Q(shop__location__dwithin=(ref_location, D(km=km)), shop__is_active=True)
    # name_similar = Q(name_sim__gt=0.1)

    # nearby_shop_products = ShopProduct.objects.filter(nearby_shops)
    # filtered_shop_products = nearby_shop_products.annotate(name_sim=name_sim).filter(
        # (name_similar | ft_in_description)
    # )
    # order_shop_products = filtered_shop_products.order_by('offered_price', '-name_sim')

    # return order_shop_products


def combos_search(phrase, coords, km=5, shops=False):
    name_sim = TrigramSimilarity("name", phrase)
    ft_in_description = Q(description=phrase)
    lat = coords['lat']
    lng = coords['lng']
    ref_location = Point(lng, lat, srid=4326)

    nearby_shops = shops if shops else Shop.objects.filter(location__dwithin=(ref_location, D(km=km)), is_active=True)
 
    name_similar_filter = Q(name_sim__gt=0.1)

    nearby_combos = Combo.objects.filter(shop__in=nearby_shops)
    filtered_combos = nearby_combos.annotate(name_sim=name_sim).filter(
        (name_similar_filter | ft_in_description)
    )
    combos = filtered_combos.order_by('offered_price')

    return combos


def search_combos_in_shop(phrase, combos):
    name_sim = TrigramSimilarity("name", phrase)
    ft_in_description = Q(description=phrase)

    name_similar = Q(name_sim__gt=0.2)
    combos = combos.annotate(name_sim=name_sim).filter((name_similar | ft_in_description))

    return combos


def search_products_in_shop(phrase, shop_products):
    name_sim = TrigramSimilarity("product__title", phrase)
    ft_in_description = Q(product__description__search=phrase)

    name_similar = Q(name_sim__gt=0.2)
    shop_products = shop_products.annotate(name_sim=name_sim).filter((ft_in_description | name_similar))

    return shop_products


def search_products_in_brand(phrase, products, sim_gt=0.2):
    name_sim = TrigramSimilarity("title", phrase)
    # ft_in_description = Q(description__search=phrase)
    name_similar = Q(name_sim__gt=sim_gt)

    products = products.annotate(name_sim=name_sim).filter(name_similar)
    return products

# from search.postgresql_search import shop_product_search
# coords = {'lat':31.707526, 'lng':76.931393}
# results = shop_product_search("reality is nto what it seems", coords)
