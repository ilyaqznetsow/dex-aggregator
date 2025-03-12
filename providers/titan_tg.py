import httpx
from httpx import AsyncClient

from emulator.emulator import UnsignedMessage, emulate_internal_messages, get_total_swap_output, create_session
from common.models import DexRouteProvider, DexRoute, BuildRouteRequest, \
    EmulationSender, EmulatedResult

TON_ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"


class TitanTgProvider(DexRouteProvider):

    def __init__(self):
        super().__init__()

        self.api_url = "https://api.titan.tg"


    async def build_route(self, client: AsyncClient, sender: EmulationSender, request: BuildRouteRequest) -> DexRoute:
        input_token = request.input_token
        output_token = request.output_token
        input_amount = request.input_amount

        input_token_address = input_token.address
        output_token_address = output_token.address,

        params = {
            "inputMint": TON_ADDRESS if input_token_address == "native" else input_token_address,
            "outputMint": TON_ADDRESS if output_token_address == "native" else output_token_address,
            "amount": input_amount,
            "slippageBps": sender.slippage * 10000,
            "dexs": "StonFi_v1,StonFi_v2,DeDust",
            "minPoolLiquidity": 1000
        }

        response = await client.get(f"{self.api_url}/v1/quote", params=params)
        response.raise_for_status()

        data = response.json()

        return DexRoute(
            input_token=input_token,
            output_token=output_token,
            provider="titan.tg",
            input_amount=input_amount,
            output_amount=int(data["expectedAmountOut"]),
            request=request,
            extra={"data": data}
        )

    def get_name(self) -> str:
        return "titan.tg"

    def is_dex(self):
        return False

    async def emulate_route(self, client: httpx.AsyncClient, sender: EmulationSender, route: DexRoute) -> EmulatedResult:
        body = {
            "senderAddress": sender.wallet_address,
            "swapDetails": route.extra["data"]
        }

        response = await client.post(f"{self.api_url}/v1/swap-messages", json=body)
        response.raise_for_status()

        data = response.json()

        messages = []

        for idx, path in enumerate(route.extra["data"]["pathDetails"]):
            message = data["messages"][idx]

            messages.append(UnsignedMessage(
                src=sender.wallet_address,
                jetton_wallet=sender.jetton_wallet_address,
                dest=message["address"],
                body=message["payload"],
                value=int(message["amount"]),
                swap_input_amount=int(path["amountIn"]),
            ))

        session_id = await create_session(client, sender.mc_block_seqno)
        result = await emulate_internal_messages(self.get_name(), client, messages, session_id)
        output, gas_used = await get_total_swap_output(result)

        return EmulatedResult(
            output_token=route.output_token,
            output_amount=output,
            gas_used=gas_used,
            splits=len(messages),
        )


# async def test():
#     provider = TitanTgProvider()
#     await test_provider(provider)
#
#
# if __name__ == "__main__":
#     import asyncio
#
#     asyncio.run(test())
