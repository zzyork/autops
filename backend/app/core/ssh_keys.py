import base64
import hashlib

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from fastapi import HTTPException

MAX_PRIVATE_KEY_BYTES = 64 * 1024


def parse_private_key(content: str) -> tuple[bytes, str, str]:
    """校验完整私钥并从公钥生成指纹，绝不在错误信息中包含原文。"""
    try:
        raw = content.encode("utf-8")
    except UnicodeEncodeError:
        raise HTTPException(422, "私钥须为 UTF-8 文本") from None
    if not raw or len(raw) > MAX_PRIVATE_KEY_BYTES:
        raise HTTPException(422, "私钥大小须为 1 至 65536 字节")
    raw = raw.strip()
    lines = raw.splitlines()
    headers = {
        b"-----BEGIN OPENSSH PRIVATE KEY-----": b"-----END OPENSSH PRIVATE KEY-----",
        b"-----BEGIN PRIVATE KEY-----": b"-----END PRIVATE KEY-----",
        b"-----BEGIN RSA PRIVATE KEY-----": b"-----END RSA PRIVATE KEY-----",
        b"-----BEGIN EC PRIVATE KEY-----": b"-----END EC PRIVATE KEY-----",
    }
    if not lines or lines[0] not in headers or lines[-1] != headers[lines[0]]:
        raise HTTPException(422, "请提供完整的无口令 OpenSSH 或 PEM 私钥")
    if any(line.startswith((b"-----BEGIN", b"-----END")) for line in lines[1:-1]):
        raise HTTPException(422, "每条密钥记录只能包含一把私钥")
    loader = serialization.load_ssh_private_key if lines[0] == b"-----BEGIN OPENSSH PRIVATE KEY-----" else serialization.load_pem_private_key
    try:
        key = loader(raw, password=None)
        if not isinstance(key, (rsa.RSAPrivateKey, ed25519.Ed25519PrivateKey, ec.EllipticCurvePrivateKey)):
            raise HTTPException(422, "仅支持 RSA、Ed25519 和 ECDSA 私钥")
        public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
    except (ValueError, TypeError, UnsupportedAlgorithm):
        raise HTTPException(422, "私钥无效、不受支持或受口令保护") from None
    algorithm, encoded = public.split()
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(base64.b64decode(encoded)).digest()).decode().rstrip("=")
    return raw + b"\n", algorithm.decode(), fingerprint
