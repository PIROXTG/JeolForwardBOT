import os
import asyncio
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from datetime import date, datetime
from vars import SESSION, API_HASH, API_ID, BOT_TOKEN, LOG_CHANNEL, PORT, APP_URL
from typing import Union, Optional, AsyncGenerator
from script import scripts
from pyrogram import types
from utils import temp_utils
from aiohttp import web, ClientSession
from plugins import web_server
import logging
import pytz
import logging.config
import signal

logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

SESSION_FILE = f"{SESSION}.session"
if os.path.exists(SESSION_FILE):
    os.remove(SESSION_FILE)

class Bot(Client):
    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=25,
            plugins={"root": "plugins"},
            sleep_threshold=7
        )
        self.keep_alive_task = None

    async def keep_alive(self):
        """
        Periodically ping the app URL to prevent the application from sleeping
        """
        while True:
            try:
                async with ClientSession() as session:
                    async with session.get(APP_URL) as response:
                        if response.status == 200:
                            logging.info(f"Keep-alive ping to {APP_URL} successful")
                        else:
                            logging.warning(f"Keep-alive ping failed. Status code: {response.status}")
            except Exception as e:
                logging.error(f"Keep-alive error: {e}")
            
            await asyncio.sleep(7 * 60)

    async def start(self):
        await super().start()
        me = await self.get_me()
        temp_utils.ME = me.id
        temp_utils.USER_NAME = me.username
        temp_utils.BOT_NAME = me.first_name
        self.username = '@' + me.username
        logging.info(f"{me.first_name} with for Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
        
        tz = pytz.timezone('Asia/Kolkata')
        today = date.today()
        now = datetime.now(tz)
        time = now.strftime("%H:%M:%S %p")
        
        await self.send_message(chat_id=LOG_CHANNEL, text=scripts.RESTART_TXT.format(today, time))
        
        app = web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(app, bind_address, PORT).start()
        
        if APP_URL:
            self.keep_alive_task = asyncio.create_task(self.keep_alive())
        
    async def stop(self, *args):
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
        
        await super().stop()
        logging.info("Bot stopped. Bye.")
    
    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially.
        This convenience method does the same as repeatedly calling :meth:`~pyrogram.Client.get_messages` in a loop, thus saving
        you from the hassle of setting up boilerplate code. It is useful for getting the whole chat messages with a
        single call.
        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).
                
            limit (``int``):
                Identifier of the last message to be returned.
                
            offset (``int``, *optional*):
                Identifier of the first message to be returned.
                Defaults to 0.
        Returns:
            ``Generator``: A generator yielding :obj:`~pyrogram.types.Message` objects.
        Example:
            .. code-block:: python
                for message in app.iter_messages("pyrogram", 1, 15000):
                    print(message.text)
        """
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current+new_diff+1)))
            for message in messages:
                yield message
                current += 1

async def main():
    """
    Main async function to run the bot
    """
    app = Bot()
    await app.start()

    stop_event = asyncio.Event()
    def signal_handler():
        stop_event.set()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    await stop_event.wait()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())