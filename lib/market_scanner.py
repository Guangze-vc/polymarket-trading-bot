"""
Market Scanner - Find markets with win probability above a threshold

Scans Gamma API for markets where the leading outcome's probability (price)
meets or exceeds a given percentage. Supports filtering by category (tag slug)
such as politics, sports, crypto, or all markets.

Usage:
    from lib.market_scanner import scan_markets, ScanResult

    results = scan_markets(min_probability=0.7, max_probability=0.9, category="politics", max_results=50, sort_order="desc")
    for r in results:
        print(r.slug, r.win_probability, r.leading_outcome)
"""

import requests
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.gamma_client import GammaClient


@dataclass
class ScanResult:
    """Single market scan result with key fields for high-win scanning."""

    slug: str
    question: str
    end_date: str  # Market end / resolution time, ISO format e.g. 2025-01-15T00:00:00Z
    leading_outcome: str
    win_probability: float
    outcomes: List[str]
    outcome_prices: List[float]
    volume: Optional[str] = None
    volume_num: Optional[float] = None  # Trading volume as number (from API volumeNum)
    liquidity: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None

    @property
    def win_probability_percent(self) -> float:
        """Win probability as 0-100 percentage."""
        return self.win_probability * 100.0

    @property
    def resolution_time(self) -> str:
        """Market resolution / settlement time, same as end_date."""
        return self.end_date


