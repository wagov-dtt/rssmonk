
from multiprocessing import Process
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


def make_feed_subscribers(admin_session: requests.Session):
    for i in range(10000):
        subscriber_data = {
            "email": f"example{i}@example.com",
            "preconfirm_subscriptions": True,
            "status": "enabled",
            "lists": [],
            "attribs": {
                "2653364234567542344343": {
                    "subscribe_query": f"?region={i}&area=233,222",
                    "unsubscribe_query": f"?id={i:03}&token=12234234234"
                }
            }
        }
        admin_session.post("http://localhost:9000/api/subscribers", json=subscriber_data)


def make_instant_template(admin_session):
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
<p>You received this email because you subscribed.
 If at any time you would like to stop please click <a href=\"{{ .Tx.Data.base_url }}{{ $feed_attribs.unsubscribe_query }}\"
 target=\"_blank\" rel=\"noopener noreferrer\">unsubscribe</a></p>

<p>Click <a href=\"{{ .Tx.Data.base_url }}{{ $feed_attribs.subscribe_query }}\" target=\"_blank\" rel=\"noopener noreferrer\">subscribe</a>
 if this has been forwarded to you and you would like to receive it directly. Please do not reply to this address as it is not monitored.</p>
</body></html>
"""
    }
    response = admin_session.post("http://localhost:9000/api/templates", json=template_data)
    return response.json()["data"]["id"]


def make_daily_template(admin_session):
    template_data = {
        "name": "test-daily",
        "subject": "Daily Digest",
        "type": "tx",
        "body": """
<html><body>
{{ range $item := $.Tx.Data.items }}
<div class="repeater-item">
  <p><a href=\"{{ index $item "link" }}\" target=\"_blank\" rel=\"noopener noreferrer\">{{ index $item "title" }}</a></p>
  <p>{{ index $item "description" | Safe }}</p>
</div>
{{end}}

<strong>About this email</strong>
{{ $feed_attribs := index .Subscriber.Attribs "2653364234567542344343" }}
<p>You received this email because you subscribed.
 If at any time you would like to stop please click <a href=\"{{ .Tx.Data.base_url }}{{ $feed_attribs.unsubscribe_query }}\"
 target=\"_blank\" rel=\"noopener noreferrer\">unsubscribe</a></p>

<p>Click <a href=\"{{ .Tx.Data.base_url }}{{ $feed_attribs.subscribe_query }}\" target=\"_blank\" rel=\"noopener noreferrer\">subscribe</a>
 if this has been forwarded to you and you would like to receive it directly. Please do not reply to this address as it is not monitored.</p>
</body></html>
"""
    }
    response = admin_session.post("http://localhost:9000/api/templates", json=template_data)
    return response.json()["data"]["id"]


def send_instant_email(client: requests.Session, template_id: int, email: str | list[str], iteration: int):
    payload = {
        "from_email": "no@reply.com",
        "subject": "Person's Running Challenge reaches final lap for 2022",
        "template_id": template_id,
        "data": {
            "item": {
                "title": "Person's Running Challenge reaches final lap for 2022",
                "link": "https://media-statements/persons-running-challenge-reaches-final-lap-2022-20221203",
                "description": """The 2022 Person's Running Challenge has drawn to a close, with almost 5,000 registered participants logging nearly 53,000 activities.<br>
Published: Wed, 03 Dec 2022 16:49:09 +0000<br>
Person: Peron doing the running<br>
Area: Running<br>
Regions: State wide""",
            },
            "base_url": "http://sub",
        },
        "content_type": "html"
    }
    if isinstance(email, str):
        payload["subscriber_email"] = email
    else:
        payload["subscriber_emails"] = email

    # {{ feed.url }}{{.Subscriber.Attribs.{Feed_hash}.unsub_link}}
    # {{ feed.url }}{{.Subscriber.Attribs.{Feed_hash}.sub_link}}
    response = client.post("http://localhost:9000/api/tx", json=payload)
    print(f"{iteration}: {response.status_code}")


def send_daily_email(client: requests.Session, template_id: int, email: str | list[str], iteration: int):
    payload = {
        "from_email": "no@reply.com",
        "template_id": template_id,
        "data": {
            "items": [{
                "title": "Person's Running Challenge reaches final lap for 2022",
                "link": "https://media-statements/persons-running-challenge-reaches-final-lap-2022-20221203",
                "description": """The 2022 Person's Running Challenge has drawn to a close, with almost 5,000 registered participants logging nearly 53,000 activities.<br>
