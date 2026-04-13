import random
import string


def random_string():
    return "".join(random.choices(string.ascii_letters + string.digits, k=22))


# It is unfortunately necessary to replace some characters for ACTS
_ACTS_ENUM_UNSAFE_CHARS = ['"', ",", "&", "%", "+", "<", ">", "="]


def string_to_acts_enum(s: str) -> str:
    """Replace unsafe characters for processing in ACTS"""
    for char in _ACTS_ENUM_UNSAFE_CHARS:
        s = s.replace(char, f"@{char.encode('ascii').hex()}@")
    return s


def acts_enum_to_string(s: str) -> str:
    """Recover unsafe characters from ACTS"""
    for char in _ACTS_ENUM_UNSAFE_CHARS:
        s = s.replace(f"@{char.encode('ascii').hex()}@", char)
    return s
