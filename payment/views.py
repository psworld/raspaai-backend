from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from payment.utils import Checksum

import os

FRONT_END = os.environ.get("CORS_ORIGIN_WHITELIST")


@csrf_exempt
def handle_callback(request):
    form = request.POST
    response_dict = {}
    for i in form.keys():
        response_dict[i] = form[i]
        if i == 'CHECKSUMHASH':
            checksum = form[i]

    verify = Checksum.verify_checksum(response_dict, os.environ.get('MKEY'), checksum)
    if verify:
        resp_status = response_dict["STATUS"]
        order_id = response_dict["ORDERID"]

        # CORS_ORIGIN_WHITELIST is the front end url
        redirect_url = f'{FRONT_END}/dashboard/shop/plans/buy/payment/{resp_status}/{order_id}'

        return render(request, 'payment/PaymentStatus.html', {'response': response_dict, 'redirect_url': redirect_url})

    else:
        raise Exception("Something went wrong please try again later.")