Published: Wed, 03 Dec 2022 16:49:09 +0000<br>
Person: Peron doing the running<br>
Area: Running<br>
Regions: State wide""",
            },{
                "title": "Lanterns of the Terracotta Warriors",
                "link": "https://media-statements/lanterns-of-the-terracotta-warriors-20221203",
                "description": """Welcomes the Lanterns of the Terracotta Warriors installation, a stunning display of 80 brightly coloured lantern warriors set to light up the city across various locations.<br>
Published: Wed, 03 Dec 2022 12:21:15 +0000<br>
Person: Mueseum<br>
Area: History<br>
Regions: City""",
            },{
                "title": "Major tourism conference arrives in Emutopia",
                "link": "https://media-statements/major-tourism-conference-arrives-emutopia-20221203",
                "description": """Tourism representatives from across the world have arrived in Emutopia for the council meeting place.<br>
Published: Wed, 03 Dec 2022 10:02:42 +0000<br>
Person: Tourist head<br>
Area: Tourism<br>
Regions: City""",
            }],
            "base_url": "http://sub",
        },
        "content_type": "html"
    }

    if isinstance(email, str):
        payload["subscriber_email"] = email
    else:
        payload["subscriber_emails"] = email

    # {{ feed.url }}{{.Subscriber.Attribs.{Feed_hash}.unsub_link}}
    # {{ feed.url }}{{.Subscriber.Attribs.{Feed_hash}.sub_link}}
    response = client.post("http://localhost:9000/api/tx", json=payload)
    print(f"{iteration}: {response.status_code}")


async def main_send(clients, template_id):
    threads = []
    results = []
    tasks = {}
    async with asyncio.TaskGroup() as tg:
        for i in range(10000):
            email = "example@example.com"
            threads.append(tg.create_task(send_instant_email(clients[i % 10], template_id, email, i)))

    # Extract the results
    for name, task in tasks.items():
        results[name] = asyncio.Task(task).result()


def threading_send(clients, template_id):
    for i in range(10):
        process: list[Process] = []
        for j in range(100):
            iteration = i*100+j
            emails = [f"example{i}@example.com" for i in range(10)]
            t = Process(target=send_instant_email, args=(clients[j], template_id, emails, iteration,), kwargs={})
            process.append(t)

        # Start each thread
        for t in process:
            t.start() # Start immediately ?

        # Wait for all threads to finish
        for t in process:
            t.join()

        process.clear()


def using_array_emails_instant_send(clients, template_id):
    iteration = 0
    emails = [f"example{i}@example.com" for i in range(10000)]
    send_instant_email(clients[0], template_id, emails, iteration)


def using_array_emails_daily_send(clients, template_id):
    iteration = 0
    for i in range(10):
        emails = [f"example{j}@example.com" for j in range(i*1000, (i+1)*1000)]
        send_daily_email(clients[0], template_id, emails, iteration)


# Quick create tens of thousands of api calls to mail
if __name__ == "__main__":
    clients = []
    for i in range(100):
        # Make 10 clients
        clients.append(make_session())

    # Make user
    #make_feed_subscribers(clients[0])
    # Make template
    instant_template_id = make_instant_template(clients[0])
    daily_template_id = make_daily_template(clients[0])
    
    start = datetime.now().timestamp()

    #main_send(clients, template_id)
    #threading_send(clients, instant_template_id)
    #using_array_emails_instant_send(clients, instant_template_id)
    using_array_emails_daily_send(clients, daily_template_id)

    time = datetime.now().timestamp() - start
    print(f"Took {time}s")

    for i in range(10):
        clients[i].close()
