import argparse
from daChain.node.genesis import initiate_dachain, initiate_full_nodes

def main() -> None:
    parser = argparse.ArgumentParser(description="Unified initiate command")
    sub = parser.add_subparsers(dest="target", required=True)

    p_chain = sub.add_parser("daChain")
    p_chain.add_argument("N", type=int)

    p_nodes = sub.add_parser("fullNodes")
    p_nodes.add_argument("L", type=int)

    args = parser.parse_args()

    if args.target == "daChain":
        if args.N <= 0:
            raise SystemExit("N must be > 0")
        initiate_dachain(args.N)

    elif args.target == "fullNodes":
        if args.L <= 1:
            raise SystemExit("L must be > 1")
        initiate_full_nodes(args.L)


if __name__ == "__main__":
    main()
