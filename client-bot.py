import asyncio
import base64
import json
import logging
import sys
import os
import math
from datetime import datetime, timedelta
from hashlib import blake2s

from cryptography.fernet import Fernet, InvalidToken
from telegram.ext import CommandHandler, Updater
from telegram.ext.dispatcher import run_async
from yaml import dump, load

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("VnStat Telegram Bot")


async def get_vnstat(f, addr):
    try:
        reader, writer = await asyncio.open_connection(
            addr.get("HOST"), addr.get("PORT")
        )
    except ConnectionRefusedError:
        logger.warning(f"ConnectionRefusedError for {addr.get('HOST')}")
        return False
    begin = addr.get("BEGIN")
    if begin > datetime.now().day:
        cycle = datetime.today().replace(day=begin) - timedelta(days=31)
    else:
        cycle = datetime.today().replace(day=begin)
    cycle_date = cycle.strftime("%Y-%m-%d")
    request_encrypted = f.encrypt(cycle_date.encode())
    writer.write(request_encrypted)
    await writer.drain()
    data = await reader.read(4096)
    writer.close()
    try:
        data_decrypted = json.loads(f.decrypt(data))
    except InvalidToken:
        logger.warning(f"InvalidToken for {addr.get('HOST')}")
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


def get_sum(dict):
    return convert_size(sum(dict))


def get_expect(dict):
    return convert_size(sum(dict) / len(dict) * 30)


def convert_size(size):
    size_name = "BKMGTPEZ"
    if isinstance(size, str):
        try:
            i = size_name.index(size[-1])
        except ValueError:
            i = 0
            size += size_name[i]
        p = math.pow(1024, i)
        size = int(size.rstrip(size_name))
        s = round(size * p, 2)
        return s
    else:
        if size == 0:
            return f"{size}{size_name[0]}"
        i = int(math.floor(math.log(int(size), 1024)))
        p = math.pow(1024, i)
        s = round(size / p, 2)
        return f"{s}{size_name[i]}"


@run_async
def error(update, context):
    logger.warning(f"Update {context} caused error {error}")


@run_async
def start(update, context):
    message = update.message
    chat = message.forward_from_chat if message.forward_from_chat else message.chat
    for job in context.job_queue.get_jobs_by_name(str(config.get("CHAT"))):
        job.schedule_removal()
    context.job_queue.run_repeating(
        check_queue, interval=config.get("INTERVAL"), first=1, context=context, name=str(config.get("CHAT"))
    )
    jobs = [t.name for t in context.job_queue.jobs()]
    message.reply_markdown(f"CHAT ID: `{chat.id}`\nSending to {config.get('CHAT')}\nCurrent Jobs: {jobs}")
    logger.info(f"Start command: Current Jobs: {jobs}")


@run_async
def check_queue(context):
    password = config.get("PASSWORD")
    f = init_key(password)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [get_vnstat(f, addr) for addr in config.get("ADDRS")]
    results = loop.run_until_complete(asyncio.gather(*tasks))
    message = context.bot.send_message(
        config.get("CHAT"), f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    text = str()
    for i, result in enumerate(results):
        conf = config.get("ADDRS")[i]
        if not result:
            text += (f"#{conf.get('HOST')} 掉线")
            continue
        interface = result.get("interfaces")[0]
        rx = [day.get("rx") for day in interface.get("traffic").get("day")]
        tx = [day.get("tx") for day in interface.get("traffic").get("day")]
        text += config.get("INFO").format(
            host=conf.get("HOST"),
            interface=interface.get("name"),
            rx=get_sum(rx),
            tx=get_sum(tx),
            exrx=get_expect(rx),
            extx=get_expect(tx),
        )
        warning = (
            (convert_size(conf.get("LIMIT")) < sum(rx) + sum(tx))
            if conf.get("LIMIT")
            else None
        )
        if warning:
            text += config.get("WARNING")
    logger.info(text)
    message.edit_text(f"{message.text}\n{text}")


def load_yaml(filename="config.yml"):
    try:
        with open(filename, "r") as file:
            config = load(file, Loader=Loader)
    except FileNotFoundError:
        try:
            filename = f"{os.path.split(os.path.realpath(__file__))[0]}/{filename}"
            with open(filename, "r") as file:
                config = load(file, Loader=Loader)
        except FileNotFoundError:
            logger.exception(f"Cannot find {filename}.")
            sys.exit(1)
    logger.info(f"Yaml: Loaded {filename}")
    return config


if __name__ == "__main__":
    if len(sys.argv) >= 2 and os.path.exists(sys.argv[1]):
        config = load_yaml(sys.argv[1])
    else:
        config = load_yaml()
    logger.info(f"Bot: Starting & Sending to {config.get('CHAT')}")
    updater = Updater(config.get("TOKEN"), use_context=True)
    updater.job_queue.run_repeating(
        check_queue, interval=config.get("INTERVAL"), name=str(config.get("CHAT"))
    )
    updater.dispatcher.add_handler(CommandHandler("start", start))
    updater.dispatcher.add_error_handler(error)
    updater.start_polling()
    updater.idle()
