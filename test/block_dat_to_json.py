from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from daChain.core.serialize import block_bytes_to_Block


def block_to_dict(block) -> dict:
    return {
        "header": {
            "block_height": block.header.block_height,
            "prev_hash": block.header.prev_hash.hex(),
            "nonce": block.header.nonce,
            "merkle_root": block.header.merkle_root.hex(),
        },
        "tx_count": block.tx_count,
        "txs": [
            {
                "txid": tx.txid.hex(),
                "input_count": tx.input_count,
                "inputs": [
                    {
                        "prev_txid": tx_in.prev_txid.hex(),
                        "prev_out_index": tx_in.prev_out_index,
                        "pubK": tx_in.pubK.hex(),
                        "sig": tx_in.sig.hex(),
                    }
                    for tx_in in tx.inputs
                ],
                "output_count": tx.output_count,
                "outputs": [
                    {
                        "asset_id": tx_out.asset_id,
                        "pubKhash": tx_out.pubKhash.hex(),
                        "portion": tx_out.portion,
                    }
                    for tx_out in tx.outputs
                ],
            }
            for tx in block.txs
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="block .dat파일 JSON 변환"
    )
    parser.add_argument(
        "--block-path",
        type=Path,
        default=Path("full-node/FN000/blocks/B0004_3.dat"),
        help="읽을 block .dat 경로",
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=Path("test/output/block_preview.json"),
        help="변환된 JSON 출력 경로",
    )
    args = parser.parse_args()

    if not args.block_path.exists() or not args.block_path.is_file():
        raise SystemExit(f"invalid block file: {args.block_path}")

    raw = args.block_path.read_bytes()
    block = block_bytes_to_Block(raw)
    block_json = block_to_dict(block)

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(json.dumps(block_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] block parsed: {args.block_path}")
    print(f"[OK] json saved : {args.out_path}")
    print(f"[INFO] height={block.header.block_height}, tx_count={block.tx_count}")


if __name__ == "__main__":
    main()