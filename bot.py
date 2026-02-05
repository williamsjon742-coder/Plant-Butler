import discord
from discord import app_commands
import sqlite3
import time
import asyncio
import os

# ---------------- CONFIG ---------------- #

TOKEN = os.getenv("DISCORD_TOKEN")  # Load token securely from Railway
CHECK_INTERVAL = 60      # seconds for testing; change to 3600 for 1 hour
DAY_SECONDS = 60         # seconds for testing; change to 86400 for 1 day

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ---------------- DATABASE ---------------- #

# SQLite DB for plants
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

# ---------------- WATER COMMANDS ---------------- #

@tree.command(name="water", description="Log that you watered this plant")
async def water(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "🌱 Use this command inside a plant thread.", ephemeral=True
        )
        return

    await interaction.channel.join()

    thread_id = interaction.channel.id
    cursor.execute("""
        INSERT INTO plants (thread_id, interval_days, last_watered, reminded_water)
        VALUES (?, 7, ?, 0)
        ON CONFLICT(thread_id)
        DO UPDATE SET last_watered=?, reminded_water=0
    """, (thread_id, now(), now()))
    db.commit()

    await interaction.response.send_message("💧 Watered! Timer reset.")

@tree.command(name="interval", description="Set watering interval in days")
@app_commands.describe(days="Number of days between watering checks")
async def interval(interaction: discord.Interaction, days: int):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "🌱 Use this command inside a plant thread.", ephemeral=True
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

    await interaction.response.send_message(f"⏱ Watering interval set to **{days} days**")

# ---------------- FERTILIZER COMMANDS ---------------- #

@tree.command(name="fertilize", description="Log that you fertilized this plant")
async def fertilize(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "🌱 Use this command inside a plant thread.", ephemeral=True
        )
        return

    await interaction.channel.join()
    thread_id = interaction.channel.id
    cursor.execute("""
        INSERT INTO plants (thread_id, interval_fertilizer, last_fertilized, reminded_fertilizer)
        VALUES (?, 30, ?, 0)
        ON CONFLICT(thread_id)
        DO UPDATE SET last_fertilized=?, reminded_fertilizer=0
    """, (thread_id, now(), now()))
    db.commit()
    await interaction.response.send_message("🌿 Fertilized! Timer reset.")

@tree.command(name="fertilizer_interval", description="Set fertilizer interval in days")
@app_commands.describe(days="Number of days between fertilizer checks")
async def fertilizer_interval(interaction: discord.Interaction, days: int):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "🌱 Use this command inside a plant thread.", ephemeral=True
        )
        return

    await interaction.channel.join()
    cursor.execute("""
        INSERT INTO plants (thread_id, interval_fertilizer)
        VALUES (?, ?)
        ON CONFLICT(thread_id)
        DO UPDATE SET interval_fertilizer=?
    """, (interaction.channel.id, days, days))
    db.commit()
    await interaction.response.send_message(f"⏱ Fertilizer interval set to **{days} days**")

# ---------------- STATUS COMMAND ---------------- #

@tree.command(name="status", description="Check plant watering and fertilizer status")
async def status(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "🌱 Use this command inside a plant thread.", ephemeral=True
        )
        return

    await interaction.channel.join()
    cursor.execute("""
        SELECT interval_days, last_watered, interval_fertilizer, last_fertilized
        FROM plants
        WHERE thread_id=?
    """, (interaction.channel.id,))
    row = cursor.fetchone()

    if not row:
        await interaction.response.send_message("🌱 No plant data yet.")
        return

    interval_days, last_watered, interval_fertilizer, last_fertilized = row
    water_days = (now() - last_watered) // DAY_SECONDS if last_watered else "N/A"
    fertilizer_days = (now() - last_fertilized) // DAY_SECONDS if last_fertilized else "N/A"

    await interaction.response.send_message(
        f"🌿 **Plant Status**\n"
        f"Last watered: **{water_days} days ago** (Interval: {interval_days} days)\n"
        f"Last fertilized: **{fertilizer_days} days ago** (Interval: {interval_fertilizer} days)"
    )

# ---------------- REMINDER LOOP ---------------- #

async def reminder_loop():
    await client.wait_until_ready()
    while True:
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

        await asyncio.sleep(CHECK_INTERVAL)

# ---------------- BOT READY ---------------- #

@client.event
async def on_ready():
    await tree.sync()
    client.loop.create_task(reminder_loop())
    print(f"Logged in as {client.user}")

client.run(TOKEN)
