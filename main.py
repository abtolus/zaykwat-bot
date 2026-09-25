from __future__ import annotations

from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Callable, Optional
from contextlib import asynccontextmanager
from dotenv import find_dotenv, load_dotenv
from curl_cffi.requests import AsyncSession
from fastapi import FastAPI, Request, Response
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

try: from curl_cffi.requests.exceptions import RequestException as CurlRequestError
except ImportError: from curl_cffi.requests.errors import RequestsError as CurlRequestError

import os
import json
import secrets
import logging
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(name="zaykwat-bot")

DIRECTORY = Path(__file__).resolve().parent

load_dotenv(find_dotenv())

def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )
    return value

BOT_TOKEN = require_env('BOT_TOKEN')
FASTAPI_WEBHOOK_URL = require_env('FASTAPI_WEBHOOK_URL')
FOREIGN_EXCHANGE_RATES_API_URL = require_env('FOREIGN_EXCHANGE_RATES_API_URL')
FUEL_PRICES_API_URL = require_env('FUEL_PRICES_API_URL')
GOLD_PRICES_API_URL = require_env('GOLD_PRICES_API_URL')

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or None
MARKET_PRICES_API_URL = os.getenv('MARKET_PRICES_API_URL')

try:
    with open(DIRECTORY / "translations.json", "r", encoding="utf-8") as f:
        translations: dict[str, str] = json.load(f)
except (OSError, json.JSONDecodeError) as e:
    raise RuntimeError(f"Could not load translations.json: {e}") from e

class ServiceError(Exception):
    pass

bot = AsyncTeleBot(BOT_TOKEN)
http_session: Optional[AsyncSession] = None

def get_session() -> AsyncSession:
    if http_session is None:
        raise RuntimeError("HTTP session cannot be initialised")
    return http_session

main_menu_text: str = "သိလိုသည့် အမျိုးအစားကို ရွေးချယ်ပါ။"
division_menu_text: str = "ပြည်နယ်/တိုင်းဒေသကြီးကို ရွေးချယ်ပါ။"

regions = [
    "Yangon Division", "Bago Division", "Nay Pyi Taw Division", "Ayeyarwady Division",
    "Kayin State", "Mon State", "Mandalay Division", "Magwe Division", "Shan State",
]
region_set = frozenset(regions)

def get_main_menu() -> InlineKeyboardMarkup:
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

def get_back_menu() -> InlineKeyboardMarkup:
    backMenuButtons = [
        [InlineKeyboardButton("မူလစာမျက်နှာသို့", callback_data="backButton")],
        [InlineKeyboardButton("အခြားစာမျက်နှာသို့", callback_data="newButton")]
    ]
    return InlineKeyboardMarkup(backMenuButtons)

def get_fuel_prices_menu() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    division_buttons = [
        InlineKeyboardButton(translations.get(" ".join(d.split()[:-1]), d), callback_data=d)
        for d in regions
    ]
    for i in range(0, len(division_buttons), 3):
        markup.row(*division_buttons[i:i + 3])
    markup.row(InlineKeyboardButton("မူလစာမျက်နှာသို့", callback_data="backButton"))
    return markup

main_menu = get_main_menu()
back_menu = get_back_menu()
fuel_prices_menu = get_fuel_prices_menu()

@bot.message_handler(chat_types=['private'], commands=['start'])
async def send_welcome(message) -> None:
    await bot.send_message(
        chat_id=message.chat.id,
        text=main_menu_text,
        reply_markup=main_menu)

@bot.message_handler(chat_types=['private'], func=lambda m: True)
async def echo_all(message) -> None:
    await bot.send_message(
        chat_id=message.chat.id,
        text=main_menu_text,
        reply_markup=main_menu)

def get_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_price_change_indicator(now: str, previous: list[str]) -> str:
    now, difference = int(now.replace(',', '')), 0
    for raw in previous:
        value = int(raw.replace(',', ''))
        if abs(now - value) > abs(difference):
            difference = now - raw
    if difference == 0: return ""
    return f"(+{difference})" if difference > 0 else f"(-{abs(difference)})"

