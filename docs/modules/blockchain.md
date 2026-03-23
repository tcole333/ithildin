# Blockchain & Crypto

Tools for Ethereum and Solana blockchain analysis, token holder tracing, transfer event tracking, and on-chain analytics via Dune SQL queries.

**When to read this module:** When investigating crypto-related financial flows -- stablecoin issuers (USD1/WLFI), meme coin holder distributions (TRUMP/MELANIA), or tracing wallet-level transaction patterns.

## Tool Inventory

| Tool | Chain | Auth | Rate Limit | Primary Use |
|------|-------|------|------------|-------------|
| `query_etherscan.py` | Ethereum (ERC-20) | `ETHERSCAN_API_KEY` | 5 req/sec (free tier) | Token holders, transfers, balances, contract metadata |
| `query_solscan.py` | Solana (SPL) | `SOLSCAN_API_KEY` | ~1 req/sec (enforced) | TRUMP/MELANIA coin holders, transfer flows |
| `query_dune.py` | Multi-chain (SQL) | `DUNE_API_KEY` | 10 req/min, 2500 credits/mo | Community analytics dashboards, custom queries |

## Subcommands & Examples

### query_etherscan.py -- Ethereum Blockchain

```bash
# Token holder analysis
uv run python tools/query_etherscan.py token-holders 0xCONTRACT
uv run python tools/query_etherscan.py token-holders 0xCONTRACT --limit 100 --decimals 18

# Token transfer events
uv run python tools/query_etherscan.py token-transfers 0xCONTRACT
uv run python tools/query_etherscan.py token-transfers 0xCONTRACT --address 0xHOLDER
uv run python tools/query_etherscan.py token-transfers 0xCONTRACT --start-block 19000000

# Token metadata
uv run python tools/query_etherscan.py token-info 0xCONTRACT

# Wallet analysis
uv run python tools/query_etherscan.py balance 0xADDRESS
uv run python tools/query_etherscan.py token-balance 0xCONTRACT 0xADDRESS --decimals 18

# Transaction and contract inspection
uv run python tools/query_etherscan.py tx 0xHASH
uv run python tools/query_etherscan.py address 0xADDRESS --limit 50
uv run python tools/query_etherscan.py contract 0xADDRESS
```

| Subcommand | Description |
|------------|-------------|
| `token-holders` | Top holders for an ERC-20 contract address |
| `token-transfers` | Transfer events, filterable by address and block range |
| `token-info` | Token metadata: name, symbol, decimals, supply, holders |
| `balance` | ETH balance for an address (in Wei and ETH) |
| `token-balance` | ERC-20 token balance for a specific holder |
| `tx` | Transaction details by hash |
| `address` | Recent transactions for an address |
| `contract` | Contract ABI and source code (if verified) |

**Auth:** Requires `ETHERSCAN_API_KEY` in `.env`. Free tier: 5 calls/sec, 100K calls/day. Tool self-limits to 1 req/sec with exponential backoff on 429.

### query_solscan.py -- Solana Blockchain

Built-in token aliases: `TRUMP` -> `6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN`, `MELANIA` -> `FUAfBo2jgks6gB4Z4LfZkqSZgzNucisEHqnNebaRxM1P`.

```bash
# Token metadata
uv run python tools/query_solscan.py token-info TRUMP
uv run python tools/query_solscan.py token-info 6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN

# Token holder analysis
uv run python tools/query_solscan.py token-holders TRUMP --limit 40
uv run python tools/query_solscan.py token-holders MELANIA --min-amount 1000000
uv run python tools/query_solscan.py token-holders TRUMP --max-amount 500000

# Transfer events
uv run python tools/query_solscan.py token-transfers TRUMP --limit 20
uv run python tools/query_solscan.py token-transfers TRUMP --from-addr <address>
uv run python tools/query_solscan.py token-transfers TRUMP --to-addr <address>
uv run python tools/query_solscan.py token-transfers TRUMP --exclude-zero

# Wallet and transaction
uv run python tools/query_solscan.py account <wallet_address>
uv run python tools/query_solscan.py account <wallet_address> --show-zero
uv run python tools/query_solscan.py tx <signature>

# Token discovery
uv run python tools/query_solscan.py token-list --sort market_cap --limit 20
```

