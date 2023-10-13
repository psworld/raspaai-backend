import os
import uuid
from json import dumps

import graphene
import requests
from graphql_jwt.decorators import user_passes_test, login_required
from graphql_relay import from_global_id

from shop.models import ShopPlan, PlanQueue
from .utils import Checksum

allowed_host = os.environ.get('ALLOWED_HOSTS')
PAYTM_STAGE = os.environ.get('PAYTM_STAGE')

MKEY = os.environ.get('MKEY')
MID = os.environ.get('MID')

callback_url = f"http://{allowed_host}:8000/paytm/callback/" if allowed_host == 'localhost' else f"https://{allowed_host}/paytm/callback/"


class GetPaytmSubmitForm(graphene.relay.ClientIDMutation):
    paytm_params = graphene.JSONString()

    class Input:
        plan_id = graphene.ID(required=True)

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        plan_id = from_global_id(input.get('plan_id'))[1]

        try:
            plan = ShopPlan.objects.get(id=plan_id)

            user = info.context.user
            order_id = str(uuid.uuid4())
            # body parameters

            paytm_params = {
                "MID": MID,
                "WEBSITE": os.environ.get('WEBSITE_NAME'),
                "INDUSTRY_TYPE_ID": "Retail",
                "CHANNEL_ID": "WEB",
                "ORDER_ID": order_id,
                "EMAIL": user.email,
                "CALLBACK_URL": callback_url,
                # Order Transaction Amount here
                "TXN_AMOUNT": f'{plan.price}',
                "CUST_ID": f'{user.id}',
            }
            paytm_params['CHECKSUMHASH'] = Checksum.generate_checksum(paytm_params, MKEY)

            return cls(paytm_params)

        except ShopPlan.DoesNotExist:
            raise Exception("No plan exist with this id")


class Mutation(graphene.ObjectType):
    get_paytm_submit_form = GetPaytmSubmitForm.Field()


class Query(graphene.ObjectType):
    transaction_status = graphene.JSONString(order_id=graphene.String(required=True))

    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def resolve_transaction_status(self, info, **kwargs):
        order_id = kwargs.get('order_id')
        shop = info.context.user.shop

        paytm_params = {
            "MID": MID,
            "ORDER_ID": order_id,
        }
        checksum = Checksum.generate_checksum(paytm_params, MKEY)
        paytm_params['CHECKSUMHASH'] = checksum

        post_data = dumps(paytm_params)
        # for Staging
        url = "https://securegw-stage.paytm.in/order/status" if PAYTM_STAGE else "https://securegw.paytm.in/order/status"

        transaction_status_response = requests.post(url, data=post_data,
                                                    headers={"Content-type": "application/json"}).json()

        if transaction_status_response['STATUS'] == 'TXN_SUCCESS':
            txn_amount = transaction_status_response['TXNAMOUNT']
            order_id_uuid = uuid.UUID(order_id)
            # check if already exist a plan queue with same order id. It means the transaction_status_response page
            # was refreshed by user
            try:
                plan_queue = PlanQueue.objects.get(order_id=order_id_uuid)
                return transaction_status_response

            except PlanQueue.DoesNotExist:
                try:
                    plan = ShopPlan.objects.get(plan_id=str(int(float(txn_amount))))

                    PlanQueue.objects.add_plan_to_queue(plan=plan, shop=shop)

                    return transaction_status_response

                except Exception as e:
                    raise Exception(e)
                    # raspaai system error. Money has been transacted initiate refund
                    # initiate_refund_params = dict()
                    # initiate_refund_params["body"] = {
                    # "mid" :MID,
                    # # This has fixed value for refund transaction
                    # "txnType" : "REFUND",
                    # "orderId" : order_id,
                    # "txnId" : transaction_status_response["TXNID"],
                    # # Enter numeric or alphanumeric unique refund id
                    # "refId" : order_id,
                    # # Enter amount that needs to be refunded, this must be numeric
                    # "refundAmount" : f'{round(float(txn_amount)*0.99)}'
                    # }

                    # checksum = Checksum.generate_checksum_by_str(dumps(initiate_refund_params["body"]), MKEY)
                    # # head parameters
                    # initiate_refund_params["head"] = {
                    # # This is used when you have two different merchant keys. In case you have only one please put - C11
                    # "clientId" : "C11",
                    # # put generated checksum value here
                    # "signature" : checksum
                    # }

                    # # prepare JSON string for request
                    # post_data = dumps(initiate_refund_params)
                    # # for Staging
                    # url = "https://securegw-stage.paytm.in/refund/apply" if PAYTM_STAGE else "https://securegw.paytm.in/refund/apply"
                    # initiate_refund_response = requests.post(url, data = post_data, headers = {"Content-type": "application/json"}).json()
                    # return initiate_refund_response["body"]

        else:
            return transaction_status_response
