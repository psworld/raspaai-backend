import base64
import random
import re
import sys
from io import BytesIO
from os import environ

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import gettext_lazy as _

username_re = r'^[a-zA-Z0-9_.]+\Z'


def validate_username(public_username):
    normalized_username = public_username_normalizer(public_username)
    if normalized_username.find('raspaai') == -1 and normalized_username.find('raspai') == -1:
        if re.match(username_re, normalized_username):
            check_period_validity(normalized_username)
            return normalized_username
        else:
            raise Exception(f'{public_username} contains invalid characters.')
    raise Exception(f'Username {public_username} is already taken. Try another.')


def public_username_normalizer(public_username):
    normalized_username = public_username.replace(' ', '').lower()

    return normalized_username


def check_period_validity(normalized_username):
    sliced_char_list = list(normalized_username)
    if sliced_char_list[-1] != '.':
        for index, char in enumerate(sliced_char_list):
            if char == '.' and char == sliced_char_list[index + 1]:
                raise ValidationError('Consecutive periods are not allowed')
    else:
        raise ValidationError('Username can not end with a period')


def image_from_64(img_64, img_name, max_width):
    _format, _img_str = img_64.split(';base64,')
    decoded64_img = base64.b64decode(_img_str)
    temporary_image = Image.open(BytesIO(decoded64_img))
    output = BytesIO()
    
    if temporary_image.mode != 'RGB':
        temporary_image = temporary_image.convert('RGB')

    width, height = temporary_image.size
    if width > max_width:
        resize_ratio = height / width
        new_height = int(round(resize_ratio * max_width))
        new_size = (max_width, new_height)
        temporary_image = temporary_image.resize(new_size, Image.ANTIALIAS)

    temporary_image.save(output, format="JPEG", quality=75, optimize=True)
    output.seek(0)
    uploaded_image = InMemoryUploadedFile(output, 'VersatileImageField', "%s.jpg" % img_name.split('.')[0],
                                          'image/jpeg', sys.getsizeof(output), None)

    return uploaded_image


# def image_from_64(img_64):
# _format, _img_str = img_64.split(';base64,')

# decoded64_img = base64.b64decode(_img_str)
# img_content_file = ContentFile(decoded64_img)

# return img_content_file


def n_len_rand(len_, floor=1):
    top = 10 ** len_
    if floor > top:
        raise ValueError(f"Floor {floor} must be less than requested top {top}")
    return f'{random.randrange(floor, top):0{len_}}'


def paytm_endpoint_generator(option, order_id, api=False):
    if environ.get('PAYTM_STAGE'):
        if api:
            return f'https://securegw-stage.paytm.in/{api}/{option}?mid={environ.get("MID")}&orderId={order_id}'
        else:
            return f'https://securegw-stage.paytm.in/{option}?mid={environ.get("MID")}&orderId={order_id}'

    else:
        return f'https://securegw.paytm.in/{api}?mid={environ.get("MID")}&orderId={order_id}'
