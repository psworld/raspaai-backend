import graphene

from user.schema import Mutation as UserMutation
from user.schema import Query as UserQuery

from product.schema import Query as ProductQuery
from product.schema import Mutation as ProductMutation

from shop.schema import Query as ShopQuery
from shop.schema import Mutation as ShopMutation

from order.schema import Query as OrderQuery
from order.schema import Mutation as OrderMutation

from payment.schema import Mutation as PaymentMutation
from payment.schema import Query as PaymentQuery


class Mutation(UserMutation, PaymentMutation, ProductMutation, ShopMutation, OrderMutation, graphene.ObjectType):
    pass
    # token_auth = graphql_jwt.relay.ObtainJSONWebToken.Field()
    # verify_token = graphql_jwt.relay.Verify.Field()
    # refresh_token = graphql_jwt.relay.Refresh.Field()
    #
    # # Long running refresh tokens
    # revoke_token = graphql_jwt.relay.Revoke.Field()


class Query(UserQuery, ShopQuery, ProductQuery, OrderQuery, PaymentQuery, graphene.ObjectType):
    pass


root_schema = graphene.Schema(query=Query, mutation=Mutation)
