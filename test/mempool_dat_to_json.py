from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from daChain.core.constants import TXID_SIZE


from  daChain.core.constants import (
    TXIN_PREV_TXID_SIZE,
    TXIN_PUBK_SIZE,
    TXIN_SIG_SIZE,
    TXOUT_PUBKHASH_SIZE,
)




def _read_u32(raw: bytes, offset: int) -> tuple[int, int]:
    next_offset = offset + 4
    if next_offset > len(raw):
        raise ValueError(f"u32 read out of range: offset={offset}, len={len(raw)}")
    return int.from_bytes(raw[offset:next_offset], "big"), next_offset


def _read_bytes(raw: bytes, offset: int, size: int, field_name: str) -> tuple[bytes, int]:
    next_offset = offset + size
    if next_offset > len(raw):
        raise ValueError(
            f"{field_name} read out of range: offset={offset}, size={size}, len={len(raw)}"
        )
    return raw[offset:next_offset], next_offset


def parse_tx_dat(raw: bytes) -> dict:
    offset = 0

    txid, offset = _read_bytes(raw, offset, TXID_SIZE, "txid")

    input_count, offset = _read_u32(raw, offset)
    inputs: list[dict] = []
    for idx in range(input_count):
        prev_txid, offset = _read_bytes(raw, offset, TXIN_PREV_TXID_SIZE, "prev_txid")
        prev_out_index, offset = _read_u32(raw, offset)
        pubk, offset = _read_bytes(raw, offset, TXIN_PUBK_SIZE, "pubK")
        sig, offset = _read_bytes(raw, offset, TXIN_SIG_SIZE, "sig")

        inputs.append(
            {
                "index": idx,
                "prev_txid": prev_txid.hex(),
                "prev_out_index": prev_out_index,
                "pubK": pubk.hex(),
                "sig": sig.hex(),
            }
        )

    output_count, offset = _read_u32(raw, offset)
    outputs: list[dict] = []
    for idx in range(output_count):
        asset_id, offset = _read_u32(raw, offset)
        pubkhash, offset = _read_bytes(raw, offset, TXOUT_PUBKHASH_SIZE, "pubKhash")
        portion, offset = _read_u32(raw, offset)

        outputs.append(
            {
                "index": idx,
                "asset_id": asset_id,
                "pubKhash": pubkhash.hex(),
                "portion": portion,
            }
        )

    if offset != len(raw):
        raise ValueError(
            f"trailing bytes found: parsed={offset}, total={len(raw)}, trailing={len(raw) - offset}"
        )

    return {
        "txid": txid.hex(),
        "input_count": input_count,
        "inputs": inputs,
        "output_count": output_count,
        "outputs": outputs,
        "raw_size": len(raw),
    }


def convert_one_file(dat_path: Path, out_dir: Path) -> Path:
    raw = dat_path.read_bytes()
    tx_json = parse_tx_dat(raw)

    out_path = out_dir / f"{dat_path.stem}.json"
    out_path.write_text(json.dumps(tx_json, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="mempool tx .dat 파일을 JSON으로 변환합니다."
    )
    parser.add_argument(
        "--mempool-dir",
        type=Path,
        default=Path("full-node/FN004/mempool"),
        help=".dat 파일이 있는 mempool 디렉터리",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("test/output"),
        help="변환된 JSON 저장 디렉터리",
    )
    args = parser.parse_args()

    mempool_dir = args.mempool_dir
    if not mempool_dir.exists() or not mempool_dir.is_dir():
        raise SystemExit(f"invalid mempool dir: {mempool_dir}")

    dat_files = sorted(mempool_dir.glob("*.dat"))
    if not dat_files:
        raise SystemExit(f"no .dat files found in: {mempool_dir}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] input dir : {mempool_dir}")
    print(f"[INFO] output dir: {args.out_dir}")
    for dat_file in dat_files:
        out_path = convert_one_file(dat_file, args.out_dir)
        print(f"[OK] {dat_file.name} -> {out_path}")


if __name__ == "__main__":
    main()
