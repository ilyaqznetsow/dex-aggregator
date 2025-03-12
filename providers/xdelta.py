import asyncio

import httpx
from httpx import AsyncClient

from common.util import address_to_friendly
from emulator.emulator import UnsignedMessage, emulate_internal_messages, get_total_swap_output, create_session
from common.models import DexRouteProvider, DexRoute, BuildRouteRequest, \
    EmulationSender, EmulatedResult


class XdeltaRouteProvider(DexRouteProvider):

    def __init__(self):
        super().__init__()
        self.api_url = "https://backend.xdelta.fi"

    async def build_route(self, client: AsyncClient, sender: EmulationSender, request: BuildRouteRequest) -> DexRoute:
        input_token = request.input_token
        output_token = request.output_token
        input_amount = request.input_amount

        input_token_address = input_token.address
        output_token_address = output_token.address

        body = {
            "input_token": "TON" if input_token_address == "native" else address_to_friendly(input_token_address),
            "output_token": "TON" if output_token_address == "native" else address_to_friendly(output_token_address),
            "input_amount": str(input_amount / 10 ** input_token.decimals),
            "max_splits": request.max_splits,
            "max_length": request.max_length,
            "intermediate_tokens": "optimal"
        }

        response = await client.post(f"{self.api_url}/api/v1/route", json=body)
        data = response.json()

        response.raise_for_status()

        return DexRoute(
            input_token=input_token,
            output_token=output_token,
            provider="xdelta.fi",
            input_amount=input_amount,
            output_amount=int(data["data"]["output_amount"] * 10 ** output_token.decimals),
            request=request,
            extra={"data": data["data"]}
        )

    def get_name(self) -> str:
        return "xdelta.fi"

    def is_dex(self):
        return False

    async def emulate_route(self, client: httpx.AsyncClient, sender: EmulationSender, route: DexRoute) -> EmulatedResult:
        await asyncio.sleep(5)

        body = {
            "multiroute": route.extra["data"]["multiroute"],
            "user_address": sender.wallet_address,
            "slippage": 5,
            "timeout": 300
        }

        response = await client.post(f"{self.api_url}/api/v1/compose", json=body)
        response.raise_for_status()

        data = response.json()

        messages = []

        for idx, path in enumerate(route.extra["data"]["multiroute"]["routes"]):
            message = data["data"]["messages"][idx]

            messages.append(UnsignedMessage(
                src=sender.wallet_address,
                jetton_wallet=sender.jetton_wallet_address,
                dest=message["address"],
                body=message["payload"],
                value=message["amount"],
                swap_input_amount=int(path["in_amount"]),
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