import os
import time
import math
import shutil
from urllib.parse import unquote
from pySmartDL import SmartDL
from urllib.error import HTTPError
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import BadRequest
from dotenv import load_dotenv

load_dotenv()

API_HASH = os.getenv('API_HASH')  # Api hash
APP_ID = int(os.getenv('APP_ID'))  # Api id/App id
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Bot token
OWNER_ID = os.getenv('OWNER_ID')  # Your telegram id
AS_ZIP = bool(os.getenv('AS_ZIP'))  # Upload method. If True: will Zip all your files and send as zipfile | If False: will send file one by one
BUTTONS = bool(os.getenv('BUTTONS'))  # Upload mode. If True: will send buttons (Zip or One by One) instead of AZ_ZIP | If False: will do as you've fill on AZ_ZIP

# Buttons
START_BUTTONS = [
    [
        InlineKeyboardButton("Source", url="https://github.com/X-Gorn/BulkLoader"),
        InlineKeyboardButton("Project Channel", url="https://t.me/xTeamBots"),
    ],
    [InlineKeyboardButton("Author", url="https://t.me/xgorn")],
]

CB_BUTTONS = [
    [
        InlineKeyboardButton("Zip", callback_data="zip"),
        InlineKeyboardButton("One by one", callback_data="1by1"),
    ]
]


# Helpers

# https://github.com/SpEcHiDe/AnyDLBot
async def progress_for_pyrogram(
    current,
    total,
    ud_type,
    message,
    start
):
    now = time.time()
    diff = now - start
    if round(diff % 10.00) == 0 or current == total:
        # if round(current / total * 100, 0) % 5 == 0:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion

        elapsed_time = TimeFormatter(milliseconds=elapsed_time)
        estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

        progress = "[{0}{1}] \nP: {2}%\n".format(
            ''.join(["█" for i in range(math.floor(percentage / 5))]),
            ''.join(["░" for i in range(20 - math.floor(percentage / 5))]),
            round(percentage, 2))

        tmp = progress + "{0} of {1}\nSpeed: {2}/s\nETA: {3}\n".format(
            humanbytes(current),
            humanbytes(total),
            humanbytes(speed),
            # elapsed_time if elapsed_time != '' else "0 s",
            estimated_total_time if estimated_total_time != '' else "0 s"
        )
        try:
            await message.edit(
                text="{}\n {}".format(
                    ud_type,
                    tmp
                )
            )
        except:
            pass


def humanbytes(size):
    # https://stackoverflow.com/a/49361727/4723940
    # 2**10 = 1024
    if not size:
        return ""
    power = 2 ** 10
    n = 0
    Dic_powerN = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


class TimeFormatter:
    def __init__(self, **kwargs):
        self.ms = kwargs.get('milliseconds', 0) % 1000
        self.seconds = kwargs.get('seconds', 0) % 60
        self.minutes = kwargs.get('minutes', 0) % 60
        self.hours = kwargs.get('hours', 0) % 24
        self.days = kwargs.get('days', 0)

    def __str__(self):
        # https://stackoverflow.com/a/32100285/4723940
        # https://code.luasoftware.com/tutorials/python/python-display-friendly-time-delta/
        if self.days:
            fmt = '{d}d {h}h {m}m {s}s'
        elif self.hours:
            fmt = '{h}h {m}m {s}s'
        elif self.minutes:
            fmt = '{m}m {s}s'
        else:
            fmt = '{s}s'

        return fmt.format(
            d=self.days,
            h=self.hours,
            m=self.minutes,
            s=self.seconds
        )


# Bot

app = Client("BulkLoader", bot_token=BOT_TOKEN, api_hash=API_HASH, api_id=APP_ID)

