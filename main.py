import requests
from urllib.parse import urlparse, parse_qs
import hashlib
import time
import threading
import telebot
import os
import socket
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up your Telegram bot
TOKEN = "7712603902:AAHGFpU5lAQFuUUPYlM1jbu1u6XJGgs15Js"
bot = telebot.TeleBot(TOKEN)
is_collecting = False  # Flag to control continuous collection
chat_id = None  # Stores the chat ID for sending messages
session_url = None  # Stores the session URL provided by the user

# Define headers and functions for coin collection
headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'authorization': '',
    'x-requested-with': 'org.telegram.messenger',
}

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
            logger.info("Coin collection successful.")
            bot.send_message(chat_id, "Coin collection successful.")
        except Exception as e:
            bot.send_message(chat_id, f"An error occurred: {e}")
            logger.error(f"An error occurred: {e}")
        
        time.sleep(interval)

@bot.message_handler(commands=['start'])
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
        logger.info("Coin collection stopped.")
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
        bot.send_message(chat_id, "Session URL received! Now, use /start to begin collecting coins.")
        logger.info("Session URL accepted.")
    else:
        bot.send_message(message.chat.id, "Please send a valid session URL (link containing `tgWebAppData`).")

# Add a welcome message with available scripts
@bot.message_handler(commands=['scripts'])
def scripts_list(message):
    accepted_scripts = """
    Accepted scripts:
    1. Circle
    2. MemeFi
    3. Booms
    4. Cherry Game
    5. Paws
    6. Seed
    7. Blum
    8. FreeDogs
    """
    bot.send_message(message.chat.id, accepted_scripts)

def open_dummy_port():
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if PORT env variable is not set
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("0.0.0.0", port))
        sock.listen(1)
        logger.info(f"Listening on port {port} to keep Render service running.")
        sock.accept()  # Accept a connection to keep the port open

# Start the bot polling and dummy port listener in separate threads
if __name__ == "__main__":
    logger.info("Bot is starting...")
    threading.Thread(target=open_dummy_port).start()
    bot.polling()
