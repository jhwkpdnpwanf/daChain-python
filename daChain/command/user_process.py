import argparse

from daChain.node.user import run_user_process


def main() -> None:
    parser = argparse.ArgumentParser(description="Run random user transaction generator")
    parser.add_argument("--error-rate", type=float, default=0.2, help="Corrupted tx ratio (0.0~1.0)")
    parser.add_argument("--interval", type=float, default=12.0, help="Loop interval seconds")
    parser.add_argument("--batch-size", type=int, default=5, help="Transactions per loop")
    args = parser.parse_args()

    if not (0.0 <= args.error_rate <= 1.0):
        raise SystemExit("--error-rate must be between 0.0 and 1.0")
    if args.interval <= 0:
        raise SystemExit("--interval must be > 0")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")

    run_user_process(error_rate=args.error_rate, interval=args.interval, batch_size=args.batch_size)


if __name__ == "__main__":
    main()