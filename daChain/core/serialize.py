from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from daChain.core.crypto import sha256
from daChain.core.da_types import Block, BlockHeader, Tx, TxIn, TxOut


from  daChain.core.constants import (
    TXID_SIZE,
    TXIN_SIZE, TXIN_PREV_TXID_SIZE,
    TXOUT_SIZE,
    TX_INPUT_COUNT_SIZE, TX_OUTPUT_COUNT_SIZE,
    INPUT_INDEX_SIZE, INPUT_PUBK_SIZE, INPUT_SIG_SIZE,
    OUTPUT_ASSET_ID_SIZE, OUTPUT_PUBKHASH_SIZE, OUTPUT_PORTION_SIZE
)


# Tx 직렬화
def tx_to_bytes(tx: Tx) -> bytes:
    body = tx_body_to_bytes(tx.inputs, tx.outputs)

    txid = tx.txid
    if not isinstance(txid, (bytes, bytearray)) or len(txid) != TXIN_PREV_TXID_SIZE:
        txid = sha256(body)

    return bytes(txid) + body

# Tx 역직렬화 
def tx_bytes_to_Tx(tx_bytes: bytes) -> Tx:
    # TxID 분리
    txid = tx_bytes[:TXID_SIZE]
    body = tx_bytes[TXID_SIZE:]
    
    offset = 0

    # Inputs
    input_count = int.from_bytes(body[offset:offset + TX_INPUT_COUNT_SIZE], "big")
    offset += TX_INPUT_COUNT_SIZE
    
    inputs = []
    for _ in range(input_count):
        prev_txid = body[offset : offset + TXIN_PREV_TXID_SIZE]
        idx_start = offset + TXIN_PREV_TXID_SIZE
        
        prev_out_index = int.from_bytes(body[idx_start : idx_start + INPUT_INDEX_SIZE], "big")
        pubK = body[idx_start + INPUT_INDEX_SIZE : idx_start + INPUT_INDEX_SIZE + INPUT_PUBK_SIZE]
        sig = body[idx_start + INPUT_INDEX_SIZE + INPUT_PUBK_SIZE : idx_start + INPUT_INDEX_SIZE + INPUT_PUBK_SIZE + INPUT_SIG_SIZE]
        
        inputs.append(TxIn(prev_txid, prev_out_index, pubK, sig))
        offset += TXIN_SIZE

    # Outputs
    output_count = int.from_bytes(body[offset : offset + TX_OUTPUT_COUNT_SIZE], "big")
    offset += TX_OUTPUT_COUNT_SIZE
    
    outputs = []
    for _ in range(output_count):
        asset_id = int.from_bytes(body[offset : offset + OUTPUT_ASSET_ID_SIZE], "big")
        pubKhash = body[offset + OUTPUT_ASSET_ID_SIZE : offset + OUTPUT_ASSET_ID_SIZE + OUTPUT_PUBKHASH_SIZE]
        portion  = int.from_bytes(body[offset + OUTPUT_ASSET_ID_SIZE + OUTPUT_PUBKHASH_SIZE : offset + TXOUT_SIZE], "big")
        
        outputs.append(TxOut(asset_id, pubKhash, portion))
        offset += TXOUT_SIZE

    return Tx(txid=txid, inputs=tuple(inputs), outputs=tuple(outputs))


# TxIns와 TxOuts로 transaction 직렬화 
def tx_body_to_bytes(TxIns: Sequence[TxIn], TxOuts: Sequence[TxOut]) -> bytes:
    out = bytearray()

    out += len(TxIns).to_bytes(4, "big")

    for txin in TxIns:
        out += txin.prev_txid
        out += txin.prev_out_index.to_bytes(4, "big")
        out += txin.pubK
        out += txin.sig

    out += len(TxOuts).to_bytes(4, "big")

    for txout in TxOuts:
        out += txout.asset_id.to_bytes(4, "big")
        out += txout.pubKhash
        out += txout.portion.to_bytes(4, "big")

    return bytes(out)


# BlockHeader 와 txs로 block 직렬화 (인자 2개 버전)
"""
def block_to_byte(header: BlockHeader, txs: tuple[Tx]) -> bytes:
    out = bytearray()

    out += header.block_height.to_bytes(4, "big")
    out += header.prev_hash
    out += header.nonce.to_bytes(4, "big")
    out += header.merkle_root

    out += len(txs).to_bytes(4, "big")

    for tx in txs:
        body = tx_body_to_bytes(tx.inputs, tx.outputs)
        out += tx.txid
        out += body

    return bytes(out)
    """

# BlockHeader 와 txs로 block 직렬화 (인자 1개 버전)
def block_to_bytes(block: Block) -> bytes:
    h = block.header
    out = bytearray()

    out += h.block_height.to_bytes(4, "big")
    out += h.prev_hash
    out += h.nonce.to_bytes(4, "big")
    out += h.merkle_root

    out += len(block.txs).to_bytes(4, "big")

    for tx in block.txs:
        body = tx_body_to_bytes(tx.inputs, tx.outputs)
        out += tx.txid
        out += body

    return bytes(out)


def txin_body_without_sig(tx_in: TxIn) -> bytes:
    out = bytearray()

    out += tx_in.prev_txid
    out += tx_in.prev_out_index.to_bytes(4, "big")
    out += tx_in.pubK

    # sig
    out += b'\x00' * 64
    
    return bytes(out)