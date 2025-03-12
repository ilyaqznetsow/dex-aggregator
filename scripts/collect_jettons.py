import json

import requests

url = "https://tokens.swap.coffee/api/v2/tokens"

def paged_collect(
        page: int,
        limit: int
):
    params = {
        "page": page,
        "limit": 50
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()
    items = data["items"]

    if data["page"] < data["pages"] and len(items) < limit:
        return items + paged_collect(page + 1, limit - len(items))

    return items

def collect_and_save_jettons(limit: int):
    items = paged_collect(1, limit)

    jettons_to_save = [
        {
            "address": item["address"],
            "symbol": item["symbol"],
            "decimals": item["decimals"]
        }
        for item in items
    ]

    with open("jettons.json", "w") as f:
        json.dump(jettons_to_save, f)



if __name__ == "__main__":
    collect_and_save_jettons(100)