def _parse_json_field(value: Any) -> List[Any]:
    """Parse a field that may be a JSON string or a list."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            out = json.loads(value)
            return out if isinstance(out, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(value, list):
        return value
    return []


def _market_win_probability(market: Dict[str, Any]) -> tuple[float, str, List[str], List[float]]:
    """
    Get leading outcome and win probability from raw market.
    Returns (win_probability, leading_outcome, outcomes, outcome_prices).
    """
    prices_raw = market.get("outcomePrices", "[]")
    outcomes_raw = market.get("outcomes", "[]")
    prices = _parse_json_field(prices_raw)
    outcomes = _parse_json_field(outcomes_raw)

    prices_float: List[float] = []
    for p in prices:
        try:
            prices_float.append(float(p))
        except (TypeError, ValueError):
            prices_float.append(0.0)

    if not prices_float or not outcomes:
        return 0.0, "", outcomes if isinstance(outcomes[0], str) else [], prices_float

    max_idx = max(range(len(prices_float)), key=lambda i: prices_float[i])
    win_prob = prices_float[max_idx]
    leading = str(outcomes[max_idx]) if max_idx < len(outcomes) else ""
    return win_prob, leading, [str(o) for o in outcomes], prices_float


def scan_markets(
    min_probability: float,
    category: Optional[str] = None,
    max_results: int = 100,
    limit: Optional[int] = None,
    max_probability: Optional[float] = None,
    sort_order: str = "desc",
    client: Optional[GammaClient] = None,
) -> List[ScanResult]:
    """
    Scan for markets where current win probability is in [min_probability, max_probability].

    Args:
        min_probability: Minimum leading-outcome probability in 0-1 (e.g. 0.75 = 75%).
        category: None or "all" = all markets; else tag slug (e.g. "politics", "sports", "crypto").
        max_results: Maximum number of markets to return (used when limit is not set).
        limit: If set, cap the number of results to this value (overrides max_results when set).
        max_probability: If set, only include markets with win_probability <= this (0-1). Enables range filter.
        sort_order: Default "desc" = highest probability first (top to bottom). "asc" = lowest first.
        client: Optional GammaClient; if None, a default client is used.

    Returns:
        List of ScanResult. By default sorted by win_probability descending (highest first).
        Use sort_order="asc" for lowest-first.
    """
    if client is None:
        client = GammaClient()

    cap = limit if limit is not None else max_results

    tag_id: Optional[int] = None
    if category and category.strip().lower() != "all":
        tag = client.get_tag_by_slug(category.strip().lower())
        if tag is None:
            return []
        raw_id = tag.get("id")
        if raw_id is not None:
            try:
                tag_id = int(raw_id) if not isinstance(raw_id, int) else raw_id
            except (ValueError, TypeError):
                return []

    results: List[ScanResult] = []
    page_size = min(100, cap)
    offset = 0

    while len(results) < cap:
        batch = client.list_markets(
            limit=page_size,
            offset=offset,
            tag_id=tag_id,
            closed=False,
        )
        if not batch:
            break

        for market in batch:
            if len(results) >= cap:
                break
            win_prob, leading_outcome, outcomes, outcome_prices = _market_win_probability(market)
            if win_prob < min_probability:
                continue
            if max_probability is not None and win_prob > max_probability:
                continue

            slug = market.get("slug") or ""
            question = market.get("question") or ""
            end_date = market.get("endDate") or market.get("end_date") or ""
            volume = market.get("volume")
            if volume is not None and not isinstance(volume, str):
                volume = str(volume)
            volume_num_raw = market.get("volumeNum") or market.get("volume_num")
            volume_num = None
            if volume_num_raw is not None:
                try:
                    volume_num = float(volume_num_raw)
                except (TypeError, ValueError):
                    pass
            liquidity = market.get("liquidity")
            if liquidity is not None and not isinstance(liquidity, (int, float)):
                try:
                    liquidity = float(liquidity)
                except (TypeError, ValueError):
                    liquidity = None

            results.append(
                ScanResult(
                    slug=slug,
                    question=question,
                    end_date=end_date,
                    leading_outcome=leading_outcome,
                    win_probability=win_prob,
                    outcomes=outcomes,
                    outcome_prices=outcome_prices,
                    volume=volume,
                    volume_num=volume_num,
                    liquidity=liquidity,
                )
            )

        offset += len(batch)
        if len(batch) < page_size:
            break

    reverse = sort_order.strip().lower() in ("desc", "descendant")
    results.sort(key=lambda r: r.win_probability, reverse=reverse)
    return results


from datetime import datetime, timezone

def scan_bitcoin_5min_markets(
    min_probability: float = 0.0,
    max_probability: float = 1.0,
    client: Optional[GammaClient] = None,
) -> List[ScanResult]:
    """
    Scan specifically for 'Bitcoin Up or Down' markets with a ~5 minute duration.
    
    Filters:
    1. Slug must contain "btc-updown-5m".
    2. Market must be active (end_date > now).
    3. Returns the SINGLE "latest" (current/soonest active) market in a list.
    """
    if client is None:
        client = GammaClient()
    
    # Strategy: Construct event slug by timestamp
    now_ts = int(time.time())
    timestamp = now_ts - now_ts % 300
    event_slug = f"btc-updown-5m-{timestamp}"
    
    url = f"https://gamma-api.polymarket.com/events/slug/{event_slug}"
    
    candidates = []
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            event = resp.json()
            # Only consider if event is active? User snippet checks checking event["active"]
            if event.get("active"):
                candidates = event.get("markets", [])
    except Exception:
        pass

    # If no candidates found, fallback to generic search (optional, but let's stick to what works for now)
    # or return empty if primary method fails.
    if not candidates:
        return []

    # Current UTC time for expiration check
    now = datetime.now(timezone.utc)
        
    valid_markets: List[tuple[ScanResult, datetime]] = []

    for market in candidates:
        question = market.get("question", "")
        slug = market.get("slug", "")
        
        # 3. Expiration Check
        end_date_str = market.get("endDate")
        if not end_date_str:
            continue
            
        try:
            # Handle ISO format. "Z" -> "+00:00" for compatibility
            end_date_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            if end_date_dt <= now:
                continue
        except ValueError:
            continue
        
        # Initial extraction from market object
        win_prob, leading_outcome, outcomes, outcome_prices = _market_win_probability(market)
        bb_raw = market.get("bestBid")
        ba_raw = market.get("bestAsk")

        # --- CLOB PRICE FETCHING ---
        try:
            # Extract Token IDs
            clob_token_ids_raw = market.get("clobTokenIds", "[]")
            token_ids = _parse_json_field(clob_token_ids_raw)
            
            # Fetch prices from CLOB for each outcome
            clob_prices = {}
            for outcome, tid in zip(outcomes, token_ids):
                if not tid:
                     continue
                try:
                    r = requests.get(
                        f"https://clob.polymarket.com/price?token_id={tid}&side=BUY",
                        timeout=5
                    )
                    if r.status_code == 200:
                        data = r.json()
                        price_val = data.get("price")
                        if price_val is not None:
                             clob_prices[outcome] = float(price_val)
                except Exception:
                    pass

            # If we successfully fetched CLOB prices, update prob/prices
            if clob_prices:
                # Reconstruct outcome_prices list based on outcomes order
                new_outcome_prices = []
                for o in outcomes:
                    new_outcome_prices.append(clob_prices.get(str(o), 0.0))
                
                outcome_prices = new_outcome_prices
                
                if outcome_prices:
                    max_idx = max(range(len(outcome_prices)), key=lambda i: outcome_prices[i])
                    win_prob = outcome_prices[max_idx]
                    leading_outcome = outcomes[max_idx] if max_idx < len(outcomes) else ""
                    
                    # Update best bid to match the winning probability (approx)
                    # The user specifically wanted the "price" from CLOB
                    bb_raw = win_prob 
        except Exception as e:
            pass
        # ---------------------------

        if win_prob < min_probability:
            continue
        if max_probability is not None and win_prob > max_probability:
            continue
            
        volume = market.get("volume")
        if volume is not None and not isinstance(volume, str):
            volume = str(volume)
        
        volume_num = None
        v_num_raw = market.get("volumeNum") or market.get("volume_num")
        if v_num_raw is not None:
             try:
                 volume_num = float(v_num_raw)
             except (TypeError, ValueError):
                 pass
                 
        liquidity = None
        liq_raw = market.get("liquidity")
        if liq_raw is not None:
            try:
                liquidity = float(liq_raw)
            except (TypeError, ValueError):
                pass

        scan_res = ScanResult(
            slug=slug,
            question=question,
            end_date=end_date_str,
            leading_outcome=leading_outcome,
            win_probability=win_prob,
            outcomes=outcomes,
            outcome_prices=outcome_prices,
            volume=volume,
            volume_num=volume_num,
            liquidity=liquidity,
            best_bid=bb_raw,
            best_ask=ba_raw,
        )
        valid_markets.append((scan_res, end_date_dt))
        
    # Sort by end_date ascending (soonest expiration first = Current Active)
    valid_markets.sort(key=lambda x: x[1])
    
    if not valid_markets:
        return []
        
    # Return the single best candidate
    return [valid_markets[0][0]]