def get_first_word(name: str) -> str:
    words = name.split()
    return words[0] if words else name

def get_formatted_prices(rows, header: str, name_function: Callable[[str], str] = lambda n: n) -> str:
    message = f"```text\n{header}\n\n{'Price':<15}{'Type'}\n{'*':<15}*\n"
    for row in rows:
        cols = [td.next.strip() for td in row.find_all("td")]
        raw_name, price = cols[1], cols[-1]
        name = name_function(raw_name)
        translated = translations.get(name, name)
        indicator = get_price_change_indicator(cols[-1], cols[2:-1])
        message += f"{price + indicator:<15}{translated}\n"
    message += "```\n"
    return message + get_timestamp()

async def fetch_category(category: str, error: str) -> list:
    try:
        response = await get_session().post(
            MARKET_PRICES_API_URL,
            data={"Category": category, "Page": "1", "Language": "English"},
            impersonate="chrome",
            timeout=15
        )
        response.raise_for_status()
        html = response.json()
    except (CurlRequestError, ValueError) as e:
        raise ServiceError(error) from e
    return BeautifulSoup(html, "html.parser").find_all("tr")

async def get_foreign_exchange_rates() -> str:
    try:
        response = await get_session().get(FOREIGN_EXCHANGE_RATES_API_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
    except (CurlRequestError, ValueError) as e:
        raise ServiceError("Error connecting to the Foreign Exchange Rates service.") from e

    if data.get("result") != "success":
        raise ServiceError("Unable to fetch the Foreign Exchange Rates data at the moment.")
    rates = data["rates"]
    usd_to_mmk = rates.get('MMK', 0)
    targets = ["USD", "EUR", "SGD", "MYR", "CNY", "THB", "JPY"]
    message = f"```text\nနိုင်ငံခြားငွေလဲလှယ်နှုန်းများ\n\n{'Currency':<12}{'Rates'}\n{'*':<12}*\n"
    for target in targets:
        if target == "USD": mmk = usd_to_mmk
        else:
            rate_in_usd = rates.get(target)
            mmk = (usd_to_mmk / rate_in_usd) if rate_in_usd else 0
        message += f"{translations.get(target, target):<12}{mmk:,.2f}\n"
    message += "```\n"
    return message + get_timestamp()

async def fetch_fuel_prices(division: str) -> dict:
    try:
        response = await get_session().get(FUEL_PRICES_API_URL, impersonate="chrome", timeout=15)
        response.raise_for_status()
    except CurlRequestError as e:
        raise ServiceError("Error connecting to the Fuel Prices service.") from e

    soup = BeautifulSoup(response.text, 'html.parser')
    data: dict[str, dict[str, str]] = {}
    for row in soup.find_all("tr"):
        cols = row.find_all('td')
        if len(cols) >= 6:
            row_division = cols[0].get_text(strip=True)

            data[row_division] = {
                "station": cols[1].get_text(strip=True),
                "diesel": cols[2].get_text(strip=True),
                "premiumDiesel": cols[3].get_text(strip=True),
                "octane92": cols[4].get_text(strip=True),
                "octane95": cols[5].get_text(strip=True)
            }
    if division not in data:
        raise ServiceError(f"No Fuel Prices data available: {translations.get(division, division)}")
    return data[division]

async def get_fuel_prices(division: str) -> str:
    data = await fetch_fuel_prices(division)
    message = (
        f"```text\n{translations.get(division, division)}\n\n"
        "စက်သုံးဆီဈေးနှုန်းများ\n*\n"
        f"{'Diesel':<19}{data['diesel']}\n"
        f"{'Premium Diesel':<19}{data['premiumDiesel']}\n"
        f"{'Octane 92':<19}{data['octane92']}\n"
        f"{'Octane 95':<19}{data['octane95']}\n\n"
        "```\n"
    )
    return message + get_timestamp()

async def get_gold_prices() -> str:
    try:
        thread_response = await get_session().get(GOLD_PRICES_API_URL, impersonate="chrome", timeout=15)
        thread_response.raise_for_status()
    except CurlRequestError as e:
        raise ServiceError("Error connecting to the Gold Prices service.") from e
    thread_soup = BeautifulSoup(thread_response.text, 'html.parser')
    thread_row = thread_soup.find('thead', class_="table-header-colour")
    if thread_row is None:
        raise ServiceError("Error connecting to the Fuel Prices service.")
    thread_cols = [td.next.strip() for td in thread_row.find_all('td')]

    tbody_rows = await fetch_category("Gold Price", "Error connecting to the Gold Prices service.")
    if not tbody_rows:
        raise ServiceError("Error connecting to the Gold Prices service.")
    tbody_cols = [td.next.strip() for td in tbody_rows[0].find_all('td')]

    message = f"```text\nရွှေဈေးနှုန်းများ\n\n{'Date':<10} {'16 PE':<14} {'15 PE'}\n{'*':<11}{'*':<15}*\n"
    try:
        for i, col in enumerate(tbody_cols[:1:-1]):
            date_part = '-'.join(thread_cols[:1:-1][i].split('-')[:-1])
            message += f"{date_part:<10} {int(col.replace(',', '')):<14,.0f} {(int(col.replace(',', '')) * (15 / 16)):,.0f}\n"
    except (IndexError, ValueError) as e:
        raise ServiceError("Error connecting to the Gold Prices service.") from e
    message += "```\n"
    return message + get_timestamp()

async def get_rice_prices() -> str:
    rows = await fetch_category("Rice", "Error connecting to the Rice Prices service.")
    return get_formatted_prices(rows[:-1], "ဆန်ဈေးနှုန်းများ")

async def get_edible_oil_prices() -> str:
    rows = await fetch_category("Edible Oil", "Error connecting to the Edible Oil Prices service.")
    return get_formatted_prices(rows[:-1], "စားသုံးဆီဈေးနှုန်းများ")

async def get_pulses_prices() -> str:
    rows = await fetch_category("Pulses", "Error connecting to the Pulses Prices service.")
    return get_formatted_prices(rows[:-1], "ပဲဈေးနှုန်းများ", get_first_word)

async def get_spices_prices() -> str:
    rows = await fetch_category("Spices", "Error connecting to the Spices Prices service.")
    return get_formatted_prices(rows[:-1], "ဟင်းခတ်အမွှေးအကြိုင်ဈေးနှုန်းများ", get_first_word)

async def get_meat_prices() -> str:
    rows = await fetch_category("Fish and Prawn", "Error connecting to the Meat Prices service.")
    return get_formatted_prices(rows[:4], "အသားဈေးနှုန်းများ")

async def get_fish_prices() -> str:
    rows = await fetch_category("Fish and Prawn", "Error connecting to the Fish Prices service.")
    return get_formatted_prices(rows[4:9], "ငါးဈေးနှုန်းများ")

async def get_prawn_prices() -> str:
    rows = await fetch_category("Fish and Prawn", "Error connecting to the Prawn Prices service.")
    return get_formatted_prices(rows[9:-1], "ပုဇွန်ဈေးနှုန်းများ")

price_handlers: dict[str, tuple[str, Callable]] = {
    "foreignExchangeRatesButton": ("Fetching the Foreign Exchange Rates data", get_foreign_exchange_rates),
    "goldPricesButton": ("Fetching the Gold Prices data", get_gold_prices),
    "meatPricesButton": ("Fetching the Meat Prices data", get_meat_prices),
    "fishPricesButton": ("Fetching the Fish Prices data", get_fish_prices),
    "prawnPricesButton": ("Fetching the Prawn Prices data", get_prawn_prices),
    "ricePricesButton": ("Fetching the Rice Prices data", get_rice_prices),
    "edibleOilPricesButton": ("Fetching the Edible Oil Prices data", get_edible_oil_prices),
    "pulsesPricesButton": ("Fetching the Pulses Prices data", get_pulses_prices),
    "spicesPricesButton": ("Fetching the Spices Prices data", get_spices_prices)
}

async def _reply_with_price_data(call, loading_text: str, getter: Callable, *args) -> None:
    await bot.answer_callback_query(call.id, text=loading_text)
    try:
        text = await getter(*args)
    except ServiceError as e:
        logger.warning("Price fetch failed for %s%s: %s", getter.__name__, args, e)
        text = str(e)
    except Exception:
        logger.exception("Unexpected error while handling %s%s", getter.__name__, args)
        text = "An error occurred while fetching the data. Please try again in a moment."
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=back_menu,
    )

