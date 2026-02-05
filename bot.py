import discord
from discord import app_commands
import sqlite3
import time
import asyncio
import os

# ---------------- CONFIG ---------------- #

TOKEN = os.getenv("DISCORD_TOKEN")  # Load token securely from environment variable
CHECK_INTERVAL = 60      # seconds for testing; change to 3600 for 1-hour checks
DAY_SECONDS = 60         # seconds for testing; change to 86400 for 1-day checks

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
    reminded INTEGER DEFAULT 0
)
""")
db.commit()

def now():
    return int(time.time())

# ---------------- COMMANDS ---------------- #

@tree.command(name="water", description="Log that you watered this plant")
async def water(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "🌱 Use this command inside a plant thread.",
            ephemeral=True
        )
        return

    await interaction.channel.join()

    thread_id = interaction.channel.id
    cursor.execute("""
        INSERT INTO plants (thread_id, interval_days, last_watered, reminded)
        VALUES (?, 7, ?, 0)
        ON CONFLICT(thread_id)
        DO UPDATE SET last_watered=?, reminded=0
    """, (thread_id, now(), now()))
    db.commit()

    await interaction.response.send_message("💧 Watered! Timer reset.")

@tree.command(name="interval", description="Set watering interval in days")
@app_commands.describe(days="Number of days between watering checks")
async def interval(interaction: discord.Interaction, days: int):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "🌱 Use this command inside a plant thread.",
            ephemeral=True
        )
        return

    await interaction.channel.join()

    cursor.execute("""
        INSERT INTO plants (thread_id, interval_days)
        VALUES (?, ?)
        ON CONFLICT(thread_id)
        DO UPDATE SET interval_days=?
    """, (interaction.channel.id, days, days))
    db.commit()

    await interaction.response.send_message(f"⏱ Interval set to **{days} days**")

@tree.command(name="status", description="Check plant watering status")
async def status(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "🌱 Use this command inside a plant thread.",
            ephemeral=True
        )
        return

    await interaction.channel.join()

    cursor.execute("""
        SELECT interval_days, last_watered FROM plants
        WHERE thread_id=?
    """, (interaction.channel.id,))
    row = cursor.fetchone()

    if not row or not row[1]:
        await interaction.response.send_message("🌱 No watering data yet.")
        return

    interval_days, last_watered = row
    days_ago = (now() - last_watered) // DAY_SECONDS

    await interaction.response.send_message(
        f"🌿 **Plant Status**\n"
        f"Last watered: **{days_ago} days ago**\n"
        f"Interval: **{interval_days} days**"
    )

# ---------------- REMINDER LOOP ---------------- #

async def reminder_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        cursor.execute("""
            SELECT thread_id, interval_days, last_watered, reminded
            FROM plants
            WHERE last_watered IS NOT NULL
        """)
        for thread_id, interval_days, last_watered, reminded in cursor.fetchall():
            if reminded:
                continue
            if now() >= last_watered + (interval_days * DAY_SECONDS):
                thread = client.get_channel(thread_id)
                if thread:
                    await thread.send(
                        "🌿 **Plant check reminder!** Time to check soil moisture 💧"
                    )
                    cursor.execute(
                        "UPDATE plants SET reminded=1 WHERE thread_id=?",
                        (thread_id,)
                    )
                    db.commit()
        await asyncio.sleep(CHECK_INTERVAL)

# ---------------- BOT READY ---------------- #

@client.event
async def on_ready():
    await tree.sync()
    client.loop.create_task(reminder_loop())
    print(f"Logged in as {client.user}")

client.run(TOKEN)

