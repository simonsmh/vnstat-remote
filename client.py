import socket
import logging
import json

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("VnStat Client")


def get_vnstat(mode, host, port):
    with socket.create_connection((host, port)) as s:
        s.sendall(mode.encode())
        data = s.recv(4096)
    return json.loads(data.decode())


if __name__ == "__main__":
    result = get_vnstat("m", "127.0.0.1", 10000)
    logger.info(result)
