# Polymarket Documentation Index

> Source: https://docs.polymarket.com/llms.txt  
> Use this index to discover all available documentation pages.

---

## Quickstart (First Order & Data)

- [Placing Your First Order](https://docs.polymarket.com/quickstart/first-order.md) – Set up authentication and submit your first trade
- [Fetching Market Data](https://docs.polymarket.com/quickstart/fetching-data.md) – Fetch Polymarket data in minutes with no authentication required
- [Developer Quickstart](https://docs.polymarket.com/quickstart/overview.md) – Get started building with Polymarket APIs
- [API Rate Limits](https://docs.polymarket.com/quickstart/introduction/rate-limits.md)
- [Endpoints](https://docs.polymarket.com/quickstart/reference/endpoints.md) – All Polymarket API URLs and base endpoints
- [Glossary](https://docs.polymarket.com/quickstart/reference/glossary.md) – Key terms and concepts for Polymarket developers
- [WSS Quickstart](https://docs.polymarket.com/quickstart/websocket/WSS-Quickstart.md)

---

## CLOB (Central Limit Order Book)

### Authentication & Overview

- [Authentication](https://docs.polymarket.com/developers/CLOB/authentication.md) – Understanding authentication using Polymarket's CLOB
- [CLOB Introduction](https://docs.polymarket.com/developers/CLOB/introduction.md)
- [Geographic Restrictions](https://docs.polymarket.com/developers/CLOB/geoblock.md) – Check before placing orders
- [Quickstart](https://docs.polymarket.com/developers/CLOB/quickstart.md) – Initialize the CLOB and place your first order

### Client Methods (by auth level)

- [Methods Overview](https://docs.polymarket.com/developers/CLOB/clients/methods-overview.md) – What credentials you need for each method
- [Public Methods](https://docs.polymarket.com/developers/CLOB/clients/methods-public.md) – No signer/credentials (market data, prices, order books)
- [L1 Methods](https://docs.polymarket.com/developers/CLOB/clients/methods-l1.md) – Wallet signer only (initial setup)
- [L2 Methods](https://docs.polymarket.com/developers/CLOB/clients/methods-l2.md) – User API credentials (placing trades, managing positions)
- [Builder Methods](https://docs.polymarket.com/developers/CLOB/clients/methods-builder.md) – Builder API credentials (order attribution)

### Orders

- [Orders Overview](https://docs.polymarket.com/developers/CLOB/orders/orders.md)
- [Place Single Order](https://docs.polymarket.com/developers/CLOB/orders/create-order.md)
- [Place Multiple Orders (Batching)](https://docs.polymarket.com/developers/CLOB/orders/create-order-batch.md)
- [Get Active Orders](https://docs.polymarket.com/developers/CLOB/orders/get-active-order.md)
- [Get Order](https://docs.polymarket.com/developers/CLOB/orders/get-order.md)
- [Cancel Orders](https://docs.polymarket.com/developers/CLOB/orders/cancel-orders.md)
- [Onchain Order Info](https://docs.polymarket.com/developers/CLOB/orders/onchain-order-info.md)
- [Check Order Reward Scoring](https://docs.polymarket.com/developers/CLOB/orders/check-scoring.md)

### Trades & Timeseries

- [Trades Overview](https://docs.polymarket.com/developers/CLOB/trades/trades-overview.md)
- [Get Trades](https://docs.polymarket.com/developers/CLOB/trades/trades.md)
- [Historical Timeseries Data](https://docs.polymarket.com/developers/CLOB/timeseries.md)

### WebSocket

- [WSS Overview](https://docs.polymarket.com/developers/CLOB/websocket/wss-overview.md)
- [WSS Authentication](https://docs.polymarket.com/developers/CLOB/websocket/wss-auth.md)
- [Market Channel](https://docs.polymarket.com/developers/CLOB/websocket/market-channel.md)
- [User Channel](https://docs.polymarket.com/developers/CLOB/websocket/user-channel.md)

---

## Gamma / Markets API

- [How to Fetch Markets](https://docs.polymarket.com/developers/gamma-markets-api/fetch-markets-guide.md)
- [Gamma Structure](https://docs.polymarket.com/developers/gamma-markets-api/gamma-structure.md)
- [Get market by id](https://docs.polymarket.com/api-reference/markets/get-market-by-id.md)
- [Get market by slug](https://docs.polymarket.com/api-reference/markets/get-market-by-slug.md)
- [List markets](https://docs.polymarket.com/api-reference/markets/list-markets.md)
- [Get market tags by id](https://docs.polymarket.com/api-reference/markets/get-market-tags-by-id.md)

---

## API Reference (Data / Bridge / Builders / etc.)

### Bridge

- Create deposit addresses, Create withdrawal addresses, Get a quote, Get supported assets, Get transaction status

### Builders

- Get aggregated builder leaderboard, Get daily builder volume time-series
- [Builder Program Introduction](https://docs.polymarket.com/developers/builders/builder-intro.md)
- [Order Attribution](https://docs.polymarket.com/developers/builders/order-attribution.md)
- [Builder Profile & Keys](https://docs.polymarket.com/developers/builders/builder-profile.md)
- [Relayer Client](https://docs.polymarket.com/developers/builders/relayer-client.md)

### Core (positions, trades, activity)

- Get closed positions for a user, Get current positions for a user, Get top holders, Get total value of positions
- Get trader leaderboard rankings, Get trades for a user or markets, Get user activity

### Events

- Get event by id, Get event by slug, Get event tags, List events

### Orderbook & Pricing

- Get order book summary, Get multiple order books summaries
- Get market price, Get midpoint price, Get multiple market prices, Get price history for a traded token

### Other

- Comments, Profiles, Search, Series, Tags, Sports, Spreads, Misc (accounting snapshot, live volume, open interest, etc.)
- Data API Health check, Gamma API Health check

---

## CTF (Conditional Token Framework)

- [Overview](https://docs.polymarket.com/developers/CTF/overview.md)
- [Splitting USDC](https://docs.polymarket.com/developers/CTF/split.md)
- [Merging Tokens](https://docs.polymarket.com/developers/CTF/merge.md)
- [Redeeming Tokens](https://docs.polymarket.com/developers/CTF/redeem.md)
- [Deployment and Additional Information](https://docs.polymarket.com/developers/CTF/deployment-resources.md)

---

## Market Makers

- [Market Maker Introduction](https://docs.polymarket.com/developers/market-makers/introduction.md)
- [Setup](https://docs.polymarket.com/developers/market-makers/setup.md)
- [Trading](https://docs.polymarket.com/developers/market-makers/trading.md)
- [Data Feeds](https://docs.polymarket.com/developers/market-makers/data-feeds.md)
- [Inventory Management](https://docs.polymarket.com/developers/market-makers/inventory.md)
- [Liquidity Rewards](https://docs.polymarket.com/developers/market-makers/liquidity-rewards.md)
- [Maker Rebates Program](https://docs.polymarket.com/developers/market-makers/maker-rebates-program.md)

---

## Other Developer Topics

- [Bridge Overview](https://docs.polymarket.com/developers/misc-endpoints/bridge-overview.md)
- [Neg-Risk Overview](https://docs.polymarket.com/developers/neg-risk/overview.md)
- [Resolution (UMA)](https://docs.polymarket.com/developers/resolution/UMA.md)
- [Proxy Wallet](https://docs.polymarket.com/developers/proxy-wallet.md)
- RTDS (Real Time Data Socket): Comments, Crypto Prices, Overview
- Sports WebSocket: Overview, Quickstart, Message Format
- Subgraph overview

---

## Polymarket Learn (FAQ, Deposits, Markets, Trading)

- What is Polymarket?, How to Sign-Up, How to Deposit, Making Your First Trade
- Deposits: Coinbase, MoonPay, supported tokens, USDC on Eth, how to withdraw, large cross-chain
- Markets: dispute, clarified, created, resolved
- Trading: fees, holding rewards, how prices are calculated, limit orders, liquidity rewards, maker rebates, market orders, order book, trading limits
- FAQ: API, embeds, geoblocking, export key, money safe, house, polling, recover deposit, sell early, support, token, prediction markets, why crypto

---

## Optional Links

- [Polymarket](https://polymarket.com)
- [Discord Community](https://discord.gg/polymarket)
- [Twitter](https://x.com/polymarket)
- [Polymarket Changelog](https://docs.polymarket.com/changelog/changelog.md)
