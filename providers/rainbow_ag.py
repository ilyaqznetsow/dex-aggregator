import httpx
from httpx import AsyncClient
from pytoniq_core import begin_cell

from emulator.emulator import UnsignedMessage, emulate_internal_messages, get_total_swap_output, create_session
from common.models import DexRouteProvider, DexRoute, BuildRouteRequest, \
    EmulationSender, EmulatedResult

EMPTY_CELL = begin_cell().end_cell().to_boc().hex()


class RainbowAgProvider(DexRouteProvider):

    def __init__(self):
        super().__init__()
        self.api_url = "https://api.rainbow.ag"

    async def build_route(self, client: AsyncClient, sender: EmulationSender, request: BuildRouteRequest) -> DexRoute:
        input_token = request.input_token
        output_token = request.output_token
        input_amount = request.input_amount
        input_token_address = input_token.address
        output_token_address = output_token.address

        params = {
            "inputAssetAmount": input_amount,
            "inputAssetAddress": "ton" if input_token_address == "native" else input_token_address,
            "outputAssetAddress": "ton" if output_token_address == "native" else output_token_address,
            "senderAddress": sender.wallet_address,
            "maxDepth": request.max_length,
            "maxSplits": request.max_splits,
            "maxSlippage": int(sender.slippage * 100),
        }

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-UA,ru-RU;q=0.9,ru;q=0.8,en-US;q=0.7,en;q=0.6',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Origin': 'https://rainbow.ag',
            'Pragma': 'no-cache',
            'Referer': 'https://rainbow.ag/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }

        response = await client.get(f"{self.api_url}/api/best-route", params=params, headers=headers)
        response.raise_for_status()

        data = response.json()

        return DexRoute(
            input_token=input_token,
            output_token=output_token,
            provider="rainbow.ag",
            input_amount=input_amount,
            output_amount=int(data["displayData"]["outputAssetAmount"] * 10 ** output_token.decimals),
            request=request,
            extra={
                "routes": data["displayData"]["routes"],
                "messages": data["swapMessages"]
            }
        )

    def get_name(self) -> str:
        return "rainbow.ag"

    def is_dex(self):
        return False

    async def emulate_route(self, client: httpx.AsyncClient, sender: EmulationSender,
                            route: DexRoute) -> EmulatedResult:
        routes = route.extra["routes"]
        messages = route.extra["messages"]

        transactions = []

        for idx, message in enumerate(messages):
            if idx < len(routes):
                path = routes[idx]
                input_percent = path["inputPercent"]
                input_amount = int(route.input_amount * (input_percent / 100))
                payload = message["payload"]
            else:
                input_amount = 0
                payload = EMPTY_CELL

            transaction = UnsignedMessage(
                src=sender.wallet_address,
                jetton_wallet=sender.jetton_wallet_address,
                dest=message["address"],
                body=payload,
                value=int(message["amount"]),
                swap_input_amount=input_amount,
            )

            transactions.append(transaction)

        session_id = await create_session(client, sender.mc_block_seqno)
        result = await emulate_internal_messages(self.get_name(), client, transactions, session_id)

        output, gas_used = await get_total_swap_output(result)

        return EmulatedResult(
            output_token=route.output_token,
            output_amount=output,
            gas_used=gas_used,
            splits=len(messages),
        )

# async def test():
#     provider = RainbowAgProvider()
#     await test_provider(provider)
#
#
# if __name__ == "__main__":
#     import asyncio
#
#     asyncio.run(test())
