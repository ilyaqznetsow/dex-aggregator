import random
import string
from typing import Callable

from httpx import AsyncClient
from pydantic import BaseModel
from pytoniq import Contract
from pytoniq_core import Address, Cell

from emulator.models import EmulatorResult, TransactionModel, InternalMsgBodyExcess, \
    InternalMsgBodyJettonInternalTransfer

BASE_URL = f"https://tvm.swap.coffee/api"
JettonInternalTransfer = InternalMsgBodyJettonInternalTransfer
Excesses = InternalMsgBodyExcess


class EmulationRequest(BaseModel):
    boc: str
    format: str = "base64"


class UnsignedMessage(BaseModel):
    src: str
    dest: str
    body: str
    value: int
    swap_input_amount: int
    jetton_wallet: str


class EmulatedTransaction(BaseModel):
    message: UnsignedMessage
    emulation_result: EmulatorResult


async def emulate_to_trace(client: AsyncClient, request: EmulationRequest, session_id: str) -> EmulatorResult:
    response = await client.post(f"{BASE_URL}/v1/emulate/trace", json=request.model_dump(),
                                 params={"session_id": session_id})

    response.raise_for_status()

    return EmulatorResult.model_validate(response.json())


async def create_session(client: AsyncClient, mc_block_seqno: int) -> str:
    response = await client.post(f"{BASE_URL}/v1/emulate/session", json={"block_seqno": mc_block_seqno})
    response.raise_for_status()

    return response.json()["session_id"]


async def emulate_internal_messages(provider_name: str, client: AsyncClient, messages: list[UnsignedMessage], session_id: str) -> list[
    EmulatedTransaction]:
    results = []

    for message in messages:
        msg = Contract.create_internal_msg(
            src=Address(message.src),
            dest=Address(message.dest),
            value=message.value,
            body=Cell.one_from_boc(message.body)
        )

        msg_cell = msg.serialize().to_boc().hex()

        request = EmulationRequest(boc=msg_cell, format="hex")

        result = await emulate_to_trace(client, request, session_id)

        results.append(EmulatedTransaction(message=message, emulation_result=result))

    return results

def traverse(
        model: TransactionModel,
        func: Callable[[TransactionModel], None],
):
    func(model)
    for child in model.children:
        traverse(child, func)

def find_messages_by_body(model: TransactionModel, body_type: type) -> list[TransactionModel]:
    result = []
    if isinstance(model.in_msg.decoded_body, body_type):
        result.append(model.in_msg)
    for child in model.children:
        result.extend(find_messages_by_body(child, body_type))

    return result


async def get_total_swap_output(results: list[EmulatedTransaction]):
    total_output = 0
    total_excesses = 0
    total_gas = 0

    payout_op_codes = [
        "0x474f86cf" # dedust payout
        "0x01f3835d" # pton transfer
    ]

    for result in results:
        sender_raw = Address(result.message.src).to_str(is_user_friendly=False)
        jetton_wallet_raw = Address(result.message.jetton_wallet).to_str(is_user_friendly=False)
        emulation_result = result.emulation_result.result

        internal_transfers = find_messages_by_body(emulation_result, JettonInternalTransfer)

        total_gas += emulation_result.in_msg.value - result.message.swap_input_amount

        for internal_transfer in internal_transfers:
            if internal_transfer.dest == jetton_wallet_raw:

                total_output += internal_transfer.decoded_body.amount

        def collect_value(model: TransactionModel):
            nonlocal total_excesses

            # FIXME: stonfi v2 routers can refund tons without non-zero exit codes..

            if model.in_msg.dest == sender_raw and model.compute_phase.exit_code == 0 and model.in_msg.decoded_op not in payout_op_codes:
                total_excesses += model.in_msg.value

        traverse(emulation_result, collect_value)


    gas_used = total_gas - total_excesses

    return total_output, max(0, gas_used)
#
# async def test():
#     client = AsyncClient()
#
#     print(create_session(client, 45268044))
#
#
# if __name__ == "__main__":
#     import asyncio
#
#     asyncio.run(test())
