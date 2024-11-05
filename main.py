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
is_collecting = False  # Flag to control continuous collection
chat_id = None  # Stores the chat ID for sending messages
session_url = None  # Stores the session URL provided by the user

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

def continuous_collect(init_url, interval=60):
    global is_collecting
    while is_collecting:
        try:
            result = do_click(init_url)
            # Send success message to the bot
            bot.send_message(chat_id, "Collection successful!")
        except Exception as e:
            bot.send_message(chat_id, f"An error occurred: {e}")
        
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
    global is_collecting, chat_id, session_url
    chat_id = message.chat.id
    
    # If session URL hasn't been provided, prompt the user for it
    if not session_url:
        bot.send_message(chat_id, "Please send your session URL first (the link with `tgWebAppData`).")
        return
    
    # Start the collecting process if not already running
    if not is_collecting:
        is_collecting = True
        bot.send_message(chat_id, "Started collecting coins every minute.")
        threading.Thread(target=continuous_collect, args=(session_url, 60)).start()
    else:
        bot.send_message(chat_id, "Already collecting coins!")

@bot.message_handler(commands=['stop'])
def stop_collecting(message):
    global is_collecting
    if is_collecting:
        is_collecting = False
        bot.send_message(message.chat.id, "Stopped collecting coins.")
    else:
        bot.send_message(message.chat.id, "Coin collection is not active.")

@bot.message_handler(commands=['status'])
def status(message):
    if is_collecting:
        bot.send_message(message.chat.id, "Currently collecting coins every minute.")
    else:
        bot.send_message(message.chat.id, "Coin collection is inactive.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    global session_url, chat_id
    if 'tgWebAppData' in message.text:
        session_url = message.text.strip()
        chat_id = message.chat.id
        bot.send_message(chat_id, "Session URL received! Now, use /start_collecting to begin.")
    else:
        bot.send_message(message.chat.id, "Please send a valid session URL (link containing `tgWebAppData`).")

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
    # Set webhook
    bot.remove_webhook()
    bot.set_webhook(url='https://freedogs-1.onrender.com/' + TOKEN)

    # Run Flask app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
