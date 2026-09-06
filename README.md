# TEM Python SDK (tem_sdk)

A lightweight Python SDK for interacting with the Tron Energy Market (TEM) HTTP API.
The SDK wraps common endpoints for market information, account credit operations and
order management — including creating, listing, filling and cancelling orders.

## Supported endpoints

- `/info` — market information
- `/status` — health / status
- `/order/*` — creating, listing, filling, cancelling orders (no reclaim)
- `/credit/*` — deposit / withdraw

## Key features

- Async, `httpx`-based `TemClient` for all API requests.
- Pydantic models for request/response payloads and validation.
- Field aliases/validation aliases support (snake_case, camelCase, TitleCase) so responses
  with different naming conventions are accepted.
- Helpers for TRX/SUN conversions and payment calculation.

## Requirements

- Python 3.10+ recommended
- Install runtime deps:
    - `httpx`
    - `pydantic`

## Installation

1. Add the package to your project (if published to pip) or install dependencies locally:

```sh
# Example (install dependencies)
pip install httpx pydantic
```

## Quick usage (async)

- The client is async and should be used with `async with TemClient(...)` or created and closed manually.

### Example: basic health check and market info

```python
import asyncio
from tem_sdk import TemClient


async def main():
    async with TemClient() as client:
        ok = await client.check_status()
        print("API status:", ok)

        info = await client.get_market_info()
        print("Market address:", info.address)
        # info.market, info.price, info.order, etc. available as Pydantic models


asyncio.run(main())
```

### Example: get account balance (SUN)

```python
import asyncio
from tem_sdk import TemClient


async def main():
    address = "Txxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    async with TemClient() as client:
        balance_sun = await client.get_balance(address)
        print("Balance (SUN):", balance_sun)


asyncio.run(main())
```

## Working with orders

- Models and enums are exported from `tem_sdk`. Typical imports:

```python
from decimal import Decimal
from tem_sdk import TemClient, MarketType, Resource, OrderStatus, SignedMS
```

### Create an order

- `create_order` automatically computes the `payment` field from price, amount and duration.
- Use `MarketType`, `Resource`, provide either `api_key` or signatures (`signed_tx` or `signed_ms`) as required by your workflow.

```python
import asyncio
from decimal import Decimal
from tem_sdk import TemClient, MarketType, Resource


async def create_example():
    async with TemClient() as client:
        order_id = await client.create_order(
            market=MarketType.Open,  # Market type: Open or Fast
            account_address="TYourAccountAddress",
            target="TTargetAddress",  # or list[str] for bulk
            resource=Resource.Energy,  # Resource enum
            amount=Decimal(100),  # amount (integer-like Decimal)
            duration=Decimal(86400),  # seconds (1 day)
            price=Decimal(10),  # price per unit (in SUN)
            partfill=True,  # allow partial fills
            # provide authentication: api_key or signed_ms/signed_tx per API rules
        )
        print("Created order id:", order_id)


asyncio.run(create_example())
```

### Fill an order

```python
import asyncio
from tem_sdk import TemClient


async def fill_order_example():
    async with TemClient() as client:
        await client.fill_order(
            order_id=12345,
            account_address="TYourAccountAddress",
            signed_tx="...signed TRX transaction hex/string...",
            target=None,  # optional origin_address for the fill
        )
        print("Order filled")


asyncio.run(fill_order_example())
```

### Cancel an order (requires SignedMS)

```python
import asyncio
from tem_sdk import TemClient
from tem_sdk.models.parts import SignedMS


async def cancel_example():
    signed_ms = SignedMS(message="te_abc123", signature="signature_string")
    async with TemClient() as client:
        await client.cancel_order(
            order_id=12345, account_address="TYourAccount", signed_ms=signed_ms
        )
        print("Order cancelled")


asyncio.run(cancel_example())
```

## Deposit and withdraw (credit)

```python
import asyncio
from decimal import Decimal
from tem_sdk import TemClient, SignedMS


async def credit_example():
    address = "TYourAccount"
    signed_tx = "signed_trx_for_deposit"
    async with TemClient() as client:
        # Deposit (signed TRX)
        await client.deposit_balance(account_address=address, signed_tx=signed_tx)

        # Withdraw (requires SignedMS)
        signed_ms = SignedMS(message="te_abc", signature="signature")
        await client.withdraw_balance(
            account_address=address, signed_ms=signed_ms, amount=Decimal(1_000_000)
        )
        # amount is in SUN (integer)


asyncio.run(credit_example())
```

## Utility helpers

- The client exposes small helpers for common numeric conversions and payment calculation:
    - `TemClient.convert_sun_to_trx(sun)` → Decimal (TRX)
    - `TemClient.convert_trx_to_sun(trx)` → Decimal (SUN, quantized)
    - `TemClient.calculate_order_payment(price, amount, duration)` → Decimal (payment in SUN)

## Notes about models

- Pydantic models live under `tem_sdk.models` (enums, info, requests, responses, orders, parts).
- Response models include validation aliases so payload keys using snake_case, camelCase or TitleCase are accepted.
- Order and Info models are full Pydantic models: use them to parse and inspect API responses.

### Examples of reading orders and iterating all orders

```python
import asyncio
from tem_sdk import TemClient, OrderStatus


async def list_orders_example():
    async with TemClient() as client:
        # Get a single page (skip/take)
        orders = await client.get_orders(skip=0, take=100, status=OrderStatus.Pending)
        print("Got", len(orders), "orders (page)")

        # Get all orders (will page through until exhausted)
        all_orders = await client.get_all_orders(status=OrderStatus.Pending)
        print("Total orders retrieved:", len(all_orders))


asyncio.run(list_orders_example())
```

## Development notes

- The client uses `httpx.AsyncClient` with default base_url `https://api.tronenergy.market/`. You can override `base_url` when creating `TemClient`.
- The SDK expects the API to return JSON compatible with the models. Validation aliases allow some flexibility in field naming.

## Contributing

- Open PRs with tests and a short rationale.
- Keep API surface backwards compatible where possible.
