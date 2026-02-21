ZERO32 = b"\x00" * 32


TXIN_SIZE = 32 + 4 + 64 + 64
TXID_SIZE = 32
"""
input 구조 (164 bytes)
--------------------------------
prev_txid       : 32 bytes
prev_out_index  : 4 bytes (uint32)
pubK            : 64 bytes
sig             : 64 bytes
--------------------------------
"""

TXOUT_SIZE = 4 + 20 + 4
"""
output 구조 (28 bytes)
----------------------------
asset_id  : 4 bytes (uint32)
pubKhash  : 20 bytes
portion   : 4 bytes (uint32)
----------------------------
"""






U32_SIZE = 4

HASH32_SIZE = 32
PUBK64_SIZE = 64
SIG64_SIZE = 64
PUBKHASH20_SIZE = 20

HEADER_SIZE = 72

TXID_SIZE = 32
TXIN_SIZE = 32 + 4 + 64 + 64   # 164
TXOUT_SIZE = 4 + 20 + 4        # 28



"""
input 구조
--------------------------------
prev_txid       : 32 bytes
prev_out_index  : 4 bytes (uint32)
pubK            : 64 bytes
sig             : 64 bytes
--------------------------------
"""

"""
output 구조
----------------------------
asset_id  : 4 bytes (uint32)
pubKhash  : 20 bytes
portion   : 4 bytes (uint32)
----------------------------
"""

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