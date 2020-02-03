import base64
import json
import logging
import socket
import sys
from hashlib import blake2s

from cryptography.fernet import Fernet

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("VnStat Client")


def get_vnstat(mode, host, port):
    with socket.create_connection((host, port)) as s:
        s.sendall(mode.encode())
        data = s.recv(4096)
    data_decrypted = f.decrypt(data)
    return json.loads(data_decrypted)


def init_key(password):
    key = base64.urlsafe_b64encode(
        blake2s(password.encode(), digest_size=16).hexdigest().encode()
    )
    return Fernet(key)


if __name__ == "__main__":
    password = sys.argv[1] if len(sys.argv) >= 2 else "test"
    f = init_key(password)
    result = get_vnstat("m", "127.0.0.1", 10000)
    logger.info(result)
