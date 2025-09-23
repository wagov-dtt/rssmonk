# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests",
# ]
# ///

# TODO - Move to notifications_ops
# This script is to initialise a Listmonk client from scratch. It should be idempotent if there are no new rss feeds



import random
import string
import requests

from rssmonk.utils import make_url_hash

_API_ROLE_NAME = "api-role"
#_URL = "http://listmonk.rssmonk.svc.cluster.local:9000"
_URL = "http://localhost:9000"

def _authenticate_with_listmonk(session: requests.Session) -> bool :
    # Setup session tracking cookie - TODO Not sure this is required
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=65))
    session.cookies.set('session', random_string, domain='localhost', path='/')
    response = session.post(f'{_URL}/admin/login', data={
        'next':'%2Fadmin',
        'username':'admin', # TODO
        'password':'admin123' # TODO
    }, timeout=10)
    return response.status_code == 302

# Need to return the user role id
def _make_user_role(session: requests.Session, role_name: str) -> int:
    response = session.post(f'{_URL}/api/roles/users', data={
        "name":role_name,
        "permissions":["subscribers:get","subscribers:manage","tx:send","templates:get"]
    }, timeout=10)
    return response.status_code == 200 or (response.status_code == 500 and ("already exists" in response.text))


def _create_admin_api_account(session: requests.Session, api_name: str) -> string:
    # Pull password from secrets (would rather push up but TBD)
    response = session.post(f'{_URL}/api/users', data={
        "username": api_name,
        "email": "", "name":"",
        "type": "api", "status": "enabled",
        "password": None, "password_login": False,
        "password2": None, "passwordLogin": False,
        "userRoleId": 1, "listRoleId": None,
        "user_role_id": 1, "list_role_id": None
    }, timeout=30)

    # Need to return the list passcode
    if response.status_code == 200:
        # Return password
        data = response.json()
        return data["password"]
    elif (response.status_code == 500 and ("already exists" in response.text)):
        # TODO - Already exists, return error so they can recreate account, or bail
        return 2
    else:
        # TODO - Other error
        return 0


def _make_template():
    template = {
        "name": "Blank transactional template",
        "type": "tx",
        "subject": "{{ .Tx.Data.header }}",
        "body": "<!doctype html>\n<html>\n<head>\n</head>\n<body>\n{{ .Tx.Data.body }}\n</body>\n</html>",
    }
    # TODO - push template into system. Hopefully at location 5


if __name__ == "__main__":
    '''
    This script handles the creation of all accounts required to run Listmonk and flows through rsssmonk
    '''
    s = requests.Session()
    if _authenticate_with_listmonk(s):
        # TODO - Make admin api
        role_id = _make_user_role(s, _API_ROLE_NAME)
        _make_template()

        # TODO - Modify default campaign
        # TODO - Remove all others?

        print("Done")
    else:
        print("failed to auth")
    s.close()
