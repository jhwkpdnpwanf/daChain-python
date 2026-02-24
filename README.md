# daChain

`daChain`은 임의 자산에 대한 지분 기반 블록체인 프로젝트입니다.   

daChain은 단일 화폐 개념이 아닌 다중 자산을 지원하도록 설계되었으며, 자산별 지분 관리가 가능하도록 구조화되어 있습니다.  

또한 복잡한 난이도 조정 및 네트워크 합의 구조를 단순화한 PoW 모델을 사용하고, 중앙 Master Process를 통해 각 노드의 체인 상태, 트랜잭션 검증 결과, 자산 흐름을 모니터링할 수 있도록 구현된 실험 목적의 블록체인 시스템입니다. 

<br>

## 1. 핵심 개념

- **트랜잭션 검증**
  - txid 무결성 검증 (`txid == sha256(tx_body)`)
  - 입력 outpoint(UTXO) 미사용 여부 검증
  - 공개키 해시(pubKhash) 일치 검증
  - 디지털 서명 검증(ECDSA)
  - 자산 일관성(입/출력 asset_id) + 지분 합(입력 합 = 출력 합) 검증

- **블록 생성/전파**
  - 각 Full Node는 주기적으로 자신의 mempool을 기준으로 채굴 시도
  - 유효 블록 채굴 시 이웃 노드에 전파
  - 더 긴 유효 체인 후보를 수신하면 체인 갱신

- **User Process**
  - 랜덤 트랜잭션을 연속 생성
  - 일부 비율(`error-rate`)은 의도적으로 잘못된 값으로 생성
  - 임의 Full Node에 트랜잭션 전송

- **Master Process**
  - Full Node의 체인/거래 상태 조회
  - `verify-transaction`, `snapshot`, `trace`, `monitor` 명령어 제공


<br>

## 2. 패키지 설치  

```bash
pip install cryptography
pip install base58
pip install ecdsa
```

<br>

## 3. 명령어 실행

### 3-1) daChain 초기화 (권장 N = 8)

```bash
# python -m daChain.command.initiate daChain <N>
python -m daChain.command.initiate daChain 8
```

- `N`은 asset 수가 되며 유저의 수는 2N이 됩니다.
- 초기 유저에 대한 정보는 `daChain/data/`에 생성합니다. (privatekey, publickey, pubKhash) 
- 만든 asset은 임의의 유저 N명이 각각 100의 지분을 가지게 됩니다. 
- genesis 트랜잭션 N개로 해당 정보가 적혀있으며, 이를 전부 포함한 초기 블록을 하나 생성합니다.  

<br>

### 3-2) Full Node 초기화 (권장 N = 10)

```bash
# python -m daChain.command.initiate fullNodes <N>
python -m daChain.command.initiate fullNodes 10
```

- `FN000`, `FN001`, ... 형태의 Full Node를 `daChain/full-node/`에 생성합니다.  
- 각 풀노드 폴더에는 `block/`, `mempool/`, `UTXO`, `info.json`이 생성됩니다. 
  - `block/`    : 유효성 검증이 끝난 블록들 기록
  - `mempool/`  : 수신한 트랜잭션 보관
  - `UTXO`      : 확정된 트랜잭션으로 사용가능한 outpoint 집합
  - `info.json` : 자신의 ip/포트와 인접 풀노드들 정보

<br>

### 3-3) User Process 실행

```bash
# python -m daChain.command.user_process
# python -m daChain.command.user_process --error-rate <0-1> --interval <N> --batch-size <N'>
python -m daChain.command.user_process
``` 
- Default 값으로 `error-rate` 0.2, `interval` 12, `batch-size` 5가 설정됩니다. 
- 숫자를 입력해서 별도로 값을 지정할 수 있습니다. 
  - `--error-rate`: 잘못된 트랜잭션 비율 (예: `0.2` = 20%)
  - `--interval`: 배치 생성 주기 (초)
  - `--batch-size`: 한 번에 전송할 트랜잭션 수
  - 한번에 batch size 만큼 랜덤 트랜잭션을 생성하고 interval 초 마다 랜덤한 풀노드에게 트랜잭션을 전송합니다.  

<br>

### 3-4) Master Process 명령

```bash
python -m daChain.command.master_process verify-transaction FN000
python -m daChain.command.master_process snapshot ALL
python -m daChain.command.master_process trace 0 ALL
python -m daChain.command.master_process monitor
```

- `verify-transaction <FN:i>`  
  해당 노드가 최근 채굴 시 머클트리의 가장 왼쪽에 포함시킨 리프에 해당하는 트랜잭션을 단계별로 검증해 리포트 형태로 출력합니다.
- `snapshot ALL|FNxxx`  
  현재 시점의 daChain 높이 흐름을 노드별로 출력합니다.
- `trace <assetID> ALL|k`  
  특정 자산의 거래 이력을 최근 순으로 조회합니다.
- `monitor`  
  채굴 블록 발생 상황을 실시간 폴링 방식으로 출력합니다.

