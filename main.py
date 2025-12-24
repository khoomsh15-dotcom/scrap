import os
import re
import random
import asyncio
from pyrogram import Client, filters, compose
from threading import Thread
from flask import Flask

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "31177437")) 
API_HASH = os.environ.get("API_HASH", "2edea950fe232f2e0ba6febfcd036452")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
TARGET_GROUP = os.environ.get("TARGET_GROUP", "-1003211737650")

# --- FLASK KEEP ALIVE ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is Running"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- CLIENTS ---
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_app = Client("my_scrapper", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# --- HELPER FUNCTIONS ---
def extract_numbers(text):
    if not text: return []
    matches = re.findall(r'\b\d{10,13}\b', text)
    clean_numbers = []
    for num in matches:
        clean_num = num[-10:]
        if clean_num[0] in ['6', '7', '8', '9']:
            clean_numbers.append(clean_num)
    return clean_numbers

async def perform_scraping(client, message, mode, limit):
    status_msg = await message.reply_text(f"🤖 Scraping started for **{mode}** mode.\nChecking last {limit} messages...")
    
    extracted_data = []
    try:
        target = int(TARGET_GROUP)
    except ValueError:
        target = TARGET_GROUP

    count = 0
    try:
        async for msg in user_app.get_chat_history(target, limit=limit):
            if not msg.text: continue
            text = msg.text
            found_numbers_in_msg = []

            if mode == "not_found":
                if "Not Found" in text:
                    found_numbers_in_msg = extract_numbers(text)
            elif mode == "found":
                if "SIM" in text: 
                    lines = text.split('\n')
                    for line in lines:
                        if "SIM" in line and "Not Found" not in line:
                            nums = extract_numbers(line)
                            found_numbers_in_msg.extend(nums)

            for num in found_numbers_in_msg:
                extracted_data.append(num)

            count += 1

    except Exception as e:
        await status_msg.edit(f"❌ Error during scraping: {str(e)}")
        return

    if not extracted_data:
        await status_msg.edit("❌ No data found matching your criteria.")
        return

    random.shuffle(extracted_data)
    file_path = f"{mode}_data.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        for num in extracted_data:
            f.write(f"{num}\n")

    await message.reply_document(
        document=file_path,
        caption=f"✅ **Scraping Complete**\n📂 Mode: {mode}\n🔢 Numbers found: {len(extracted_data)}\n🔀 Sequence: Randomized"
    )
    os.remove(file_path)
    await status_msg.delete()

# --- COMMANDS ---

# REMOVED filters.user(users=None) so it works for everyone
@bot.on_message(filters.command("scrapnotfound")) 
async def scrap_not_found_cmd(client, message):
    try:
        limit = int(message.command[1])
    except IndexError:
        limit = 1000 
    await perform_scraping(client, message, "not_found", limit)

@bot.on_message(filters.command("scrapfound"))
async def scrap_found_cmd(client, message):
    try:
        limit = int(message.command[1])
    except IndexError:
        limit = 1000
    await perform_scraping(client, message, "found", limit)

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("Bot is Online!\nUse:\n`/scrapnotfound <amount>`\n`/scrapfound <amount>`")

# --- MAIN ---
if __name__ == "__main__":
    print("Starting Web Server...")
    keep_alive()
    print("Starting Clients...")
    compose([bot, user_app])
