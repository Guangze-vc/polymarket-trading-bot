"""
Signer Module - EIP-712 Order Signing (STABLE / PRO VERSION)

This version intentionally DOES NOT use py-clob-client.
It avoids poly_eip712_structs Address incompatibilities.

Uses direct EIP-712 encoding with primitive types only.
"""

import time
import secrets
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

def _debug_log_path():
    p = Path(__file__).resolve().parent.parent / ".cursor" / "debug.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

from eth_account import Account
from eth_account.messages import encode_typed_data, encode_defunct
from eth_utils import to_checksum_address

# =============================================================================
# Constants
# =============================================================================

USDC_DECIMALS = 6
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# =============================================================================
# Order Dataclass
# =============================================================================

@dataclass
class Order:
    token_id: str
    price: float
    size: float
    side: str
    maker: str
    nonce: Optional[int] = None
    fee_rate_bps: int = 0
    signature_type: int = 2  # 2 = proxy/safe (gasless)
    expiration: Optional[int] = None

    # --------------------------------------------------------------------------------
    # Automatically calculate maker/taker amounts and side enum on init
    # --------------------------------------------------------------------------------
    def __post_init__(self):
        self.side = self.side.upper()
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {self.side}")

        if not (0 < self.price <= 1):
            raise ValueError(f"Invalid price: {self.price}")

        if self.size <= 0:
            raise ValueError(f"Invalid size: {self.size}")

        if self.nonce is None:
            self.nonce = int(time.time())

        # ensure expiration is set and valid
        if self.expiration is None:
            # default expire in 24h
            self.expiration = int(time.time() + 60 * 60 * 24)

        self.maker = to_checksum_address(self.maker)

        # BUY orders pay USDC and receive outcome
        if self.side == "BUY":
            self.maker_amount = int(self.size * self.price * 10**USDC_DECIMALS)
            self.taker_amount = int(self.size * 10**USDC_DECIMALS)
            # 0 = BUY enum in CLOB API
            self.side_value = 0
        else:
            self.maker_amount = int(self.size * 10**USDC_DECIMALS)
            self.taker_amount = int(self.size * self.price * 10**USDC_DECIMALS)
            # 1 = SELL enum in CLOB API
            self.side_value = 1

# =============================================================================
# Exceptions
# =============================================================================

class SignerError(Exception):
    pass

# =============================================================================
# Order Signer
# =============================================================================

