from __future__ import annotations

import argparse
import asyncio
import struct
import json
import os
import random
import struct
from pathlib import Path

from daChain.core.crypto import sha256
from daChain.core.da_types import Block, BlockHeader, Tx
from daChain.core.merkle import merkle_root
from daChain.core.serialize import block_bytes_to_Block, block_to_bytes, tx_bytes_to_Tx, tx_to_bytes
from daChain.core.validate import validate_transaction


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FULLNODE_DIR = PROJECT_ROOT / "full-node"
DATA_DIR = PROJECT_ROOT / "daChain" / "data"


from  daChain.core.constants import (
    MSG_TX_NEW, MSG_TX_ACK,  MSG_BLOCK_NEW,
    MINE_INTERVAL_SEC, MAX_TXS_PER_BLOCK, ZERO32,
)

POW_TARGET_PREFIX_HEX = os.getenv("POW_TARGET_PREFIX_HEX", "000000")
MAX_NONCE = 2 ** 32
POW_MINING_NONCE_CHUNK = int(os.getenv("POW_MINING_NONCE_CHUNK", "50000"))
POW_TX_ORDER_VARIANTS = max(1, int(os.getenv("POW_TX_ORDER_VARIANTS", "8")))


class NodeRuntime:

    def __init__(self, name: str) -> None:
        self.name = name
        self.node_dir = FULLNODE_DIR / name
        self.mempool_dir = self.node_dir / "mempool"
        self.mempool_dir.mkdir(parents=True, exist_ok=True)
        self.blocks_dir = self.node_dir / "blocks"
        self.utxo_path = self.node_dir / "UTXO" / "utxo.json"
        self.blocks_dir.mkdir(parents=True, exist_ok=True)

        info = json.loads((self.node_dir / "info.json").read_text(encoding="utf-8"))

        self.ip = info["ip"]
        self.port = info["port"]
       
        connected_names = info.get("connected", [])
        global_nodes = json.loads((DATA_DIR / "node.json").read_text(encoding="utf-8"))
        self.neighbors = []
        for target_name in connected_names:
            if target_name in global_nodes:
                self.neighbors.append(global_nodes[target_name])
            # else:
                # print(f"[{self.name}] Warning: Neighbor {target_name} not found in node.json")

        # print(f"[{self.name}] Initialized. Neighbors to broadcast: {self.neighbors}")
        self.chain_lock = asyncio.Lock()
        self.chain, self.chain_tip_hash, self.utxos = self._load_chain_and_utxos()

    def _load_chain_and_utxos(self) -> tuple[list[tuple[bytes, Block]], bytes, dict]:
        chain = []
        for block_path in sorted(self.blocks_dir.glob("B*.dat")):
            block = block_bytes_to_Block(block_path.read_bytes())
            block_hash = self._hash_header(block.header)
            chain.append((block_hash, block))

        if not chain:
            raise RuntimeError(f"[{self.name}] no genesis block")

        file_utxos = self._load_file_utxos()
        rebuilt = self._rebuild_utxos_from_chain(chain)
        if file_utxos != rebuilt:
            self._persist_utxos(rebuilt)
            file_utxos = rebuilt

        return chain, chain[-1][0], file_utxos

    def _load_file_utxos(self) -> dict:
        if not self.utxo_path.exists():
            return {}

        payload = json.loads(self.utxo_path.read_text(encoding="utf-8"))
        out = {}
        for key, value in payload.get("utxos", {}).items():
            out[key] = {
                "asset_id": int(value["asset_id"]),
                "portion": int(value["portion"]),
                "pubKhash": bytes.fromhex(value["pubKhash"]),
            }
        return out

    def _persist_utxos(self, utxos: dict) -> None:
        payload = {
            "utxos": {
                key: {
                    "asset_id": int(value["asset_id"]),
                    "portion": int(value["portion"]),
                    "pubKhash": value["pubKhash"].hex(),
                }
                for key, value in utxos.items()
            }
        }
        self.utxo_path.parent.mkdir(parents=True, exist_ok=True)
        self.utxo_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _hash_header(self, header: BlockHeader) -> bytes:
        return sha256(
            header.block_height.to_bytes(4, "big")
            + header.prev_hash
            + header.nonce.to_bytes(4, "big")
            + header.merkle_root
        )

    def _pow_ok(self, block_hash: bytes) -> bool:
        return block_hash.hex().startswith(POW_TARGET_PREFIX_HEX)
    

    async def _mine_pow(self, header: BlockHeader) -> tuple[BlockHeader | None, bytes | None]:
        nonce = 0
        while nonce < MAX_NONCE:
            end = min(nonce + POW_MINING_NONCE_CHUNK, MAX_NONCE)
            for current_nonce in range(nonce, end):
                h = BlockHeader(
                    block_height=header.block_height,
                    prev_hash=header.prev_hash,
                    nonce=current_nonce,
                    merkle_root=header.merkle_root,
                )
                block_hash = self._hash_header(h)
                if self._pow_ok(block_hash):
                    return h, block_hash

            nonce = end
            await asyncio.sleep(0)

        return None, None

    def _build_candidate_variants(
        self,
        tx_files: list[Path],
        base_height: int,
        base_tip: bytes,
    ) -> list[tuple[list[Tx], dict, BlockHeader]]:
        variants: list[tuple[list[Tx], dict, BlockHeader]] = []
        seed = base_height ^ int.from_bytes(base_tip[-8:], "big")

        for variant_idx in range(POW_TX_ORDER_VARIANTS):
            ordered_files = list(tx_files)
            if variant_idx > 0:
                rng = random.Random(seed + variant_idx)
                rng.shuffle(ordered_files)

            snapshot = dict(self.utxos)
            txs: list[Tx] = []
            consumed: set[str] = set()

            for tx_file in ordered_files:
                tx_bytes = tx_file.read_bytes()
                tx = tx_bytes_to_Tx(tx_bytes)
                txid_hex = tx.txid.hex()
                if txid_hex in consumed:
                    continue

                if validate_transaction(tx_bytes, snapshot):
                    txs.append(tx)
                    consumed.add(txid_hex)
                    self._apply_tx_to_utxo(snapshot, tx)

            if not txs:
                continue

            root = merkle_root(txs)
            candidate_header = BlockHeader(
                block_height=base_height + 1,
                prev_hash=base_tip,
                nonce=0,
                merkle_root=root,
            )
            variants.append((txs, snapshot, candidate_header))

        return variants
    
    
    def _rebuild_utxos_from_chain(self, chain: list[tuple[bytes, Block]]) -> dict:
        utxos = {}
        for _, block in chain:
            for tx in block.txs:
                for tx_in in tx.inputs:
                    key = f"{tx_in.prev_txid.hex()}:{tx_in.prev_out_index}"
                    utxos.pop(key, None)

                for idx, tx_out in enumerate(tx.outputs):
                    key = f"{tx.txid.hex()}:{idx}"
                    utxos[key] = {
                        "asset_id": int(tx_out.asset_id),
                        "portion": int(tx_out.portion),
                        "pubKhash": tx_out.pubKhash,
                    }
        return utxos

    async def start_server(self) -> None:
        server = await asyncio.start_server(self.handle_conn, self.ip, self.port)
        print(f"[{self.name}] listen {self.ip}:{self.port}", flush=True)
        async with server:
            await server.serve_forever()
    async def mine_loop(self) -> None:
        while True:
            await asyncio.sleep(MINE_INTERVAL_SEC + random.random())
            await self.try_mine_block()

    async def try_mine_block(self) -> None:
        async with self.chain_lock:
            tx_files = sorted(self.mempool_dir.glob("*.dat"))[:MAX_TXS_PER_BLOCK]
            if not tx_files:
                return

            base_tip = self.chain_tip_hash
            base_height = self.chain[-1][1].header.block_height

            variants = self._build_candidate_variants(tx_files, base_height, base_tip)

        if not variants:
            return

        selected_txs: list[Tx] | None = None
        selected_snapshot: dict | None = None
        mined_header: BlockHeader | None = None
        block_hash: bytes | None = None

        for txs, snapshot, candidate_header in variants:
            mined_header, block_hash = await self._mine_pow(candidate_header)
            if mined_header is not None and block_hash is not None:
                selected_txs = txs
                selected_snapshot = snapshot
                break


        if mined_header is None or block_hash is None or selected_txs is None or selected_snapshot is None:
            return

        block = Block(header=mined_header, txs=tuple(selected_txs))

        async with self.chain_lock:
            if self.chain_tip_hash != base_tip or self.chain[-1][1].header.block_height != base_height:
                return

            self.chain.append((block_hash, block))
            self.chain_tip_hash = block_hash
            self.utxos = selected_snapshot

            self._write_chain_files(self.chain)
            self._persist_utxos(self.utxos)

            for tx in selected_txs:
                path = self.mempool_dir / f"{tx.txid.hex()}.dat"
                if path.exists():
                    path.unlink()

        print(f"[{self.name}] mined block h={mined_header.block_height} txs={len(selected_txs)}", flush=True)
        asyncio.create_task(self.broadcast_block(block_to_bytes(block)))


    def _apply_tx_to_utxo(self, utxos: dict, tx: Tx) -> None:
        for tx_in in tx.inputs:
            key = f"{tx_in.prev_txid.hex()}:{tx_in.prev_out_index}"
            utxos.pop(key, None)

        for idx, tx_out in enumerate(tx.outputs):
            key = f"{tx.txid.hex()}:{idx}"
            utxos[key] = {
                "asset_id": int(tx_out.asset_id),
                "portion": int(tx_out.portion),
                "pubKhash": tx_out.pubKhash,
            }

    def _write_chain_files(self, chain: list[tuple[bytes, Block]]) -> None:
        for p in self.blocks_dir.glob("B*.dat"):
            p.unlink()

        for idx, (_, block) in enumerate(chain):
            path = self.blocks_dir / f"B{idx + 1:04d}_{block.header.block_height}.dat"
            path.write_bytes(block_to_bytes(block))
    

    # 수신한 트랜잭션을 이웃 노드에 전달
    async def broadcast_tx(self, tx_bytes: bytes):
        header = struct.pack(">BI", MSG_TX_NEW, len(tx_bytes))
        message = header + tx_bytes

        for neighbor in self.neighbors:
            try:
                reader, writer = await asyncio.open_connection(neighbor["ip"], neighbor["port"])
                writer.write(message)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                # print(f"[{self.name}] Propagated tx to {neighbor['port']}")
            except Exception as e:
                print(f"[{self.name}] Failed to send to {neighbor['port']}: {e}")


    async def broadcast_block(self, block_bytes: bytes):
        header = struct.pack(">BI", MSG_BLOCK_NEW, len(block_bytes))
        message = header + block_bytes

        for neighbor in self.neighbors:
            try:
                reader, writer = await asyncio.open_connection(neighbor["ip"], neighbor["port"])
                writer.write(message)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


    async def handle_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                header = await reader.readexactly(5)
                msg_type = header[0]
                length = struct.unpack(">I", header[1:])[0]

                payload = await reader.readexactly(length)

                if msg_type == MSG_TX_NEW:
                    await self.handle_tx(payload, writer)

                if msg_type == MSG_BLOCK_NEW:
                    await self.handle_block(payload)

        except asyncio.IncompleteReadError:
            pass
        except (ConnectionResetError, OSError) as e:
                # [WinError 64] 지정된 네트워크 이름을 더 이상 사용할 수 없습니다 -> 무시
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionResetError, OSError):
                pass

    # ACK 전송 (트랜잭션 수신 후 검증 결과 알리기)
    async def _send_ack(self, writer: asyncio.StreamWriter, message: bytes):
        try:
            header = struct.pack(">BI", MSG_TX_ACK, len(message))
            writer.write(header + message)
            await writer.drain()
        except Exception:
            pass
    
    async def handle_tx(self, tx_bytes: bytes, writer: asyncio.StreamWriter):
        if len(tx_bytes) < 32:
            await self._send_ack(writer, b"INVALID")
            return


        txid_hex = tx_bytes[:32].hex()
        path = self.mempool_dir / f"{txid_hex}.dat"

        # 신규 트랜잭션만 이웃에게 전달
        if path.exists():
            #print(f"[{self.name}] duplicate tx ignored", flush=True)
            await self._send_ack(writer, b"DUPLICATE")
            return
        
        async with self.chain_lock:
            if not validate_transaction(tx_bytes, self.utxos):
                # print(f"[{self.name}] Invalid transaction rejected: {txid_hex[:8]}", flush=True)
                await self._send_ack(writer, b"INVALID")
                return
            
            path.write_bytes(tx_bytes)

        print(f"[{self.name}] mempool +1 -> {path.name}", flush=True)
        asyncio.create_task(self.broadcast_tx(tx_bytes))
        await self._send_ack(writer, b"OK")        


    def _build_candidate_chain(self, incoming: Block) -> list[tuple[bytes, Block]] | None:
        incoming_hash = self._hash_header(incoming.header)

        by_hash = {block_hash: (idx, block) for idx, (block_hash, block) in enumerate(self.chain)}
        prev = incoming.header.prev_hash
        if prev not in by_hash:
            return None

        parent_idx, parent_block = by_hash[prev]
        expected_height = parent_block.header.block_height + 1
        if incoming.header.block_height != expected_height:
            return None

        candidate = list(self.chain[: parent_idx + 1])

        if parent_idx + 1 < len(self.chain):
            if len(self.chain) >= incoming.header.block_height + 1:
                return None

        candidate.append((incoming_hash, incoming))
        return candidate

    def _validate_chain(self, chain: list[tuple[bytes, Block]]) -> tuple[bool, dict]:
        if not chain:
            return False, {}

        for idx, (block_hash, block) in enumerate(chain):
            if self._hash_header(block.header) != block_hash:
                return False, {}

            if idx == 0:
                if block.header.prev_hash != ZERO32 or block.header.block_height != 0:
                    return False, {}
            else:
                prev_hash = chain[idx - 1][0]
                prev_height = chain[idx - 1][1].header.block_height
                if block.header.prev_hash != prev_hash:
                    return False, {}
                if block.header.block_height != prev_height + 1:
                    return False, {}

            if merkle_root(block.txs) != block.header.merkle_root:
                return False, {}

            if idx > 0 and not self._pow_ok(block_hash):
                return False, {}

        utxos = {}
        for idx, (_, block) in enumerate(chain):
            if idx == 0:
                utxos = self._rebuild_utxos_from_chain([(b"", block)])
                continue

            for tx in block.txs:
                tx_bytes = tx_to_bytes(tx)
                if not validate_transaction(tx_bytes, utxos):
                    return False, {}
                self._apply_tx_to_utxo(utxos, tx)

        return True, utxos

    async def handle_block(self, block_bytes: bytes):
        incoming = block_bytes_to_Block(block_bytes)

        async with self.chain_lock:
            candidate = self._build_candidate_chain(incoming)
            if candidate is None:
                return

            ok, candidate_utxos = self._validate_chain(candidate)
            if not ok:
                return

            current_height = self.chain[-1][1].header.block_height
            incoming_height = candidate[-1][1].header.block_height
            if incoming_height <= current_height:
                return

            self.chain = candidate
            self.chain_tip_hash = self.chain[-1][0]
            self.utxos = candidate_utxos
            self._write_chain_files(self.chain)
            self._persist_utxos(self.utxos)

            included_txids = {tx.txid.hex() for _, block in self.chain for tx in block.txs}
            for memp in self.mempool_dir.glob("*.dat"):
                if memp.stem in included_txids:
                    memp.unlink()

        print(f"[{self.name}] adopted chain height={self.chain[-1][1].header.block_height}", flush=True)
        asyncio.create_task(self.broadcast_block(block_bytes))

    async def run(self):
        await asyncio.gather(self.start_server(), self.mine_loop())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    rt = NodeRuntime(args.name)
    asyncio.run(rt.run())


if __name__ == "__main__":
    main()