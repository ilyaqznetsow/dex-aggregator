import httpx
from httpx import AsyncClient

from common.models import DexRouteProvider, DexRoute, BuildRouteRequest, EmulationSender, EmulatedResult
from providers.swap_coffee import SwapCoffeeRouteProvider, SwapRoute, DexPool, build_paths

TON_ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"
LEGACY_ROUTER = "EQB3ncyBUTjZUA5EnFKR5_EnOMI9V1tTEAAPaiU71gc4TiUt"

class StonfiProvider(DexRouteProvider):

    def __init__(self, builder: SwapCoffeeRouteProvider | None = None):
        super().__init__()

        self.api_url = "https://rpc.ston.fi/"
        self.builder = builder

    async def build_route(self, client: AsyncClient, sender: EmulationSender, request: BuildRouteRequest) -> DexRoute:
        input_token = request.input_token
        output_token = request.output_token
        input_amount = request.input_amount
        input_token_address = input_token.address
        output_token_address = output_token.address

        body = {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "dex.simulate_swap",
            "params": {
                "offer_address": TON_ADDRESS if input_token_address == "native" else input_token_address,
                "offer_units": str(input_amount),
                "ask_address": TON_ADDRESS if output_token_address == "native" else output_token_address,
                "slippage_tolerance": "0.05"
            }
        }

        response = await client.post(self.api_url, json=body)
        response.raise_for_status()

        data = response.json()

        return DexRoute(
            input_token=input_token,
            output_token=output_token,
            provider="stonfi",
            input_amount=input_amount,
            output_amount=int(data["result"]["ask_units"]),
            request=request,
            extra={"data": data["result"]}
        )

    def get_name(self) -> str:
        return "stonfi"

    def is_dex(self):
        return True

    async def emulate_route(self,
                            client: httpx.AsyncClient,
                            sender: EmulationSender,
                            route: DexRoute) -> EmulatedResult:
        if not self.builder:
            return await super().emulate_route(client, sender, route)

        result = route.extra["data"]

        dex_name = "stonfi" if result["router_address"] == LEGACY_ROUTER else "stonfi_v2"

        swap_route = SwapRoute(
            gas_amount=0.15,
            pools=[
                DexPool(
                    input_token=route.input_token.address,
                    output_token=route.output_token.address,
                    amount_in=route.input_amount,
                    dex_name=dex_name,
                    amount_out=route.output_amount,
                    pool_address=result["pool_address"]
                )
            ]
        )

        route.extra = {
            "paths": await build_paths(client, [swap_route])
        }

        return await self.builder.emulate_route(client, sender, route)

# async def test():
#     provider = StonfiProvider()
#     await test_provider(provider)
#
#
# if __name__ == "__main__":
#     import asyncio
#
#     asyncio.run(test())
