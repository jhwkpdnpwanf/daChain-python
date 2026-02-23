import json
import random
import socket
import struct
import time
from pathlib import Path

from daChain.core.da_types import TxIn, TxOut, Tx
from daChain.core.crypto import sha256, sign
from daChain.core.serialize import tx_body_to_bytes, txin_body_without_sig, tx_to_bytes
from daChain.core.constants import MSG_TX_NEW, MSG_TX_ACK, MSG_UTXO_REQ, MSG_UTXO_RESP

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "daChain" / "data"
USERS_PATH = DATA_DIR / "user.json"
NODE_PATH = DATA_DIR / "node.json"



"""
JSON 관련 함수
"""
def _load_json(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)

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


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf

def _request_spendable_utxos(ip: str, port: int, timeout: float = 3.0) -> list[dict]:
    with socket.create_connection((ip, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(struct.pack(">BI", MSG_UTXO_REQ, 0))

        resp_hdr = _recv_exact(sock, 5)
        resp_type = resp_hdr[0]
        resp_len = struct.unpack(">I", resp_hdr[1:])[0]
        payload = _recv_exact(sock, resp_len)

        if resp_type != MSG_UTXO_RESP:
            raise ValueError(f"unexpected response type: {resp_type}")

        obj = json.loads(payload.decode("utf-8"))
        utxos = obj.get("utxos", [])
        if not isinstance(utxos, list):
            raise ValueError("bad UTXO payload")
        return utxos

def _choose_random_asset_and_outputs(utxos: list[dict]) -> tuple[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for utxo in utxos:
        asset_id = int(utxo["asset_id"])
        grouped.setdefault(asset_id, []).append(utxo)

    if not grouped:
        raise ValueError("no spendable utxo")

    asset_id = random.choice(list(grouped.keys()))
    candidates = grouped[asset_id]

    n = random.randint(1, len(candidates))
    chosen = random.sample(candidates, k=n)

    return asset_id, chosen


"""
Tx generation
"""
# 랜덤 Tx 객체 생성 
def _make_random_Tx(utxos: list[dict]) -> Tx:
    asset_id, chosen_utxos = _choose_random_asset_and_outputs(utxos)
    
    users = _load_json(USERS_PATH)
    user_names = list(users.keys())

    temp_inputs = []
    for utxo in chosen_utxos:
        owner_name = utxo["owner"]
        user_info = users[owner_name]
        
        pub_key = bytes.fromhex(user_info["publickey"])
        
        tx_in = TxIn(
            prev_txid=bytes.fromhex(utxo["txid"]),
            prev_out_index=int(utxo["output_idx"]),
            pubK=pub_key,
            sig=b'\x00' * 64 # 우선 0으로 패딩
        )
        temp_inputs.append(tx_in)

    # TxIn 생성
    final_inputs = []
    for i, tx_in in enumerate(temp_inputs):
        owner_name = chosen_utxos[i]["owner"]
        priv_key = bytes.fromhex(users[owner_name]["privatekey"])
        
        message_to_sign = txin_body_without_sig(tx_in)
        
        sig = sign(priv_key, message_to_sign)
        
        signed_tx_in = TxIn(
            prev_txid=tx_in.prev_txid,
            prev_out_index=tx_in.prev_out_index,
            pubK=tx_in.pubK,
            sig=sig,
        )
        final_inputs.append(signed_tx_in)

    # TxOut 생성
    total_input_portion = sum(int(utxo["portion"]) for utxo in chosen_utxos)
    tx_outputs = []
    
    max_outputs = max(1, min(5, total_input_portion))
    num_outputs = random.randint(1, max_outputs)
    
    if num_outputs > 1 and total_input_portion > num_outputs:
        cuts = sorted(random.sample(range(1, total_input_portion), num_outputs - 1))
        portions = [cuts[0]] + [cuts[i] - cuts[i - 1] for i in range(1, len(cuts))] + [
            total_input_portion - cuts[-1]
        ]    
    else:
        portions = [total_input_portion]

    for p in portions:
        receiver_name = random.choice(user_names)
        receiver_info = users[receiver_name]
        
        tx_out = TxOut(
            asset_id=asset_id,
            pubKhash=bytes.fromhex(receiver_info["pubKhash"]),
            portion=p,
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
    )



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
        inputs[idx] = TxIn(inputs[idx].prev_txid, inputs[idx].prev_out_index, inputs[idx].pubK, b"\x00" * 64)        
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


def _send_tx_bytes(ip: str, port: int, payload: bytes, timeout: float = 3.0) -> tuple[bool, bytes]:
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


def _build_tx_batch(utxos: list[dict], batch_size: int, error_rate: float) -> list[tuple[Tx, bool]]:
    tx_batch: list[tuple[Tx, bool]] = []
    for _ in range(batch_size):
        tx = _make_random_Tx(utxos)
        is_corrupted = False
        if random.random() < error_rate:
            tx = _corrupt_transaction(tx)
            is_corrupted = True
            print("[user] corrupted tx generated", flush=True)
        tx_batch.append((tx, is_corrupted))
    return tx_batch

# interval 초마다 무작위 노드에서 UTXO 받아와서 Tx 생성 -> 무작위 노드에 Tx 전달
# error_rate 만큼의 유효하지 않은 Tx도 섞어서 전달
def run_user_process(error_rate: float = 0.2, interval: float = 12.0, batch_size: int = 5) -> None:
    node_addrs = _get_node_addrs()

    while True:
        try:
            ip, port = random.choice(node_addrs)
            utxos = _request_spendable_utxos(ip, port, timeout=3.0)
            if not utxos:
                print(f"[user] no spendable utxo from {ip}:{port}", flush=True)
                time.sleep(interval)
                continue

            tx_batch = _build_tx_batch(utxos, batch_size=batch_size, error_rate=error_rate)
            print(f"[user] tx batch prepared from node utxo ({len(tx_batch)} txs)", flush=True)

            for tx, is_corrupted in tx_batch:
                target_ip, target_port = random.choice(node_addrs)
                tx_bytes = tx_to_bytes(tx)
                print(
                    f"[user] send TX_NEW bytes -> {target_ip}:{target_port} (valid={not is_corrupted})",
                    flush=True,
                )

                try:
                    ok, ack_payload = _send_tx_bytes(target_ip, target_port, tx_bytes, timeout=3.0)
                    if not ok:
                        print(f"[user] unexpected ACK type / payload={ack_payload!r}", flush=True)
                except Exception as e:
                    print(f"[user] node comm failed: {e}", flush=True)
                
                time.sleep(1.5)  # tx 연속 전달에서 시간차 두기

            time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[user] stopped", flush=True)
            break
        except Exception as e:
            print(f"[user] loop error: {e}", flush=True)
            time.sleep(2.0)


if __name__ == "__main__":
    run_user_process()