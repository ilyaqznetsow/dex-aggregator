import asyncio
import time
from abc import abstractmethod, ABC

import httpx
from pydantic import BaseModel
from loguru import logger


class BlockchainToken(BaseModel):
    address: str
    symbol: str
    decimals: int


class DexRoute(BaseModel):
    input_token: BlockchainToken
    output_token: BlockchainToken
    provider: str
    input_amount: int
    output_amount: int
    request: "BuildRouteRequest"
    extra: dict = None



class BuildRouteRequest(BaseModel):
    input_token: BlockchainToken
    output_token: BlockchainToken
    input_amount: int
    max_splits: int
    max_length: int


class EmulatedResult(BaseModel):
    output_token: BlockchainToken
    output_amount: int
    gas_used: int
    splits: int


class EmulationSender(BaseModel):
    wallet_address: str
    jetton_wallet_address: str
    slippage: float = 0.05
    mc_block_seqno: int


class DexBenchmarkResult(BaseModel):
    route: DexRoute
    elapsed: float
    ratio: float = 0
    provider: "DexRouteProvider"
    emulation_result: EmulatedResult | None = None

    class Config:
        arbitrary_types_allowed = True

class DexRouteProvider(ABC):

    def __init__(self):
        self.leaky_bucket = asyncio.Queue(1)
        self.last_request_time = 0

    async def acquire(self, permits = 1):
        await self.leaky_bucket.put(permits)

        current_time = time.time()
        elapsed_time = current_time - self.last_request_time
        if elapsed_time < 1:
            logger.info(f"Sleeping for {1 - elapsed_time} seconds for {self.get_name()}")
            await asyncio.sleep(1 - elapsed_time)

        self.last_request_time = time.time()
        self.leaky_bucket.get_nowait()


    @abstractmethod
    async def build_route(self, client: httpx.AsyncClient,
                          sender: EmulationSender,
                          request: BuildRouteRequest) -> DexRoute:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def is_dex(self):
        pass

    async def emulate_route(self, client: httpx.AsyncClient, sender: EmulationSender,
                            route: DexRoute) -> EmulatedResult:
        return EmulatedResult(output_token=route.output_token, output_amount=0, gas_used=0, splits=0)


class DexBenchmarkExporter(ABC):

    @abstractmethod
    def export(self, results: dict[int, list[DexBenchmarkResult]]):
        pass


class ProviderException(Exception):
    def __init__(self, provider: DexRouteProvider, request: BuildRouteRequest, message: str):
        self.provider = provider
        self.message = message
        self.request = request

        super().__init__(message)
