"""
Trading Bot Module - Main Trading Interface

A production-ready trading bot for Polymarket with:
- Gasless transactions via Builder Program
- Encrypted private key storage
- Modular strategy support
- Comprehensive order management

Example:
    from src.bot import TradingBot

    # Initialize with config
    bot = TradingBot(config_path="config.yaml")

    # Or manually
    bot = TradingBot(
        safe_address="0x...",
        builder_creds=builder_creds,
        private_key="0x..."  # or use encrypted key
    )

    # Place an order
    result = await bot.place_order(
        token_id="123...",
        price=0.65,
        size=10,
        side="BUY"
    )
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable, TypeVar
from dataclasses import dataclass, field
from enum import Enum

from eth_utils import to_checksum_address

from .config import Config, BuilderConfig
from .signer import OrderSigner, Order
from .client import ClobClient, RelayerClient, ApiCredentials
from .crypto import KeyManager, CryptoError, InvalidPasswordError

try:
    from py_clob_client.client import ClobClient as PyClobClient
    from py_clob_client.clob_types import OrderArgs as PyOrderArgs, PartialCreateOrderOptions, OrderType as PyOrderType
    from py_clob_client.order_builder.constants import BUY as PY_BUY, SELL as PY_SELL
    _PY_CLOB_AVAILABLE = True
except ImportError:
    PyClobClient = None
    PyOrderArgs = None
    PartialCreateOrderOptions = None
    PyOrderType = None
    PY_BUY = "BUY"
    PY_SELL = "SELL"
    _PY_CLOB_AVAILABLE = False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

T = TypeVar("T")

class OrderSide(str, Enum):
    """Order side constants."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type constants."""
    GTC = "GTC"  # Good Till Cancelled
    GTD = "GTD"  # Good Till Date
    FOK = "FOK"  # Fill Or Kill


@dataclass
class OrderResult:
    """Result of an order operation."""
    success: bool
    order_id: Optional[str] = None
    status: Optional[str] = None
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> "OrderResult":
        """Create from API response (supports orderId, orderID, id)."""
        success = response.get("success", False)
        error_msg = response.get("errorMsg", "")
        order_id = (
            response.get("orderId")
            or response.get("orderID")
            or response.get("id")
        )
        if order_id is not None and not isinstance(order_id, str):
            order_id = str(order_id)
        return cls(
            success=success,
            order_id=order_id,
            status=response.get("status"),
            message=error_msg if not success else "Order placed successfully",
            data=response
        )


