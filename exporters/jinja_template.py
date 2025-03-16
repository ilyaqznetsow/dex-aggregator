from typing import Tuple, Dict, List

from jinja2 import FileSystemLoader, Environment
from pydantic import BaseModel

from common.models import DexBenchmarkExporter, DexBenchmarkResult


def sort_by_symbols(results: List[DexBenchmarkResult]) -> Dict[str, List[DexBenchmarkResult]]:
    by_output_symbol = {}

    for result in results:
        if not isinstance(result, DexBenchmarkResult):
            continue

        output_symbol = result.route.output_token.symbol
        if output_symbol not in by_output_symbol:
            by_output_symbol[output_symbol] = []
        by_output_symbol[output_symbol].append(result)

    return by_output_symbol


def by_sorted_field(
        results: List[DexBenchmarkResult],
        provider_type: type,
        extractor,
        reverse: bool = True
) -> Tuple[int, int, set]:
    hit_count = 0
    by_output_symbol = sort_by_symbols(results)
    tokens = []

    for symbol, results in by_output_symbol.items():
        results = sorted(results, key=extractor, reverse=reverse)
        best_result = extractor(results[0])

        provider_found = False
        for result in results:
            if type(result.provider) == provider_type:
                provider_result = extractor(result)
                if reverse:
                    diff = 1 - provider_result / best_result if best_result != 0 else float('inf')
                else:
                    diff = 1 - best_result / provider_result if provider_result != 0 else float('inf')

                if diff < 1e-4:
                    provider_found = True
                    break

        if provider_found:
            hit_count += 1
            tokens.append(symbol)

    return len(by_output_symbol), hit_count, set(tokens)


def most_profitable_all(
        results: List[DexBenchmarkResult],
        provider_type: type,
) -> Tuple[int, int, set]:
    def extractor(r: DexBenchmarkResult):
        return r.ratio

    return by_sorted_field(results, provider_type, extractor=extractor, reverse=True)


def lowest_route_build_time_filtered(
        results: List[DexBenchmarkResult],
        provider_type: type,
        dex_flag: bool
) -> Tuple[int, int, set]:
    def extractor(x):
        return x.elapsed if dex_flag == x.provider.is_dex() else float('inf')

    return by_sorted_field(results, provider_type, extractor=extractor, reverse=False)


class ProviderStats(BaseModel):
    profitable_total: int
    profitable_hit: int

    fast_total_aggregators: int
    fast_hit_aggregators: int

    provider_name: str
    avg_elapsed: float

    tokens: set[str] = []


class StatsGroup(BaseModel):
    input_amount: float
    stats: List[ProviderStats]


def measure_provider_stats(
        results: List[DexBenchmarkResult],
        provider_type: type,
        provider_name: str
) -> ProviderStats:
    profitable_total, profitable_hit, tokens = most_profitable_all(results, provider_type)
    fast_total_agg, fast_hit_agg, _ = lowest_route_build_time_filtered(results, provider_type, dex_flag=False)
    provider_results = [r for r in results if isinstance(r, DexBenchmarkResult) and type(r.provider) == provider_type and r.elapsed > 0]
    avg_elapsed = sum(r.elapsed for r in provider_results) / len(provider_results)

    return ProviderStats(
        profitable_total=profitable_total,
        profitable_hit=profitable_hit,
        fast_total_aggregators=fast_total_agg,
        fast_hit_aggregators=fast_hit_agg,
        provider_name=provider_name,
        avg_elapsed=avg_elapsed,
        tokens=tokens
    )


class Jinja2Exporter(DexBenchmarkExporter):
    def __init__(self, template_name: str, output_file: str, directory: str = 'exporters'):
        self.template_name = template_name
        self.output_file = output_file
        self.env = Environment(loader=FileSystemLoader(directory))

    def export(self, results: dict[int, list[DexBenchmarkResult]]):
        template = self.env.get_template(self.template_name)

        providers = {r.provider for r in results.values() for r in r if isinstance(r, DexBenchmarkResult)}

        groups: List[StatsGroup] = []

        for input_amount, results in results.items():
            provider_stats = []
            for provider in providers:
                provider_stats.append(measure_provider_stats(results, type(provider), provider.get_name()))

            groups.append(StatsGroup(input_amount=input_amount, stats=provider_stats))

        with open(self.output_file, 'w') as file:
            file.write(template.render(groups=groups))
