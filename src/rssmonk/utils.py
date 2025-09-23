import hashlib

FEED_ACCOUNT_PREFIX = "user_"

class ErrorMessages:
    NO_AUTH_FEED = "Not authorised to interact with this feed"

# Removes everything except for the one key in the dict, empty if the key is not present in the dict
def remove_other_keys(attr: dict, key: str) -> dict:
    if key in attr:
        return {key: attr[key]}
    return {}

def numberfy_subbed_lists(subs : list[dict]):
    subbed_lists : list[int] = []
    for sub_list in subs:
        subbed_lists.append(sub_list["id"])
    return subbed_lists

def make_url_tag(url: str) -> str:
    return f"url:{hashlib.sha256(url.encode()).hexdigest()}"

def make_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

def make_api_username(feed_url :str) -> str:
    return f"{make_url_hash(feed_url)}-api"