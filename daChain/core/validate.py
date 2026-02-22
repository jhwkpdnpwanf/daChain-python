from daChain.core.crypto import make_pubkey_hash, verify
from daChain.core.serialize import tx_bytes_to_Tx, txin_body_without_sig


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



def verify_signatures(tx_bytes: bytes, utxo_dict: dict) -> bool:
    try:
        tx = tx_bytes_to_Tx(tx_bytes)

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

    except Exception as e:
        print(f"Script Execution Error: {e}")
        return False