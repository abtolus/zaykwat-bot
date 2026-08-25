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
        [InlineKeyboardButton("စက်သုံးဆီဈေး", callback_data="fuelPricesButton"),
         InlineKeyboardButton("စားသုံးဆီဈေး", callback_data="edibleOilPricesButton")],
        [InlineKeyboardButton("ဆန်ဈေး", callback_data="ricePricesButton"),
         InlineKeyboardButton("ရွှေဈေး", callback_data="goldPricesButton"),
         InlineKeyboardButton("ပဲဈေး", callback_data="pulsesPricesButton")],
        [InlineKeyboardButton("အသားဈေး", callback_data="meatPricesButton"),
         InlineKeyboardButton("ငါးဈေး", callback_data="fishPricesButton"),
         InlineKeyboardButton("ပုဇွန်ဈေး", callback_data="prawnPricesButton")],
        [InlineKeyboardButton("ဟင်းခတ်အမွှေးအကြိုင်ဈေး", callback_data="spicesPricesButton")]
    ]
    return InlineKeyboardMarkup(mainMenuButtons)
def back_menu():
    backMenuButtons = [
        [InlineKeyboardButton("မူလစာမျက်နှာသို့", callback_data="backButton")],
        [InlineKeyboardButton("အခြားစာမျက်နှာသို့", callback_data="newButton")]
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
        bodyMessage = f"```text\nနိုင်ငံခြားငွေလဲလှယ်နှုန်းများ\n\n{'ငွေကြေး':<12} {'ဈေးနှုန်း'}\n{'-' * 20}\n"

        for target in targets:
            if target == "USD":
                MMK = USDToMMK
            else:
                rateInUSD = rates.get(target)
                MMK = (USDToMMK / rateInUSD) if rateInUSD else 0
            bodyMessage += f"{translator.get(target, target):<11} {MMK:,.2f}\n"

        bodyMessage += "```\n"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        footerMessage = now
        return bodyMessage + footerMessage

    except requests.exceptions.RequestException:
        return "Error connecting to the Foreign Exchange Rates service."

def get_fuel_prices(division):
    data = fetch_fuel_prices(division)
    message = "```text\n"
    message += f"{translator.get(division, division)}\n\nစက်သုံးဆီဈေးနှုန်းများ\n{'-' * 23}\n"
    message += f"{'Diesel':<18} {data['diesel']}\n{'Premium Diesel':<18} {data['premiumDiesel']}\n{'Octane 92':<18} {data['octane92']}\n{'Octane 95':<18} {data['octane95']}\n\n"
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

def get_rice_prices():
    rows = fetch_rice_prices()
    message = "```text\n"
    message += f"ဆန်ဈေးနှုန်းများ\n\n{'အမျိုးအစား':<14} {'ဈေးနှုန်း'}\n{'-' * 20}\n"
    for i, row in enumerate(rows):
        cols = [td.next.strip() for td in row.find_all('td')]
        riceName = cols[1]
        ricePrice = cols[-1]
        translated = translator.get(riceName, riceName)
        paddings = [15, 20]
        message += f"{translated:<{paddings[i]}}{ricePrice}\n"
    message += "```\n"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return message + now
def fetch_rice_prices():
    try:
        payload = {
            "Category": "Rice", "Page": "1", "Language": "English"
        }
        response = requests.post("https://csostat.gov.mm/Statistics/GetMarketPriceByCategory", data=payload, impersonate="chrome", timeout=15)
        response.raise_for_status()
        data = response.json()
        soup = BeautifulSoup(data, 'html.parser')
        rows = soup.find_all('tr')
        return rows[:-1]
    except requests.exceptions.RequestException:
        return "Error connecting to the Rice Prices service."
def get_edible_oil_prices():
    rows = fetch_edible_oil_prices()
    message = "```text\n"
    message += f"စားသုံးဆီဈေးနှုန်းများ\n\n{'အမျိုးအစား':<19} {'ဈေးနှုန်း'}\n{'-' * 25}\n"
    for i, row in enumerate(rows):
        cols = [td.next.strip() for td in row.find_all('td')]
        edibleOilName = cols[1]
        edibleOilPrice = cols[-1]
        translated = translator.get(edibleOilName, edibleOilName)
        paddings = [21, 21, 22, 22]
        message += f"{translated:<{paddings[i]}}{edibleOilPrice}\n"
    message += "```\n"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return message + now
def fetch_edible_oil_prices():
    try:
        payload = {
            "Category": "Edible Oil", "Page": "1", "Language": "English"
        }
        response = requests.post("https://csostat.gov.mm/Statistics/GetMarketPriceByCategory", data=payload, impersonate="chrome", timeout=15)
        response.raise_for_status()
        data = response.json()
        soup = BeautifulSoup(data, 'html.parser')
        rows = soup.find_all('tr')
        return rows[:-1]
    except requests.exceptions.RequestException:
        return "Error connecting to the Edible Oil Prices service."

def get_meat_prices():
    rows = fetch_meat_fish_prawn_prices("meat")
    message = "```text\n"
    message += f"အသားဈေးနှုန်းများ\n\n{'အမျိုးအစား':<13} {'ဈေးနှုန်း'}\n{'-' * 19}\n"
    for row in rows:
        cols = [td.next.strip() for td in row.find_all('td')]
        meatName = cols[1]
        meatPrice = cols[-1]
        formatted = "".join(meatName.split()[0])
        translated = translator.get(formatted, formatted)
        message += f"{translated:<12} {meatPrice}\n"
    message += "```\n"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return message + now
def get_fish_prices():
    rows = fetch_meat_fish_prawn_prices("fish")
    message = "```text\n"
    message += f"ငါးဈေးနှုန်းများ\n\n{'အမျိုးအစား':<14} {'ဈေးနှုန်း'}\n{'-' * 20}\n"
    for i, row in enumerate(rows):
        cols = [td.next.strip() for td in row.find_all('td')]
        fishName = cols[1]
        fishPrice = cols[-1]
        formatted = "".join(fishName.split()[0])
        translated = translator.get(formatted, formatted)
        paddings = [16, 16, 14, 16, 18]
        message += f"{translated:<{paddings[i]}}{fishPrice}\n"
    message += "```"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return message + now
def get_prawn_prices():
    rows = fetch_meat_fish_prawn_prices("prawn")
    message = "```text\n"
    message += f"ပုဇွန်ဈေးနှုန်းများ\n\n{'အမျိုးအစား':<14} {'ဈေးနှုန်း'}\n{'-' * 20}\n"
    for i, row in enumerate(rows):
        cols = [td.next.strip() for td in row.find_all('td')]
        prawnName = cols[1]
        prawnPrice = cols[-1]
        formatted = "".join(prawnName.split()[0])
        translated = translator.get(formatted, formatted)
        paddings = [17, 18]
        message += f"{translated:<{paddings[i]}}{prawnPrice}\n"
    message += "```"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return message + now

def fetch_meat_fish_prawn_prices(name: str):
    try:
        payload = {
            "Category": "Fish and Prawn", "Page": "1", "Language": "English"
        }
        response = requests.post("https://csostat.gov.mm/Statistics/GetMarketPriceByCategory", data=payload, impersonate="chrome", timeout=15)
        response.raise_for_status()
        data = response.json()
        soup = BeautifulSoup(data, 'html.parser')
        rows = soup.find_all('tr')

        meatRows, fishRows, prawnRows = rows[:4], rows[4:9], rows[9:-1]
        result = {
            "meat": meatRows, "fish": fishRows, "prawn": prawnRows
        }
        return result[name]
    except requests.exceptions.RequestException:
        return "Error connecting to the Meat, Fish and Prawn Prices service."

def get_gold_prices():
    url = os.getenv('GOLD_PRICES_API_URL')
    try:
        theadResponse = requests.get(url, impersonate="chrome", timeout=15)
        theadSoup = BeautifulSoup(theadResponse.text, 'html.parser')
        theadRow = theadSoup.find('thead', class_="table-header-colour")
        theadCols = [td.next.strip() for td in theadRow.find_all('td')]

        payload = {
            "Category": "Gold Price", "Page": "1", "Language": "English"
        }
        tbodyResponse = requests.post("https://csostat.gov.mm/Statistics/GetMarketPriceByCategory", data=payload, impersonate="chrome", timeout=15)
        tbodyResponse.raise_for_status()
        tbodyData = tbodyResponse.json()
        tbodySoup = BeautifulSoup(tbodyData, 'html.parser')
        tbodyRow = tbodySoup.find('tr')
        tbodyCols = [td.next.strip() for td in tbodyRow.find_all('td')]

        message = "```text\n"
        message += f"ရွှေဈေးနှုန်းများ\n\n{'ရက်စွဲ':<11} {'အခေါက်ရွှေ':<14} {'၁၅ပဲရည်'}\n{'-' * 33}\n"
        for i, col in enumerate(tbodyCols[:1:-1]):
            message += f"{"-".join(theadCols[:1:-1][i].split("-")[:-1]):<9} {int(col):<13,.0f} {(int(col) * (15 / 16)):,.0f}\n"
        message += "```\n"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return message + now
    except requests.exceptions.RequestException:
        return "Error connecting to the Gold Prices service."

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
    elif call.data == "goldPricesButton":
        bot.answer_callback_query(call.id, text="Fetching the Gold Prices data")
        message = get_gold_prices()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=back_menu()
        )
    elif call.data == "meatPricesButton":
        bot.answer_callback_query(call.id, text="Fetching the Meat Prices data")
        message = get_meat_prices()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=back_menu()
        )
    elif call.data == "fishPricesButton":
        bot.answer_callback_query(call.id, text="Fetching the Fish Prices data")
        message = get_fish_prices()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=back_menu()
        )
    elif call.data == "prawnPricesButton":
        bot.answer_callback_query(call.id, text="Fetching the Prawn Prices data")
        message = get_prawn_prices()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=back_menu()
        )
    elif call.data == "ricePricesButton":
        bot.answer_callback_query(call.id, text="Fetching the Rice Prices data")
        message = get_rice_prices()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=back_menu()
        )
    elif call.data == "edibleOilPricesButton":
        bot.answer_callback_query(call.id, text="Fetching the Edible Oil Prices data")
        message = get_edible_oil_prices()
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
    elif call.data == "newButton":
        bot.answer_callback_query(call.id, text=f"Creating the new Main Menu")
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        message = "သိလိုသည့် အမျိုးအစားကို ရွေးချယ်ပါ။"
        bot.send_message(
            chat_id=call.message.chat.id,
            text=message,
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
bot.infinity_polling()