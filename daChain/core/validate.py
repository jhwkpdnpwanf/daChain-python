from daChain.core.crypto import make_pubkey_hash, sha256, verify
from daChain.core.da_types import Tx
from daChain.core.serialize import tx_body_to_bytes, tx_bytes_to_Tx, txin_body_without_sig


def _op_dup(stack: list):
    stack.append(stack[-1])

def _op_hash160(stack: list):
    pubkey = stack.pop()
    pkh = make_pubkey_hash(pubkey)
    stack.append(pkh)

def _op_equalverify(stack: list) -> bool:
    val1 = stack.pop()
    val2 = stack.pop()
    return val1 == val2

def _op_checksig(stack: list, message: bytes) -> bool:
    pubkey = stack.pop()
    sig = stack.pop()
    return verify(pubkey, message, sig)


# sig 검증
def _verify_signatures(tx_bytes: bytes, utxo_dict: dict) -> bool:
    tx: Tx = tx_bytes_to_Tx(tx_bytes)

    for input in tx.inputs:
        utxo_key = f"{input.prev_txid.hex()}:{input.prev_out_index}"
        if utxo_key not in utxo_dict:
            print(f"[{utxo_key}] Double spend or invalid UTXO")
            return False
        
        target_pkh = utxo_dict[utxo_key]["pubKhash"]

        message = txin_body_without_sig(input)

        stack = []

        stack.append(input.sig)
        stack.append(input.pubK)

        _op_dup(stack)
        _op_hash160(stack)
        
        stack.append(target_pkh)

        if not _op_equalverify(stack):
            print("Validation Error: PubKhash mismatch!")
            return False

        if not _op_checksig(stack, message):
            print("Validation Error: Invalid Signature!")
            return False
        
    return True

    


# 자산 지분 검증
def _verify_balances(tx_bytes: bytes, utxo_dict: dict) -> bool:
    tx: Tx = tx_bytes_to_Tx(tx_bytes)

    total_in = 0
    input_asset = None
    
    for input in tx.inputs:
        utxo = utxo_dict[f"{input.prev_txid.hex()}:{input.prev_out_index}"]
        total_in += utxo["portion"]
        input_asset = utxo["asset_id"]
        
    total_out = sum(out.portion for out in tx.outputs)
    
    if any(out.asset_id != input_asset for out in tx.outputs):
        return False

    return total_in == total_out


# 최종 트랜잭션 검증
def validate_transaction(tx_bytes: bytes, utxo_dict: dict) -> bool:
    try:
        tx = tx_bytes_to_Tx(tx_bytes)

        actual_hash = sha256(tx_body_to_bytes(tx.inputs, tx.outputs))
        if tx.txid != actual_hash:
            print("TXID 오류")
            return False

        if not _verify_signatures(tx_bytes, utxo_dict):
            print("서명 오류")
            return False
            
        if not _verify_balances(tx_bytes, utxo_dict):
            print("지분 오류")
            return False
            
        return True
    except Exception:
        print("예외 발생")
        return False