# Start command
@app.on_message(filters.command('start') & filters.private)
async def start(_, message):
    # Send start message
    if BUTTONS:
        await app.send_message(
            chat_id=message.chat.id,
            text="Hi {},\n\nI'm BulkLoader Bot!\n\nPlease send me a file with a list of URLs or a text file containing URLs.".format(
                message.from_user.first_name
            ),
            reply_markup=InlineKeyboardMarkup(START_BUTTONS)
        )
    else:
        await app.send_message(
            chat_id=message.chat.id,
            text="Hi {},\n\nI'm BulkLoader Bot!\n\nPlease send me a file with a list of URLs or a text file containing URLs.\n\nReply /cancel to stop the process.".format(
                message.from_user.first_name
            )
        )


# Callbacks
@app.on_callback_query(filters.regex(pattern="zip"))
async def zip_button(_, c: CallbackQuery):
    # Store user's choice (as ZIP)
    await c.answer("You have selected Zip mode!")
    await c.message.edit_reply_markup(InlineKeyboardMarkup(CB_BUTTONS))
    await app.set_config("as_zip", True)


@app.on_callback_query(filters.regex(pattern="1by1"))
async def one_by_one_button(_, c: CallbackQuery):
    # Store user's choice (one by one)
    await c.answer("You have selected One by One mode!")
    await c.message.edit_reply_markup(InlineKeyboardMarkup(CB_BUTTONS))
    await app.set_config("as_zip", False)


# File handler
@app.on_message(filters.document & filters.private)
async def process_file(_, message):
    # Check if the message has a document
    if message.document:
        file_name = message.document.file_name
        if not file_name.lower().endswith('.txt'):
            await message.reply_text('Please upload a text file (.txt) only.')
            return

        # Download the file
        start_time = time.time()
        await message.reply_text('Downloading file...')
        downloaded_file_path = await app.download_media(message)

        # Read the URLs from the file
        urls = []
        with open(downloaded_file_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line:
                    urls.append(line)

        total_urls = len(urls)
        if total_urls == 0:
            await message.reply_text('The file does not contain any valid URLs.')
            return

        # Start processing the URLs
        await message.reply_text('Processing {} URLs...'.format(total_urls))

        as_zip = await app.get_config("as_zip")
        if as_zip:
            zip_file_name = f"{file_name}_bulk.zip"
            zip_file_path = os.path.join('downloads', zip_file_name)

            # Create a directory to store the downloaded files
            download_directory = os.path.join('downloads', file_name)
            os.makedirs(download_directory, exist_ok=True)

            # Download the files
            success_count = 0
            failure_count = 0
            for index, url in enumerate(urls, start=1):
                try:
                    dl = SmartDL(url, progress_bar=False, dest=download_directory)
                    dl.start()
                    success_count += 1
                except HTTPError:
                    failure_count += 1

            # Zip the downloaded files
            shutil.make_archive(download_directory, 'zip', download_directory)

            # Move the zip file to the downloads folder
            shutil.move(f"{download_directory}.zip", zip_file_path)

            elapsed_time = TimeFormatter(milliseconds=(time.time() - start_time) * 1000)

            # Send the zip file
            await app.send_document(
                chat_id=message.chat.id,
                document=zip_file_path,
                caption=f"Processed {total_urls} URLs in {elapsed_time}\n\nSuccess: {success_count}\nFailure: {failure_count}",
                progress=progress_for_pyrogram,
                progress_args=(
                    "Uploading...",
                    start_time
                )
            )

            # Remove the downloaded files and directory
            shutil.rmtree(download_directory)

        else:
            success_count = 0
            failure_count = 0
            for index, url in enumerate(urls, start=1):
                try:
                    dl = SmartDL(url, progress_bar=False)
                    dl.start()
                    success_count += 1
                except HTTPError:
                    failure_count += 1

            elapsed_time = TimeFormatter(milliseconds=(time.time() - start_time) * 1000)

            await message.reply_text(
                f"Processed {total_urls} URLs in {elapsed_time}\n\nSuccess: {success_count}\nFailure: {failure_count}"
            )

        # Delete the downloaded file
        os.remove(downloaded_file_path)

    else:
        await message.reply_text('Please upload a file with a list of URLs.')


# Cancel command
@app.on_message(filters.command('cancel') & filters.private)
async def cancel(_, message):
    # Stop the current process
    await message.reply_text('Process canceled.')


app.run()
