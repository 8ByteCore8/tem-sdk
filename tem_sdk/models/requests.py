from decimal import Decimal

from pydantic import BaseModel, Field, computed_field, model_validator

from tem_sdk.models.enums import MarketType, Resource
from tem_sdk.models.parts import SignedMS


class BalanceDepositRequest(BaseModel):
    """
    Request model for depositing TRX into an account balance.

    Fields:
        address (str): The address of the account receiving the deposit.
        signed_tx (str): The signed TRX transaction used to deposit funds.

    Example:
        BalanceDepositRequest(address="T...", signed_tx="...signed transaction...")
    """

    address: str = Field(...)
    signed_tx: str = Field(...)


class BalanceWithdrawRequest(BaseModel):
    """
    Request model for withdrawing balance from an account.

    Fields:
        address (str): The address of the account from which to withdraw.
        signed_ms (SignedMS): A multisignature payload required for authorization.
        amount (Decimal | None): Optional amount to withdraw (in SUN). If None, full available amount is assumed.

    Example:
        BalanceWithdrawRequest(
            address="T...",
            signed_ms=SignedMS(message="te_...", signature="..."),
            amount=Decimal("1000000")
        )
    """

    address: str = Field(...)
    signed_ms: SignedMS = Field(...)
    amount: Decimal | None = Field(..., decimal_places=0)


class CreateOrderRequest(BaseModel):
    """
    Request model for creating a new order on the market.

    This model encapsulates all parameters accepted by the `/order/new` endpoint.
    It includes validators that normalize `target` (single vs bulk targets) and
    enforce signature/API-key rules.

    Fields:
        market (MarketType): Market type for the order (e.g., Open, Fast).
        address (str): Sender TRX address placing the order.
        target (str | list[str]): Rent target — a single target address or a list of addresses for bulk orders.
        payment (Decimal): Payment amount in SUN (integer-like Decimal).
        resource (Resource): Rented resource type (e.g., Energy, Bandwidth).
        duration (Decimal): Rent duration in seconds (integer-like Decimal).
        price (Decimal): Price per unit (in SUN, integer-like Decimal).
        partfill (bool): Whether partial order filling is allowed.
        api_key (str | None): Optional user API key; if present, signature fields are ignored.
        signed_ms (SignedMS | None): Optional multisignature payload used to sign the order.
        signed_tx (str | None): Optional signed TRX transaction used to sign the order.

    Computed properties:
        bulk (bool): True when `target` is a list (bulk order), False when single target.

    Validators:
        validate_targets(): Ensures `target` is valid; if list of length 1 is provided it is normalized to a single string value.
        validate_signature(): Ensures exactly one signing method is provided: either `api_key`, or (`signed_tx` and/or `signed_ms`).

    Notes:
        - If `api_key` is provided, both `signed_tx` and `signed_ms` will be cleared by the validator.
        - If both `signed_tx` and `signed_ms` are provided, `api_key` will be cleared.
        - A target list must be non-empty; empty list raises ValueError.

    Example:
        CreateOrderRequest(
            market=MarketType.Open,
            address="T...",
            target=["T1", "T2"],
            payment=Decimal("1000000"),
            resource=Resource.Energy,
            duration=Decimal("86400"),
            price=Decimal("10"),
            partfill=True,
            api_key=None,
            signed_ms=None,
            signed_tx=None,
        )
    """

    market: MarketType = Field(...)
    """Market type"""
    address: str = Field(...)
    """Sender of TRX"""
    target: str | list[str] = Field(...)
    """Rent target"""
    amount: int = Field(...)
    """Rent amount"""
    resource: Resource = Field(...)
    """Rented resource"""
    duration: int = Field(...)
    """Rent duration"""
    price: int = Field(...)
    """Rent price"""
    partfill: bool = Field(...)
    """Allow partial order execution"""
    instant: bool | None = Field(None)
    """Instant order execution"""
    listed: bool | None = Field(None)
    """Public order visibility"""
    api_key: str | None = Field(None)
    """User API key"""
    signed_ms: SignedMS | None = Field(None)
    """Signed multisignature payload (when not using api_key)"""
    signed_tx: str | None = Field(None)
    """Signed TRX transaction (when not using api_key)"""

    @computed_field()
    @property
    def bulk(self) -> bool:
        """
        Computed property indicating whether the order is a bulk order.

        Returns:
            bool: True if `target` is a list (bulk order), False otherwise.
        """
        return isinstance(self.target, list)

    @model_validator(mode="after")
    def validate_targets(self) -> "CreateOrderRequest":
        """
        Validator that normalizes and validates the `target` field.

        Behavior:
            - If `target` is a string, it is considered valid as-is.
            - If `target` is a list with a single element, it is normalized to that string.
            - If `target` is a non-empty list with more than one element, it is valid (bulk).
            - If `target` is an empty list or an unsupported type, ValueError is raised.

        Returns:
            CreateOrderRequest: The validated (and possibly normalized) instance.

        Raises:
            ValueError: If `target` is an empty list or of an invalid type.
        """
        if isinstance(self.target, str):
            return self
        if isinstance(self.target, list):  # pyright: ignore[reportUnnecessaryIsInstance]
            if len(self.target) == 1:
                self.target = self.target[0]
                return self

            if len(self.target) > 0:
                return self

            raise ValueError("Target list cannot be empty")

        raise ValueError("Invalid target type")

    @model_validator(mode="after")
    def validate_signature(self) -> "CreateOrderRequest":
        """
        Validator that enforces signature or API key presence rules.

        Behavior:
            - If `api_key` is present, both `signed_tx` and `signed_ms` are cleared.
            - If both `signed_tx` and `signed_ms` are provided, `api_key` is cleared.
            - If neither a valid API key nor valid signature(s) are present, a ValueError is raised.

        Returns:
            CreateOrderRequest: The validated (and possibly normalized) instance.

        Raises:
            ValueError: If neither signature nor API key information is provided or signature rules are violated.
        """
        if self.api_key:
            self.signed_tx = None
            self.signed_ms = None
            return self

        if self.signed_tx and self.signed_ms:
            self.api_key = None
            return self

        raise ValueError("Invalid signature")


class FillOrderRequest(BaseModel):
    """
    Request model for filling an existing order.

    Fields:
        id (int): The identifier of the order to fill.
        origin_address (str | None): Optional origin address for the fill operation.
        address (str): The address performing the fill (filler).
        signed_tx (str): The signed TRX transaction authorizing the fill.

    Example:
        FillOrderRequest(id=123, origin_address=None, address="T...", signed_tx="...signed...")
    """

    id: int = Field(...)
    origin_address: str | None = Field(None)
    address: str = Field(...)
    signed_tx: str = Field(...)


class CancelOrderRequest(BaseModel):
    """
    Request model for canceling an existing order.

    Fields:
        order (int): The identifier of the order to cancel.
        address (str): The address requesting the cancellation.
        signed_ms (SignedMS): A multisignature payload authorizing the cancellation.

    Example:
        CancelOrderRequest(order=123, address="T...", signed_ms=SignedMS(...))
    """

    order: int = Field(...)
    address: str = Field(...)
    signed_ms: SignedMS = Field(...)
