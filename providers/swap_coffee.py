from httpx import AsyncClient
from pydantic import BaseModel

from common.util import get_token_metadata, address_to_friendly
from emulator.emulator import UnsignedMessage, emulate_internal_messages, get_total_swap_output, create_session
from common.models import DexRouteProvider, BlockchainToken, DexRoute, BuildRouteRequest, \
    EmulationSender, EmulatedResult


class DexPool(BaseModel):
    input_token: str
    output_token: str
    amount_in: int
    dex_name: str
    amount_out: int
    pool_address: str


class SwapRoute(BaseModel):
    gas_amount: float
    pools: list[DexPool]


async def build_paths(client: AsyncClient, routes: list[SwapRoute]) -> list:
    paths = []
    for swap_route in routes:
        current_path = None
        root_path = None

        for pool in swap_route.pools:
            pool_address = pool.pool_address
            input_token = pool.input_token
            output_token = pool.output_token
            amount_in = pool.amount_in
            amount_out = pool.amount_out

            input_metadata = await get_token_metadata(client, input_token)
            output_metadata = await get_token_metadata(client, output_token)

            path = {
                "blockchain": "ton",
                "dex": pool.dex_name,
                "pool_address": pool_address,
                "input_token": {
                    "address": {
                        "blockchain": "ton",
                        "address": address_to_friendly(input_token)
                    },
                    "metadata": input_metadata
                },
                "output_token": {
                    "address": {
                        "blockchain": "ton",
                        "address": address_to_friendly(output_token)
                    },
                    "metadata": output_metadata
                },
                "swap": {
                    "result": "fully_fulfilled",
                    "input_amount": amount_in / 10 ** input_metadata["decimals"],
                    "output_amount": amount_out / 10 ** output_metadata["decimals"],
                    "before_reserves": [1, 1],
                    "after_reserves": [1, 1],
                    "left_amount": 1
                },
                "recommended_gas": swap_route.gas_amount if not current_path else 0,
                "average_gas": 0
            }

            if current_path is None:
                current_path = path
            else:
                current_path["next"] = [path]
                current_path = path

            if not root_path:
                root_path = current_path

        paths.append(root_path)

    return paths


class SwapCoffeeRouteProvider(DexRouteProvider):

    def __init__(self):
        super().__init__()

        self.api_url = "https://backend.swap.coffee"

    async def build_route(self, client: AsyncClient, sender: EmulationSender, request: BuildRouteRequest) -> DexRoute:
        input_token = request.input_token
        output_token = request.output_token
        input_amount = request.input_amount
        input_token_address = input_token.address
        output_token_address = output_token.address

        body = {
            "input_token": {
                "blockchain": "ton",
                "address": input_token_address
            },
            "output_token": {
                "blockchain": "ton",
                "address": output_token_address
            },
            "input_amount": input_amount / 10 ** input_token.decimals,
            "max_splits": request.max_splits,
            "max_length": request.max_length
        }

        response = await client.post(f"{self.api_url}/v1/route", json=body)
        response.raise_for_status()

        data = response.json()

        return DexRoute(
            input_token=input_token,
            output_token=BlockchainToken(address=data["output_token"]["address"]["address"],
                                         symbol=data["output_token"]["metadata"]["symbol"],
                                         decimals=data["output_token"]["metadata"]["decimals"]),
            provider="swap.coffee",
            input_amount=input_amount,
            output_amount=int(data["output_amount"] * 10 ** data["output_token"]["metadata"]["decimals"]),
            request=request,
            extra={
                "paths": data["paths"]
            }
        )

    def get_name(self) -> str:
        return "swap.coffee"

    def is_dex(self):
        return False

    async def emulate_route(self, client: AsyncClient, sender: EmulationSender, route: DexRoute) -> EmulatedResult:
        body = {
            "slippage": sender.slippage,
            "sender_address": sender.wallet_address,
            "paths": route.extra["paths"]
        }

        response = await client.post(f"{self.api_url}/v2/route/transactions", json=body)
        response.raise_for_status()
        data = response.json()

        messages = []

        for idx, path in enumerate(route.extra["paths"]):
            message = data["transactions"][idx]
            messages.append(UnsignedMessage(
                src=sender.wallet_address,
                jetton_wallet=sender.jetton_wallet_address,
                dest=message["address"],
                body=message["cell"],
                value=int(message["value"]),
                swap_input_amount=int(path["swap"]["input_amount"] * 10 ** path["input_token"]["metadata"]["decimals"]),
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
