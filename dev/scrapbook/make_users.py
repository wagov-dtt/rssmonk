
import httpx
import warnings

warnings.warn("This module should not be imported for use.", ImportWarning)


# Quick dirty item to test user creation limits get users is not paginated.
# 1k so far
if __name__ == "__main__":
    username="adminapi"
    password="" # TODO - fill in

    client = httpx.Client(
        base_url="http://127.0.0.1:9000",
        auth=httpx.BasicAuth(username=username, password=password),
        timeout=30.0,
        headers={"Content-Type": "application/json"},
    )
    for i in range(1000):
        json_data = {
            "username": f"AA-{i}",
            "email": "", "name":"",
            "type": "api", "status": "enabled",
            "password": None, "password_login": False,
            "password2": None, "passwordLogin": False,
            "userRoleId": 1, "listRoleId": None,
            "user_role_id": 1, "list_role_id": None
        }
        response = client.post("/api/users", json=json_data)
        if response.status_code != 200:
            print(response)

    print("Done")
    client.close()