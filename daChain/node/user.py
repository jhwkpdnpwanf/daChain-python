import json
import random
import socket
import struct
import time
from pathlib import Path

from daChain.core.da_types import TxIn, TxOut, Tx
from daChain.core.crypto import sha256, sign
from daChain.core.serialize import tx_body_to_bytes, txin_body_without_sig, tx_to_bytes
from  daChain.core.constants import MSG_TX_NEW, MSG_TX_ACK

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "daChain" / "data"
STAKES_PATH = DATA_DIR / "stakes.json"
USERS_PATH = DATA_DIR / "user.json"
NODE_PATH = DATA_DIR / "node.json"



"""
JSON 관련 함수
"""
def _load_json(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)

def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")



# 노드 정보 가져오기
def _get_node_addrs(path: Path = NODE_PATH) -> list[tuple[str, int]]:
    nodes_data = _load_json(path)
    addrs: list[tuple[str, int]] = []
    for _, info in nodes_data.items():
        ip = info.get("ip")
        port = info.get("port")
        if ip and port is not None:
            addrs.append((str(ip), int(port)))

    if not addrs:
        raise ValueError("node.json 세팅 오류입니다.")
    return addrs


# random 자산을 선택함 
def _choose_random_asset_and_outputs(path: Path = STAKES_PATH) -> tuple[int, list[dict]]:
    payload = _load_json(path)
    assets = payload.get("assets", {})
    if not isinstance(assets, dict) or not assets:
        raise ValueError("stakes.json: 'assets' is missing/empty")

    candidates: list[int] = []
    for k, v in assets.items():
        if isinstance(v, dict) and v.get("stakes"):
            candidates.append(int(k))

    if not candidates:
        raise ValueError("stakes.json: no asset has non-empty stakes")

    asset_id = random.choice(candidates)
    stakes_list = assets[str(asset_id)]["stakes"]

    # 특정 자산 내에서 랜덤한 개수의 stakes를 선택
    n = random.randint(1, len(stakes_list))
    chosen = random.sample(stakes_list, k=n)

    return asset_id, chosen


"""
Tx generation
"""
# 랜덤 Tx 객체 생성 
def _make_random_Tx() -> Tx:
    asset_id, chosen_stakes = _choose_random_asset_and_outputs(STAKES_PATH)
    
    users = _load_json(USERS_PATH)
    user_names = list(users.keys())

    temp_inputs = []
    for stake in chosen_stakes:
        owner_name = stake["owner"]
        user_info = users[owner_name]
        
        pub_key = bytes.fromhex(user_info["publickey"])
        
        tx_in = TxIn(
            prev_txid=bytes.fromhex(stake["txid"]),
            prev_out_index=stake["output_idx"],
            pubK=pub_key,
            sig=b'\x00' * 64 # 우선 0으로 패딩
        )
        temp_inputs.append(tx_in)

    # TxIn 생성
    final_inputs = []
    for i, tx_in in enumerate(temp_inputs):
        owner_name = chosen_stakes[i]["owner"]
        priv_key = bytes.fromhex(users[owner_name]["privatekey"])
        
        message_to_sign = txin_body_without_sig(tx_in)
        
        sig = sign(priv_key, message_to_sign)
        
        signed_tx_in = TxIn(
            prev_txid=tx_in.prev_txid,
            prev_out_index=tx_in.prev_out_index,
            pubK=tx_in.pubK,
            sig=sig
        )
        final_inputs.append(signed_tx_in)

    # TxOut 생성
    total_input_portion = sum(stake["portion"] for stake in chosen_stakes)
    tx_outputs = []
    
    max_outputs = max(1, min(5, total_input_portion))
    num_outputs = random.randint(1, max_outputs)
    
    if num_outputs > 1 and total_input_portion > num_outputs:
        cuts = sorted(random.sample(range(1, total_input_portion), num_outputs - 1))
        portions = [cuts[0]] + [cuts[i] - cuts[i-1] for i in range(1, len(cuts))] + [total_input_portion - cuts[-1]]
    else:
        portions = [total_input_portion]

    for p in portions:
        receiver_name = random.choice(user_names)
        receiver_info = users[receiver_name]
        
        tx_out = TxOut(
            asset_id=asset_id,
            pubKhash=bytes.fromhex(receiver_info["pubKhash"]),
            portion=p
        )
        tx_outputs.append(tx_out)

    # txid 계산 후 Tx 생성
    final_inputs_tuple = tuple(final_inputs)
    final_outputs_tuple = tuple(tx_outputs)
    
    tx_body = tx_body_to_bytes(final_inputs_tuple, final_outputs_tuple)
    real_txid = sha256(tx_body)

    return Tx(
        txid=real_txid,
        inputs=final_inputs_tuple,
        outputs=final_outputs_tuple
    ), chosen_stakes, asset_id



