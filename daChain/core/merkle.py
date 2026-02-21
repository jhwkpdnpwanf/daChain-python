from typing import Iterable, Sequence

from daChain.core.crypto import sha256
from daChain.core.da_types import Tx, TxIn, TxOut
from  daChain.core.constants import ZERO32

# n보다 같거나 큰 최소 2의 제곱수 계산
# 2진수를 활용함
def _next_pow2(n: int) -> int:
    if n <= 0: return 0
    if (n & (n - 1)) == 0: return n
    return 1 << n.bit_length()


# 2^n개에 맞춰서 0으로 패딩
def _pad_to_pow2(txs: Sequence[Tx]) -> list[bytes]:
    leaves = [tx.txid for tx in txs]

    t_pow2 = _next_pow2(len(leaves))
    while len(leaves) < t_pow2:
        leaves.append(ZERO32)
    
    return leaves


# Block class에서 txs의 merkle-root를 계산함
# 2^n 개에 맞춰 계산하며 tx 개수가 부족하면 0x00으로 패딩함
def merkle_root(txs: Sequence[Tx]) -> bytes:
    leaves = _pad_to_pow2(txs)

    if not leaves:
        return ZERO32

    while len(leaves) > 1:
        tmp_list = []
        for i in range(0, len(leaves), 2):
            tmp_list.append(sha256(leaves[i] + leaves[i + 1]))
        leaves = tmp_list
    
    return leaves[0]

            

"""if __name__ == "__main__":
    # 데이터 오염을 막기 위해 정확히 32바이트짜리 더미 데이터를 준비합니다.
    # b"a"를 32번 반복, b"b"를 32번 반복, b"c"를 32번 반복
    tx1_id = b"A" * 32
    tx2_id = b"B" * 32
    tx3_id = b"C" * 32

    test_txs = [
        Tx(txid=tx1_id, inputs=(), outputs=()),
        Tx(txid=tx2_id, inputs=(), outputs=()),
        Tx(txid=tx3_id, inputs=(), outputs=())
    ]

    result = merkle_root(test_txs)
    
    print(f"최종 머클 루트(hex): {result.hex()}")"""