from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


Hash32 = bytes      # 32-byte hash
PubKey64 = bytes    # 64-byte public key
Sig64 = bytes       # 64-byte signature
PubKeyHash20 = bytes  # 20-byte pubKeyHash


@dataclass(frozen=True, slots=True)
class TxIn:
    """
    input 구조
    --------------------------------
    prev_txid       : 32 bytes
    prev_out_index  : 4 bytes (uint32)
    pubK            : 64 bytes
    sig             : 64 bytes
    --------------------------------
    """
    prev_txid: Hash32
    prev_out_index: int
    pubK: PubKey64
    sig: Sig64


@dataclass(frozen=True, slots=True)
class TxOut:
    """
    output 구조
    ----------------------------
    asset_id  : 4 bytes (uint32)
    pubKhash  : 20 bytes
    portion   : 4 bytes (uint32)
    ----------------------------
    """
    asset_id: int
    pubKhash: PubKeyHash20
    portion: int


@dataclass(frozen=True, slots=True)
class Tx:
    """
    transaction 구조 (txid : 32 bytes)
    ------------------------------
    input_count     : 4 bytes
    input           : 164 bytes * input_count
    output_count    : 4 bytes
    output          : 28 bytes * output_count
    ------------------------------
    """
    txid: Hash32
    inputs: tuple[TxIn, ...]
    outputs: tuple[TxOut, ...]

    @property
    def input_count(self) -> int:
        return len(self.inputs)

    @property
    def output_count(self) -> int:
        return len(self.outputs)


@dataclass(frozen=True, slots=True)
class BlockHeader:
    """
    Block Header 구조 (총 72 bytes)
    --------------------------
    blockHeight  : 4 bytes (uint32)
    prevHash     : 32 bytes
    nonce        : 4 bytes (uint32)
    merkleRoot   : 32 bytes
    --------------------------
    """
    block_height: int
    prev_hash: Hash32
    nonce: int
    merkle_root: Hash32


@dataclass(frozen=True, slots=True)
class Block:
    """
    Block 구조
    --------------------------
    Header (72 bytes)
    tx_count : 4 bytes (uint32)
    txs      : 가변 (tx raw들의 연속 or tx 구조 리스트)
    --------------------------
    """
    header: BlockHeader
    txs: tuple[Tx, ...]

    @property
    def tx_count(self) -> int:
        return len(self.txs)

    def iter_txids(self) -> Iterable[Hash32]:
        for tx in self.txs:
            yield tx.txid
