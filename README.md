python -m daChain.command.initiate daChain 5  
python -m daChain.command.initiate fullNodes 5


txid -> sha256(tx)

pubK -> ECDSA

pubKhash -> sha256(pubK)

sig -> 



pip install cryptography
pip install base58
pip install ecdsa
pip install requests


| 단계 | 데이터                             | 바이트          |
| -- | ------------------------------- | ------------ |
| 1  | privkey (hex 64자)               | **32 bytes** |
| 2  | pubkey (hex 130자, uncompressed) | **64 bytes** |
| 3  | SHA-256(pubkey)                 | **32 bytes** |
| 4  | RIPEMD-160(SHA256(pubkey))      | **20 bytes** |
| 5  | 0x00 + hash160                  | **21 bytes** |
| 6  | checksum (SHA256×2 앞 4바이트)      | **4 bytes**  |
| 7  | Base58Check 인코딩 입력              | **25 bytes** |
