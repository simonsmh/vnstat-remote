import asyncio
import base64
import json
import logging
import sys
from hashlib import blake2s

from cryptography.fernet import Fernet

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("VnStat Client")


async def get_vnstat(mode, addr):
    host, port = addr
    try:
        reader, writer = await asyncio.open_connection(host, port, loop=loop)
    except ConnectionRefusedError:
        return False
    writer.write(mode.encode())
    await writer.drain()
    data = await reader.read(4096)
    data_decrypted = f.decrypt(data)
    writer.close()
    data_decrypted = json.loads(data_decrypted)
    if data_decrypted.get("result"):
        return False
    return data_decrypted


def init_key(password):
    key = base64.urlsafe_b64encode(
        blake2s(password.encode(), digest_size=16).hexdigest().encode()
    )
    return Fernet(key)


if __name__ == "__main__":
    password = sys.argv[1] if len(sys.argv) >= 2 else "test"
    f = init_key(password)
    addrs = [("127.0.0.1", 10000), ("127.0.0.1", 10000)]
    loop = asyncio.get_event_loop()
    tasks = [get_vnstat("m", addr) for addr in addrs]
    result = loop.run_until_complete(asyncio.gather(*tasks))
    for i, r in enumerate(result):
        if r:
            logger.info(f"Received from {addrs[i][0]}:\n{r}")
