#!/usr/bin/env python3
"""
Claim Looper - Periodically check and redeem resolved positions.

Every N seconds runs on-chain redeem_all (same as run_time_momentum strategy).
Use when running the bot headless or to collect winnings without the strategy UI.

Usage:
    python scripts/claim_looper.py
    python scripts/claim_looper.py --interval 120
"""

import os
import sys
import argparse
import asyncio
import logging
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.console import Colors
from claim_rewards import run_redeem_all


async def run_claim_once() -> tuple[bool, str]:
    """Run redeem_all in a thread (same as time_momentum._run_claim)."""
    try:
        success, msg = await asyncio.to_thread(run_redeem_all)
        return success, msg
    except Exception as e:
        return False, str(e)


async def loop_claim(interval_seconds: float) -> None:
    """Loop: wait interval, run redeem_all, print result."""
    print(f"{Colors.BOLD}Claim Looper{Colors.RESET} – checking every {interval_seconds:.0f}s (Ctrl+C to stop)\n")
    while True:
        success, msg = await run_claim_once()
        if success:
            if "Redeemed" in msg or "redeemed" in msg.lower():
                print(f"{Colors.GREEN}[OK] {msg}{Colors.RESET}")
            else:
                print(f"[--] {msg}")
        else:
            print(f"{Colors.RED}[FAIL] {msg}{Colors.RESET}")
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Periodically redeem resolved Polymarket positions (claim winnings)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Seconds between redeem checks (default: 60)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    if not os.getenv("POLY_PRIVATE_KEY") or not os.getenv("POLY_SAFE_ADDRESS"):
        print(f"{Colors.RED}Error: POLY_PRIVATE_KEY and POLY_SAFE_ADDRESS must be set{Colors.RESET}")
        print("Set them in .env or export before running.")
        sys.exit(1)

    try:
        asyncio.run(loop_claim(args.interval))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