def _response_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert py-clob-client response (dict or object) to dict for OrderResult."""
    if isinstance(obj, dict):
        return obj
    out: Dict[str, Any] = {}
    for key in ("success", "orderId", "orderID", "id", "errorMsg", "status"):
        val = getattr(obj, key, None)
        if val is not None:
            out[key] = val
    if hasattr(obj, "__dict__"):
        for k, v in obj.__dict__.items():
            if k not in out and not k.startswith("_"):
                out[k] = v
    return out


class TradingBotError(Exception):
    """Base exception for trading bot errors."""
    pass


class NotInitializedError(TradingBotError):
    """Raised when bot is not initialized."""
    pass


class TradingBot:
    """
    Main trading bot class for Polymarket.

    Provides a high-level interface for:
    - Order placement and cancellation
    - Position management
    - Trade history
    - Gasless transactions (with Builder Program)

    Attributes:
        config: Bot configuration
        signer: Order signer instance
        clob_client: CLOB API client
        relayer_client: Relayer API client (if gasless enabled)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config: Optional[Config] = None,
        safe_address: Optional[str] = None,
        builder_creds: Optional[BuilderConfig] = None,
        private_key: Optional[str] = None,
        encrypted_key_path: Optional[str] = None,
        password: Optional[str] = None,
        api_creds_path: Optional[str] = None,
        log_level: int = logging.INFO
    ):
        """
        Initialize trading bot.

        Can be initialized in multiple ways:

        1. From config file:
           bot = TradingBot(config_path="config.yaml")

        2. From Config object:
           bot = TradingBot(config=my_config)

        3. With manual parameters:
           bot = TradingBot(
               safe_address="0x...",
               builder_creds=builder_creds,
               private_key="0x..."
           )

        4. With encrypted key:
           bot = TradingBot(
               safe_address="0x...",
               encrypted_key_path="credentials/key.enc",
               password="mypassword"
           )

        Args:
            config_path: Path to config YAML file
            config: Config object
            safe_address: Safe/Proxy wallet address
            builder_creds: Builder Program credentials
            private_key: Raw private key (with 0x prefix)
            encrypted_key_path: Path to encrypted key file
            password: Password for encrypted key
            api_creds_path: Path to API credentials file
            log_level: Logging level
        """
        # Set log level
        logger.setLevel(log_level)

        # Load configuration
        if config_path:
            self.config = Config.load(config_path)
        elif config:
            self.config = config
        else:
            self.config = Config()

        # Override with provided parameters
        if safe_address:
            self.config.safe_address = safe_address
        if builder_creds:
            self.config.builder = builder_creds
            self.config.use_gasless = True

        # Initialize components
        self.signer: Optional[OrderSigner] = None
        self.clob_client: Optional[ClobClient] = None
        self.relayer_client: Optional[RelayerClient] = None
        self._api_creds: Optional[ApiCredentials] = None
        self._private_key: Optional[str] = None
        self._py_clob: Optional[Any] = None

        # Load private key
        if private_key:
            self._private_key = private_key
            self.signer = OrderSigner(private_key)
        elif encrypted_key_path and password:
            self._load_encrypted_key(encrypted_key_path, password)

        # Load API credentials
        if api_creds_path:
            self._load_api_creds(api_creds_path)

        # Initialize API clients (and derive API creds when using official py-clob-client)
        self._init_clients()

        # Auto-derive API credentials if using our client (no py-clob) and we have signer but no creds
        if not self._py_clob and self.signer and not self._api_creds:
            self._derive_api_creds()

        logger.info(f"TradingBot initialized (gasless: {self.config.use_gasless})")

    def _load_encrypted_key(self, filepath: str, password: str) -> None:
        """Load and decrypt private key from encrypted file."""
        try:
            manager = KeyManager()
            private_key = manager.load_and_decrypt(password, filepath)
            self.signer = OrderSigner(private_key)
            logger.info(f"Loaded encrypted key from {filepath}")
        except FileNotFoundError:
            raise TradingBotError(f"Encrypted key file not found: {filepath}")
        except InvalidPasswordError:
            raise TradingBotError("Invalid password for encrypted key")
        except CryptoError as e:
            raise TradingBotError(f"Failed to load encrypted key: {e}")

    def _load_api_creds(self, filepath: str) -> None:
        """Load API credentials from file."""
        if os.path.exists(filepath):
            try:
                self._api_creds = ApiCredentials.load(filepath)
                logger.info(f"Loaded API credentials from {filepath}")
            except Exception as e:
                logger.warning(f"Failed to load API credentials: {e}")

    def _derive_api_creds(self) -> None:
        """Derive L2 API credentials from signer."""
        if not self.signer or not self.clob_client:
            return

        try:
            logger.info("Deriving L2 API credentials...")
            self._api_creds = self.clob_client.create_or_derive_api_key(self.signer)
            if not self._api_creds.is_valid():
                logger.warning(
                    "API credentials are empty or invalid; create may have failed and derive returned no key"
                )
            self.clob_client.set_api_creds(self._api_creds)
            logger.info("L2 API credentials derived successfully")
        except Exception as e:
            logger.warning(f"Failed to derive API credentials: {e}")
            logger.warning("Some API endpoints may not be accessible")

    def _init_clients(self) -> None:
        """Initialize API clients."""
        self.clob_client = ClobClient(
            host=self.config.clob.host,
            chain_id=self.config.clob.chain_id,
            signature_type=self.config.clob.signature_type,
            funder=self.config.safe_address,
            api_creds=self._api_creds,
            builder_creds=self.config.builder if self.config.use_gasless else None,
            auth_address=self.signer.address if self.signer else None,
        )

        if _PY_CLOB_AVAILABLE and self._private_key and self.config.safe_address:
            try:
                signer_addr = self.signer.address
                safe_lower = self.config.safe_address.lower()
                use_eoa = (
                    safe_lower == signer_addr.lower()
                    and self.config.clob.signature_type != 2
                )
                if use_eoa:
                    sig_type = 0
                    funder = to_checksum_address(signer_addr)
                    logger.info("EOA mode: safe_address matches signer, using signature_type=0")
                else:
                    sig_type = self.config.clob.signature_type
                    funder = to_checksum_address(self.config.safe_address)
                key = self._private_key.strip()
                if key and not key.startswith("0x"):
                    key = "0x" + key
                py_clob = PyClobClient(
                    self.config.clob.host,
                    chain_id=self.config.clob.chain_id,
                    key=key,
                    signature_type=sig_type,
                    funder=funder,
                )
                creds = py_clob.create_or_derive_api_creds()
                if creds and getattr(creds, "api_key", None):
                    py_clob.set_api_creds(creds)
                    self._py_clob = py_clob
                    self._api_creds = ApiCredentials(
                        api_key=creds.api_key,
                        secret=creds.api_secret,
                        passphrase=creds.api_passphrase,
                    )
                    self.clob_client.set_api_creds(self._api_creds)
                    logger.info(
                        "L2 API credentials set (py-clob-client) | signature_type=%s funder=%s...",
                        sig_type,
                        funder[:10] + "..." if len(funder) > 10 else funder,
                    )
                else:
                    logger.warning("py-clob-client derive returned no valid creds")
            except Exception as e:
                logger.warning("Could not init py-clob-client for orders: %s", e)

        if self.config.use_gasless:
            self.relayer_client = RelayerClient(
                host=self.config.relayer.host,
                chain_id=self.config.clob.chain_id,
                builder_creds=self.config.builder,
                tx_type=self.config.relayer.tx_type,
            )
            logger.info("Relayer client initialized (gasless enabled)")

    async def _run_in_thread(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a blocking call in a worker thread to avoid event loop stalls."""
        return await asyncio.to_thread(func, *args, **kwargs)

    def is_initialized(self) -> bool:
        """Check if bot is properly initialized."""
        return (
            self.signer is not None and
            self.config.safe_address and
            self.clob_client is not None
        )

    def require_signer(self) -> OrderSigner:
        """Get signer or raise if not initialized."""
        if not self.signer:
            raise NotInitializedError(
                "Signer not initialized. Provide private_key or encrypted_key."
            )
        return self.signer

    async def place_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: str = "GTC",
        fee_rate_bps: int = 0,
        market_options: Optional[Dict[str, Any]] = None,
    ) -> OrderResult:
        """
        Place a limit order. Uses official py-clob-client when available for correct payload and L2 auth.
        """
        if self._py_clob and PyOrderArgs and PartialCreateOrderOptions and PyOrderType:
            return await self._place_order_py_clob(
                token_id, price, size, side, order_type, fee_rate_bps, market_options
            )
        return await self._place_order_legacy(
            token_id, price, size, side, order_type, fee_rate_bps, market_options
        )

    async def _place_order_py_clob(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: str,
        fee_rate_bps: int,
        market_options: Optional[Dict[str, Any]],
    ) -> OrderResult:
        try:
            side_val = PY_BUY if str(side).upper() == "BUY" else PY_SELL
            order_type_val = getattr(PyOrderType, order_type, PyOrderType.GTC)
            args = PyOrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side_val,
                fee_rate_bps=fee_rate_bps,
            )
            options = None
            if market_options:
                tick = str(market_options.get("tick_size", "0.01"))
                if tick not in ("0.1", "0.01", "0.001", "0.0001"):
                    tick = "0.01"
                options = PartialCreateOrderOptions(
                    tick_size=tick,
                    neg_risk=bool(market_options.get("neg_risk", True)),
                )
            py_clob = self._py_clob

            def create_and_post():
                created = py_clob.create_order(args, options)
                return py_clob.post_order(created, order_type_val)

            response = await self._run_in_thread(create_and_post)
            logger.info("Order placed: %s %s@%s (py-clob-client)", side, size, price)
            if not isinstance(response, dict):
                response = _response_to_dict(response)
            return OrderResult.from_response(response)
        except Exception as e:
            logger.error("Failed to place order (py-clob): %s", e)
            return OrderResult(success=False, message=str(e))

    async def _place_order_legacy(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: str,
        fee_rate_bps: int,
        market_options: Optional[Dict[str, Any]],
    ) -> OrderResult:
        signer = self.require_signer()
        try:
            order = Order(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                maker=self.config.safe_address,
                fee_rate_bps=fee_rate_bps,
            )
            options = {"tick_size": "0.0001", "neg_risk": False}
            if market_options:
                options["tick_size"] = market_options.get("tick_size", options["tick_size"])
                options["neg_risk"] = bool(market_options.get("neg_risk", False))
            else:
                try:
                    market_info = await self._run_in_thread(self.clob_client.get_market, token_id)
                    if market_info:
                        options["tick_size"] = market_info.get("tickSize", "0.0001")
                        options["neg_risk"] = market_info.get("negRisk", False)
                except Exception as e:
                    logger.warning("Could not fetch market info for %s: %s", token_id, e)
            signed = signer.sign_order(order, options=options)
            response = await self._run_in_thread(
                self.clob_client.post_order, signed, order_type
            )
            logger.info("Order placed: %s %s@%s (legacy)", side, size, price)
            return OrderResult.from_response(response)
        except Exception as e:
            logger.error("Failed to place order: %s", e)
            return OrderResult(success=False, message=str(e))

    async def place_orders(
        self,
        orders: List[Dict[str, Any]],
        order_type: str = "GTC"
    ) -> List[OrderResult]:
        """
        Place multiple orders.

        Args:
            orders: List of order dictionaries with keys:
                - token_id: Market token ID
                - price: Price per share
                - size: Number of shares
                - side: 'BUY' or 'SELL'
            order_type: Order type (GTC, GTD, FOK)

        Returns:
            List of OrderResults
        """
        results = []
        for order_data in orders:
            result = await self.place_order(
                token_id=order_data["token_id"],
                price=order_data["price"],
                size=order_data["size"],
                side=order_data["side"],
                order_type=order_type,
            )
            results.append(result)

            # Small delay between orders to avoid rate limits
            await asyncio.sleep(0.1)

        return results

    async def cancel_order(self, order_id: str) -> OrderResult:
        """
        Cancel a specific order.

        Args:
            order_id: Order ID to cancel

        Returns:
            OrderResult with cancellation status
        """
        try:
            response = await self._run_in_thread(self.clob_client.cancel_order, order_id)
            logger.info(f"Order cancelled: {order_id}")
            return OrderResult(
                success=True,
                order_id=order_id,
                message="Order cancelled",
                data=response
            )
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return OrderResult(
                success=False,
                order_id=order_id,
                message=str(e)
            )

    async def cancel_all_orders(self) -> OrderResult:
        """
        Cancel all open orders.

        Returns:
            OrderResult with cancellation status
        """
        try:
            response = await self._run_in_thread(self.clob_client.cancel_all_orders)
            logger.info("All orders cancelled")
            return OrderResult(
                success=True,
                message="All orders cancelled",
                data=response
            )
        except Exception as e:
            logger.error(f"Failed to cancel orders: {e}")
            return OrderResult(success=False, message=str(e))

    async def cancel_market_orders(
        self,
        market: Optional[str] = None,
        asset_id: Optional[str] = None
    ) -> OrderResult:
        """
        Cancel orders for a specific market.

        Args:
            market: Condition ID of the market (optional)
            asset_id: Token/asset ID (optional)

        Returns:
            OrderResult with cancellation status
        """
        try:
            response = await self._run_in_thread(
                self.clob_client.cancel_market_orders,
                market,
                asset_id,
            )
            logger.info(f"Market orders cancelled (market: {market or 'all'}, asset: {asset_id or 'all'})")
            return OrderResult(
                success=True,
                message=f"Orders cancelled for market {market or 'all'}",
                data=response
            )
        except Exception as e:
            logger.error(f"Failed to cancel market orders: {e}")
            return OrderResult(success=False, message=str(e))

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get all open orders.

        Returns:
            List of open orders
        """
        try:
            orders = await self._run_in_thread(self.clob_client.get_open_orders)
            logger.debug(f"Retrieved {len(orders)} open orders")
            return orders
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order details.

        Args:
            order_id: Order ID

        Returns:
            Order details or None
        """
        try:
            return await self._run_in_thread(self.clob_client.get_order, order_id)
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None

    async def get_trades(
        self,
        token_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get trade history.

        Args:
            token_id: Optional token ID to filter
            limit: Maximum number of trades

        Returns:
            List of trades
        """
        try:
            trades = await self._run_in_thread(self.clob_client.get_trades, token_id, limit)
            logger.debug(f"Retrieved {len(trades)} trades")
            return trades
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            return []

    async def claim_winnings(
        self,
        market_slug: str,
        side: str,
        token_id: str,
        size: float,
    ) -> bool:
        """
        Claim winnings for a resolved winning position.
        Proxy/Safe wallets: redeem is done on-chain; CLOB has no claim API.
        This logs the winning position; actual redeem can be done on Polymarket website
        or via future CTF/Safe integration.

        Args:
            market_slug: Resolved market slug
            side: "up" or "down"
            token_id: Outcome token ID
            size: Position size (shares)

        Returns:
            True (caller can treat as acknowledged)
        """
        logger.info(
            f"Winning position: market={market_slug} side={side} size={size:.2f} token_id={token_id[:16]}... "
            "(Redeem on Polymarket website or use CTF redeem for proxy.)"
        )
        return True

    async def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Get order book for a token.

        Args:
            token_id: Market token ID

        Returns:
            Order book data
        """
        try:
            return await self._run_in_thread(self.clob_client.get_order_book, token_id)
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            return {}

    async def get_market_price(self, token_id: str) -> Dict[str, Any]:
        """
        Get current market price for a token.

        Args:
            token_id: Market token ID

        Returns:
            Price data
        """
        try:
            return await self._run_in_thread(self.clob_client.get_market_price, token_id)
        except Exception as e:
            logger.error(f"Failed to get market price: {e}")
            return {}

    async def deploy_safe_if_needed(self) -> bool:
        """
        Deploy Safe proxy wallet if not already deployed.

        Returns:
            True if deployment was needed or successful
        """
        if not self.config.use_gasless or not self.relayer_client:
            logger.debug("Gasless not enabled, skipping Safe deployment")
            return False

        try:
            response = await self._run_in_thread(
                self.relayer_client.deploy_safe,
                self.config.safe_address,
            )
            logger.info(f"Safe deployment initiated: {response}")
            return True
        except Exception as e:
            logger.warning(f"Safe deployment failed (may already be deployed): {e}")
            return False

    def create_order_dict(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str
    ) -> Dict[str, Any]:
        """
        Create an order dictionary for batch processing.

        Args:
            token_id: Market token ID
            price: Price per share
            size: Number of shares
            side: 'BUY' or 'SELL'

        Returns:
            Order dictionary
        """
        return {
            "token_id": token_id,
            "price": price,
            "size": size,
            "side": side.upper(),
        }


# Convenience function for quick initialization
def create_bot(
    config_path: str = "config.yaml",
    private_key: Optional[str] = None,
    encrypted_key_path: Optional[str] = None,
    password: Optional[str] = None,
    **kwargs
) -> TradingBot:
    """
    Create a TradingBot instance with common options.

    Args:
        config_path: Path to config file
        private_key: Private key (with 0x prefix)
        encrypted_key_path: Path to encrypted key file
        password: Password for encrypted key
        **kwargs: Additional arguments for TradingBot

    Returns:
        Configured TradingBot instance
    """
    return TradingBot(
        config_path=config_path,
        private_key=private_key,
        encrypted_key_path=encrypted_key_path,
        password=password,
        **kwargs
    )