@bot.callback_query_handler(func=lambda call: True)
async def handle_query(call) -> None:
    data = call.data
    if call.message is None:
        await bot.answer_callback_query(call.id)
        return
    try:
        if data in price_handlers:
            loading_text, getter = price_handlers[data]
            await _reply_with_price_data(call, loading_text, getter)

        elif data == "fuelPricesButton":
            await bot.answer_callback_query(call.id, text="Fetching the Fuel Prices data")
            await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=division_menu_text,
                parse_mode="Markdown",
                reply_markup=fuel_prices_menu,
            )

        elif data in region_set:
            await _reply_with_price_data(call, f"Getting the data for the {data}", get_fuel_prices, data)

        elif data == "backButton":
            await bot.answer_callback_query(call.id, text="Going back to the Main Menu")
            await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=main_menu_text,
                parse_mode="Markdown",
                reply_markup=main_menu,
            )

        elif data == "newButton":
            await bot.answer_callback_query(call.id, text="Creating the new Main Menu")
            await bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None,
            )
            await bot.send_message(
                chat_id=call.message.chat.id,
                text=main_menu_text,
                parse_mode="Markdown",
                reply_markup=main_menu,
            )
        else: await bot.answer_callback_query(call.id)
    except Exception:
        logger.exception("Unhandled error in callback handler for data=%r", data)
        try: await bot.answer_callback_query(call.id, text="Something went wrong. Please try again.")
        except Exception: logger.exception("Failed to even answer the callback query for data=%r", data)

