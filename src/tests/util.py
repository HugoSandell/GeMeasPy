import random
import string


def random_string():
    return "".join(random.choices(string.ascii_letters + string.digits, k=22))
