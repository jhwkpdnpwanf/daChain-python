import hashlib
import secrets
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import utils

Hash32 = bytes
PubKey64 = bytes
PrivKey32 = bytes
PubKeyHash20 = bytes
Sig64 = bytes

def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def double_sha256(data: bytes) -> bytes:
    return sha256(sha256(data))


def ripemd160(data: bytes) -> bytes:
    h = hashlib.new("ripemd160")
    h.update(data)
    return h.digest()


def pubkey_hash160(pubkey64: PubKey64) -> PubKeyHash20:
    return ripemd160(sha256(pubkey64))


def make_private_key() -> PrivKey32:
    return secrets.token_bytes(32)


def make_public_key(privkey32: PrivKey32) -> PubKey64:
    if not isinstance(privkey32, (bytes, bytearray)) or len(privkey32) != 32:
        raise ValueError("privkey32 must be 32 bytes")

    d = int.from_bytes(privkey32, "big")
    private_key = ec.derive_private_key(d, ec.SECP256K1())
    pub = private_key.public_key().public_numbers()
    x = pub.x.to_bytes(32, "big")
    y = pub.y.to_bytes(32, "big")
    return x + y


def make_pubkey_hash(pubkey64: PubKey64) -> PubKeyHash20:
    if not isinstance(pubkey64, (bytes, bytearray)) or len(pubkey64) != 64:
        raise ValueError("pubkey64 must be 64 bytes")
    return pubkey_hash160(pubkey64)


def sign(privkey32: PrivKey32, message: bytes) -> Sig64:
    d = int.from_bytes(privkey32, "big")
    private_key = ec.derive_private_key(d, ec.SECP256K1())
    der_sig = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_sig)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")

def verify(pubkey64: PubKey64, message: bytes, sig64: Sig64) -> bool:
    x = int.from_bytes(pubkey64[:32], "big")
    y = int.from_bytes(pubkey64[32:], "big")
    public_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1()).public_key()
    r = int.from_bytes(sig64[:32], "big")
    s = int.from_bytes(sig64[32:], "big")
    der_sig = utils.encode_dss_signature(r, s)
    try:
        public_key.verify(der_sig, message, ec.ECDSA(hashes.SHA256()))
        return True
    except:
        return False






@dataclass(frozen=True, slots=True)
class Wallet:
    privkey: PrivKey32
    pubkey: PubKey64
    pubkey_hash: PubKeyHash20


def make_wallet() -> Wallet:
    sk = make_private_key()
    pk = make_public_key(sk)
    pkh = make_pubkey_hash(pk)
    return Wallet(privkey=sk, pubkey=pk, pubkey_hash=pkh)