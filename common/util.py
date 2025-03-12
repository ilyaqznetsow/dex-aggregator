from httpx import AsyncClient
from pytoniq_core import Address


def address_to_raw(address: str) -> str:
    if address == "native":
        return "native"
    return Address(address).to_str(is_user_friendly=False)


def address_to_friendly(address: str) -> str:
    if address == "native":
        return "native"

    return Address(address).to_str(is_user_friendly=True, is_bounceable=True, is_url_safe=True)

async def get_latest_mc_seqno(client: AsyncClient) -> int:
    response = await client.get("https://tonapi.io/v2/blockchain/masterchain-head")
    response.raise_for_status()

    data = response.json()

    return data["seqno"]

async def get_jetton_wallet_address(client: AsyncClient, user: str, jetton_master: str):
    response = await client.get(f"https://tonapi.io/v2/blockchain/accounts/{address_to_raw(jetton_master)}/methods/get_wallet_address?args={address_to_raw(user)}")
    response.raise_for_status()

    data = response.json()

    return data["decoded"]["jetton_wallet_address"]

async def get_token_metadata(client: AsyncClient, token_address: str):
    if token_address == "native":
        return {
            "name": "TON",
            "symbol": "TON",
            "decimals": 9,
            "listed": True
        }
    response = await client.get(f"https://tokens.swap.coffee/api/v2/tokens/address/{token_address}")
    response.raise_for_status()

    data = response.json()

    return {
        "name": data["name"],
        "symbol": data["symbol"],
        "decimals": data["decimals"],
        "listed": True
    }

async def normalize_token_amount(client: AsyncClient, token_address: str, amount: int):
    if token_address == "native":
        return amount / 1e9

    metadata = await get_token_metadata(client, token_address)

    return amount / 10 ** int(metadata["decimals"])
