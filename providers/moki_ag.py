import asyncio

import httpx
from httpx import AsyncClient

from common.models import DexRouteProvider, DexRoute, BuildRouteRequest, EmulationSender, EmulatedResult
from common.util import address_to_friendly
from providers.swap_coffee import SwapCoffeeRouteProvider, DexPool, SwapRoute, build_paths


def _map_dex_name(dex_name: str) -> str:
    if dex_name == "DeDust":
        return "dedust"
    elif dex_name == "Ston":
        return "stonfi"
    elif dex_name == "Ston_V2":
        return "stonfi_v2"
    else:
        return dex_name


class MokiAgProvider(DexRouteProvider):

    def __init__(self, builder: SwapCoffeeRouteProvider | None = None):
        super().__init__()

        self.api_url = "https://api.leapwallet.io/ton-sor-service/api/v2/best-route"
        self.builder = builder

    async def build_route(self, client: AsyncClient, sender: EmulationSender, request: BuildRouteRequest,
                          slippage: float = 0.05) -> DexRoute:
        input_token = request.input_token
        output_token = request.output_token
        input_amount = request.input_amount
        input_token_address = input_token.address
        output_token_address = output_token.address

        body = {
            "inputAssetAmount": str(input_amount),
            "inputAssetAddress": address_to_friendly(
                input_token_address) if input_token_address != "native" else input_token_address,
            "outputAssetAddress": address_to_friendly(
                output_token_address) if output_token_address != "native" else output_token_address,
        }

        response = await client.post(self.api_url, json=body)
        response.raise_for_status()

        data = response.json()

        return DexRoute(
            input_token=input_token,
            output_token=output_token,
            provider="moki.ag",
            input_amount=int(input_amount),
            request=request,
            output_amount=int(data["bestRoute"][0]["route"][-1]["outputAssetAmount"]),
            extra={"data": data}
        )

    def get_name(self) -> str:
        return "moki.ag"

    def is_dex(self):
        return False


    async def emulate_route(self, client: httpx.AsyncClient, sender: EmulationSender,
                            route: DexRoute) -> EmulatedResult:

        if not self.builder:
            return await super().emulate_route(client, sender, route)

        splits = route.extra["data"]["bestRoute"]
        routes = []

        for split in splits:
            pools = []

            for pool in split["route"]:
                pools.append(DexPool(
                    input_token=pool["inputAssetAddress"],
                    output_token=pool["outputAssetAddress"],
                    amount_in=int(pool["inputAssetAmount"]),
                    amount_out=int(pool["outputAssetAmount"]),
                    dex_name=_map_dex_name(pool["dexType"]),
                    pool_address=pool["dexPairAddress"]
                ))

            routes.append(
                SwapRoute(
                    gas_amount=int(split["fee"]) / 1e9,
                    pools=pools
                )
            )

        route.extra = {
            "paths": await build_paths(client, routes)
        }

        return await self.builder.emulate_route(client, sender, route)

# async def test():
#     provider = MokiAgProvider()
#     await test_provider(provider)
#
#
# if __name__ == "__main__":
#     import asyncio
#
#     asyncio.run(test())
