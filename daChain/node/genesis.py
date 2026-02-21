from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import time
import os
from pathlib import Path
from typing import Sequence
from dataclasses import asdict

from daChain.core.crypto import sha256, make_wallet, Wallet
from daChain.core.da_types import Tx, TxIn, TxOut, Block, BlockHeader
from daChain.core.serialize import tx_body_to_bytes, block_to_bytes
from daChain.core.merkle import merkle_root


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENESIS_DIR = PROJECT_ROOT / "genesis"
FULLNODE_DIR = PROJECT_ROOT / "full-node"
DATA_DIR = PROJECT_ROOT / "daChain" / "data"

ZERO32 = b"\x00" * 32



def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# genesis 정보는 보기좋게 json으로 저장하기 위한 함수
def _save_dat_to_json(obj, file_path):
    def hex_encoder(o):
        if isinstance(o, bytes):
            return o.hex()

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(asdict(obj), f, indent=4, default=hex_encoder)



# 초기 디렉토리 정리
def _reset_genesis_dir() -> None:
    if GENESIS_DIR.exists():
        shutil.rmtree(GENESIS_DIR)

    (GENESIS_DIR / "transaction").mkdir(parents=True)
    (GENESIS_DIR / "block").mkdir(parents=True)

def _reset_fullnode_dir() -> None:
    if FULLNODE_DIR.exists():
        shutil.rmtree(FULLNODE_DIR)

    FULLNODE_DIR.mkdir(parents=True)


# 유저 생성
def _make_users(n: int) -> list[Wallet]:
    users = {}
    wallets = []

    for i in range(n):
        name = f"User{i:02d}"
        wallet = make_wallet()
        wallets.append(wallet)

        users[name] = {
            "privatekey": wallet.privkey.hex(),
            "publickey": wallet.pubkey.hex(),
            "pubKhash": wallet.pubkey_hash.hex(),
        }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(DATA_DIR / "user.json", users)

    return wallets


# genesis transaction 생성
def _make_genesis_txs(asset_count: int, wallets: list[Wallet]) -> list[Tx]:
    txs = []

    for i in range(asset_count):
        wallet = wallets[i]

        outputs = [
            TxOut(
                asset_id=i,
                pubKhash=wallet.pubkey_hash,
                portion=100,
            )
        ]

        body = tx_body_to_bytes([], outputs)
        txid = sha256(body)

        tx = Tx(
            txid=txid,
            inputs=tuple(),
            outputs=tuple(outputs),
        )

        txs.append(tx)

        tx_path = GENESIS_DIR / "transaction" / f"genesis_tx{i:02d}.json"
        _save_dat_to_json(tx, tx_path)

        
        

    return txs

# genesis block 생성
def _make_genesis_block(txs: Sequence[Tx]) -> str:
    root = merkle_root(txs)

    header = BlockHeader(
        block_height=0,
        prev_hash=ZERO32,
        nonce=0,
        merkle_root=root,
    )

    block = Block(header=header, txs=tuple(txs))
    block_bytes = block_to_bytes(block)

    block_hash = sha256(
        header.block_height.to_bytes(4, "big")
        + header.prev_hash
        + header.nonce.to_bytes(4, "big")
        + header.merkle_root
    )

    block_path_dat = GENESIS_DIR / "block" / "genesis_b0001.dat"
    block_path_dat.write_bytes(block_bytes)

    block_path = GENESIS_DIR / "block" / "genesis_b0001.json"
    _save_dat_to_json(block, block_path)

    return block_hash.hex()

# 지분 현황을 저장
def _write_stakes(asset_count: int, wallets: list[Wallet], txs: Sequence[Tx]) -> None:
    assets: dict[str, dict] = {}

    out_ref_by_asset: dict[int, tuple[str, int]] = {}
    for tx in txs:
        txid_hex = tx.txid.hex() if isinstance(tx.txid, (bytes, bytearray)) else str(tx.txid)
        for out_idx, out in enumerate(tx.outputs):
            out_ref_by_asset[out.asset_id] = (txid_hex, out_idx)

    for asset_id in range(asset_count):
        owner_name = f"User{asset_id:02d}"

        txid_hex, out_idx = out_ref_by_asset.get(asset_id, ("", -1))
        if out_idx < 0:
            raise RuntimeError(f"missing genesis output reference for asset_id={asset_id}")

        assets[str(asset_id)] = {
            "stakes": [
                {
                    "owner": owner_name,
                    "portion": 100,
                    "txid": txid_hex,
                    "output_idx": out_idx,
                }
            ]
        }

    payload = {"assets": assets}

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(DATA_DIR / "stakes.json", payload)




def initiate_dachain(asset_count: int) -> None:
    _reset_genesis_dir()

    user_count = 2 * asset_count
    wallets = _make_users(user_count)

    txs = _make_genesis_txs(asset_count, wallets)
    _write_stakes(asset_count, wallets, txs)
    block_hash = _make_genesis_block(txs)

    print(f"[initiate daChain] N={asset_count}, block_hash={block_hash}")


# full node 이름/포트/인접노드 생성
def _set_node_name(i: int) -> str:
    return f"FN{i:03d}"

