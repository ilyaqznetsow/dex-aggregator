import asyncio

import httpx
from httpx import AsyncClient

from common.models import DexRouteProvider, DexRoute, BuildRouteRequest, EmulationSender, EmulatedResult
from common.util import address_to_raw
from providers.swap_coffee import SwapCoffeeRouteProvider, DexPool, build_paths, SwapRoute


class DedustProvider(DexRouteProvider):

    def __init__(self, builder: SwapCoffeeRouteProvider | None = None):
        super().__init__()

        self.api_url = "https://api.dedust.io/v2/routing/plan"
        self.builder = builder

    async def build_route(self, client: AsyncClient, sender: EmulationSender, request: BuildRouteRequest,
                          slippage: float = 0.05) -> DexRoute:
        input_token = request.input_token
        output_token = request.output_token
        input_amount = request.input_amount
        input_token_address = input_token.address
        output_token_address = output_token.address

        body = {
            "from": f"jetton:{address_to_raw(input_token_address)}" if input_token_address != "native" else "native",
            "to": f"jetton:{address_to_raw(output_token_address)}" if output_token_address != "native" else "native",
            "amount": str(input_amount)
        }

        response = await client.post(self.api_url, json=body)
        response.raise_for_status()

        data = response.json()

        last_pool = data[0][-1]

        return DexRoute(
            input_token=input_token,
            output_token=output_token,
            provider="dedust",
            input_amount=input_amount,
            output_amount=int(last_pool["amountOut"]),
            request=request,
            extra={"slippage": slippage, "data": data}
        )

    def get_name(self) -> str:
        return "dedust"

    def is_dex(self):
        return True

    async def emulate_route(self, client: httpx.AsyncClient, sender: EmulationSender,
                            route: DexRoute) -> EmulatedResult:
        if not self.builder:
            return await super().emulate_route(client, sender, route)

        pools = []

        for pool in route.extra["data"][0]:
            pool_address = pool["pool"]["address"]
            input_token = pool["assetIn"].replace("jetton:", "")
            output_token = pool["assetOut"].replace("jetton:", "")
            amount_in = int(pool["amountIn"])
            amount_out = int(pool["amountOut"])

            pools.append(DexPool(
                input_token=input_token,
                output_token=output_token,
                amount_in=amount_in,
                amount_out=amount_out,
                pool_address=pool_address,
                dex_name="dedust"
            ))

        route.extra = {
            "paths": await build_paths(client, [
                SwapRoute(gas_amount=0.15, pools=pools)
            ])
        }

        # there is all magic here by swap.coffee <3
        return await self.builder.emulate_route(client, sender, route)

# async def test():
#     provider = DedustProvider()
#     await test_provider(provider)
#
#
# if __name__ == "__main__":
#     import asyncio
#
#     asyncio.run(test())
