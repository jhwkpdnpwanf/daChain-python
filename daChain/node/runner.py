from __future__ import annotations

import argparse
import asyncio
import struct
import time
from pathlib import Path

from daChain.core.da_types import Tx
from daChain.core.serialize import block_to_bytes

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

        info = (self.node_dir / "info.json").read_text(encoding="utf-8")
        import json
        info = json.loads(info)

        self.ip = info["ip"]
        self.port = info["port"]

    async def start_server(self) -> None:
        server = await asyncio.start_server(self.handle_conn, self.ip, self.port)
        print(f"[{self.name}] listen {self.ip}:{self.port}", flush=True)
        async with server:
            await server.serve_forever()

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
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_tx(self, tx_bytes: bytes, writer: asyncio.StreamWriter):

        suffix = int(time.time() * 1_000_000)
        path = self.mempool_dir / f"tx_{suffix}.dat"
        path.write_bytes(tx_bytes)

        print(f"[{self.name}] mempool +1 -> {path.name}", flush=True)

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