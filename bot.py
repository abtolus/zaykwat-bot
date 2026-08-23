from dotenv import find_dotenv, load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import os
import telebot
import requests
import datetime

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?", reply_markup=main_menu())
@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.reply_to(message, message.text, reply_markup=main_menu())

def main_menu():
    markup = InlineKeyboardMarkup()
    currencyExchangesButton = InlineKeyboardButton("Currency Exchanges", callback_data="currencyExchangesButton")
    refreshButton = InlineKeyboardButton("Refresh", callback_data="refreshButton")
    fuelPricesButton = InlineKeyboardButton("Fuel Prices", callback_data="fuelPricesButton")
    goldPricesButton = InlineKeyboardButton("Gold Prices", callback_data="goldPricesButton")
    markup.row(currencyExchangesButton, refreshButton)
    markup.row(fuelPricesButton, goldPricesButton)
    return markup
def get_currency_exchanges():
    url = os.getenv('CURRENCY_EXCHANGES_API_URL')
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()
        if data.get('result') != "success":
            return "Unable to fetch Currency Exchanges at the moment."

        rates = data["rates"]
        USDToMMK = rates.get('MMK', 0)
        targets = ["USD", "EUR", "SGD", "MYR", "CNY", "THB", "JPY"]
        bodyMessage = f"```text\nနိုင်ငံခြားငွေလဲလှယ်နှုန်း\n\n{'ငွေကြေး':<10} {'ဈေးနှုန်း':<5}\n{'-' * 16}\n"

        for target in targets:
            if target == "USD":
                MMK = USDToMMK
            else:
                rateInUSD = rates.get(target)
                MMK = (USDToMMK / rateInUSD) if rateInUSD else 0
            bodyMessage += f"{target:<10} {MMK:<5,.0f}\n"

        bodyMessage += "```\n"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        footerMessage = now
        return bodyMessage + footerMessage

    except requests.exceptions.RequestException:
        return "Error connecting to the Currency Exchanges service."

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == "currencyExchangesButton":
        bot.answer_callback_query(call.id, text="Fetching Currency Exchanges...")
        message = get_currency_exchanges()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    elif call.data == "refreshButton":
        bot.answer_callback_query(call.id, text="Refreshed.")
    else:
        bot.answer_callback_query(call.id, text="Coming soon.")
bot.infinity_polling()