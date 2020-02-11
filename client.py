import asyncio
import base64
import json
import logging
import sys
from datetime import datetime, timedelta
from hashlib import blake2s

from cryptography.fernet import Fernet, InvalidToken

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("VnStat Client")


async def get_vnstat(addr):
    try:
        reader, writer = await asyncio.open_connection(
            addr.get("host"), addr.get("port")
        )
    except ConnectionRefusedError:
        logger.warning(f"ConnectionRefusedError for {addr.get('host')}")
        return False
    begin = addr.get("begin")
    if begin > datetime.now().day:
        cycle = datetime.today().replace(day=begin) - timedelta(days=31)
    else:
        cycle = datetime.today().replace(day=begin)
    cycle_date = cycle.strftime("%Y-%m-%d")
    request_encrypted = f.encrypt(cycle_date.encode()) + b"\n"
    writer.write(request_encrypted)
    await writer.drain()
    data = await reader.readuntil()
    writer.close()
    try:
        data_decrypted = json.loads(f.decrypt(data))
        logger.info(f"Receiving:\n{data}\n{data_decrypted}")
    except InvalidToken:
        logger.warning(f"InvalidToken for {addr.get('host')}")
        return False
    if data_decrypted.get("error"):
        logger.warning(f"{data_decrypted.get('error')}")
        return False
    return data_decrypted


def init_key(password):
    key = base64.urlsafe_b64encode(
        blake2s(password.encode(), digest_size=16).hexdigest().encode()
    )
    return Fernet(key)



def get_expect(rx, tx, update_time):
    def today(dict, update_time):
        return (
            dict[-1] / (update_time.get("hour") * 60 + update_time.get("minute")) * 1440
        )

    def expect(dict, update_time):
        return (sum(dict[0:-1]) + today(dict, update_time)) / len(dict) * 30

    exrx, extx = expect(rx, update_time), expect(tx, update_time)
    return exrx, extx, exrx + extx



if __name__ == "__main__":
    password = sys.argv[1] if len(sys.argv) >= 2 else "test"
    f = init_key(password)
    addrs = [
        {"host": "127.0.0.1", "port": 10000, "begin": 9},
        {"host": "127.0.0.1", "port": 10000, "begin": 7},
    ]
    loop = asyncio.get_event_loop()
    tasks = [get_vnstat(addr) for addr in addrs]
    results = loop.run_until_complete(asyncio.gather(*tasks))
    for i, result in enumerate(results):
        if not result:
            continue
        logger.info(f'Received from {addrs[i].get("host")}')
        interface = result.get("interfaces")[0]
        update_time = interface.get("updated").get("time")
        logger.info(f'Parsing Interface {interface.get("name")}')
        rx = [day.get("rx") for day in interface.get("traffic").get("day")]
        tx = [day.get("tx") for day in interface.get("traffic").get("day")]
        exrx, extx, exttl = get_expect(rx, tx, update_time)
        logger.info(f"Rx: {sum(rx)}, Tx: {sum(tx)}, TTL: {sum(rx + tx)}")
        logger.info(
            f"Expect Rx: {exrx}, Expect Tx: {extx}, Expect TTL: {exttl}"
        )
