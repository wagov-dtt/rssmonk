# Removes everything except for the one key in the dict, empty if the key is not present in the dict
def remove_other_keys(attr: dict, key: str) -> dict:
    if key in attr:
        return {key: attr[key]}

    return {}
