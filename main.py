import requests
from urllib.parse import urlparse, parse_qs
import hashlib
import time
import threading
import telebot
import logging

# Set up your Telegram bot
TOKEN = "7712603902:AAHGFpU5lAQFuUUPYlM1jbu1u6XJGgs15Js"
bot = telebot.TeleBot(TOKEN)
sessions = {}  # Dictionary to store user sessions {chat_id: {'is_collecting': bool, 'session_url': str}}

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def continuous_collect(chat_id, interval=60):
    while sessions[chat_id]['is_collecting']:
        try:
            result = do_click(sessions[chat_id]['session_url'])
            logger.info(f"Collection result for {chat_id}: {result}")
            bot.send_message(chat_id, "Collection successful!")
        except Exception as e:
            bot.send_message(chat_id, f"An error occurred: {e}")
        
        time.sleep(interval)

@bot.message_handler(commands=['start'])
def start_collecting(message):
    chat_id = message.chat.id
    
    # Initialize user session if not already present
    if chat_id not in sessions:
        sessions[chat_id] = {'is_collecting': False, 'session_url': None}

    # Check if session URL is set
    if not sessions[chat_id]['session_url']:
        bot.send_message(chat_id, "Please send your session URL first (the link with `tgWebAppData`).")
        return
    
    # Start collection if not already running for this user
    if not sessions[chat_id]['is_collecting']:
        sessions[chat_id]['is_collecting'] = True
        bot.send_message(chat_id, "Started collecting coins every 1 minute.")
        threading.Thread(target=continuous_collect, args=(chat_id, 60)).start()
    else:
        bot.send_message(chat_id, "Already collecting coins!")

@bot.message_handler(commands=['stop'])
def stop_collecting(message):
    chat_id = message.chat.id
    if chat_id in sessions and sessions[chat_id]['is_collecting']:
        sessions[chat_id]['is_collecting'] = False
        bot.send_message(chat_id, "Stopped collecting coins.")
    else:
        bot.send_message(chat_id, "Coin collection is not active.")

@bot.message_handler(commands=['status'])
def status(message):
    chat_id = message.chat.id
    if chat_id in sessions and sessions[chat_id]['is_collecting']:
        bot.send_message(chat_id, "Currently collecting coins every 1 minute.")
    else:
        bot.send_message(chat_id, "Coin collection is inactive.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    if 'tgWebAppData' in message.text:
        session_url = message.text.strip()
        if chat_id not in sessions:
            sessions[chat_id] = {'is_collecting': False, 'session_url': session_url}
        else:
            sessions[chat_id]['session_url'] = session_url
        bot.send_message(chat_id, "Session URL accepted! Now, use /start to begin collecting.")
    else:
        bot.send_message(chat_id, "Please send a valid session URL (link containing `tgWebAppData`).")

bot.polling()
