# from django_elasticsearch_dsl import Document, fields
# from django_elasticsearch_dsl.registries import registry
#
#
# @registry.register_document
# class ShopProductDocument(Document):
#     shop = fields.ObjectField(properties={
#         'username': fields.TextField(),
#         'title': fields.TextField(),
#         # 'location': fields.GeoPointField()
#     })
#     product = fields.ObjectField(properties={
#         'title': fields.TextField(),
#         'description': fields.TextField(),
#         'mrp': fields.FloatField(),
#         'brand': fields.ObjectField(properties={
#             'username': fields.TextField(),
#             'title': fields.TextField()
#         })
#     })
#
#     offered_price = fields.FloatField()
#
#     class Index:
#         name = 'shop_products'
#
#     class Django:
#         model = ShopProduct
#         fields = [
#             'in_stock',
#             'is_available'
#         ]
