# Placing Your First Order

> Set up authentication and submit your first trade  
> Full guide: https://docs.polymarket.com/quickstart/first-order.md

This guide walks you through placing an order on Polymarket using your own wallet.

---

## Installation

```bash
pip install py-clob-client
```

---

## Step 1: Initialize Client with Private Key

```python
from py_clob_client.client import ClobClient
import os

host = "https://clob.polymarket.com"
chain_id = 137  # Polygon mainnet
private_key = os.getenv("PRIVATE_KEY")

client = ClobClient(host, key=private_key, chain_id=chain_id)
```

---

## Step 2: Derive User API Credentials

Your private key is used once to derive API credentials. These credentials authenticate all subsequent requests.

```python
# Get existing API key, or create one if none exists
user_api_creds = client.create_or_derive_api_creds()

print("API Key:", user_api_creds["apiKey"])
print("Secret:", user_api_creds["secret"])
print("Passphrase:", user_api_creds["passphrase"])
```

---

## Step 3: Configure Signature Type and Funder

Before reinitializing the client, determine your **signature type** and **funder address**:

| How do you want to trade?                                                                 | Type         | Value | Funder Address            |
| ----------------------------------------------------------------------------------------- | ------------ | ----- | ------------------------- |
| I want to use an EOA wallet. It holds USDCe and position tokens, and I'll pay my own gas. | EOA          | `0`   | Your EOA wallet address   |
| I want to trade through my Polymarket.com account (Magic Link email/Google login).        | POLY_PROXY   | `1`   | Your proxy wallet address |
| I want to trade through my Polymarket.com account (browser wallet connection).            | GNOSIS_SAFE  | `2`   | Your proxy wallet address |

**Note:** If you have a Polymarket.com account, your funds are in a proxy wallet (visible in the profile dropdown). Use type 1 or 2. Type 0 is for standalone EOA wallets only.

---

## Step 4: Reinitialize with Full Authentication

```python
# Choose based on your wallet type (see table above)
signature_type = 0  # EOA example
funder_address = "YOUR_WALLET_ADDRESS"  # For EOA, funder is your wallet

client = ClobClient(
    host,
    key=private_key,
    chain_id=chain_id,
    creds=user_api_creds,
    signature_type=signature_type,
    funder=funder_address
)
```

**Warning:** Do not use Builder API credentials in place of User API credentials! Builder credentials are for order attribution, not user authentication.

---

## Step 5: Place an Order

Get a token ID from the [Gamma API](https://docs.polymarket.com/developers/gamma-markets-api/get-markets).

```python
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

# Get market info first
market = client.get_market("TOKEN_ID")

response = client.create_and_post_order(
    OrderArgs(
        token_id="TOKEN_ID",
        price=0.50,       # Price per share ($0.50)
        size=10,          # Number of shares
        side=BUY,         # BUY or SELL
    ),
    options={
        "tick_size": market["tickSize"],
        "neg_risk": market["negRisk"],    # True for multi-outcome events
    },
    order_type=OrderType.GTC  # Good-Til-Cancelled
)

print("Order ID:", response["orderID"])
print("Status:", response["status"])
```

---

## Step 6: Check Your Orders

```python
# View all open orders
open_orders = client.get_open_orders()
print(f"You have {len(open_orders)} open orders")

# View your trade history
trades = client.get_trades()
print(f"You've made {len(trades)} trades")

# Cancel an order
client.cancel_order(response["orderID"])
```

---

## Troubleshooting

| Issue | Likely cause |
| ----- | ------------- |
| **Invalid Signature / L2 Auth Not Available** | Wrong private key, signature type, or funder address. Check signatureType (0/1/2) and funder; do not use Builder credentials as User credentials. |
| **Unauthorized / Invalid API Key** | Wrong API key, secret, or passphrase. Re-derive with `create_or_derive_api_creds()` and update config. |
| **Not Enough Balance / Allowance** | Not enough USDCe/position tokens at funder, or missing token approvals. Deposit USDCe and set approvals. |
| **Blocked by Cloudflare / Geoblock** | Restricted region. See [Geographic Restrictions](https://docs.polymarket.com/developers/CLOB/geoblock). |

---

## Adding Builder API Credentials

If you're building an app that routes orders for your users, you can add builder credentials for attribution on the [Builder Leaderboard](https://builders.polymarket.com/). Builder credentials are **separate** from user credentials; each user still needs their own L2 credentials to trade.

See: [Order Attribution](https://docs.polymarket.com/developers/builders/order-attribution).
