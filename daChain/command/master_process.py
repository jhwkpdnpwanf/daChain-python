from __future__ import annotations

import argparse
import time
from pathlib import Path

from daChain.core.crypto import make_pubkey_hash, sha256, verify
from daChain.core.serialize import block_bytes_to_Block, tx_body_to_bytes, txin_body_without_sig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FULLNODE_DIR = PROJECT_ROOT / "full-node"


def _load_node_names() -> list[str]:
    return sorted([p.name for p in FULLNODE_DIR.glob("FN*") if p.is_dir()])


def _load_chain_blocks(node_name: str):
    blocks_dir = FULLNODE_DIR / node_name / "blocks"
    block_files = sorted(blocks_dir.glob("B*.dat"))
    return [block_bytes_to_Block(p.read_bytes()) for p in block_files]


def _build_utxo_until(blocks, stop_height: int | None = None) -> dict:
    utxos: dict[str, dict] = {}
    for block in blocks:
        if stop_height is not None and block.header.block_height > stop_height:
            break
        for tx in block.txs:
            for tx_in in tx.inputs:
                utxos.pop(f"{tx_in.prev_txid.hex()}:{tx_in.prev_out_index}", None)
            for idx, out in enumerate(tx.outputs):
                utxos[f"{tx.txid.hex()}:{idx}"] = {
                    "asset_id": int(out.asset_id),
                    "portion": int(out.portion),
                    "pubKhash": out.pubKhash,
                }
    return utxos


def _short_hex(value: str, size: int = 32) -> str:
    if len(value) <= size:
        return value
    return f"{value[:size]}..."


def _ok_text(ok: bool) -> str:
    return "OK" if ok else "FAIL"


def verify_transaction(node_name: str) -> None:
    blocks = _load_chain_blocks(node_name)
    if len(blocks) < 2:
        print(f"[ Transaction Verification: {node_name} ]")
        print("-" * 50)
        print("Status: INVALID (no mined block beyond genesis)")
        print("-" * 50)
        return

    tip = blocks[-1]
    if not tip.txs:
        print(f"[ Transaction Verification: {node_name} ]")
        print("-" * 50)
        print("Status: INVALID (latest block has no tx)")
        print("-" * 50)
        return

    tx = tip.txs[0]
    txid_hex = tx.txid.hex()
    utxos_before = _build_utxo_until(blocks, stop_height=tip.header.block_height - 1)

    check_results: list[bool] = []

    recomputed_txid = sha256(tx_body_to_bytes(tx.inputs, tx.outputs))
    txid_ok = recomputed_txid == tx.txid
    check_results.append(txid_ok)

    outpoint_lines: list[str] = []
    pkh_lines: list[str] = []
    sig_lines: list[str] = []

    all_inputs_unspent = True
    all_pkh_match = True
    all_sig_ok = True

    input_asset_ids: list[int] = []
    input_portion_sum = 0

    for tx_in in tx.inputs:
        outpoint = f"{tx_in.prev_txid.hex()}:{tx_in.prev_out_index}"
        utxo = utxos_before.get(outpoint)

        is_unspent = utxo is not None
        all_inputs_unspent = all_inputs_unspent and is_unspent
        outpoint_lines.append(
            f"   - Outpoint [{_short_hex(outpoint, 24)}]: {'Unspent' if is_unspent else 'Spent/Unknown'} ({_ok_text(is_unspent)})"
        )
        check_results.append(is_unspent)

        if not is_unspent:
            all_pkh_match = False
            all_sig_ok = False
            pkh_lines.append("   - Public Key Hash Match: FAIL (missing referenced outpoint)")
            sig_lines.append("   - Digital Signature Verification: FAIL (missing referenced outpoint)")
            check_results.extend([False, False])
            continue

        pkh_ok = make_pubkey_hash(tx_in.pubK) == utxo["pubKhash"]
        sig_ok = verify(tx_in.pubK, txin_body_without_sig(tx_in), tx_in.sig)
        all_pkh_match = all_pkh_match and pkh_ok
        all_sig_ok = all_sig_ok and sig_ok

        pkh_lines.append(f"   - Public Key Hash Match: {_ok_text(pkh_ok)}")
        sig_lines.append(f"   - Digital Signature Verification: {_ok_text(sig_ok)}")
        check_results.extend([pkh_ok, sig_ok])

        input_asset_ids.append(int(utxo["asset_id"]))
        input_portion_sum += int(utxo["portion"])

    output_asset_ids = {int(o.asset_id) for o in tx.outputs}
    output_portion_sum = sum(int(o.portion) for o in tx.outputs)

    input_asset_uniform = len(set(input_asset_ids)) == 1 if input_asset_ids else False
    output_asset_match = input_asset_uniform and len(output_asset_ids) == 1 and next(iter(output_asset_ids)) == input_asset_ids[0]
    asset_integrity_ok = input_asset_uniform and output_asset_match
    check_results.append(asset_integrity_ok)

    balance_ok = input_portion_sum == output_portion_sum
    check_results.append(balance_ok)

    overall_ok = all(check_results)

    print(f"[ Transaction Verification: {node_name} ]")
    print("-" * 50)
    print(f"ID: {_short_hex(txid_hex)} (Match: {_ok_text(txid_ok)})")
    print(f"Status: {'VALID' if overall_ok else 'INVALID'}")
    print()
    print("1. Input Authenticity Check")
    for line in outpoint_lines:
        print(line)
    if tx.inputs:
        print(f"   - Public Key Hash Match: {_ok_text(all_pkh_match)}")
        print(f"   - Digital Signature Verification: {_ok_text(all_sig_ok)}")
    else:
        print("   - Public Key Hash Match: FAIL (no inputs)")
        print("   - Digital Signature Verification: FAIL (no inputs)")

    print()
    print("2. Asset Consistency Check")
    if input_asset_ids:
        asset_label = f"asset{input_asset_ids[0]}"
    else:
        asset_label = "unknown"
    print(
        "   - Asset Type Integrity: "
        f"{_ok_text(asset_integrity_ok)} (inputs/outputs => {asset_label})"
    )
    print(
        f"   - Value Balance: {input_portion_sum} -> {output_portion_sum} "
        f"({'Balanced' if balance_ok else 'Unbalanced'})"
    )
    print()
    print(
        f"Summary: {sum(1 for x in check_results if x)} / {len(check_results)} "
        "validation steps passed successfully."
    )
    print("-" * 50)


