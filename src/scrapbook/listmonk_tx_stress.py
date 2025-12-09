
from datetime import datetime
import json
import httpx
import warnings

import requests
warnings.warn("This module should not be imported for use.", DeprecationWarning)


def make_session() -> requests.Session:
    admin_session = requests.Session()

    admin_session.get("http://localhost:9000/admin/login")
    nonce = admin_session.cookies.get("nonce")
    assert nonce, "Nonce not found in cookies"
    login_data={
        "username": "admin",
        "password": "admin123", # Taken from /workspaces/rssmonk/kustomize/base/secrets.yaml
        "nonce": nonce,
        "next": "/admin"
    }
    admin_session.post("http://localhost:9000/admin/login", data=login_data, allow_redirects=False, timeout=30)
    return admin_session

def make_feed_subscriber(admin_session):
    subscriber_data = {
        "email": "example@example.com",
        "preconfirm_subscriptions": True,
        "status": "enabled",
        "lists": []
    }
    admin_session.post("http://localhost:9000/api/subscribers", json=subscriber_data)

def make_template(admin_session):
    template_data = {
        "name": "subscribe",
        "subject": "Subscribed Subject Line",
        "type": "tx",
        "body": "<html><body></body></html>"
    }
    response = admin_session.post("http://localhost:9000/api/templates", json=template_data)
    print(response.json())
    return response.json()["data"]["id"]


# Quick create tens of thousands of api calls to mail
if __name__ == "__main__":
    client = make_session()
    # Make user
    make_feed_subscriber(client)
    # Make template
    template_id = make_template(client)

    start = datetime.now().timestamp()
    for i in range(10000):
        payload = {
            "subscriber_email": "example@example.com",
            "from_email": "no@reply.com",
            "subject": "None",
            "template_id": template_id,
            "data": {},
            "content_type": "html"
        }
        response = client.post("http://localhost:9000/api/tx", json=payload)

    print(f"Took {(datetime.now().timestamp() - start)}ms")
    client.close()