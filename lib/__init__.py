"""
Lib - Reusable Components Library

This package provides reusable components for trading strategies and applications:

- console: Terminal output utilities (colors, formatting)
- market_manager: Market discovery and WebSocket management
- market_scanner: Scan markets by win probability and category
- price_tracker: Price history and pattern detection
- position_manager: Position tracking with TP/SL

Usage:
    from lib import MarketManager, PriceTracker, PositionManager
    from lib import scan_markets, ScanResult
    from lib.console import Colors, print_colored
"""

from lib.console import Colors
from lib.market_manager import MarketManager, MarketInfo
from lib.market_scanner import ScanResult, scan_markets, scan_bitcoin_5min_markets
from lib.price_tracker import PriceTracker, PricePoint, FlashCrashEvent
from lib.position_manager import PositionManager, Position

__all__ = [
    "Colors",
    "MarketManager",
    "MarketInfo",
    "ScanResult",
    "scan_markets",
    "scan_bitcoin_5min_markets",
    "PriceTracker",
    "PricePoint",
    "FlashCrashEvent",
    "PositionManager",
    "Position",
]
