import discord
from discord import app_commands
import sqlite3
import time
import os
import asyncio

# ---------------- CONFIG ---------------- #

TOKEN = os.getenv("DISCORD_TOKEN")  # Your bot token in Railway
DAY_SECONDS = 86400  # 1 day in seconds

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ---------------- DATABASE ---------------- #

db = sqlite3.connect("plants.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS plants (
    thread_id INTEGER PRIMARY KEY,
    interval_days INTEGER DEFAULT 7,
    last_watered INTEGER,
    reminded_water INTEGER DEFAULT 0,
    interval_fertilizer INTEGER DEFAULT 30,
    last_fertilized INTEGER,
    reminded_fertilizer INTEGER DEFAULT 0
)
""")
db.commit()

def now():
    return int(time.time())

# ---------------- REMINDER FUNCTION ---------------- #

async def send_reminders():
    await client.wait_until_ready()

    cursor.execute("""
        SELECT thread_id, interval_days, last_watered, reminded_water,
               interval_fertilizer, last_fertilized, reminded_fertilizer
        FROM plants
        WHERE last_watered IS NOT NULL OR last_fertilized IS NOT NULL
    """)
    for row in cursor.fetchall():
        (thread_id, interval_days, last_watered, reminded_water,
         interval_fertilizer, last_fertilized, reminded_fertilizer) = row

        thread = client.get_channel(thread_id)
        if not thread:
            continue

        # Water reminder
        if last_watered and not reminded_water:
            if now() >= last_watered + (interval_days * DAY_SECONDS):
                try:
                    await thread.send("💧 **Water reminder!** Time to check soil moisture 🌱")
                    cursor.execute("UPDATE plants SET reminded_water=1 WHERE thread_id=?", (thread_id,))
                    db.commit()
                except Exception as e:
                    print(f"Error sending water reminder: {e}")

        # Fertilizer reminder
        if last_fertilized and not reminded_fertilizer:
            if now() >= last_fertilized + (interval_fertilizer * DAY_SECONDS):
                try:
                    await thread.send("🌿 **Fertilizer reminder!** Time to fertilize your plant 💚")
                    cursor.execute("UPDATE plants SET reminded_fertilizer=1 WHERE thread_id=?", (thread_id,))
                    db.commit()
                except Exception as e:
                    print(f"Error sending fertilizer reminder: {e}")

    # After all reminders, the script can exit
    await client.close()

# ---------------- BOT READY ---------------- #

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await send_reminders()

# ---------------- RUN BOT ---------------- #

client.run(TOKEN)
