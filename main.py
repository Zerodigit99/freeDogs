import os
import time
import hashlib
import threading
import logging
import requests
import telebot
from flask import Flask, request
from urllib.parse import urlparse, parse_qs
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from memeFi.memefi import run_memefi_script  # Assuming memefi.py is in the memeFi directory

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram bot setup
TOKEN = "7712603902:AAHGFpU5lAQFuUUPYlM1jbu1u6XJGgs15Js"
bot = telebot.TeleBot(TOKEN)
is_collecting = {}  # Dictionary to control collection status per user
user_sessions = {}  # Dictionary to store each user's session URL
required_channel = "@gray_community"

# Flask app to handle webhook requests
app = Flask(__name__)

# Headers for requests to the coin-collection API
headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'authorization': '',
    'x-requested-with': 'org.telegram.messenger',
}

# Accepted scripts
accepted_scripts = [
    "Circle",
    "MemeFi",
    "Booms",
    "Cherry Game",
    "Paws",
    "Seed",
    "Blum",
    "FreeDogs"
]

ADMIN_ID = 7175868924  # Admin user ID for accessing special commands

def compute_md5(amount, seq):
    prefix = str(amount) + str(seq) + "7be2a16a82054ee58398c5edb7ac4a5a"
    return hashlib.md5(prefix.encode()).hexdigest()

def auth(url: str) -> dict:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.fragment)
    init = query_params.get('tgWebAppData', [None])[0]
    params = {'invitationCode': '', 'initData': init}
    data = {'invitationCode': '', 'initData': init}
    response = requests.post('https://api.freedogs.bot/miniapps/api/user/telegram_auth', params=params, headers=headers, data=data)
    return response.json()

def do_click(init):
    auth_response = auth(init)
    token = auth_response.get('data', {}).get('token')
    if not token:
        raise ValueError("Authorization token not found.")
        
    headers['authorization'] = 'Bearer ' + token

    response = requests.get('https://api.freedogs.bot/miniapps/api/user_game_level/GetGameInfo', headers=headers)
    Seq = response.json()['data']['collectSeqNo']

    hsh = compute_md5('100000', Seq)
    params = {
        'collectAmount': '100000',
        'hashCode': hsh,
        'collectSeqNo': str(Seq),
    }
    response = requests.post('https://api.freedogs.bot/miniapps/api/user_game/collectCoin', headers=headers, data=params)
    return response.json()

def continuous_collect(user_id, interval=60):
    while is_collecting.get(user_id, False):
        try:
            result = do_click(user_sessions[user_id])
            if time.time() % (30 * 60) < interval:  # Sends success message every 30 minutes
                bot.send_message(user_id, "Collection successful!")
        except Exception as e:
            bot.send_message(user_id, f"An error occurred: {e}")
        
        time.sleep(interval)

def check_channel_membership(user_id):
    """Check if the user is a member of the required channel."""
    try:
        member_status = bot.get_chat_member(required_channel, user_id)
        return member_status.status in ["member", "administrator", "creator"]
    except Exception:
        return False

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if check_channel_membership(user_id):
        bot.send_message(user_id, "Hey! Welcome to Gray Zero Bot.\n\n"
                                   "This bot allows you to interact with various scripts and automation tools.\n"
                                   "Use /scripts to view the list of available scripts you can use.")
    else:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Join Channel", url=f"https://t.me/{required_channel.strip('@')}"))
        keyboard.add(InlineKeyboardButton("Verify Membership", callback_data='verify_membership'))
        bot.send_message(user_id, "You must join our channel to use this bot. Click the button below to join, then press 'Verify Membership'.", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'verify_membership')
def verify_membership(call):
    user_id = call.message.chat.id
    if check_channel_membership(user_id):
        bot.answer_callback_query(call.id, "Membership verified!")
        bot.send_message(user_id, "Thank you for verifying! You can now use other bot features.")
        start(call.message)  # Automatically start the bot after successful verification
    else:
        bot.answer_callback_query(call.id, "Please join the required channel to proceed.")
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Join Channel", url=f"https://t.me/{required_channel.strip('@')}"))
        bot.send_message(user_id, "You must join our channel to use this bot.", reply_markup=keyboard)

@bot.message_handler(commands=['scripts'])
def show_scripts(message):
    user_id = message.chat.id
    if check_channel_membership(user_id):
        scripts = "\n".join([f"{i + 1}. {script}" for i, script in enumerate(accepted_scripts)])
        bot.send_message(user_id, f"Accepted scripts:\n{scripts}")
    else:
        bot.send_message(user_id, "Please join our channel to access this feature.")

@bot.message_handler(commands=['memefi'])
def run_memefi(message):
    user_id = message.chat.id

    if not check_channel_membership(user_id):
        bot.send_message(user_id, "Please join our channel to access this feature.")
        return

    if user_id not in user_sessions:
        bot.send_message(user_id, "Please send your session URL first (the link with `tgWebAppData`).")
        return
    
    try:
        result = run_memefi_script(user_sessions[user_id])  # Assuming run_memefi_script takes session URL as input
        bot.send_message(user_id, f"MemeFi Script executed successfully: {result}")
    except Exception as e:
        bot.send_message(user_id, f"An error occurred while running the MemeFi script: {e}")

@bot.message_handler(commands=['start_collecting'])
def start_collecting(message):
    user_id = message.chat.id

    if not check_channel_membership(user_id):
        bot.send_message(user_id, "Please join our channel to access this feature.")
        return

    if user_id not in user_sessions:
        bot.send_message(user_id, "Please send your session URL first (the link with `tgWebAppData`).")
        return
    
    if not is_collecting.get(user_id, False):
        is_collecting[user_id] = True
        bot.send_message(user_id, "Started collecting coins every minute.")
        threading.Thread(target=continuous_collect, args=(user_id, 60)).start()
    else:
        bot.send_message(user_id, "Already collecting coins!")

@bot.message_handler(commands=['stop'])
def stop_collecting(message):
    user_id = message.chat.id
    if check_channel_membership(user_id):
        if is_collecting.get(user_id, False):
            is_collecting[user_id] = False
            bot.send_message(user_id, "Stopped collecting coins.")
        else:
            bot.send_message(user_id, "Coin collection is not active.")
    else:
        bot.send_message(user_id, "Please join our channel to access this feature.")

@bot.message_handler(commands=['list_sessions'])
def list_sessions(message):
    if message.chat.id == ADMIN_ID:
        session_list = "\n".join([f"User ID: {uid}, Session URL: {url}" for uid, url in user_sessions.items()])
        bot.send_message(ADMIN_ID, f"Active user sessions:\n{session_list}" if session_list else "No active sessions.")
    else:
        bot.send_message(message.chat.id, "You do not have permission to access this command.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.chat.id
    if 'tgWebAppData' in message.text:
        user_sessions[user_id] = message.text.strip()  # Store the session URL for the user
        bot.send_message(user_id, "Session URL successfully saved. You can now start collecting coins using /start_collecting.")
    else:
        bot.send_message(user_id, "Please provide a valid session URL to continue.")

# Set webhook for the bot
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

@app.route('/')
def index():
    return "Bot is running!"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url='https://freedogs-1.onrender.com/' + TOKEN)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