| Subcommand | Description |
|------------|-------------|
| `token-info` | Token metadata: name, supply, holders, price, mint/freeze authority |
| `token-holders` | Top holders with amounts, percentages, and USD values |
| `token-transfers` | Transfer events filterable by from/to address |
| `account` | Wallet details + SPL token holdings |
| `tx` | Transaction details by signature |
| `token-list` | Browse tokens sorted by market cap |

**Auth:** Requires `SOLSCAN_API_KEY` in `.env`. Get key at https://solscan.io -> Account -> API Management. Auth header uses `token: <key>` (not Bearer). Tool enforces 1 req/sec with exponential backoff on 429.

### query_dune.py -- Dune Analytics

```bash
# Get cached results from a community query
uv run python tools/query_dune.py results 4166026
uv run python tools/query_dune.py results 4166026 --limit 50
uv run python tools/query_dune.py results wlfi-holders               # Known alias

# Execute a query (costs credits)
uv run python tools/query_dune.py execute 4166026
uv run python tools/query_dune.py execute 4166026 --params "wallet=0xabc..."
uv run python tools/query_dune.py execute 4166026 --no-wait          # Don't poll for results
uv run python tools/query_dune.py execute 4166026 --performance large

# Execution management
uv run python tools/query_dune.py status 01HKZJ2683PHF9Q9PHHQ8FW4Q1
uv run python tools/query_dune.py cancel 01HKZJ2683PHF9Q9PHHQ8FW4Q1
```

| Subcommand | Description |
|------------|-------------|
| `results` | Get latest cached results from a saved query (costs per-datapoint credits) |
| `execute` | Run a query fresh, optionally with parameters; polls for completion |
| `status` | Check execution state by execution ID |
| `cancel` | Cancel a running execution |

Known query aliases:
- `wlfi-holders` -> query `4166026` (World Liberty Financial token holders)

**Auth:** Requires `DUNE_API_KEY` in `.env`. Free tier: 2,500 credits/month, 10 req/min. Each `results` call costs 1 credit per datapoint returned. Get key at https://dune.com/settings/api

## Auth Requirements Summary

| Tool | Env Variable | Free Tier | Cost Model |
|------|-------------|-----------|------------|
| `query_etherscan.py` | `ETHERSCAN_API_KEY` | 5 calls/sec, 100K/day | Free |
| `query_solscan.py` | `SOLSCAN_API_KEY` | Limited daily quota | Free account, paid upgrades |
| `query_dune.py` | `DUNE_API_KEY` | 2,500 credits/month | 1 credit per datapoint |

## Known Quirks

- **Etherscan v2 API format.** Uses `chainid=1` (Ethereum mainnet). Error responses return `status: "0"` with `message: "NOTOK"`, but some "NOTOK" results are just empty results (e.g., "No transactions found"), not real errors. The tool handles this.
- **Etherscan token values are raw integers.** ERC-20 tokens store values multiplied by `10^decimals`. Pass `--decimals` to get human-readable amounts. Default is 18 (standard ERC-20).
- **Solscan auth header is `token:`, not `Bearer`.** The tool handles this, but if making raw API calls, use the `token` header.
- **Solscan page_size max is 40 for holders, 100 for transfers.** The tool caps these automatically.
- **Dune `results` vs `execute`.** `results` fetches cached data (cheap, fast). `execute` runs the query fresh (more credits, can take minutes). Prefer `results` unless the query is stale.
- **Dune query IDs change.** Community queries can be forked or deleted. Verify with `results <ID>` before building workflows around them.
- **Dune execution polling.** `execute` polls every 5s for up to 5 minutes. Use `--no-wait` to get the execution_id and check later with `status`.

## Skills That Use These Tools

These are niche tools used only for crypto-related investigations:
- No dedicated skill; invoked manually during `/pursue-lead` or `/deep-investigate` when leads involve blockchain assets
- Relevant investigations: USD1 stablecoin (WLFI/World Liberty Financial), TRUMP/MELANIA meme coins (CIC Digital LLC)