class OrderSigner:
    """
    Provides:
    - L1 authentication signing
    - Order signing for Polymarket CLOB
    """

    AUTH_DOMAIN = {
        "name": "ClobAuthDomain",
        "version": "1",
        "chainId": 137,
    }

    EXCHANGE_DOMAIN_NEG_RISK = {
        "name": "CTF Exchange",
        "version": "1",
        "chainId": 137,
        "verifyingContract": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    }
    EXCHANGE_DOMAIN_REGULAR = {
        "name": "CTF Exchange",
        "version": "1",
        "chainId": 137,
        "verifyingContract": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    }

    ORDER_TYPES = {
        "Order": [
            {"name": "salt", "type": "uint256"},
            {"name": "maker", "type": "address"},
            {"name": "signer", "type": "address"},
            {"name": "taker", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
            {"name": "makerAmount", "type": "uint256"},
            {"name": "takerAmount", "type": "uint256"},
            {"name": "expiration", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
            {"name": "feeRateBps", "type": "uint256"},
            {"name": "side", "type": "uint8"},
            {"name": "signatureType", "type": "uint8"},
        ]
    }

    # -------------------------------------------------------------------------
    # INIT
    # -------------------------------------------------------------------------
    def __init__(self, private_key: str):
        if private_key.startswith("0x"):
            private_key = private_key[2:]

        try:
            self.wallet = Account.from_key("0x" + private_key)
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}")

        self.address = to_checksum_address(self.wallet.address)

    # -------------------------------------------------------------------------
    # L1 AUTH
    # -------------------------------------------------------------------------
    def sign_auth_message(
        self,
        timestamp: Optional[str] = None,
        nonce: int = 0
    ) -> str:
        if timestamp is None:
            timestamp = str(int(time.time()))

        auth_types = {
            "ClobAuth": [
                {"name": "address", "type": "address"},
                {"name": "timestamp", "type": "string"},
                {"name": "nonce", "type": "uint256"},
                {"name": "message", "type": "string"},
            ]
        }

        message_data = {
            "address": self.address,
            "timestamp": timestamp,
            "nonce": nonce,
            "message": "This message attests that I control the given wallet",
        }

        signable = encode_typed_data(
            domain_data=self.AUTH_DOMAIN,
            message_types=auth_types,
            message_data=message_data,
        )

        signed = self.wallet.sign_message(signable)
        return "0x" + signed.signature.hex()

    # -------------------------------------------------------------------------
    # ORDER SIGNING
    # -------------------------------------------------------------------------
    def sign_order(
        self,
        order: Order,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:

        try:
            # #region agent log
            _opt = options or {}
            _neg = _opt.get("neg_risk", False)
            _use_neg = bool(_neg)
            _domain = self.EXCHANGE_DOMAIN_NEG_RISK if _use_neg else self.EXCHANGE_DOMAIN_REGULAR
            _vc = _domain.get("verifyingContract", "")
            _debug_log_path().open("a").write(
                __import__("json").dumps({"id": "sign_order_enter", "timestamp": int(__import__("time").time() * 1000), "location": "signer.py:sign_order", "message": "sign_order options and domain", "data": {"neg_risk": _neg, "verifyingContract": _vc, "maker": order.maker, "signer": self.address}, "runId": "debug", "hypothesisId": "H1_H3"}) + "\n"
            )
            # #endregion
            message = {
                "salt": secrets.randbits(256),
                "maker": order.maker,
                "signer": self.address,
                "taker": ZERO_ADDRESS,
                "tokenId": int(order.token_id),
                "makerAmount": int(order.maker_amount),
                "takerAmount": int(order.taker_amount),
                "expiration": int(order.expiration),
                "nonce": int(order.nonce),
                "feeRateBps": int(order.fee_rate_bps),
                "side": int(order.side_value),
                "signatureType": int(order.signature_type),
            }

            # #region agent log
            _debug_log_path().open("a").write(
                __import__("json").dumps({"id": "sign_order_message_types", "timestamp": int(__import__("time").time() * 1000), "location": "signer.py:sign_order", "message": "order message value types", "data": {k: type(v).__name__ for k, v in message.items()}, "runId": "debug", "hypothesisId": "H2"}) + "\n"
            )
            # #endregion

            # build typed data for EIP-712 (domain by neg_risk)
            signable = encode_typed_data(
                domain_data=_domain,
                message_types=self.ORDER_TYPES,
                message_data=message,
            )

            signed = self.wallet.sign_message(signable)

            out_order = {k: str(v) for k, v in message.items()}
            # #region agent log
            _debug_log_path().open("a").write(
                __import__("json").dumps({"id": "sign_order_return_types", "timestamp": int(__import__("time").time() * 1000), "location": "signer.py:sign_order", "message": "returned order value types", "data": {k: type(v).__name__ for k, v in out_order.items()}, "runId": "debug", "hypothesisId": "H2"}) + "\n"
            )
            # #endregion
            return {
                "order": out_order,
                "signature": "0x" + signed.signature.hex(),
                "signer": self.address,
            }

        except Exception as e:
            raise SignerError(f"Failed to sign order: {e}")

    # -------------------------------------------------------------------------
    # HELPER
    # -------------------------------------------------------------------------
    def sign_order_dict(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        maker: str,
        nonce: Optional[int] = None,
        fee_rate_bps: int = 0,
        expiration: Optional[int] = None,
    ) -> Dict[str, Any]:
        order = Order(
            token_id=token_id,
            price=price,
            size=size,
            side=side,
            maker=maker,
            nonce=nonce,
            fee_rate_bps=fee_rate_bps,
            signature_type=2,
            expiration=expiration,
        )
        return self.sign_order(order)

    def sign_message(self, message: str) -> str:
        signable = encode_defunct(text=message)
        signed = self.wallet.sign_message(signable)
        return "0x" + signed.signature.hex()

# alias
WalletSigner = OrderSigner
