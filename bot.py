from dotenv import find_dotenv, load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bs4 import BeautifulSoup
from curl_cffi import requests

import os
import telebot
import datetime
import json

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
with open('translator.json', "r", encoding="utf-8") as f:
    translator = json.load(f)

BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "သိလိုသည့် အမျိုးအစားကို ရွေးချယ်ပါ။", reply_markup=main_menu())
@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.reply_to(message, "သိလိုသည့် အမျိုးအစားကို ရွေးချယ်ပါ။", reply_markup=main_menu())

def main_menu():
    mainMenuButtons = [
        [InlineKeyboardButton("နိုင်ငံခြားငွေလဲလှယ်နှုန်းများ", callback_data="foreignExchangeRatesButton")],
        [InlineKeyboardButton("စက်သုံးဆီဈေးနှုန်းများ", callback_data="fuelPricesButton")],
        [InlineKeyboardButton("ရွှေဈေးနှုန်းများ", callback_data="goldPricesButton")]
    ]
    return InlineKeyboardMarkup(mainMenuButtons)
def back_menu():
    backMenuButtons = [
        [InlineKeyboardButton("မူလစာမျက်နှာသို့", callback_data="backButton")]
    ]
    return InlineKeyboardMarkup(backMenuButtons)
def fuel_prices_menu():
    markup = InlineKeyboardMarkup()
    divisions = ["Yangon Division", "Bago Division", "Nay Pyi Taw Division", "Ayeyarwady Division", "Kayin State", "Mon State", "Mandalay Division", "Magwe Division", "Shan State"]
    divisionButtons = [InlineKeyboardButton(translator.get(" ".join(division.split()[:-1]), division), callback_data=division) for division in divisions]
    for i in range(0, len(divisionButtons), 3):
        markup.row(*divisionButtons[i:i+3])
    backButton = InlineKeyboardButton("မူလစာမျက်နှာသို့", callback_data="backButton")
    markup.row(backButton)
    return markup
def get_foreign_exchange_rates():
    url = os.getenv('FOREIGN_EXCHANGE_RATES_API_URL')
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()
        if data.get('result') != "success":
            return "Unable to fetch the Foreign Exchange Rates data at the moment."

        rates = data["rates"]
        USDToMMK = rates.get('MMK', 0)
        targets = ["USD", "EUR", "SGD", "MYR", "CNY", "THB", "JPY"]
        bodyMessage = f"```text\nနိုင်ငံခြားငွေလဲလှယ်နှုန်းများ\n\n{'ငွေကြေး':<14} {'ဈေးနှုန်း'}\n{'-' * 23}\n"

        for target in targets:
            if target == "USD":
                MMK = USDToMMK
            else:
                rateInUSD = rates.get(target)
                MMK = (USDToMMK / rateInUSD) if rateInUSD else 0
            bodyMessage += f"{translator.get(target, target):<14} {MMK:,.2f}\n"

        bodyMessage += "```\n"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        footerMessage = now
        return bodyMessage + footerMessage

    except requests.exceptions.RequestException:
        return "Error connecting to the Foreign Exchange Rates service."
def get_fuel_prices(division):
    data = fetch_fuel_prices(division)
    message = "```text\n"
    message += f"{translator.get(division, division)}\n\nစက်သုံးဆီဈေးနှုန်းများ\n{'-' * 25}\n"
    message += f"{'Diesel':<20} {data['diesel']}\n{'Premium Diesel':<20} {data['premiumDiesel']}\n{'Octane 92':<20} {data['octane92']}\n{'Octane 95':<20} {data['octane95']}\n\n"
    message += "```\n"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return message + now
def fetch_fuel_prices(division):
    url = os.getenv('FUEL_PRICES_API_URL')
    try:
        response = requests.get(url, impersonate="chrome", timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        data = {}
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                _division = cols[0].get_text(strip=True)
                station = cols[1].get_text(strip=True)
                diesel = cols[2].get_text(strip=True)
                premiumDiesel = cols[3].get_text(strip=True)
                octane92 = cols[4].get_text(strip=True)
                octane95 = cols[5].get_text(strip=True)

                data[division] = {
                    "station": station, "diesel": diesel, "premiumDiesel": premiumDiesel, "octane92": octane92, "octane95": octane95
                }
        return data[division]
    except requests.exceptions.RequestException:
        return "Error connecting to the Fuel Prices service."

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == "foreignExchangeRatesButton":
        bot.answer_callback_query(call.id, text="Fetching the Foreign Exchange Rates data")
        message = get_foreign_exchange_rates()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=back_menu()
        )
    elif call.data == "fuelPricesButton":
        bot.answer_callback_query(call.id, text="Fetching the Fuel Prices data")
        message = "ပြည်နယ်/တိုင်းဒေသကြီးကို ရွေးချယ်ပါ။"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=fuel_prices_menu()
        )
    elif not call.data.endswith("Button"):
        division = call.data
        bot.answer_callback_query(call.id, text=f"Getting the data for the {division}")
        message = get_fuel_prices(division)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=back_menu()
        )
    elif call.data == "backButton":
        bot.answer_callback_query(call.id, text=f"Going back to the Main Menu")
        message = "သိလိုသည့် အမျိုးအစားကို ရွေးချယ်ပါ။"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
bot.infinity_polling()