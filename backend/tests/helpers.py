AUTH_URL = "/api/v1/auth"
ACCESS_COOKIE = "jacrag_access"


async def register_and_login(client, email: str) -> dict[str, str]:
    await client.post(
        f"{AUTH_URL}/register", json={"email": email, "password": "supersecret"}
    )
    response = await client.post(
        f"{AUTH_URL}/login", json={"email": email, "password": "supersecret"}
    )
    token = response.cookies.get(ACCESS_COOKIE)
    return {"Authorization": f"Bearer {token}"}


async def user_id_for(client, headers) -> int:
    return (await client.get(f"{AUTH_URL}/me", headers=headers)).json()["id"]
