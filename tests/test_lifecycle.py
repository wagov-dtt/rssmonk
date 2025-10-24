# This pytest is to test the entire lifecycle of a feed, primarily as a sanity check on changes
# - Feed creation
# - Feed account creation
# - Feed template insertions
# - Subscribe to feed
# - Confirm subscription to feed
# - Unsubscribe from feed
# - Delete feed
# Requires k3s to be running with a freshly created RSSMonk, Listmonk and Postgres running
from http import HTTPStatus
import pytest
import requests
from requests.auth import HTTPBasicAuth

admin_auth=HTTPBasicAuth("admin", "admin123") # Default k3d credentials

def test_accounts_lifecycle():
    rssmonk_api_addr = "http://localhost:8000"

    # - Feed creation
    create_feed_json = {
        "feed_url": "https://example.com/rss/example",
        "email_base_url": "https://example.com/media",
        "frequency": ["instant", "daily"],
        "name": "Example Media Statements"
    }
    response = requests.post(rssmonk_api_addr+"/api/feeds", auth=admin_auth, json=create_feed_json)
    assert (response.status_code == HTTPStatus.CREATED), response.text
    response_json = response.json()
    assert isinstance(response_json, dict)
    # Check values reflected back
    for key, item in create_feed_json.items():
        assert key in response_json, f"{key} not found in response"
        assert item == response_json[key], f"Non matching values for {key}; in: {item}, out:{response_json[key]}"
    assert "id" in response_json
    assert "url_hash" in response_json and "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" == response_json["url_hash"]

    # - Feed account creation
    create_account = {
        "feed_url": "https://example.com/rss/example"
    }
    response = requests.post(rssmonk_api_addr+"/api/feeds/account", auth=admin_auth, json=create_account)
    assert (response.status_code == HTTPStatus.CREATED), response.text
    response_json = response.json()
    assert isinstance(response_json, dict)
    assert {"id", "name", "api_password"} == set(response_json.keys())
    example_username = response_json["name"]
    example_password = response_json["api_password"]

    assert example_username == "user_091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180"
    assert len(example_password) == 32 # Doesn't matter what the password is as long as it is usable

    # Change to using the local account
    example_auth=HTTPBasicAuth(example_username, example_password)
    # - Feed template insertions
    subscribe_template = {
        "feed_url": "https://example.com/rss/example",
        "template_type": "tx",
        "phase_type": "subscribe",
        "subject": "Please confirm email preferences for WA media statements",
        "body": "<html><body>\r\n<p>Thank you for subscribing to media statement updates from the WA Government.</p>\r\n<p>To start receiving "
                + "updates, please verify your email address by clicking on the link below:</p>\r\n<a href=\"{{ .Tx.Data.confirmation_link }}\" "
                + "target=\"_blank\" rel=\"noopener noreferrer\">{{ .Tx.Data.confirmation_link }}</a></p>\r\n<p>You have subscribed to the "
                + "following statements:</p>\r\n{{ $ministers := index .Tx.Data.filter \"ministers\" }}\r\n{{ if $ministers }}\r\n<p><b>Minister(s)"
                + "</b>\r\n<ul>\r\n {{range $val := $ministers}}\r\n <li>{{ $val }}</li>\r\n {{end}}\r\n</ul>\r\n</p>{{ end }}\r\n{{ $region := "
                + "index .Tx.Data.filter \"region\" }}\r\n{{ if $region }}\r\n<p><b>Region(s)</b><br>\r\n<ul>\r\n {{range $val := $region}}\r\n "
                + "<li>{{ $val }}</li>\r\n {{end}}\r\n</ul>\r\n</p>\r\n{{ end }}\r\n{{ $portfolio := index .Tx.Data.filter \"portfolio\" }}\r\n{{ "
                + "if $portfolio }}\r\n<p><b>Portfolio(s)</b><br>\r\n<ul>\r\n {{range $val := $portfolio}}\r\n <li>{{ $val }}</li>\r\n {{end}}\r\n"
                + "</ul>\r\n</p>\r\n{{ end }}\r\n<p>This link will expire in 24 hours for your security. If it expires, you can return to the <a"
                + " href=\"{{ .Tx.Data.subscription_link }}\" target=\"_blank\" rel=\"noopener noreferrer\">subscription page</a> and start again."
                + "</p>\r\n<p>If you did not make this request, please ignore this email.</p>\r\n<p>Thank you.</p>\r\n<p><b>WA Government Media "
                + "Statement Team.</b></p>\r\n</body></html>"
    }
    response = requests.post(rssmonk_api_addr+"/api/feeds/templates", auth=example_auth, json=subscribe_template)
    assert (response.status_code == HTTPStatus.CREATED), response.text
    response_json = {}
    # Check values reflected back
    for key, item in create_feed_json.items():
        assert key in response_json, f"{key} not found in response"
        assert item == response_json[key], f"Non matching values for {key}; in: {item}, out:{response_json[key]}"
    assert "id" in response_json
    assert "name" in response_json
    assert response_json["name"]  == "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180-subscribe"

    # - Subscribe to feed
    subscription_request = {
        "email": "john@example.com",
        "filter": {
            "ministers": [1, 2],
            "region": [2, 3],
            "portfolio": [1 ,2]
        },
        "display_text": {
            "instant" : {
                "ministers": ["Minister 1", "Minister 2"],
                "region": ["Region 2", "Region 3"],
                "portfolio": ["Portfolio 1", "Portfolio 2"]
            }
        }
    }

    # - Confirm subscription to feed
    confirm_sub = {
        "id": "bedce6892e11403e8d755da2922413bf",
        "guid": "1133931c77fe43d7a0fde6f86c29222c"
    }

    # - Unsubscribe from feed
    unsub_request = {
        "id": "bedce6892e11403e8d755da2922413bf",
        "token": "0a6f75c68b6f45bead43a1d11f0e40f4"
    }

    # - Delete feed
    delete_feed_request = {
        "feed_url": "https://dev2.wagov.pipeline.development.digital.wa.gov.au/rss/media-statements",
        "notify": False
    }
    # Attempt self deletion
    # Delete with admin

