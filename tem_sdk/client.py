from collections.abc import Awaitable
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from types import TracebackType

from httpx import AsyncClient, HTTPError

from tem_sdk.models.enums import MarketType, OrderStatus, Resource
from tem_sdk.models.info import Info
from tem_sdk.models.orders import Order
from tem_sdk.models.parts import SignedMS
from tem_sdk.models.requests import (
    BalanceDepositRequest,
    BalanceWithdrawRequest,
    CancelOrderRequest,
    CreateOrderRequest,
    FillOrderRequest,
)
from tem_sdk.models.responses import (
    CreateOrderResponse,
    GetBalanceResponse,
    GetMarketInfoResponse,
    GetOrderResponse,
    GetOrdersResponse,
)


class TemClient:
    """
    A client for interacting with the Tron Energy Market API.

    This class provides methods to perform various operations such as checking
    API status, retrieving market information, managing orders, and handling
    account balances.
    """

    __client__: AsyncClient

    async def __aenter__(self) -> "TemClient":
        """
        Enter the asynchronous context manager.

        Returns:
            TemClient: The instance of the client.
        """
        await self.__client__.__aenter__()  # pyright: ignore[reportUnusedCallResult]
        return self

    @staticmethod
    def calculate_order_payment(
        price: Decimal | int, amount: Decimal | int, duration: Decimal | int
    ) -> Decimal:
        """
        Calculate the total payment for an order based on price, amount, and duration.

        Args:
            price (Decimal | int): The price per unit of resource.
            amount (Decimal | int): The amount of resource being ordered.
            duration (Decimal | int): The duration for which the resource is being ordered.

        Returns:
            Decimal: The total payment required for the order.
        """
        day = Decimal(86400)
        price = Decimal(price)
        amount = Decimal(amount)
        duration = Decimal(duration) + day if duration < day else Decimal(duration)
        return ((price * amount * duration) / day).quantize(
            Decimal("1."), rounding=ROUND_UP
        )

    @staticmethod
    def convert_sun_to_trx(sun: Decimal | int) -> Decimal:
        """
        Convert SUN to TRX.

        Args:
            sun (Decimal | int): The amount in SUN.

        Returns:
            Decimal: The equivalent amount in TRX.
        """
        return Decimal(sun) / Decimal(1_000_000)

    @staticmethod
    def convert_trx_to_sun(trx: Decimal | int | float) -> Decimal:
        """
        Convert TRX to SUN.

        Args:
            trx (Decimal | int | float): The amount in TRX.

        Returns:
            Decimal: The equivalent amount in SUN.
        """
        return (Decimal(trx) * Decimal(1_000_000)).quantize(
            Decimal("1."), rounding=ROUND_DOWN
        )

    def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> Awaitable[None]:
        """
        Exit the asynchronous context manager.

        Args:
            exc_type (type[BaseException] | None): The exception type, if any.
            exc_value (BaseException | None): The exception value, if any.
            traceback (TracebackType | None): The traceback, if any.

        Returns:
            Coroutine[Any, Any, None]: The coroutine for exiting the context.
        """
        return self.__client__.__aexit__(
            exc_type,
            exc_value,
            traceback,
        )

    def __init__(
        self,
        *,
        base_url: str = "https://api.tronenergy.market/",
    ) -> None:
        self.__client__ = AsyncClient(base_url=base_url)

    async def check_status(self):
        """
        Check the status of the API.

        Returns:
            bool: True if the API is reachable and operational, False otherwise.
        """
        try:
            response = await self.__client__.get("/status")
            return response.is_success
        except HTTPError:
            return False

    async def get_market_info(self) -> Info:
        """
        Retrieve market information.

        Returns:
            Info: The market information.
        """
        response = await self.__client__.get("/info")
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]
        data = GetMarketInfoResponse.model_validate_json(response.content)
        return Info(
            address=data.address,
            market=data.market,
            price=data.price,
            order=data.order,
            pool=data.pool,
            credit=data.credit,
            referral=data.referral,
            reward=data.reward,
            tron=data.tron,
        )

    async def get_balance(self, account: str) -> Decimal:
        """
        Get the account balance in SUN.

        Args:
            account (str): The address of the account.

        Returns:
            Decimal: The account balance in SUN.
        """
        response = await self.__client__.get("/credit", params={"address": account})
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]
        return GetBalanceResponse.model_validate_json(response.content).value

    async def deposit_balance(
        self,
        account: str,
        signed_tx: str,
    ) -> None:
        """
        Deposit balance into the account.

        Args:
            account (str): The address of the account.
            signed_tx (str): The signed transaction for the deposit.

        Returns:
            None
        """
        response = await self.__client__.post(
            url="/credit/deposit",
            json=BalanceDepositRequest(
                address=account,
                signed_tx=signed_tx,
            ).model_dump(mode="json", exclude_none=True, exclude_unset=True),
        )
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]

    async def withdraw_balance(
        self,
        account: str,
        signed_ms: SignedMS,
        amount: int | Decimal | None = None,
    ) -> None:
        """
        Withdraw balance from the account.

        Args:
            account (str): The address of the account.
            signed_ms (SignedMS): The signed multisignature for the withdrawal.
            amount (int | Decimal | None): The amount to withdraw (optional).

        Returns:
            None
        """
        response = await self.__client__.post(
            url="/credit/withdraw",
            json=BalanceWithdrawRequest(
                address=account,
                amount=Decimal(amount) if amount else None,
                signed_ms=signed_ms,
            ).model_dump(mode="json", exclude_none=True, exclude_unset=True),
        )
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]

    async def get_orders(
        self,
        *,
        skip: int = 0,
        take: int = 1000,
        status: OrderStatus | None = None,
        account: str | None = None,
    ) -> list[Order]:
        """
        Retrieve a list of orders.

        Args:
            skip (int): The number of orders to skip.
            take (int): The number of orders to retrieve.
            status (OrderStatus | None): The status of the orders to filter by (optional).
            account (str | None): The account address to filter by (optional).

        Returns:
            list[Order]: The list of orders.
        """
        params: dict[str, str] = {
            "skip": str(skip),
            "limit": str(take),
        }
        if status is not None:
            params["status"] = status.value
        if account is not None:
            params["address"] = account

        response = await self.__client__.get("/order/list", params=params)
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]
        return GetOrdersResponse.model_validate_json(response.content).orders

    async def get_all_orders(
        self,
        *,
        status: OrderStatus | None = None,
        account: str | None = None,
    ) -> list[Order]:
        """
        Retrieve all orders, optionally filtered by status or account address.

        Args:
            status (OrderStatus | None): The status of the orders to filter by (optional).
            account (str | None): The account address to filter by (optional).

        Returns:
            list[Order]: The list of all orders.
        """
        orders: set[Order] = set()
        skip = 0
        take = 1000

        while True:
            chunk = await self.get_orders(
                skip=skip,
                take=take,
                status=status,
                account=account,
            )
            orders.update(chunk)
            if len(chunk) < take:
                break
            skip += take

        return list(orders)

    async def get_order(self, order_id: int) -> Order:
        """
        Retrieve details of a specific order.

        Args:
            order_id (int): The ID of the order.

        Returns:
            Order: The details of the order.
        """
        params = {
            "id": str(order_id),
        }

        response = await self.__client__.get("/order/info", params=params)
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]
        data = GetOrderResponse.model_validate_json(response.content)
        return Order(
            id=data.id,
            type=data.type,
            market=data.market,
            origin=data.origin,
            target=data.target,
            price=data.price,
            amount=data.amount,
            freeze=data.freeze,
            frozen=data.frozen,
            resource=data.resource,
            locked=data.locked,
            duration=data.duration,
            payment=data.payment,
            partfill=data.partfill,
            extend=data.extend,
            maxlock=data.maxlock,
            status=data.status,
            archive=data.archive,
            created_at=data.created_at,
            updated_at=data.updated_at,
        )

    async def create_order(
        self,
        market: MarketType,
        account: str,
        target: str | list[str],
        resource: Resource,
        amount: Decimal | int,
        duration: Decimal | int,
        price: Decimal | int,
        partfill: bool = True,
        instant: bool | None = None,
        listed: bool | None = None,
        api_key: str | None = None,
        signed_ms: SignedMS | None = None,
        signed_tx: str | None = None,
    ) -> Decimal:
        """
        Create a new order.

        Args:
            market (MarketType): The market mode (e.g., Open or Fast).
            account (str): The address placing the order.
            target (str | list[str]): Target address or list of addresses for bulk orders.
            resource (Resource): The resource type (e.g., Energy, Bandwidth).
            amount (Decimal | int): The amount of resource to rent.
            duration (Decimal | int): The duration of the order in seconds.
            price (Decimal | int): The price per unit of the resource (in SUN).
            partfill (bool): Whether partial fills are allowed (default: True).
            api_key (str | None): Optional API key; if provided, signature fields are ignored.
            signed_ms (SignedMS | None): Optional multisignature payload for signed requests.
            signed_tx (str | None): Optional signed TRX transaction for signed requests.

        Returns:
            int: The ID of the created order.

        Notes:
            The `payment` field sent to the API is computed from `price`, `amount`, and `duration`.
        """
        amount = Decimal(amount)
        response = await self.__client__.post(
            "/order/new",
            json=CreateOrderRequest(
                market=market,
                address=account,
                target=target,
                amount=amount,
                payment=self.calculate_order_payment(price, amount, duration),
                resource=resource,
                price=Decimal(price),
                duration=Decimal(duration),
                partfill=partfill,
                instant=instant,
                listed=listed,
                api_key=api_key,
                signed_ms=signed_ms,
                signed_tx=signed_tx,
            ).model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]
        return CreateOrderResponse.model_validate_json(response.content).order_id

    async def fill_order(
        self,
        order_id: int,
        account: str,
        signed_tx: str,
        target: str | None = None,
    ) -> None:
        """
        Fill an existing order.

        Args:
            order_id (int): The ID of the order to fill.
            account (str): The address of the account filling the order.
            signed_tx (str): The signed transaction for the fill.
            target (str | None): The target address for the fill (optional).

        Returns:
            None
        """
        response = await self.__client__.post(
            "/order/fill",
            json=FillOrderRequest(
                id=order_id,
                address=account,
                signed_tx=signed_tx,
                origin_address=target,
            ).model_dump(mode="json", exclude_none=True, exclude_unset=True),
        )
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]

    async def cancel_order(
        self, order_id: int, account: str, signed_ms: SignedMS
    ) -> None:
        """
        Cancel an existing order.

        Args:
            order_id (int): The ID of the order to cancel.
            account (str): The address of the account canceling the order.
            signed_ms (SignedMS): The signed multisignature for the cancellation.

        Returns:
            None
        """
        response = await self.__client__.post(
            "/order/cancel",
            json=CancelOrderRequest(
                order=order_id,
                address=account,
                signed_ms=signed_ms,
            ).model_dump(mode="json", exclude_none=True, exclude_unset=True),
        )
        response.raise_for_status()  # pyright: ignore[reportUnusedCallResult]

    # No info about this method
    # async def reclaim_order(session: ClientSession, payload: CancelOrder):
    #     await session.post("/order/reclaim", json=payload.model_dump(mode="json"))
