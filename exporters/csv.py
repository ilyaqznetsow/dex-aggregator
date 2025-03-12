import csv
from pathlib import Path

from common.models import ProviderException, DexBenchmarkResult, DexBenchmarkExporter

HEADER = [
    'provider',
    'input_token_symbol',
    'output_token_symbol',
    'input_amount',
    "ratio",
    'emulated_output_amount',
    'output_amount',
    'gas_used',
    'elapsed',
    'max_splits',
    'max_length',
    'splits',
    'error_message'
]


def _build_row(benchmark_result: DexBenchmarkResult) -> list:
    if isinstance(benchmark_result, ProviderException):
        provider_name = benchmark_result.provider.get_name()
        request = benchmark_result.request
        output_amount = emulated_output_amount = gas_used = elapsed = splits = 0
        error_message = benchmark_result.message
        ratio = 0
    else:
        provider_name = benchmark_result.route.provider
        request = benchmark_result.route.request
        output_amount = benchmark_result.route.output_amount
        elapsed = benchmark_result.elapsed
        emulated_output_amount = benchmark_result.emulation_result.output_amount if benchmark_result.emulation_result else 0
        gas_used = benchmark_result.emulation_result.gas_used if benchmark_result.emulation_result else 0
        splits = benchmark_result.emulation_result.splits if benchmark_result.emulation_result else 0
        ratio = benchmark_result.ratio
        error_message = ""

    return [
        provider_name,
        request.input_token.symbol,
        request.output_token.symbol,
        request.input_amount / 10 ** request.input_token.decimals,
        ratio,
        emulated_output_amount / 10 ** request.output_token.decimals,
        output_amount / 10 ** request.output_token.decimals,
        float(gas_used / 1e9),
        elapsed,
        request.max_splits,
        request.max_length,
        splits,
        error_message,
    ]


class CsvExporter(DexBenchmarkExporter):

    def __init__(self, directory: str = "results"):
        self.directory = directory

    def export(self, results: dict[int, list[DexBenchmarkResult]]):
        # ensure the directory exists
        Path(self.directory).mkdir(parents=True, exist_ok=True)

        for input_amount, results in results.items():
            with open(f"{self.directory}/{input_amount}.csv", 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(HEADER)

                for result in results:
                    row = _build_row(result)

                    writer.writerow(row)