background_tasks: set[asyncio.Task] = set()

def get_track(task: asyncio.Task) -> None:
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

async def process_update_safely(update: Update) -> None:
    try: await bot.process_new_updates([update])
    except Exception: logger.exception("Error while processing a Telegram update")

async def setup_webhook(webhook_url: str, maximum: int = 3) -> None:
    for attempt in range(1, maximum + 1):
        start = asyncio.get_running_loop().time()
        try:
            if WEBHOOK_SECRET: await bot.set_webhook(url=webhook_url, secret_token=WEBHOOK_SECRET, timeout=30)
            else: await bot.set_webhook(url=webhook_url, timeout=30)
            logger.info(
                "Webhook set to %s on attempt %d (%.1fs)",
                webhook_url, attempt, asyncio.get_running_loop().time() - start,
            )
            return
        except Exception:
            elapsed = asyncio.get_running_loop().time() - start
            logger.warning(
                "set_webhook attempt %d/%d failed after %.1fs",
                attempt, maximum, elapsed, exc_info=True,
            )
            if attempt == maximum:
                logger.error("Giving up on setting the webhook after %d attempts", attempt)
                return
            await asyncio.sleep(attempt * 3)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_session
    http_session = AsyncSession()
    webhook_url = f"{FASTAPI_WEBHOOK_URL}/webhook"

    get_track(asyncio.create_task(setup_webhook(webhook_url)))

    try:
        yield
    finally:
        await bot.remove_webhook()
        await bot.close_session()
        await http_session.close()
        for task in list(background_tasks):
            task.cancel()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def handle_webhook(request: Request) -> Response:
    if WEBHOOK_SECRET:
        provided = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not secrets.compare_digest(provided, WEBHOOK_SECRET): return Response(status_code=403)

    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json"): return Response(status_code=403)

    try: json_data = await request.json()
    except Exception: return Response(status_code=400)
    update = Update.de_json(json_data)
    get_track(asyncio.create_task(process_update_safely(update)))
    return Response(status_code=200)

@app.get("/")
async def handle_get():
    return {"status": "ok"}

@app.head('/')
async def handle_head() -> Response:
    return Response(status_code=200)