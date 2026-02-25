"""
Time Momentum Strategy - Trade 5-Minute Markets based on Time and Price

Strategy Logic:
1. Auto-discover current 5-minute market for selected coin
2. Monitor remaining time and outcome prices
3. Trigger condition:
   - Remaining time < threshold_seconds (e.g. 30s)
   - Either outcome price in (price_min, price_max), e.g. (0.90, 0.98)
4. Execute BUY order on the triggered outcome

Usage:
    from strategies.time_momentum import TimeMomentumStrategy, TimeMomentumConfig

    strategy = TimeMomentumStrategy(bot, config)
    await strategy.run()
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from claim_rewards import run_redeem_all
from lib.console import Colors, format_countdown
from lib.market_manager import MarketInfo
from strategies.base import BaseStrategy, StrategyConfig
from src.bot import TradingBot
from src.websocket_client import OrderbookSnapshot


@dataclass
class TimeMomentumConfig(StrategyConfig):
    """Time momentum strategy configuration."""
    
    # Override defaults for 5m strategy
    coin: str = "BTC"
    market_duration: int = 5  # 5 minutes
    
    # Trigger settings
    time_threshold_seconds: int = 30
    price_min: float = 0.90  # trigger when outcome price > min
    price_max: float = 0.98  # and outcome price < max
    trade_amount: float = 10.0  # USDC to bet
    
    # Safety
    max_slippage: float = 0.05


class TimeMomentumStrategy(BaseStrategy):
    """
    Time Momentum Strategy.
    
    Monitors 5-minute markets and aggressively enters when 
    one side dominates near expiration.
    """

    def __init__(self, bot: TradingBot, config: TimeMomentumConfig):
        """Initialize time momentum strategy."""
        # Force correct duration in market manager
        super().__init__(bot, config)
        self.market.duration = config.market_duration

        self.tm_config = config
        self.has_traded_current_market = False
        
        # Setup file logging
        self._setup_file_logging()
        
        self.market.on_before_market_switch(self._before_market_switch)

    def _setup_file_logging(self):
        """Initialize local file logging."""
        log_dir = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(log_dir, f"time_momentum_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        self.file_logger = logging.getLogger(f"TimeMomentum_{id(self)}")
        self.file_logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate handlers
        if not self.file_logger.handlers:
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            self.file_logger.addHandler(fh)
            
        self.log(f"Strategy initialized. Logging to {log_file}", "info")

    def log(self, msg: str, level: str = "info") -> None:
        """Override base log to include file logging and timestamps."""
        # Call base class log for TUI/Console
        super().log(msg, level)
        
        # Map levels to standard logging levels
        level_map = {
            "info": logging.INFO,
            "success": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "trade": logging.INFO
        }
        log_level = level_map.get(level, logging.INFO)
        
        # Write to file if logger exists
        if hasattr(self, 'file_logger'):
            # Only log significant events to file to avoid bloat
            self.file_logger.log(log_level, f"[{level.upper()}] {msg}")

    async def _run_claim(self) -> None:
        """Run on-chain redeem_all in a thread; log result."""
        try:
            success, msg = await asyncio.to_thread(run_redeem_all)
            if success:
                self.log(f"Claim/redeem: {msg}", "info")
            else:
                self.log(f"Claim skipped or failed: {msg}", "warning")
        except Exception as e:
            self.log(f"Claim error: {e}", "warning")

    async def on_start(self) -> None:
        """Check claim on strategy start."""
        self.log("Checking claim (redeem) on start...", "info")
        await self._run_claim()

    async def _before_market_switch(
        self, old_market: Optional[MarketInfo], new_market: MarketInfo
    ) -> None:
        """Run before market switch: settle/claim for the ending market."""
        if old_market:
            await self._check_resolved_and_claim(old_market.slug)

    async def on_market_ending(self, slug: str) -> None:
        """Settle/claim for ending market before refresh (when run loop triggers switch)."""
        await self._check_resolved_and_claim(slug)

    async def on_book_update(self, snapshot: OrderbookSnapshot) -> None:
        """Handle orderbook update."""
        pass

    async def on_tick(self, prices: Dict[str, float]) -> None:
        """Check triggers on each tick."""
        try:
            if not self.is_connected or not self.current_market:
                return

            # Check if we already traded this market slug to avoid double entry
            # (This simple flag resets on market change)
            if self.has_traded_current_market:
                return

            # 1. Check Time Remaining
            mins, secs = self.current_market.get_countdown()
            if mins < 0:
                return
                
            remaining_seconds = mins * 60 + secs
            if remaining_seconds > self.tm_config.time_threshold_seconds:
                return
                
            # 2. Check Price: either up or down in (price_min, price_max)
            triggered_side = None
            current_price = 0.0
            pmin = self.tm_config.price_min
            pmax = self.tm_config.price_max

            up_price = prices.get("up", 0.0)
            down_price = prices.get("down", 0.0)

            # Log prices if we are in the time threshold but haven't traded yet
            if remaining_seconds <= self.tm_config.time_threshold_seconds:
                # Only log every few seconds to avoid file bloat
                if int(remaining_seconds) % 5 == 0 and abs(remaining_seconds - round(remaining_seconds)) < 0.1:
                    self.file_logger.info(
                        f"DEBUG: Time={remaining_seconds}s, Prices: UP={up_price:.4f}, DOWN={down_price:.4f}, Range=({pmin:.2f}, {pmax:.2f})"
                    )

            if pmin < up_price < pmax:
                triggered_side = "up"
                current_price = up_price
            elif pmin < down_price < pmax:
                triggered_side = "down"
                current_price = down_price

            if triggered_side:
                self.log(
                    f"TRIGGER: Time {remaining_seconds}s < {self.tm_config.time_threshold_seconds}s "
                    f"AND {triggered_side.upper()} Price {current_price:.2f} in ({pmin:.2f}, {pmax:.2f})",
                    "trade"
                )
                
                # Execute Trade
                # We override the base execute_buy to use specific sizing/price logic if needed, 
                # or just call it. Base execute_buy uses config.size.
                # Let's verify size config.
                
                # Adjust config size to match trade_amount if needed
                self.config.size = self.tm_config.trade_amount
                
                success = await self.execute_buy(triggered_side, current_price)
                if success:
                    self.has_traded_current_market = True
                else:
                    self.log(f"Triggered but order failed for {triggered_side}", "error")
        except Exception as e:
            self.log(f"Error in on_tick: {e}", "error")
            if hasattr(self, 'file_logger'):
                self.file_logger.exception("Exception in on_tick")

    async def execute_buy(self, side: str, current_price: float) -> bool:
        """
        Execute market buy order (Aggressive Fill).
        """
        token_id = self.token_ids.get(side)
        if not token_id:
            self.log(f"No token ID for {side}", "error")
            return False

        # Calculate size based on trade amount (not share count)
        # user config.trade_amount is in USDC
        # If we buy at 1.0 (worst case), size = amount
        # If we buy at 0.5, size = amount / 0.5
        # To be safe and ensure we spend ~amount, we can set size = amount / current_price 
        # but cap price at 1.0.
        
        # User wants "Market Buy". 
        # We will set Limit Price to 1.0 to cross the entire book.
        # But we must be careful with size. 
        # CLOB `size` is number of shares.
        # If we want to spend $10, and price is 0.5, we want 20 shares.
        # If we set price 1.0, and it fills at 0.5, we spend $10.
        # If it fills at 0.99, we spend $19.8.
        # Wait, if we set price 1.0, we are willing to pay $1 per share.
        # To spend exactly $10 USDC, we should buy 10 shares at price 1.0.
        # But if the actual price is 0.1, we only spend $1.
        
        # User said "buy at market price". 
        # Usually checking `current_price` from the book.
        # Let's trust `current_price` from the last tick for size calculation, 
        # but set limit price to 1.0 to ensure fill.
        
        # Adjust size calculation:
        # If we want to spend X USDC, and we expect price P.
        # Shares = X / P.
        # If we limit at 1.0, and fill at P, Cost = (X/P) * P = X. Matches.
        # If we fill at 1.0 (slippage), Cost = (X/P) * 1.0 = X/P. This could be much larger than X if P is small.
        
        # Safer approach:
        # Use a limit price slightly higher than current ask, or just 1.0 if user really wants "Market".
        # Given "buy at market price not listed price", I'll use 1.0 but calculate size conservatively based on 0.99 
        # OR just calculate size based on current_price + slippage buffer.
        
        # The user's log showed `BUY UP @ 0.99`. This is already aggressive.
        # Maybe they mean "Order failed" is the problem?
        # Yes, "Order failed" is the real problem.
        # But they also said "still should buy at market price".
        
        # I will set price to 0.99 (safe limit) and size = trade_amount / current_price.
        # Round size to 2 decimal places to avoid precision issues.
        
        limit_price = 0.99
        # Calculate shares based on current price (to spend approx trade_amount)
        # But if we really want to buy, we should handle the fact that we might pay up to 0.99.
        # If we set size = amount / current_price, and pay 0.99, we spend more than amount.
        # Conservative: size = amount / limit_price. But then we might spend less if fill is better.
        # Aggressive (spend target amount): size = amount / current_price.
        
        # User wants to trade `trade_amount` (USDC).
        # We'll stick to the original calculation but round it.
        
        raw_size = self.tm_config.trade_amount / max(current_price, 0.01)
        size = round(raw_size, 2)
        
        self.log(f"MARKET BUY {side.upper()} @ {current_price:.4f} (Limit: {limit_price}) size={size}", "trade")

        raw = self.market.gamma.get_market_by_token_id(token_id) if getattr(self.market, "gamma", None) else None
        if raw:
            market_options = {
                "tick_size": str(raw.get("minimumTickSize", raw.get("tickSize", "0.01"))),
                "neg_risk": raw.get("negRisk", True),
            }
        else:
            market_options = {"tick_size": "0.01", "neg_risk": True}

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if self.current_market and self.current_market.has_ended():
                self.log("Market ended, cancel order attempt", "warning")
                return False
            result = await self.bot.place_order(
                token_id=token_id,
                price=limit_price,
                size=size,
                side="BUY",
                market_options=market_options,
            )
            if result.success:
                oid = result.order_id or "(placed)"
                self.log(f"Order placed: {oid}", "success")
                market_slug = self.current_market.slug if self.current_market else None
                self.positions.open_position(
                    side=side,
                    token_id=token_id,
                    entry_price=current_price,
                    size=size,
                    order_id=result.order_id,
                    market_slug=market_slug,
                )
                return True
            if attempt < max_attempts:
                self.log(f"Order failed (attempt {attempt}/{max_attempts}): {result.message}, retrying...", "warning")
                await asyncio.sleep(1.0)

        self.log(f"Order failed after {max_attempts} attempts: {result.message}", "error")
        if hasattr(self, 'file_logger'):
            self.file_logger.error(f"FINAL ORDER FAILURE: {result.message} - Response: {getattr(result, 'raw_response', 'N/A')}")
        return False

    def on_market_change(self, old_slug: str, new_slug: str) -> None:
        """Reset trade flag (claim already ran in before_switch)."""
        self.has_traded_current_market = False
        msg = f"New market detected: {new_slug} (Prev: {old_slug}). Resetting trade flag."
        self.log(msg, "info")
        if hasattr(self, 'file_logger'):
            self.file_logger.info("=" * 50)
            self.file_logger.info(f"MARKET START: {new_slug}")
            self.file_logger.info("=" * 50)

    async def _check_resolved_and_claim(self, resolved_slug: str) -> None:
        """If we have a position from the resolved market, check winner and claim if profitable."""
        positions = self.positions.get_positions_by_market(resolved_slug)
        if not positions:
            self.log(f"No positions to settle for {resolved_slug}", "info")
            return
        self.log(f"Settling {len(positions)} position(s) for {resolved_slug}...", "info")
        winner = None
        for attempt in range(5):
            try:
                winner = await asyncio.to_thread(
                    self.market.gamma.get_resolved_winner,
                    resolved_slug,
                )
                if winner is not None:
                    break
            except Exception as e:
                self.log(f"Resolution check failed for {resolved_slug}: {e}", "warning")
            if attempt < 4:
                await asyncio.sleep(3.0)
        for position in positions:
            if winner and position.side == winner:
                pnl = (1.0 - position.entry_price) * position.size
                self.log(
                    f"Resolved WIN: {resolved_slug} {position.side.upper()} PnL ~${pnl:.2f}",
                    "success",
                )
                await self.bot.claim_winnings(
                    market_slug=resolved_slug,
                    side=position.side,
                    token_id=position.token_id,
                    size=position.size,
                )
            elif winner:
                pnl = (0.0 - position.entry_price) * position.size
                self.log(
                    f"Resolved LOSS: {resolved_slug} {position.side.upper()} PnL ${pnl:.2f}",
                    "warning",
                )
            else:
                pnl = 0.0
                self.log(
                    f"Resolved unknown for {resolved_slug} (API not ready), closing position.",
                    "warning",
                )
            self.positions.close_position(position.id, realized_pnl=pnl)
        self.log("Running on-chain redeem at endtime...", "info")
        await self._run_claim()

    def render_status(self, prices: Dict[str, float]) -> None:
        """Render TUI status display."""
        lines = []

        # Header
        ws_status = f"{Colors.GREEN}WS{Colors.RESET}" if self.is_connected else f"{Colors.RED}REST{Colors.RESET}"
        countdown = self._get_countdown_str()
        stats = self.positions.get_stats()
        
        total_pnl = stats.get("total_pnl", 0.0)
        pnl_str = f"+${total_pnl:.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):.2f}"
        pnl_color = Colors.GREEN if total_pnl >= 0 else (Colors.RED if total_pnl < 0 else Colors.RESET)
        dm = self.tm_config.market_duration
        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
        lines.append(
            f"{Colors.CYAN}[{self.config.coin} {dm}m]{Colors.RESET} [{ws_status}] "
            f"Ends: {countdown} | Threshold: <{self.tm_config.time_threshold_seconds}s | PnL: {pnl_color}{pnl_str}{Colors.RESET}"
        )
        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")

        # Prices
        up_price = prices.get("up", 0.0)
        down_price = prices.get("down", 0.0)
        
        # Format similar to user request: Outcome Prices: [p1, p2]
        # Assuming [Up, Down] order for consistency
        outcome_prices_list = [up_price, down_price]
        
        pmin, pmax = self.tm_config.price_min, self.tm_config.price_max
        up_in = pmin < up_price < pmax
        down_in = pmin < down_price < pmax
        up_color = Colors.GREEN if up_in else Colors.RESET
        down_color = Colors.RED if down_in else Colors.RESET

        lines.append(f"Outcome Prices: {outcome_prices_list}")
        lines.append(f"Price range: ({pmin:.2f}, {pmax:.2f})")
        lines.append(
            f"UP:   {up_color}{up_price:.4f}{Colors.RESET}"
        )
        lines.append(
            f"DOWN: {down_color}{down_price:.4f}{Colors.RESET}"
        )
        lines.append("-" * 80)

        # Status
        if self.has_traded_current_market:
            traded_msg = f"{Colors.YELLOW}TRADED - WAITING FOR END{Colors.RESET}" 
        else:
            traded_msg = f"{Colors.GREEN}SCANNING{Colors.RESET}"
            
        lines.append(f"Status: {traded_msg}")
        
        # Recent logs
        if self._log_buffer.messages:
            lines.append("-" * 80)
            lines.append(f"{Colors.BOLD}Recent Events:{Colors.RESET}")
            for msg in self._log_buffer.get_messages():
                lines.append(f"  {msg}")

        # Render
        output = "\033[H\033[J" + "\n".join(lines)
        print(output, flush=True)

    def _get_countdown_str(self) -> str:
        """Get formatted countdown string."""
        market = self.current_market
        if not market:
            return "--:--"

        mins, secs = market.get_countdown()
        color = Colors.RED if (mins * 60 + secs) < self.tm_config.time_threshold_seconds else Colors.GREEN
        return f"{color}{format_countdown(mins, secs)}{Colors.RESET}"
