# Removes everything except for the one key in the dict, empty if the key is not present in the dict
import hashlib


def remove_other_keys(attr: dict, key: str) -> dict:
    if key in attr:
        return {key: attr[key]}

    return {}

def make_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()
