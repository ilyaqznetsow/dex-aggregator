# Aggregators Benchmark ![Docker Pulls](https://img.shields.io/docker/pulls/etobaza/dex-aggregator) 

## Introduction

This project is a benchmark/comparison for aggregators that build routes for swapping tokens on the TON blockchain.
The following metrics are measured:

- Emulated route output amount
- Route building time
- Route gas usage
- Ratio of route input to emulated output

Ratio of route input to output is key metric for measuring the efficiency of a route provider. It calculates as follows:

```python
output = emulated_result.output_amount
input_amount = route.input_amount + emulated_result.gas_used
ratio = output / input_amount
```

## Usage

```bash
docker run --rm -v "$(pwd)/results:/code/results" etobaza/dex-aggregator python run.py --in 100,1000
```

```bash
Usage: run.py [options]

Options:
  -h, --help            show this help message and exit
  -i INPUT_AMOUNT, --in=INPUT_AMOUNT
                        Input amounts separated by comma
  -p PAIRS, --pairs=PAIRS
                        Pairs file path
  -s SENDER, --sender=SENDER
                        Sender wallet address
  --slippage=SLIPPAGE   Slippage used in emulation
  --dir=DIR             Results directory
  --max-splits=MAX_SPLITS
                        Route max splits
  --size=SIZE           Specifiy size of input pairs
  --max-length=MAX_LENGTH
                        Route max length
  -e EXCLUDE, --exclude=EXCLUDE
                        Exclude some providers by name
```

## Research Methodology

For testing, we take the top 100 tokens of the TON ecosystem by TVL.
Then, we
ask [swap.coffee](https://swap.coffee), [rainbow.ag](https://rainbow.ag), [titan.tg](https://titan.tg), [moki.ag](https://moki.ag), [xdelta.fi](https://xdelta.fi)
to build the most profitable route for each token. We immediately emulate the built route and divide the obtained
emulate_output_amount by the sum of input_amount + gas used. The service with the best ratio wins.

We also measure the time spent on building the route - the fastest builder wins.
If a route takes more than 6 seconds to build, its results are discarded since the blockchain state could have changed
significantly.

A two-second timeout is taken between route constructions to avoid affecting rate limits.

### Methodology Proof

When building a route, it's crucial to emulate the transaction and consider not just the emulated output amount but also
the gas costs, as a route might appear more profitable, but all profits could be lost in execution costs.

⚠️ This methodology isn't perfect since there's no way to specify which block state the routes are built on, and there's
no ability to emulate the route on that specific block. However, with a large sample size, the research can be
considered reliable.

## Supported Providers

| Feature                    | swap.coffee | rainbow.ag | titan.tg | moki.ag | xdelta.fi |
|----------------------------|-------------|------------|----------|---------|-----------|
| Trading Competitions       | ✅           | ✅          | ✅        | ✅       | ❌         |
| Partner System             | ✅           | ✅          | ✅        | ✅       | ❌         |
| SDK                        | ✅           | ✅          | ✅        | ❌       | ❌         |
| Documentation              | ✅           | ✅          | ✅        | ❌       | ❌         |
| Airdrop Center             | ✅           | ✅          | ❌        | ❌       | ❌         |
| Referral System            | ✅           | ✅          | ❌        | ❌       | ❌         |
| Cross-DEX Support          | ✅           | ✅          | ❌        | ❌       | ✅         |
| LST Support                | ✅           | ❌          | ❌        | ❌       | ✅         |
| Charts                     | ✅           | ❌          | ❌        | ✅       | ✅         |
| Trading Profit Display     | ✅           | ❌          | ❌        | ❌       | ❌         |
| Limit Orders               | ✅           | ❌          | ❌        | ❌       | ❌         |
| DCA                        | ✅           | ❌          | ❌        | ❌       | ❌         |
| Cashback                   | ✅           | ❌          | ❌        | ❌       | ❌         |
| Exact-Out Swap             | ✅           | ❌          | ❌        | ❌       | ❌         |
| Extended Documentation     | ✅           | ❌          | ❌        | ❌       | ❌         |
| Widget Kit                 | ✅           | ❌          | ❌        | ❌       | ❌         |
| Cross-device Settings Sync | ✅           | ❌          | ❌        | ❌       | ❌         |
| Maximum Intermediates      | 5           | 3          | 3        | 3       | 3         |
| Maximum Splits             | 20          | 4          | 4        | 4       | 4         |
| Supported Languages        | 7           | 1          | 5        | 2       | 1         |
| Supported Themes           | 3           | 2          | 1        | 1       | 1         |

| Performance Metrics          | swap.coffee | rainbow.ag | titan.tg | moki.ag | xdelta.fi |
|------------------------------|-------------|------------|----------|---------|-----------|
| Most Profitable Routes Built | 1792        | 0          | 1        | 1       | 199       |
| Fastest Routes Built         | 1711        | 0          | 229      | 50      | 9         |

## Caveats

For emulation, used TVM emulator swap.coffee. But you can adapt any other emulation API (
like TON Center, TON API).

moki.ag cannot provide API for building transactions, so the swap.coffee engine is used to build them, which optimizes gas
consumption for these transactions.

API of rainbow.ag and titan.tg works unstably. If you are owner of these services, you're welcome to contribute.

For testing, more than 2000 routes were built and emulated on different servers in various locations. A total of 8
hours of server time was spent.

Data presented in the report was obtained on 12.03.2023

## Docker

### Docker Hub Repository

The Docker image is available on Docker Hub at [etobaza/dex-aggregator](https://hub.docker.com/r/etobaza/dex-aggregator).

### Available Tags

- `latest`: The most recent build from the main branch
- `vX.Y.Z`: Specific version releases (e.g., `v1.0.0`)
- `vX.Y`: Major.Minor version (e.g., `v1.0`)

### Building the Docker Image Locally

```bash
docker build -t etobaza/dex-aggregator .
```

### Environment Variables

The Docker container supports the following environment variables:

- None currently defined

### Volumes

- `/code/results`: Mount this volume to persist benchmark results
