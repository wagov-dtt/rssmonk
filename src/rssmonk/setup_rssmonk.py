# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests",
# ]
# ///

# This script is to initialise a Listmonk client from scratch. It should be idempotent if there are no new rss feeds


from typing import Optional
import requests


_FEED_ROLE_NAME = "limited-api-role"
#_URL = "http://listmonk.rssmonk.svc.cluster.local:9000"
_URL = "http://localhost:9000"


def _authenticate_with_listmonk() -> Optional[requests.Session]:
    session = requests.Session()
    # Collect the nonce from the login page to satisfy CSRF protection
    response = session.get(f"{_URL}/admin/login")
    nonce = session.cookies["nonce"]
    username = "admin"
    password = "admin123"

    login_data={
        "username": username,
        "password": password,
        "nonce": nonce,
        "next": "/admin"
    }

    response = session.post(f"{_URL}/admin/login", data=login_data, allow_redirects=False, timeout=30)
    return session if response.status_code == 302 else None

def _make_limited_user_role(session: requests.Session) -> bool:
    # TODO - Remove in favour of RSSMonk
    payload = {
        "name": _FEED_ROLE_NAME,
        "permissions": ["subscribers:get","subscribers:manage","tx:send","templates:get"]
    }
    response = session.post(f"{_URL}/api/roles/users", json=payload, timeout=30)
    return response.status_code == 200 or (response.status_code == 500 and ("already exists" in response.text))


def _set_up_transactional_template(session: requests.Session) -> bool:
    """Create blank tempte """
    template = {
        "name": "Blank transactional template",
        "type": "tx",
        "subject": "{{ .Tx.Data.subject }}",
        "body": "<!doctype html>\n<html>\n<head>\n</head>\n<body>\n{{ .Tx.Data.body }}\n</body>\n</html>",
    }
    response = session.post(f"{_URL}/api/templates", json=template)
    return response.status_code == 200


def _update_listmonk_settings() -> bool:
    """Create blank tempte """
    new_settings = {}
    response = session.post(f"{_URL}/api/settings", json=new_settings)
    return response.status_code == 200


if __name__ == "__main__":
    """
    This script handles the creation of all accounts required to run Listmonk and flows through rsssmonk
    """
    session = _authenticate_with_listmonk()
    if session is not None:
        with session:
            # Make limited user role for feed accounts
            _make_limited_user_role(session)
            for item in range(100):
                _set_up_transactional_template(session)
                #response = session.delete(f"{_URL}/api/templates/{(item + 7064)}")

        print("Done")
    else:
        print("failed to auth")
