import warnings
warnings.warn("This module should not be imported for use. It is solely for mass api endpoint calls as a test", DeprecationWarning)

# This script is a scrap to quickly populate items in Listmonk
from typing import Optional
import requests

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


def _make_subscriber(email: str):
    new_settings = {
        "email": email,
        "status": "enabled",
        "attribs": {},
        "preconfirm_subscriptions": False,
        "lists": []
    }
    response = session.post(f"{_URL}/api/subscribers", json=new_settings)
    print(response.text)


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
            for item in range(10000):
                #_set_up_transactional_template(session)
                #response = session.delete(f"{_URL}/api/templates/{(item + 7064)}")
                _make_subscriber(f"daniel{item}@wagov.au")

        print("Done")
    else:
        print("failed to auth")
