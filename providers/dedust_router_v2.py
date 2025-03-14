import httpx
from httpx import AsyncClient

from common.models import DexRouteProvider, DexRoute, BuildRouteRequest, EmulationSender, EmulatedResult
from emulator.emulator import UnsignedMessage, emulate_internal_messages, get_total_swap_output, create_session


class DedustRouterV2Provider(DexRouteProvider):

    def __init__(self):
        super().__init__()

        self.api_url = "https://api-mainnet.dedust.io/v1/router"

    async def build_route(self, client: AsyncClient, sender: EmulationSender, request: BuildRouteRequest,
                          slippage: float = 0.05) -> DexRoute:
        input_token = request.input_token
        output_token = request.output_token
        input_amount = request.input_amount
        input_token_address = input_token.address
        output_token_address = output_token.address

        body = {
            "in_minter": input_token_address,
            "out_minter": output_token_address,
            "amount": str(input_amount),
            "swap_mode": "exact_in",
            "only_verified_pools": True,
            "slippage_bps": int(slippage * 100 * 100),
            "min_pool_usd_tvl": "0",
            "min_economy_bps": 0,
            "protocols": ["dedust", "stonfi_v1", "stonfi_v2"],
            "max_splits": request.max_splits,
            "max_length": request.max_length
        }
        response = await client.post(f"{self.api_url}/quote", json=body)

        response.raise_for_status()

        data = response.json()

        return DexRoute(
            input_token=input_token,
            output_token=output_token,
            provider="dedust_v2",
            input_amount=input_amount,
            output_amount=int(data['out_amount']),
            request=request,
            extra={"slippage": slippage, "data": data}
        )

    def get_name(self) -> str:
        return "dedust_v2"

    def is_dex(self):
        return False

    async def emulate_route(self, client: httpx.AsyncClient, sender: EmulationSender,
                            route: DexRoute) -> EmulatedResult:
        body = {
            "sender_address": sender.wallet_address,
            "swap_data": route.extra["data"]["swap_data"]
        }
        response = await client.post(f"{self.api_url}/swap", json=body)
        response.raise_for_status()
        data = response.json()

        messages = []
        for idx, path in enumerate(route.extra["data"]["swap_data"]["routes"]):
            path = path[0]
            message = data["transactions"][idx]
            messages.append(UnsignedMessage(
                src=sender.wallet_address,
                jetton_wallet=sender.jetton_wallet_address,
                dest=message["address"],
                body=message["payload"],
                value=int(message["amount"]),
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