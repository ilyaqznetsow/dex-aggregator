#!/usr/bin/env python

import time
from pathlib import Path
from typing import List

from httpx import AsyncClient, Timeout, Limits
from pydantic import TypeAdapter

from exporters.csv import CsvExporter
from common.models import BlockchainToken, DexRouteProvider, BuildRouteRequest, \
    EmulationSender, DexBenchmarkResult, ProviderException
from loguru import logger

from exporters.jinja_template import Jinja2Exporter
from providers.dedust_router_v2 import DedustRouterV2Provider
from providers.moki_ag import MokiAgProvider
from providers.rainbow_ag import RainbowAgProvider
from providers.swap_coffee import SwapCoffeeRouteProvider
from common.util import get_jetton_wallet_address, get_latest_mc_seqno
from providers.titan_tg import TitanTgProvider
from providers.xdelta import XdeltaRouteProvider
from optparse import OptionParser



async def build_route(client: AsyncClient, output_token: BlockchainToken, provider: DexRouteProvider,
                      sender: EmulationSender,
                      max_splits: int, max_length: int, input_amount: int) -> DexBenchmarkResult:

    input_token = BlockchainToken(address="native", symbol="TON", decimals=9)

    request = BuildRouteRequest(input_token=input_token,
                                output_token=output_token,
                                input_amount=input_amount * 10 ** input_token.decimals,
                                max_splits=max_splits,
                                max_length=max_length)

    now = time.time()

    try:
        route = await provider.build_route(client, sender, request)
        elapsed = time.time() - now

        logger.info(f"Built route for {provider.get_name()} in {elapsed:.2f} seconds")

        route.provider = provider.get_name()

        now = time.time()
        emulation_result = await provider.emulate_route(client, sender, route)
        elapsed_emulation = time.time() - now

        logger.info(f"Emulated route for {provider.get_name()} in {elapsed_emulation:.2f} seconds (gas used: {emulation_result.gas_used})")

        output = emulation_result.output_amount / 10 ** route.output_token.decimals
        input_amount = (route.input_amount + emulation_result.gas_used) / 1e9
        ratio = output / input_amount

    except Exception as e:
        logger.error(f"Error building route for {provider.get_name()}: {e.__class__.__name__} {str(e)}")
        raise ProviderException(provider, request, str(e))

    return DexBenchmarkResult(
        route=route,
        elapsed=elapsed,
        provider=provider,
        ratio=ratio,
        emulation_result=emulation_result
    )


async def run_benchmark():
    parser = OptionParser()

    parser.add_option("-i", "--in", dest="input_amount", help="Input amounts separated by comma", type="string", default="1000")
    parser.add_option("-p", "--pairs", dest="pairs", help="Pairs file path", type="string", default="jettons.json")
    parser.add_option("-s", "--sender", dest="sender", help="Sender wallet address", type="string", default="UQCJoBrHlYgNgKMAMT5howVjiOXWbU7FewzGSzzN54rvxZIF")
    parser.add_option("--slippage", dest="slippage", help="Slippage", type="float", default=1)
    parser.add_option("--dir", dest="dir", help="Results directory", type="string", default="results")
    parser.add_option("--max-splits", dest="max_splits", help="Max splits", type="int", default=4)
    parser.add_option("--size", dest="size", help="Size", type="int", default=100)
    parser.add_option("--max-length", dest="max_length", help="Max length", type="int", default=5)
    parser.add_option("-e", "--exclude", dest="exclude", help="Exclude providers", type="string", default="")


    (options, args) = parser.parse_args()
    size = options.size

    input_amounts = [int(amount) for amount in options.input_amount.split(",")]
    adapter = TypeAdapter(List[BlockchainToken])

    with open(options.pairs, "r") as f:
        jettons = adapter.validate_json(f.read())

    jettons = jettons[:size]

    timeout = Timeout(6)
    limits = Limits(max_connections=100, max_keepalive_connections=100)
    client = AsyncClient(timeout=timeout, limits=limits)
    slippage = options.slippage
    wallet = options.sender
    results_dir = options.dir
    max_splits = options.max_splits
    max_length = options.max_length

    Path(results_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting benchmark...")

    swap_coffee = SwapCoffeeRouteProvider()
    providers = [
        swap_coffee,
        RainbowAgProvider(),
        TitanTgProvider(),
        XdeltaRouteProvider(),
        # Note: swap.coffee is used as a transaction builder, because providers below do not provide a REST API for this
        # Transaction building is required for emulation
        # To disable this functionality, set builder=None in the provider constructor
        # DedustProvider(swap_coffee),
        # StonfiProvider(swap_coffee),
        # MokiAgProvider(swap_coffee),
        DedustRouterV2Provider()
    ]

    if options.exclude:
        providers = [provider for provider in providers if provider.get_name() not in options.exclude.split(",")]


    exporters = [
        CsvExporter(results_dir),
        Jinja2Exporter(
            template_name="template.jinja2",
            output_file=f"{results_dir}/summary.md",
            directory="exporters"
        )
    ]

    results: dict[int, list[DexBenchmarkResult]] = {}

    for input_amount in input_amounts:
        pair_results = []

        for jetton in jettons:
            tasks = []

            logger.info(f"[{input_amount} TON -> {jetton.symbol}] Building routes...")

            block_seqno = await get_latest_mc_seqno(client)

            sender = EmulationSender(
                wallet_address=wallet,
                jetton_wallet_address=await get_jetton_wallet_address(client, wallet, jetton.address),
                slippage=slippage,
                mc_block_seqno=block_seqno
            )


            for provider in providers:
                tasks.append(build_route(
                    client=client,
                    output_token=jetton,
                    provider=provider,
                    sender=sender,
                    max_splits=max_splits,
                    max_length=max_length,
                    input_amount=input_amount
                ))

                if isinstance(provider, SwapCoffeeRouteProvider):
                    tasks.append(build_route(
                        client=client,
                        output_token=jetton,
                        provider=provider,
                        sender=sender,
                        max_splits=20,
                        max_length=max_length,
                        input_amount=input_amount
                    ))


            res = await asyncio.gather(*tasks, return_exceptions=True)

            logger.info(f"[{input_amount} TON -> {jetton.symbol}] ")

            pair_results.extend(res)

            logger.info(f"[{input_amount} TON -> {jetton.symbol}] Sleeping for 2 seconds...")
            await asyncio.sleep(2)

        results[input_amount] = pair_results

        logger.info(f"Finished benchmark for {input_amount} input amount")


    for exporter in exporters:
        exporter.export(results)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_benchmark())
