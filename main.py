import os
import re
import random
import asyncio
from pyrogram import Client, filters
from threading import Thread
from flask import Flask

# --- CONFIGURATION (Load from Env Variables for Render) ---
API_ID = int(os.environ.get("API_ID", "123456")) 
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
SESSION_STRING = os.environ.get("SESSION_STRING", "your_session_string")
TARGET_GROUP = os.environ.get("TARGET_GROUP", "group_username_or_id")

# --- FLASK KEEP ALIVE (For Render) ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is Running"

def run_web():
    # Render assigns a PORT via environment variable
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- TELEGRAM CLIENTS ---
# The Bot (Master) that you talk to
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# The User (Scraper) that reads the group messages
user_app = Client("my_scrapper", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# --- HELPER FUNCTIONS ---

def extract_numbers(text):
    """
    Extracts phone numbers. 
    It looks for strings of 10 to 13 digits. 
    It returns the LAST 10 digits to normalize (removing +91 prefix if present).
    """
    if not text:
        return []
    
    # Regex to find numbers that look like mobile numbers
    # Matches patterns like: 919876543210 or 9876543210
    matches = re.findall(r'\b\d{10,13}\b', text)
    
    clean_numbers = []
    for num in matches:
        # Take the last 10 digits (removes 91 or 0 prefix)
        clean_num = num[-10:]
        # Basic validation: Indian mobile numbers usually start with 6-9
        if clean_num[0] in ['6', '7', '8', '9']:
            clean_numbers.append(clean_num)
            
    return clean_numbers

async def perform_scraping(client, message, mode, limit):
    status_msg = await message.reply_text(f"🤖 Scraping started for **{mode}** mode.\nChecking last {limit} messages...")
    
    extracted_data = []
    
    # Ensure TARGET_GROUP is treated as int if it's an ID, or string if username
    try:
        target = int(TARGET_GROUP)
    except ValueError:
        target = TARGET_GROUP

    count = 0
    try:
        # Iterate through history using the User Client
        async for msg in user_app.get_chat_history(target, limit=limit):
            if not msg.text:
                continue

            text = msg.text
            found_numbers_in_msg = []

            # --- LOGIC 1: NOT FOUND CATEGORY ---
            if mode == "not_found":
                # Only process if "Not Found" is explicitly written in the message
                if "Not Found" in text:
                    # We look for numbers HIDDEN in the body (like Jio Number: xxx)
                    # We assume the SIM fields are empty/not found, so we scan the whole text
                    found_numbers_in_msg = extract_numbers(text)

            # --- LOGIC 2: FOUND CATEGORY ---
            elif mode == "found":
                # Only process if "Not Found" is NOT in the text (or we rely on SIM fields)
                # Per your logic: If one is found and one is not, it counts as found.
                # So we prioritize messages that actually contain SIM numbers.
                
                # Simple check: Does it have numbers, and is it NOT a pure "Not Found" alert?
                # Or specifically check SIM lines if you want to be strict.
                # Here we scrape everything that looks like a number provided it fits the context.
                if "SIM" in text: 
                    # Extract numbers specifically near "SIM" or just general numbers
                    # Since "Not Found" messages also have timestamps (numbers), we need to be careful.
                    
                    # If the message is strictly the "Found" type:
                    lines = text.split('\n')
                    for line in lines:
                        if "SIM" in line and "Not Found" not in line:
                            nums = extract_numbers(line)
                            found_numbers_in_msg.extend(nums)

            # Add unique numbers from this message to the main list
            for num in found_numbers_in_msg:
                extracted_data.append(num)

            count += 1
            if count % 100 == 0:
                # Log progress internally or edit message periodically (optional)
                pass

    except Exception as e:
        await status_msg.edit(f"❌ Error during scraping: {str(e)}")
        return

    if not extracted_data:
        await status_msg.edit("❌ No data found matching your criteria.")
        return

    # --- POST PROCESSING ---
    # 1. Randomize sequence
    random.shuffle(extracted_data)
    
    # 2. Write to normal .txt file
    file_path = f"{mode}_data.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        for num in extracted_data:
            f.write(f"{num}\n")

    # 3. Send file
    await message.reply_document(
        document=file_path,
        caption=f"✅ **Scraping Complete**\n📂 Mode: {mode}\n🔢 Numbers found: {len(extracted_data)}\n🔀 Sequence: Randomized"
    )

    # 4. Cleanup
    os.remove(file_path)
    await status_msg.delete()

# --- BOT COMMANDS ---

@bot.on_message(filters.command("scrapnotfound") & filters.user(users=None)) # You can restrict users here if needed
async def scrap_not_found_cmd(client, message):
    # Usage: /scrapnotfound 1000
    try:
        limit = int(message.command[1])
    except IndexError:
        limit = 1000 # Default
    
    await perform_scraping(client, message, "not_found", limit)

@bot.on_message(filters.command("scrapfound"))
async def scrap_found_cmd(client, message):
    # Usage: /scrapfound 1000
    try:
        limit = int(message.command[1])
    except IndexError:
        limit = 1000 # Default
        
    await perform_scraping(client, message, "found", limit)

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("Bot is Online!\nUse:\n`/scrapnotfound <amount>`\n`/scrapfound <amount>`")

# --- MAIN EXECUTION ---

if __name__ == "__main__":
    print("Starting Web Server...")
    keep_alive()
    
    print("Starting Pyrogram Clients...")
    # Using compose to run both User and Bot clients in the same loop
    from pyrogram import compose
    compose([bot, user_app])