"""
Corrupt Tx
"""
# 일정 비율로 잘못된 Tx 객체 생성
def _corrupt_transaction(tx: Tx) -> Tx:
    error_type = random.choice(["txid", "signature", "asset_id", "portion"])
    
    inputs = list(tx.inputs)
    outputs = list(tx.outputs)
    
    if error_type == "txid":
        print("[Corrupt] Modifying txid", flush=True)
        new_txid = bytes([random.getrandbits(8) for _ in range(32)])
        return Tx(txid=new_txid, inputs=tx.inputs, outputs=tx.outputs)
    
    elif error_type == "signature":
        print("[Corrupt] Modifying a signature", flush=True)
        idx = random.randint(0, len(inputs) - 1)
        inputs[idx] = TxIn(inputs[idx].prev_txid, inputs[idx].prev_out_index, inputs[idx].pubK, b'\x00'*64)
        corrupted_inputs = tuple(inputs)
        # 오류 검증을 위해 새로운 txid 계산
        new_txid = sha256(tx_body_to_bytes(corrupted_inputs, tx.outputs))
        return Tx(txid=new_txid, inputs=corrupted_inputs, outputs=tx.outputs)
    
    elif error_type == "asset_id":
        print("[Corrupt] Modifying asset_id", flush=True)
        idx = random.randint(0, len(outputs) - 1)
        current_asset = outputs[idx].asset_id
        candidate_assets = {out.asset_id for out in outputs}
        candidate_assets.update({0, 1, 2, 3, 4, 5, 10, 100, 1000})
        candidate_assets.discard(current_asset)

        if not candidate_assets:
            bad_asset_id = current_asset + 1
        else:
            bad_asset_id = random.choice(tuple(candidate_assets))
        outputs[idx] = TxOut(asset_id=bad_asset_id, pubKhash=outputs[idx].pubKhash, portion=outputs[idx].portion)
        corrupted_outputs = tuple(outputs)
        # 오류 검증을 위해 새로운 txid 계산
        new_txid = sha256(tx_body_to_bytes(tx.inputs, corrupted_outputs))
        return Tx(txid=new_txid, inputs=tx.inputs, outputs=corrupted_outputs)
    
    else: # portion
        print("[Corrupt] Modifying portion", flush=True)
        idx = random.randint(0, len(outputs) - 1)
        outputs[idx] = TxOut(asset_id=outputs[idx].asset_id, pubKhash=outputs[idx].pubKhash, portion=99999)
        corrupted_outputs = tuple(outputs)
        # 오류 검증을 위해 새로운 txid 계산
        new_txid = sha256(tx_body_to_bytes(tx.inputs, corrupted_outputs))
        return Tx(txid=new_txid, inputs=tx.inputs, outputs=corrupted_outputs)




"""
Local stakes update
"""
# Tx가 정상적으로 노드에 수신되어 ACK를 받았을 때, 로컬 장부인 stakes.json을 업데이트
def update_state_after_tx(tx: Tx, consumed_stakes: list[dict], asset_id: int) -> None:
    stakes_data = _load_json(STAKES_PATH)
    users = _load_json(USERS_PATH)

    # pubKhash(hex str) -> username
    hash_to_name = {info["pubKhash"]: name for name, info in users.items()}

    current_stakes = stakes_data["assets"][str(asset_id)]["stakes"]
    to_remove = {(s["txid"], int(s["output_idx"])) for s in consumed_stakes}

    updated_stakes = [s for s in current_stakes if (s["txid"], int(s["output_idx"])) not in to_remove]

    for i, tx_out in enumerate(tx.outputs):
        owner_name = hash_to_name.get(tx_out.pubKhash.hex(), "Unknown")
        updated_stakes.append(
            {
                "txid": tx.txid.hex(),
                "output_idx": i,
                "owner": owner_name,
                "portion": int(tx_out.portion),
            }
        )

    stakes_data["assets"][str(asset_id)]["stakes"] = updated_stakes
    _save_json(STAKES_PATH, stakes_data)
    print(f"[user] stakes.json updated (asset_id={asset_id})", flush=True)

    


"""
노드와 통신하여 Tx 전송
"""
def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def _send_tx_bytes(ip: str, port: int, payload: bytes, timeout: float = 3.0) -> tuple[bool, bytes]:
    # returns: (ack_ok, ack_payload_bytes)

    with socket.create_connection((ip, port), timeout=timeout) as sock:
        sock.settimeout(timeout)

        header = struct.pack(">BI", MSG_TX_NEW, len(payload))
        sock.sendall(header + payload)

        ack_hdr = _recv_exact(sock, 5)
        ack_type = ack_hdr[0]
        ack_len = struct.unpack(">I", ack_hdr[1:])[0]
        ack_payload = _recv_exact(sock, ack_len)

        if ack_type != MSG_TX_ACK:
            return False, ack_payload
        return True, ack_payload


# 사용자 프로세스 메인 루프
def run_user_process(error_rate: float = 0.2, interval: float = 2.0) -> None:
    node_addrs = _get_node_addrs()

    while True:
        try:
            tx, consumed_stakes, asset_id = _make_random_Tx()
            is_corrupted = False

            if random.random() < error_rate:
                tx = _corrupt_transaction(tx)
                is_corrupted = True
                print("[user] corrupted tx generated", flush=True)

            tx_bytes = tx_to_bytes(tx)

            ip, port = random.choice(node_addrs)
            print(f"[user] send TX_NEW bytes -> {ip}:{port} (valid={not is_corrupted})", flush=True)

            try:
                ok, ack_payload = _send_tx_bytes(ip, port, tx_bytes, timeout=3.0)

                if ok:
                    # runner의 ACK payload가 b"OK" 같은 형태라고 가정
                    print(f"[user] ACK: {ack_payload!r}", flush=True)

                    # 변조 아니면 로컬 장부 업데이트
                    if not is_corrupted:
                        update_state_after_tx(tx, consumed_stakes, asset_id)
                else:
                    print(f"[user] unexpected ACK type / payload={ack_payload!r}", flush=True)

            except Exception as e:
                print(f"[user] node comm failed: {e}", flush=True)

            time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[user] stopped", flush=True)
            break
        except Exception as e:
            print(f"[user] loop error: {e}", flush=True)
            time.sleep(2.0)


if __name__ == "__main__":
    run_user_process()