ZERO32 = b"\x00" * 32
TXID_SIZE = 32

MSG_TX_NEW = 0x01
MSG_TX_ACK = 0x02
MSG_BLOCK_NEW = 0x03
MSG_UTXO_REQ = 0x04
MSG_UTXO_RESP = 0x05
MSG_MASTER_MINED = 0x06
MSG_MASTER_REQ = 0x07
MSG_MASTER_RESP = 0x08


MINE_INTERVAL_SEC = 3.0
MAX_TXS_PER_BLOCK = 100



TXIN_SIZE = 32 + 4 + 64 + 64
TXIN_PREV_TXID_SIZE = 32
TXIN_PREV_OUT_INDEX_SIZE = 4
TXIN_PUBK_SIZE = 64
TXIN_SIG_SIZE = 64
"""
input 구조 (164 bytes)
--------------------------------
prev_txid       : 32 bytes
prev_out_index  : 4 bytes (uint32)
pubK            : 64 bytes
sig             : 64 bytes
--------------------------------
"""

TXOUT_SIZE = 28
TXOUT_ASSET_ID_SIZE = 4
TXOUT_PUBKHASH_SIZE = 20
TXOUT_PORTION_SIZE = 4
"""
output 구조 (28 bytes)
----------------------------
asset_id  : 4 bytes (uint32)
pubKhash  : 20 bytes
portion   : 4 bytes (uint32)
----------------------------
"""

INPUT_INDEX_SIZE = 4
INPUT_PUBK_SIZE = 64
INPUT_SIG_SIZE = 64
"""
input 구조
--------------------------------
prev_txid       : 32 bytes
prev_out_index  : 4 bytes (uint32)
pubK            : 64 bytes
sig             : 64 bytes
--------------------------------
"""

OUTPUT_ASSET_ID_SIZE = 4
OUTPUT_PUBKHASH_SIZE = 20
OUTPUT_PORTION_SIZE = 4
"""
output 구조
----------------------------
asset_id  : 4 bytes (uint32)
pubKhash  : 20 bytes
portion   : 4 bytes (uint32)
----------------------------
"""



TX_INPUT_COUNT_SIZE = 4
TX_OUTPUT_COUNT_SIZE = 4
"""
transaction 구조 (txid : 32 bytes)
------------------------------
input_count     : 4 bytes
input           : 164 bytes * input_count
output_count    : 4 bytes
output          : 28 bytes * output_count
------------------------------
"""



"""
Block Header 구조 (총 72 bytes)
--------------------------
blockHeight  : 4 bytes (uint32)
prevHash     : 32 bytes
nonce        : 4 bytes (uint32)
merkleRoot   : 32 bytes
--------------------------
"""

"""
Block 구조
--------------------------
Header (72 bytes)
tx_count : 4 bytes (uint32)
txs      : 가변 
--------------------------
"""