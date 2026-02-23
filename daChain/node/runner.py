from __future__ import annotations

import argparse
import asyncio
import struct
import json
from pathlib import Path

from daChain.core.serialize import tx_bytes_to_Tx
from daChain.core.validate import validate_transaction



PROJECT_ROOT = Path(__file__).resolve().parents[2]
FULLNODE_DIR = PROJECT_ROOT / "full-node"
DATA_DIR = PROJECT_ROOT / "daChain" / "data"

MSG_TX_NEW = 0x01
MSG_TX_ACK = 0x02


class NodeRuntime:

    def __init__(self, name: str) -> None:
        self.name = name
        self.node_dir = FULLNODE_DIR / name
        self.mempool_dir = self.node_dir / "mempool"
        self.mempool_dir.mkdir(parents=True, exist_ok=True)
        self.utxos = self._load_initial_utxos()

        info = (self.node_dir / "info.json").read_text(encoding="utf-8")
        info = json.loads(info)

        self.ip = info["ip"]
        self.port = info["port"]
        self.neighbors = info.get("neighbors", [])
        connected_names = info.get("connected", [])

        global_nodes_content = (DATA_DIR / "node.json").read_text(encoding="utf-8")
        global_nodes = json.loads(global_nodes_content)

        self.neighbors = []
        for target_name in connected_names:
            if target_name in global_nodes:
                self.neighbors.append(global_nodes[target_name])
            # else:
                # print(f"[{self.name}] Warning: Neighbor {target_name} not found in node.json")

        # print(f"[{self.name}] Initialized. Neighbors to broadcast: {self.neighbors}")


    def _load_initial_utxos(self) -> dict:
        users_content = (DATA_DIR / "user.json").read_text(encoding="utf-8")
        users_data = json.loads(users_content)
        name_to_pkh = {
            name: bytes.fromhex(info["pubKhash"]) 
            for name, info in users_data.items()
        }

        stakes_content = (DATA_DIR / "stakes.json").read_text(encoding="utf-8")
        stakes_data = json.loads(stakes_content)
        
        flat_utxos = {}
        for asset_id_str, asset_info in stakes_data.get("assets", {}).items():
            asset_id = int(asset_id_str)
            for stake in asset_info.get("stakes", []):
                utxo_key = f"{stake['txid']}:{stake['output_idx']}"
                
                flat_utxos[utxo_key] = {
                    "pubKhash": name_to_pkh.get(stake["owner"]),
                    "portion": int(stake["portion"]),
                    "asset_id": asset_id
                }
        
        # print(f"[{self.name}] Loaded {len(flat_utxos)} UTXOs into memory.")
        return flat_utxos

    async def start_server(self) -> None:
        server = await asyncio.start_server(self.handle_conn, self.ip, self.port)
        print(f"[{self.name}] listen {self.ip}:{self.port}", flush=True)
        async with server:
            await server.serve_forever()

    # 수신한 트랜잭션을 이웃 노드에 전달
    async def broadcast_tx(self, tx_bytes: bytes):
        header = struct.pack(">BI", MSG_TX_NEW, len(tx_bytes))
        message = header + tx_bytes

        for neighbor in self.neighbors:
            try:
                reader, writer = await asyncio.open_connection(neighbor['ip'], neighbor['port'])
                writer.write(message)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                # print(f"[{self.name}] Propagated tx to {neighbor['port']}")
            except Exception as e:
                print(f"[{self.name}] Failed to send to {neighbor['port']}: {e}")


    async def handle_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                header = await reader.readexactly(5)
                msg_type = header[0]
                length = struct.unpack(">I", header[1:])[0]

                payload = await reader.readexactly(length)

                if msg_type == MSG_TX_NEW:
                    await self.handle_tx(payload, writer)

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
            print(f"[{self.name}] invalid tx size", flush=True)
            return

        txid = tx_bytes[:32]
        txid_hex = txid.hex()

        path = self.mempool_dir / f"{txid_hex}.dat"

        # 신규 트랜잭션만 이웃에게 전달
        if path.exists():
            #print(f"[{self.name}] duplicate tx ignored", flush=True)
            await self._send_ack(writer, b"DUPLICATE")
            return
        else:
            if not validate_transaction(tx_bytes, self.utxos):
                # print(f"[{self.name}] Invalid transaction rejected: {txid_hex[:8]}", flush=True)
                await self._send_ack(writer, b"INVALID")
                return
            
            path.write_bytes(tx_bytes)
            print(f"[{self.name}] mempool +1 -> {path.name}", flush=True)

            tx = tx_bytes_to_Tx(tx_bytes)

            # 사용된 UTXO 삭제
            for input in tx.inputs:
                utxo_key = f"{input.prev_txid.hex()}:{input.prev_out_index}"
                if utxo_key in self.utxos:
                    del self.utxos[utxo_key]

            # 새로운 UTXO 생성
            for i, out in enumerate(tx.outputs):
                new_utxo_key = f"{tx.txid.hex()}:{i}"
                self.utxos[new_utxo_key] = {
                    "pubKhash": out.pubKhash,
                    "portion": int(out.portion),
                    "asset_id": int(out.asset_id)
                }

            asyncio.create_task(self.broadcast_tx(tx_bytes))

        # ACK
        ack_payload = b"OK"
        header = struct.pack(">BI", MSG_TX_ACK, len(ack_payload))
        writer.write(header + ack_payload)
        await writer.drain()

    async def run(self):
        await self.start_server()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    rt = NodeRuntime(args.name)
    asyncio.run(rt.run())


if __name__ == "__main__":
    main()