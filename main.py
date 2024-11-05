import requests
from urllib.parse import urlparse, parse_qs
import hashlib
import time
import threading
import telebot

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

def continuous_collect(init_url, interval=300):
    global is_collecting
    while is_collecting:
        try:
            result = do_click(init_url)
            print(result)  # Print to console for debugging
            # Send result to the bot for feedback
            bot.send_message(chat_id, f"Collection Result: {result}")
        except Exception as e:
            bot.send_message(chat_id, f"An error occurred: {e}")
        
        time.sleep(interval)

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
        bot.send_message(chat_id, "Started collecting coins every 5 minutes.")
        threading.Thread(target=continuous_collect, args=(session_url, 300)).start()
    else:
        bot.send_message(chat_id, "Already collecting coins!")

@bot.message_handler(commands=['stop_collecting'])
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
        bot.send_message(message.chat.id, "Currently collecting coins every 5 minutes.")
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

bot.polling()
