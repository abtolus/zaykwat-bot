from dotenv import find_dotenv, load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import os
import telebot

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
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == "refreshButton":
        bot.answer_callback_query(call.id, text="Refreshed.")
    else:
        bot.answer_callback_query(call.id, text="Coming soon.")
bot.infinity_polling()