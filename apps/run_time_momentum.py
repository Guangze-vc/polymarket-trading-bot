#!/usr/bin/env python3
"""
时间动量策略运行器

用于在 5 分钟市场上运行时间动量策略的入口点。

用法:
    python apps/run_time_momentum.py --market btc-updown-5m
    python apps/run_time_momentum.py --market eth-updown-15m --amount 10
    python apps/run_time_momentum.py --market btc-updown-5m --time 30 --min 0.90 --max 0.98
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Suppress noisy logs
logging.getLogger("src.websocket_client").setLevel(logging.WARNING)
logging.getLogger("src.bot").setLevel(logging.WARNING)

# Auto-load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.console import Colors
from src.bot import TradingBot
from src.config import Config
from strategies.time_momentum import TimeMomentumStrategy, TimeMomentumConfig

MARKET_TO_COIN_DURATION = {
    "btc-updown-5m": ("BTC", 5),
    "btc-updown-15m": ("BTC", 15),
    "eth-updown-15m": ("ETH", 15),
    "sol-updown-15m": ("SOL", 15),
    "xrp-updown-15m": ("XRP", 15),
}


async def run_strategy(args):
    """Run the strategy."""
    # Check environment
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    safe_address = os.environ.get("POLY_SAFE_ADDRESS")

    if not private_key or not safe_address:
        print(f"{Colors.RED}错误: 必须设置 POLY_PRIVATE_KEY 和 POLY_SAFE_ADDRESS{Colors.RESET}")
        print("请在 .env 文件中设置或导出为环境变量")
        sys.exit(1)

    config = Config.from_env()
    if not config.safe_address and safe_address:
        config.safe_address = safe_address
    bot = TradingBot(config=config, private_key=private_key)

    if not bot.is_initialized():
        print(f"{Colors.RED}错误: 机器人初始化失败{Colors.RESET}")
        sys.exit(1)

    coin, duration = MARKET_TO_COIN_DURATION[args.market]
    strategy_config = TimeMomentumConfig(
        coin=coin,
        trade_amount=args.amount,
        time_threshold_seconds=args.time,
        price_min=args.min,
        price_max=args.max,
        market_duration=duration,
        size=args.amount,
        take_profit=100.0,
        stop_loss=100.0,
    )

    # Print configuration
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  时间动量策略 - {strategy_config.coin} {duration}分钟市场{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    print(f"当前配置:")
    print(f"  交易市场: {args.market} ({strategy_config.coin} {duration}分钟)")
    print(f"  代理地址 (资金账户): {config.safe_address[:10]}...{config.safe_address[-6:]}")
    print(f"  签名类型: {config.clob.signature_type} (0=EOA 1=Magic 2=代理)")
    print(f"  单笔交易金额: ${strategy_config.trade_amount:.2f}")
    print(f"  时间阈值: < {strategy_config.time_threshold_seconds}秒")
    print(f"  价格范围: ({strategy_config.price_min:.2f}, {strategy_config.price_max:.2f})")
    print()

    print()

    # Continuous Retry Loop
    while True:
        try:
            # Create and run strategy
            strategy = TimeMomentumStrategy(bot=bot, config=strategy_config)
            print(f"{Colors.GREEN}正在启动策略...{Colors.RESET}")
            
            await strategy.run()
            
            # If run returns, it means it stopped or failed to start
            print(f"{Colors.YELLOW}策略已停止。3秒后重试...{Colors.RESET}")
            await asyncio.sleep(3)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"\n{Colors.RED}错误: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
            print(f"{Colors.YELLOW}5秒后重试...{Colors.RESET}")
            await asyncio.sleep(5)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Polymarket 5分钟市场时间动量策略"
    )
    parser.add_argument(
        "--market",
        type=str,
        default="btc-updown-5m",
        choices=[
            "btc-updown-5m",
            "btc-updown-15m",
            "eth-updown-15m",
            "sol-updown-15m",
            "xrp-updown-15m",
        ],
        help="交易市场 (默认: btc-updown-5m)"
    )
    parser.add_argument(
        "--amount",
        type=float,
        default=10.0,
        help="单笔交易金额(USDC) (默认: 10.0)"
    )
    parser.add_argument(
        "--time",
        type=int,
        default=30,
        help="触发交易的时间阈值(秒) (默认: 30)"
    )
    parser.add_argument(
        "--min",
        type=float,
        default=0.90,
        help="触发交易的最低价格，结果必须 > min (默认: 0.90)"
    )
    parser.add_argument(
        "--max",
        type=float,
        default=0.98,
        help="触发交易最高价格，结果必须 < max (默认: 0.98)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试日志"
    )

    args = parser.parse_args()

    # Enable debug logging if requested
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("src.websocket_client").setLevel(logging.DEBUG)

    try:
        asyncio.run(run_strategy(args))
    except KeyboardInterrupt:
        print("\n操作已中断")
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
