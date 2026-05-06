import random
import string
import json

def random_string():
    return "".join(random.choices(string.ascii_letters + string.digits, k=22))


# It is unfortunately necessary to replace some characters for ACTS
_ACTS_ENUM_UNSAFE_CHARS = ['"', ",", "&", "%", "+", "<", ">", "="]


def _string_to_acts_enum(s: str) -> str:
    """Replace unsafe characters for processing in ACTS"""
    for char in _ACTS_ENUM_UNSAFE_CHARS:
        s = s.replace(char, f"@{char.encode('ascii').hex()}@")
    return s


def _acts_enum_to_string(s: str) -> str:
    """Recover unsafe characters from ACTS"""
    for char in _ACTS_ENUM_UNSAFE_CHARS:
        s = s.replace(f"@{char.encode('ascii').hex()}@", char)
    return s


def obj2acts(o: object) -> str:
    """Encode an object for processing in ACTS"""
    return _string_to_acts_enum(json.dumps(o))


def acts2obj(s: str):
    """Decode an object after processing in ACTS"""
    return json.loads(_acts_enum_to_string(s))
