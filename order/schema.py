import graphene
from django.utils.timezone import now
from django_filters import FilterSet, OrderingFilter
from graphene_django.filter import DjangoFilterConnectionField
from graphene_django.types import DjangoObjectType
from graphql_jwt.decorators import login_required
from graphql_relay import from_global_id

from core.utils import n_len_rand
from shop.models import Shop
from . import OrderStatus
from .models import Order, ShopOrderLine, OrderItem


class OrderNode(DjangoObjectType):
    class Meta:
        model = Order
        filter_fields = ['id', 'user']
        order_by = ['-created']
        interfaces = (graphene.relay.Node,)


class ShopOrderLineNode(DjangoObjectType):
    class Meta:
        model = ShopOrderLine
        filter_fields = ['client_tracking_id', 'status', 'shop']
        interfaces = (graphene.relay.Node,)


class OrderItemNode(DjangoObjectType):
    class Meta:
        model = OrderItem
        filter_fields = ['id']
        interfaces = (graphene.relay.Node,)


class ModifyOrderStatus(graphene.relay.ClientIDMutation):
    shop_order = graphene.Field(ShopOrderLineNode)

    class Input:
        shop_order_id = graphene.ID(required=True)
        status = graphene.String(required=True)
        #     adding a new field of shop_id, front is not configured for it now
        shop_id = graphene.ID(required=True)

    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        shop_order_id = from_global_id(input.get('shop_order_id'))[1]
        shop_id = from_global_id(input.get('shop_id'))[1]
        status = input.get('status')
        user = info.context.user

        shop = Shop.objects.get(owner=user)
        if shop.id == int(shop_id):
            try:
                shop_order = ShopOrderLine.objects.get(id=shop_order_id)
                if status == "fulfilled":
                    shop_order.status = OrderStatus.FULFILLED
                elif status == "unfulfilled":
                    shop_order.status = OrderStatus.UNFULFILLED
                elif status == "canceled":
                    shop_order.status = OrderStatus.CANCELED

                shop_order.save()

                no_of_fulfilled_shop_orders = 0
                order = shop_order.order
                order_related_shop_orders = order.shop_orders.all()
                for shop_order in order_related_shop_orders:
                    if shop_order.status == "fulfilled":
                        no_of_fulfilled_shop_orders += 1

                if no_of_fulfilled_shop_orders == order_related_shop_orders.count():
                    order.status = OrderStatus.FULFILLED

                elif 0 < no_of_fulfilled_shop_orders < order_related_shop_orders.count():
                    order.status = OrderStatus.PARTIALLY_FULFILLED

                elif no_of_fulfilled_shop_orders == 0:
                    order.status = OrderStatus.UNFULFILLED

                order.save()

                return cls(shop_order)

            except ShopOrderLine.DoesNotExist:
                raise Exception("This order does not exist")

        else:
            raise Exception("Permission denied")


class ClearCart(graphene.relay.ClientIDMutation):
    success = graphene.Boolean()
    
    class Input:
        pass
        
    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        user = info.context.user
        user_cart_lines = user.cart_lines
        user_cart_lines.all().delete()
        
        return cls(True)


class CheckoutCart(graphene.relay.ClientIDMutation):
    # This needs update for per kg or per kg things
    order = graphene.Field(OrderNode)

    class Input:
        full_name = graphene.String(required=True)
        phone = graphene.String(required=True)

    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        full_name = input.get('full_name')
        phone = input.get('phone')

        user = info.context.user

        current_time = now()

        hour = f'{current_time.time().hour:02}'
        minute = '1' if current_time.time().minute < 30 else '2'
        # Both hour and minute combined are 3 digits
        # get other 3 digits

        user_cart_lines = user.cart_lines

        if user_cart_lines.count() == 0:
            raise Exception("User cart is empty")

        else:
            reference_id = n_len_rand(12)
            order = Order(user=user, reference_id=reference_id, user_phone=phone, user_full_name=full_name)
            order.save()

            order_total = 0
            order_total_items = 0

            order_items = []
            shop_orders = []
            for cart_line in user_cart_lines.all():
                shop_order_tracking_id = f'{hour}{minute}-{n_len_rand(3)}'
                shop = cart_line.shop
                shop_order = ShopOrderLine(order=order, shop=shop,
                                           client_tracking_id=shop_order_tracking_id)

                shop_order_total = 0
                shop_order_total_items = 0
                shop_order.save()

                for cart_item in cart_line.items.all():
                    product_title = cart_item.combo.name if cart_item.is_combo() else cart_item.shop_product.product.title
                    unit_price = cart_item.combo.offered_price if cart_item.is_combo() else cart_item.shop_product.offered_price

                    order_item = OrderItem(shop_order=shop_order, shop_product=cart_item.shop_product,
                                           combo=cart_item.combo,
                                           product_title=product_title, quantity=cart_item.quantity,
                                           unit_price=unit_price)
                    shop_order_total += order_item.quantity * order_item.unit_price
                    shop_order_total_items += order_item.quantity
                    # A combo is considered as a single item
                    order_items.append(order_item)

                shop_order.total = shop_order_total
                shop_order.total_items = shop_order_total_items
                # shop_order.save()
                shop_orders.append(shop_order)

                order_total_items += shop_order_total_items
                order_total += shop_order_total

            ShopOrderLine.objects.bulk_update(shop_orders, ['total', 'total_items'])
            OrderItem.objects.bulk_create(order_items)

            order.total = order_total
            order.total_items = order_total_items
            order.save()
            user_cart_lines.all().delete()

            return cls(order)


class Mutation(graphene.ObjectType):
    # checkout_cart = CheckoutCart.Field()
    clear_cart = ClearCart.Field()
    modify_order_status = ModifyOrderStatus.Field()


class UserOrderFilter(FilterSet):
    class Meta:
        model = Order
        fields = ['id', 'user']

    order_by = OrderingFilter(
        fields=(
            ('created'),
        )
    )


class ShopOrderFilter(FilterSet):
    class Meta:
        model = ShopOrderLine
        fields = ['shop', 'status', 'client_tracking_id']

    order_by = OrderingFilter(
        fields=(
            ('order__created'),
        )
    )


class Query(graphene.ObjectType):
    user_orders = DjangoFilterConnectionField(OrderNode, filterset_class=UserOrderFilter)
    shop_orders = DjangoFilterConnectionField(ShopOrderLineNode, filterset_class=ShopOrderFilter)

    @login_required
    def resolve_user_orders(self, info, **kwargs):
        return UserOrderFilter(kwargs).qs