def _set_port(i: int, base: int = 5000) -> int:
    return base + i

def _set_connect_nodes(num_nodes: int):
    connect_nodes = [[] for _ in range(num_nodes)]
    standard = 0.4

    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            compared = random.randint(0, 10) / 10
            if compared <= standard:
                connect_nodes[i].append(j)
                connect_nodes[j].append(i)

    return connect_nodes


def _check_network(connect_nodes, num_nodes):
    visited = [False] * num_nodes
    stack = [0]
    visited[0] = True

    while stack:
        cur = stack.pop()
        for nxt in connect_nodes[cur]:
            if not visited[nxt]:
                visited[nxt] = True
                stack.append(nxt)

    return all(visited)


def _make_nodes_dict(node_count: int) -> dict:
    graph = _set_connect_nodes(node_count)

    retry = 0
    while not _check_network(graph, node_count):
        graph = _set_connect_nodes(node_count)
        retry += 1
        if retry > 1000:
            raise RuntimeError("Failed to create connected graph")

    nodes_dict = {}

    for i in range(node_count):
        name = _set_node_name(i)
        nodes_dict[name] = {
            "ip": "127.0.0.1",
            "port": _set_port(i),
            "connected": [_set_node_name(j) for j in graph[i]],
        }

    return nodes_dict



# genesis_b0001.dat 파일을 각 FN에게 주어줌
# 초기 fullnode 폴더 구성 세팅
def _make_fullnode_directory(nodes_dict: dict) -> None:
    genesis_block_path = GENESIS_DIR / "block" / "genesis_b0001.dat"

    for node_name, info in nodes_dict.items():
        node_dir = FULLNODE_DIR / node_name
        node_dir.mkdir(parents=True, exist_ok=True)

        (node_dir / "blocks").mkdir(exist_ok=True)
        (node_dir / "UTXO").mkdir(exist_ok=True)
        (node_dir / "mempool").mkdir(exist_ok=True)

        if genesis_block_path.exists():
            shutil.copy(
                genesis_block_path,
                node_dir / "blocks" / "B0001_0.dat"
            )

        _write_json(node_dir / "info.json", info)


# python -m daChain.node.runner --name FN000 형태로 실행
# 모듈 import 문제 방지를 위해 PYTHONPATH에 PROJECT_ROOT를 추가
def _launch_fullnodes(nodes_dict: dict) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    procs = []
    for node_name in nodes_dict.keys():
        cmd = [
            sys.executable,
            "-m",
            "daChain.node.runner",
            "--name",
            node_name,
        ]
        p = subprocess.Popen(cmd, env=env)
        procs.append((node_name, p))

    print("[launcher] started processes:", flush=True)
    for name, p in procs:
        print(f"  - {name}: pid={p.pid}", flush=True)

    # 이 프로세스가 살아있는 동안 노드들도 유지되게 wait
    # Ctrl+C로 종료하면 하위 프로세스들도 정리
    try:
        while True:
            time.sleep(1)
            # 죽은 프로세스 있으면 알려주기
            for name, p in procs:
                if p.poll() is not None:
                    print(f"[launcher] {name} exited code={p.returncode}", flush=True)
    except KeyboardInterrupt:
        print("\n[launcher] stopping...", flush=True)
        for _, p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for _, p in procs:
            try:
                p.wait(timeout=3)
            except Exception:
                pass



# 초기 utxo 관련 함수들 (genesis tx를 보고 각 노드의 UTXO 초기화)
def _load_genesis_txs_for_utxo() -> dict[str, dict]:
    tx_dir = GENESIS_DIR / "transaction"
    if not tx_dir.exists():
        raise RuntimeError("genesis transaction dir missing. run 'initiate daChain N' first.")

    utxos: dict[str, dict] = {}

    for p in sorted(tx_dir.glob("genesis_tx*.json")):
        obj = json.loads(p.read_text(encoding="utf-8"))

        txid_hex = obj.get("txid")
        outs = obj.get("outputs", [])
        if not isinstance(txid_hex, str) or not isinstance(outs, list):
            raise ValueError(f"bad genesis tx json: {p}")

        for out_idx, o in enumerate(outs):
            asset_id = int(o["asset_id"])
            pubKhash_hex = o["pubKhash"]
            portion = int(o["portion"])

            key = f"{txid_hex}:{out_idx}"
            utxos[key] = {"asset_id": asset_id, "pubKhash": pubKhash_hex, "portion": portion}

    return utxos

def _init_utxo_for_nodes(nodes_dict: dict) -> None:
    utxos = _load_genesis_txs_for_utxo()

    for node_name in nodes_dict.keys():
        utxo_path = FULLNODE_DIR / node_name / "UTXO" / "utxo.json"
        utxo_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(utxo_path, {"utxos": utxos})





def initiate_full_nodes(node_count: int) -> None:
    _reset_fullnode_dir()

    nodes_dict = _make_nodes_dict(node_count)
    _make_fullnode_directory(nodes_dict)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(DATA_DIR / "node.json", nodes_dict)

    _launch_fullnodes(nodes_dict)
    _init_utxo_for_nodes(nodes_dict)

    print(f"[initiate fullNodes] full nodes={node_count}, connected p2p graph ready")


