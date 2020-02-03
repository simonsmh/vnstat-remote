import socket
import sys
import logging
import subprocess
import asyncio

PORT = 10000

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("VnStat Server")


async def handler(reader, writer):
    data = await reader.read(1)
    addr = writer.get_extra_info("peername")
    logger.info(f"Received {data} from {addr}")

    mode = data
    try:
        sp = subprocess.run(
            ["vnstat", "--json", mode, "--limit", "1"], capture_output=True, check=True
        )
        result = sp.stdout
    except subprocess.CalledProcessError as err:
        logger.warning(f"Subprocess: {err}")
        result = '{"result": "error"}'.encode()

    logger.debug(f"Sending: {result}")
    writer.write(result)
    await writer.drain()
    writer.close()


async def main():
    server = await asyncio.start_server(handler, port=PORT, reuse_port=True)
    addr = server.sockets[0].getsockname()
    logger.info(f"Serving on {addr}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
