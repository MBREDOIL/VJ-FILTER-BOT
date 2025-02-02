import logging
import asyncio
import sqlite3
import requests
from bs4 import BeautifulSoup
from difflib import unified_diff
from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime, timedelta

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# SQLite database setup
def init_db():
    conn = sqlite3.connect("webpage_tracker.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            selector TEXT,
            last_content TEXT,
            last_checked TEXT,
            frequency INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS url_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_id INTEGER,
            visits INTEGER,
            changes INTEGER,
            FOREIGN KEY(url_id) REFERENCES tracked_urls(id)
        )
        """
    )
    conn.commit()
    return conn

# Initialize database
db_conn = init_db()

# Command to start the bot
@Client.on_message(filters.command("start"))
async def start(Client, message: Message):
    await message.reply_text(
        "Welcome to the Advanced Webpage Tracker Bot!\n"
        "Use /addurl to add a URL to track.\n"
        "Use /removeurl to remove a URL.\n"
        "Use /stats to get URL statistics.\n"
        "Use /fetch to fetch webpage content."
    )

# Command to add a URL with custom frequency
@Client.on_message(filters.command("addurl"))
async def add_url(Client, message: Message):
    args = message.command[1:]
    if len(args) < 2:
        await message.reply_text("Usage: /addurl <URL> <Frequency in minutes> [CSS Selector]")
        return

    url = args[0]
    frequency = int(args[1])
    selector = args[2] if len(args) > 2 else None
    user_id = message.from_user.id

    # Check if URL is already tracked by the user
    cursor = db_conn.cursor()
    cursor.execute(
        "SELECT id FROM tracked_urls WHERE user_id = ? AND url = ?", (user_id, url)
    )
    if cursor.fetchone():
        await message.reply_text("This URL is already being tracked.")
        return

    # Add URL to database
    cursor.execute(
        """
        INSERT INTO tracked_urls (user_id, url, selector, last_content, last_checked, frequency)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, url, selector, "", datetime.now().isoformat(), frequency),
    )
    url_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO url_stats (url_id, visits, changes)
        VALUES (?, 0, 0)
        """,
        (url_id,),
    )
    db_conn.commit()
    await message.reply_text(f"URL {url} has been added to the tracking list with a frequency of {frequency} minutes.")

# Command to remove a URL
@Client.on_message(filters.command("removeurl"))
async def remove_url(Client, message: Message):
    args = message.command[1:]
    if len(args) < 1:
        await message.reply_text("Usage: /removeurl <URL>")
        return

    url = args[0]
    user_id = message.from_user.id

    # Remove URL from database
    cursor = db_conn.cursor()
    cursor.execute(
        "DELETE FROM tracked_urls WHERE user_id = ? AND url = ?", (user_id, url)
    )
    db_conn.commit()
    if cursor.rowcount > 0:
        await message.reply_text(f"URL {url} has been removed from the tracking list.")
    else:
        await message.reply_text("This URL is not being tracked.")

# Command to get stats of a URL
@Client.on_message(filters.command("stats"))
async def get_stats(Client, message: Message):
    args = message.command[1:]
    if len(args) < 1:
        await message.reply_text("Usage: /stats <URL>")
        return

    url = args[0]
    user_id = message.from_user.id

    # Fetch stats from database
    cursor = db_conn.cursor()
    cursor.execute(
        """
        SELECT t.url, s.visits, s.changes, t.last_content, t.last_checked
        FROM tracked_urls t
        JOIN url_stats s ON t.id = s.url_id
        WHERE t.user_id = ? AND t.url = ?
        """,
        (user_id, url),
    )
    result = cursor.fetchone()
    if result:
        url, visits, changes, last_content, last_checked = result
        await message.reply_text(
            f"Stats for {url}:\nVisits: {visits}\nChanges: {changes}\nLast Checked: {last_checked}\nLast Content: {last_content[:100]}..."
        )
    else:
        await message.reply_text("This URL is not being tracked.")

# Command to fetch webpage content
@Client.on_message(filters.command("fetch"))
async def fetch_content(Client, message: Message):
    args = message.command[1:]
    if len(args) < 1:
        await message.reply_text("Usage: /fetch <URL>")
        return

    url = args[0]
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        content = soup.get_text()
        await message.reply_text(f"Content from {url}:\n{content[:1000]}...")  # Limit to first 1000 chars
    except Exception as e:
        await message.reply_text(f"Failed to fetch content: {e}")

# Scheduled task to periodically check URLs for changes
async def check_urls():
    while True:
        cursor = db_conn.cursor()
        cursor.execute("SELECT id, user_id, url, selector, last_content, last_checked, frequency FROM tracked_urls")
        for row in cursor.fetchall():
            url_id, user_id, url, selector, last_content, last_checked, frequency = row
            last_checked_time = datetime.fromisoformat(last_checked)
            next_check_time = last_checked_time + timedelta(minutes=frequency)

            if datetime.now() >= next_check_time:
                try:
                    response = requests.get(url)
                    soup = BeautifulSoup(response.content, "html.parser")
                    content = soup.get_text() if not selector else soup.select_one(selector).get_text()

                    if content != last_content:
                        # Highlight changes using difflib
                        diff = unified_diff(
                            last_content.splitlines(), content.splitlines(), lineterm=""
                        )
                        diff_text = "\n".join(diff)
                        await Client.send_message(
                            chat_id=user_id,
                            text=f"Content of {url} has changed!\nChanges:\n{diff_text[:1000]}...",
                        )

                        # Update database
                        cursor.execute(
                            "UPDATE tracked_urls SET last_content = ?, last_checked = ? WHERE id = ?",
                            (content, datetime.now().isoformat(), url_id),
                        )
                        cursor.execute(
                            "UPDATE url_stats SET changes = changes + 1 WHERE url_id = ?",
                            (url_id,),
                        )
                        db_conn.commit()
                    else:
                        # Update last_checked time if no changes were found
                        cursor.execute(
                            "UPDATE tracked_urls SET last_checked = ? WHERE id = ?",
                            (datetime.now().isoformat(), url_id),
                        )
                        db_conn.commit()
                except Exception as e:
                    logger.error(f"Error checking {url}: {e}")
        await asyncio.sleep(60)  # Check every minute
 