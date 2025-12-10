
import asyncio
from datetime import datetime
import threading
import warnings

import requests
warnings.warn("This module should not be imported for use.", ImportWarning)


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

feed_hash = "2653364234567542344343"
def make_feed_subscriber(admin_session):
    subscriber_data = {
        "email": "example@example.com",
        "preconfirm_subscriptions": True,
        "status": "enabled",
        "lists": [],
        "attribs": {
            feed_hash: {
                "subscribe_query": "?region=1,3&portfolio=233,222",
                "unsubscribe_query": "?id=12343244&token=12234234234"
            }
        }
    }
    admin_session.post("http://localhost:9000/api/subscribers", json=subscriber_data)

def make_template(admin_session):
    template_data = {
        "name": "test-instant",
        "subject": "{{ .Tx.subject }}",
        "type": "tx",
        "body": """
<html><body>
<div class="repeater-item">
  <p><a href=\"{{ index .Tx.Data.item \"link\" }}\" target=\"_blank\" rel=\"noopener noreferrer\">{{ index .Tx.Data.item \"title\" }}</a></p>
  <p>{{ index .Tx.Data.item \"description\" | Safe }}</p>
</div>

<strong>About this email</strong>
{{ $feed_attribs := index .Subscriber.Attribs "2653364234567542344343" }}
<p>You received this email because you subscribed to the WA State Government Media Statements e-mail service.
 If at any time you would like to stop receiving media statements please click <a href=\"{{ .Tx.Data.base_url }}{{ $feed_attribs.unsubscribe_query }}\"
 target=\"_blank\" rel=\"noopener noreferrer\">unsubscribe</a></p>

<p>Click <a href=\"{{ .Tx.Data.base_url }}{{ $feed_attribs.subscribe_query }} target=\"_blank\" rel=\"noopener noreferrer\">subscribe</a>
 if this Media Statement has been forwarded to you and you would like to receive it directly. Please do not
 reply to this address, it is not checked for incoming mail.</p>
</body></html>
"""
    }
    response = admin_session.post("http://localhost:9000/api/templates", json=template_data)
    print(response.text)
    return response.json()["data"]["id"]


def send_email(client: requests.Session, iteration: int, template_id: int):
    payload = {
        "subscriber_email": "example@example.com",
        "from_email": "no@reply.com",
        "subject": "Education Minister's Running Challenge reaches final lap for 2025",
        "template_id": template_id,
        "data": {
            "item": {
                "title": "Education Minister's Running Challenge reaches final lap for 2025",
                "link": "https://dev2.wagov.pipeline.development.digital.wa.gov.au/government/media-statements/cook-labor-government/education-ministers-running-challenge-reaches-final-lap-2025-20251103",
                "description": """The 2025 Education Minister's Running Challenge has drawn to a close, with almost 5,000 registered participants logging nearly 53,000 activities and 2.1 million minutes of movement.<br>
Published: Mon, 03 Nov 2025 20:49:09 +0800<br>
Minister: Hon. Sabine Winton BA BPS MLA<br>
Portfolio: Education, Preventative Health<br>
Regions: Perth Metro, Kimberley, Gascoyne, Goldfields/Esperance, Great Southern, Mid West, Peel, Pilbara, South West, Wheatbelt""",
            },
            "base_url": "http://sub",
        },
        "content_type": "html"
    }
    # {{ feed.url }}{{.Subscriber.Attribs.{Feed_hash}.unsub_link}}
    # {{ feed.url }}{{.Subscriber.Attribs.{Feed_hash}.sub_link}}
    response = client.post("http://localhost:9000/api/tx", json=payload)
    print(f"{iteration}: {response.status_code}")


async def main_send(clients):
    threads = []
    results = []
    tasks = {}
    async with asyncio.TaskGroup() as tg:
        for i in range(10000):
            threads.append(tg.create_task(send_email(clients[i % 10], template_id)))

    # Extract the results
    for name, task in tasks.items():
        results[name] = asyncio.Task(task).result()


def threading_send(clients):
    for i in range(1000):
        threads = []
        for j in range(10):
            t = threading.Thread(target=send_email, args=(clients[j], i*10+j, template_id,), kwargs={})
            threads.append(t)

        # Start each thread
        for t in threads:
            t.start()

        # Wait for all threads to finish
        for t in threads:
            t.join()

        threads.clear()


# Quick create tens of thousands of api calls to mail
if __name__ == "__main__":
    clients = []
    for i in range(10):
        # Make 10 clients
        clients.append(make_session())

    # Make user
    make_feed_subscriber(clients[0])
    # Make template
    template_id = make_template(clients[0])
    
    start = datetime.now().timestamp()

    #main_send(clients)
    threading_send(clients)

    time = datetime.now().timestamp() - start
    print(f"Took {time//60}m {time%60}s")

    for i in range(10):
        clients[i].close()