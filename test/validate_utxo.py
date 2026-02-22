import json
from pathlib import Path
from daChain.core.da_types import Tx, TxIn, TxOut
from daChain.core.crypto import sign, sha256
from daChain.core.serialize import tx_to_bytes, txin_body_without_sig, tx_body_to_bytes
from daChain.core.validate import verify_signatures

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "daChain" / "data"
USERS_PATH = DATA_DIR / "user.json"
STAKES_PATH = DATA_DIR / "stakes.json"

def run_test():
    print("=== [Test] Transaction Validation Start ===")

    users = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    stakes_data = json.loads(STAKES_PATH.read_text(encoding="utf-8"))

    utxo_dict = {}
    asset_id_str = list(stakes_data["assets"].keys())[0] 
    target_stake = stakes_data["assets"][asset_id_str]["stakes"][0] 
    utxo_key = f"{target_stake['txid']}:{target_stake['output_idx']}"
    owner_info = users[target_stake["owner"]]
    
    utxo_dict[utxo_key] = {
        "pubKhash": bytes.fromhex(owner_info["pubKhash"]),
        "portion": target_stake["portion"],
        "asset_id": int(asset_id_str)
    }
    print(f"[*] UTXO Loaded: {utxo_key} (Owner: {target_stake['owner']})")

    # 정상 트랜잭션 생성
    # Input
    priv_key = bytes.fromhex(owner_info["privatekey"])
    pub_key = bytes.fromhex(owner_info["publickey"])
    
    # 서명 전 임시 TxIn
    unsigned_in = TxIn(
        prev_txid=bytes.fromhex(target_stake["txid"]),
        prev_out_index=target_stake["output_idx"],
        pubK=pub_key,
        sig=b'\x00' * 64
    )
    
    # 실제 서명 생성
    message_to_sign = txin_body_without_sig(unsigned_in)
    signature = sign(priv_key, message_to_sign)
    
    # 서명된 TxIn
    signed_in = TxIn(
        prev_txid=unsigned_in.prev_txid,
        prev_out_index=unsigned_in.prev_out_index,
        pubK=unsigned_in.pubK,
        sig=signature
    )

    tx_out = TxOut(
        asset_id=int(asset_id_str),
        pubKhash=bytes.fromhex(owner_info["pubKhash"]),
        portion=target_stake["portion"]
    )

    tx_body = tx_body_to_bytes((signed_in,), (tx_out,))
    test_tx = Tx(
        txid=sha256(tx_body),
        inputs=(signed_in,),
        outputs=(tx_out,)
    )
    
    tx_bytes = tx_to_bytes(test_tx)
    print(f"[*] Test Transaction Created (TXID: {test_tx.txid.hex()[:8]}...)")

    # 5. 검증 실행
    print("\n--- Running Validation ---")
    is_valid = verify_signatures(tx_bytes, utxo_dict)

    if is_valid:
        print("\n[Result] Validation SUCCESS!!!")
    else:
        print("\n[Result] Validation FAILED :(")

if __name__ == "__main__":
    run_test()