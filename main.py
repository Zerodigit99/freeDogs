import os
import time
import hashlib
import threading
import logging
import requests
import telebot
from flask import Flask, request
from urllib.parse import urlparse, parse_qs

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram bot setup
TOKEN = "7712603902:AAHGFpU5lAQFuUUPYlM1jbu1u6XJGgs15Js"
bot = telebot.TeleBot(TOKEN)
is_collecting = {}  # Dictionary to control collection status per user
user_sessions = {}  # Dictionary to store each user's session URL

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

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Hey! Welcome to Gray Zero Bot.\n\n"
                                        "This bot allows you to interact with various scripts and automation tools.\n"
                                        "Use /scripts to view the list of available scripts you can use.")

@bot.message_handler(commands=['scripts'])
def show_scripts(message):
    scripts = "\n".join([f"{i + 1}. {script}" for i, script in enumerate(accepted_scripts)])
    bot.send_message(message.chat.id, f"Accepted scripts:\n{scripts}")

@bot.message_handler(commands=['start_collecting'])
def start_collecting(message):
    user_id = message.chat.id

    # Check if session URL is provided by the user
    if user_id not in user_sessions:
        bot.send_message(user_id, "Please send your session URL first (the link with `tgWebAppData`).")
        return
    
    # Start collecting if not already active for the user
    if not is_collecting.get(user_id, False):
        is_collecting[user_id] = True
        bot.send_message(user_id, "Started collecting coins every minute.")
        threading.Thread(target=continuous_collect, args=(user_id, 60)).start()
    else:
        bot.send_message(user_id, "Already collecting coins!")

@bot.message_handler(commands=['stop'])
def stop_collecting(message):
    user_id = message.chat.id
    if is_collecting.get(user_id, False):
        is_collecting[user_id] = False
        bot.send_message(user_id, "Stopped collecting coins.")
    else:
        bot.send_message(user_id, "Coin collection is not active.")

@bot.message_handler(commands=['status'])
def status(message):
    user_id = message.chat.id
    # Check if the user has provided a session URL
    if user_id not in user_sessions:
        bot.send_message(user_id, "Please send your session URL first (the link with `tgWebAppData`).")
    elif is_collecting.get(user_id, False):
        bot.send_message(user_id, "Currently collecting coins every 30 minutes.")
    else:
        bot.send_message(user_id, "Coin collection is inactive.")

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
        user_sessions[user_id] = message.text.strip()
        bot.send_message(user_id, "Session URL received! Now, use /start_collecting to begin.")
    else:
        bot.send_message(user_id, "Please send a valid session URL (link containing `tgWebAppData`).")

# Set webhook for the bot
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url='https://freedogs-1.onrender.com/' + TOKEN)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