def snapshot(which: str) -> None:
    node_names = _load_node_names() if which == "ALL" else [which]
    for node in node_names:
        blocks = _load_chain_blocks(node)
        heights = [b.header.block_height for b in reversed(blocks)]
        print(f"{node} : " + "\t".join([f"blockHeight {h}" for h in heights]))


def trace_asset(asset_id: int, count: str) -> None:
    records = []
    for node in _load_node_names():
        for block in _load_chain_blocks(node):
            for tx in block.txs:
                if any(out.asset_id == asset_id for out in tx.outputs):
                    records.append((block.header.block_height, tx.txid.hex(), node, tx))

    records.sort(key=lambda x: x[0], reverse=True)
    if count != "ALL":
        records = records[: int(count)]

    for h, txid, node, tx in records:
        print(f"[node={node}, blockHeight {h}, txID: {txid}]")
        print(f"  inputs={len(tx.inputs)}, outputs={len(tx.outputs)}")


def monitor_mined(interval: float) -> None:
    print("[master] watching mined blocks ...")
    seen: dict[str, int] = {}
    while True:
        for node in _load_node_names():
            blocks = _load_chain_blocks(node)
            max_h = blocks[-1].header.block_height if blocks else -1
            prev = seen.get(node, -1)
            if max_h > prev:
                for h in range(prev + 1, max_h + 1):
                    if h == 0:
                        continue
                    ts = time.strftime("%H:%M:%S")
                    print(f"a block with blockHeight {h} mined by {node} (report arrived at {ts})")
                seen[node] = max_h
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Master process command interface")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify = sub.add_parser("verify-transaction")
    p_verify.add_argument("Fi")

    p_snapshot = sub.add_parser("snapshot")
    p_snapshot.add_argument("target", help="ALL or FNxxx")

    p_trace = sub.add_parser("trace")
    p_trace.add_argument("asset_id", type=int)
    p_trace.add_argument("count", help="ALL or natural number")

    p_monitor = sub.add_parser("monitor")
    p_monitor.add_argument("--interval", type=float, default=1.0)

    args = parser.parse_args()

    if args.cmd == "verify-transaction":
        verify_transaction(args.Fi)
    elif args.cmd == "snapshot":
        snapshot(args.target)
    elif args.cmd == "trace":
        trace_asset(args.asset_id, args.count)
    elif args.cmd == "monitor":
        monitor_mined(args.interval)


if __name__ == "__main__":
    main()