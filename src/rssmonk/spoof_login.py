# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests",
# ]
# ///

# TODO - Move to notifications_ops

import random
import string
import requests

_API_ROLE_NAME = "api-role"
#_URL = "http://listmonk.rssmonk.svc.cluster.local:9000"
_URL = "http://localhost:9000"

def _authenticate_with_listmonk(session: requests.Session) -> bool :
    # This should get initial cookies
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=65))
    session.cookies.set('session', random_string, domain='localhost', path='/')
    response = session.get(f'{_URL}/admin/login', timeout=10)
    print(response.headers)
    response = session.post(f'{_URL}/admin/login', data={
        'nonce':response.cookies.get('nonce'),
        'next':'%2Fadmin',
        'username':'admin', # TODO
        'password':'admin123' # TODO
    }, timeout=10)
    print(response.headers)
    print(response.status_code)
    return response.status_code == 302

# Need to return the user role id
def _make_user_role(session: requests.Session, role_name: str) -> int:
    response = session.post(f'{_URL}/api/roles/users', data={
        "name":role_name,
        "permissions":["subscribers:get","subscribers:manage","tx:send"]
    }, timeout=10)
    return response.status_code == 200 or (response.status_code == 500 and ("already exists" in response.text))


def _make_list(session: requests.Session, list_name: str) -> int:
    # Check list for existance
    response = session.get(f'{_URL}/api/lists?page=1&query={list_name}&order_by=id&order=asc', timeout=10)
    if response.status_code == 200:
        response_json = response.json()
        data = response_json['data']
        if data['total'] > 1:
            # This is bad and will require manual clean up.
            # TODO - Send error message or alert
            pass
        elif data['total'] == 1:
            # Return ID
            if 'data' in response.json and 'results' in response.json['data'] and 'id' in response.json['data']['results'][0]:
                return response.json['data']['results'][0]['id']
        else:
            # List name is not primary key
            response = session.post(f'{_URL}/api/lists', data={
                "name":f"{list_name}_list",
                "type":"public",
                "optin":"single",
                "tags":[]
            }, timeout=10)
            if response.status_code == 200:
                # Need to get the ID out
                if 'data' in response.json and 'id' in response.json['data']:
                    return response.json['data']['id']

    # TODO - return list id. WHY is this the only one with this response...
    return 0


def _make_list_role(session: requests.Session, list_name: str, list_id: int) -> int:
    response = session.post(f'{_URL}/api/roles/lists', data={
        "name":f'{list_name}-role',
        "permissions":["subscribers:get","subscribers:manage","tx:send"]
    }, timeout=10)
    return response.status_code == 200 or (response.status_code == 500 and ("already exists" in response.text))


def _make_list_api(session: requests.Session, list_name: str, user_role: int, list_role: int) -> int:
    # Pull password from secrets (would rather push up but TBD)
    response = session.post(f'{_URL}/api/users', data={
        "username":f"{list_name}-api-user",
        "email":"", "name":"",
        "type":"api",
        "password":None,"passwordLogin":False,
        "status":"enabled",
        "userRoleId":user_role, "listRoleId":list_role,
        "password2":None, "password_login":False,
        "user_role_id":user_role, "list_role_id":list_role
    }, timeout=10)

    # Need to return the list passcode
    if response.status_code == 200:
        return 1
    elif (response.status_code == 500 and ("already exists" in response.text)):
        return 2


def _make_list_set(session: requests.Session, list_name: str, user_role_id: int) -> bool:
    list_id =_make_list(session, list_name); 
    list_role_id = _make_list_role(session, list_name, list_id)
    return _make_list_api(session, list_name, user_role_id, list_role_id)


if __name__ == "__main__":
    # TODO - Would need list of accounts that need to be made
    s = requests.Session()
    if _authenticate_with_listmonk(s):
        role_id = _make_user_role(s, _API_ROLE_NAME)
        print(_make_list_set(s, "mediastatements", role_id))
        # TODO -
        print("done")
    else:
        print("failed to auth")
    s.close()    