<br>

## 4. 트랜잭션/키 데이터 구조

| 항목 | 설명 |
|---|---|
| `txid` | `sha256(tx_body)` |
| `pubK` | ECDSA 공개키(64 bytes) |
| `pubKhash` | `RIPEMD160(SHA256(pubK))` (20 bytes) |
| `sig` | ECDSA 서명(64 bytes) |

<br>

daChain에서 사용하는 주소 변환 바이트 구성

| 단계 | 데이터                                   | 바이트 |
| -: | ------------------------------------- | --: | 
|  1 | privkey (hex 64자)                     |  32 | 
|  2 | pubkey (hex 128자, raw 64B)            |  64 | 
|  3 | SHA-256(pubkey)                       |  32 |
|  4 | RIPEMD-160(SHA256(pubkey)) = pubKhash |  20 |

<br>
비트코인 주소(Base58Check) 참고(daChain에서는 사용 X)

| 단계 | 데이터          | 바이트 |
| -: | ------------------------ | --: | 
|  5 | version(0x00) + hash160  |  21 | 
|  6 | checksum (SHA256×2 앞 4B) |   4 | 
|  7 | Base58Check 입력(21+4=25B) |  25 | 


<br>
<br>

## (참고) 트랜잭션/블록 구조

### 트랜잭션 전체 구조 

| 필드             | 크기                |
| -------------- | ----------------- |
| `txid`         | 32 bytes          |
| `input_count`  | 4 bytes           |
| `inputs`       | 164 * input_count |
| `output_count` | 4 bytes           |
| `outputs`      | 28 * output_count |

<br>

### 트랜잭션 Input (TxIn) 구조

| 필드               | 크기               | 설명            |
| ---------------- | ---------------- | ------------------------- |
| `prev_txid`      | 32 bytes         | 참조하는 이전 트랜잭션 ID     |
| `prev_out_index` | 4 bytes (uint32) | 참조하는 출력 인덱스     |
| `pubK`           | 64 bytes         | 소유자 공개키 |
| `sig`            | 64 bytes         | 서명  |

<br> 

### 트랜잭션 출력 (TxOut) 구조

| 필드         | 크기               | 설명         |
| ---------- | ---------------- | ---------- |
| `asset_id` | 4 bytes (uint32) | 자산 id     |
| `pubKhash` | 20 bytes         | 수신자 공개키 해시 |
| `portion`  | 4 bytes (uint32) | 자산 지분      |

<br> 

### 블록 구조  


| 필드         | 크기                |
| ---------- | ----------------- |
| `Header`   | 72 bytes          |
| `tx_count` | 4 bytes           |
| `txs`      | 가변 (각 tx 직렬화 바이트) |

<br> 

### 블록 헤더 구조 

| 필드            | 크기               | 설명          |
| ------------- | ---------------- | ----------- |
| `blockHeight` | 4 bytes (uint32) | 블록 높이       |
| `prevHash`    | 32 bytes         | 이전 블록 해시    |
| `nonce`       | 4 bytes (uint32) | nonce |
| `merkleRoot`  | 32 bytes         | 머클 트리 루트    |

<br> 

### 풀노드 메시지 타입  

| 코드     | 의미                 | 설명                                                                  |
| ------ | ------------------ | ------------------------------------------------------------------- |
| `0x01` | `MSG_TX_NEW`       | 사용자 또는 노드가 새로운 트랜잭션을 전송할 때 사용하는 메시지. payload에는 직렬화된 트랜잭션 바이트가 포함됨.  |
| `0x02` | `MSG_TX_ACK`       | `MSG_TX_NEW` 수신에 대한 응답 메시지. 트랜잭션 수락/거절 결과 또는 상태 정보 반환에 사용됨.         |
| `0x03` | `MSG_BLOCK_NEW`    | 채굴된 새로운 블록을 다른 노드에 전파할 때 사용하는 메시지. payload에는 직렬화된 블록 데이터 포함.        |
| `0x04` | `MSG_UTXO_REQ`     | 특정 노드에 현재 사용 가능한 UTXO 목록을 요청하는 메시지. user_process가 트랜잭션 생성을 위해 호출.   |
| `0x05` | `MSG_UTXO_RESP`    | `MSG_UTXO_REQ`에 대한 응답 메시지. 현재 노드가 보유한 spendable UTXO 목록(JSON 등) 반환. |
| `0x06` | `MSG_MASTER_MINED` | Full Node가 블록 채굴 성공 시 Master Process에 보고하는 메시지. 채굴 이벤트 알림용.         |
| `0x07` | `MSG_MASTER_REQ`   | Master Process가 특정 노드에 상태/데이터 조회를 요청할 때 사용하는 메시지.                   |
| `0x08` | `MSG_MASTER_RESP`  | `MSG_MASTER_REQ`에 대한 응답 메시지. 노드가 요청된 데이터(체인 상태, 트랜잭션 정보 등)를 반환.     |
