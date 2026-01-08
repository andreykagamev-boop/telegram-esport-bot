import asyncio
import logging
import os
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ХРАНИМ ВЫБОР ИГРЫ ---
user_game = {}

# --- КЛАВИАТУРЫ ---

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 CS2"), KeyboardButton(text="🛡 Dota 2")],
        [KeyboardButton(text="📊 Аналитика")]
    ],
    resize_keyboard=True
)

game_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="⏭ Завтра")],
        [KeyboardButton(text="🔴 Live")],
        [KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# --- API ---

async def get_cs2_today_matches():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    url = "https://api.pandascore.co/csgo/matches"
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[begin_at]": today, "sort": "begin_at"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

async def get_dota2_today_matches():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    url = "https://api.pandascore.co/dota2/matches"
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[begin_at]": today, "sort": "begin_at"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def start(message):
    await message.answer("Привет! Выбери игру 👇", reply_markup=main_keyboard)

@dp.message()
async def handle_menu(message):
    text = message.text
    user_id = message.from_user.id

    if text == "🎮 CS2":
        user_game[user_id] = "cs2"
        await message.answer("CS2 — выбери раздел:", reply_markup=game_keyboard)

    elif text == "🛡 Dota 2":
        user_game[user_id] = "dota2"
        await message.answer("Dota 2 — выбери раздел:", reply_markup=game_keyboard)

    elif text == "📅 Сегодня":
        game = user_game.get(user_id)

        if game == "cs2":
            await message.answer("Загружаю матчи CS2 на сегодня ⏳")
            matches = await get_cs2_today_matches()
        elif game == "dota2":
            await message.answer("Загружаю матчи Dota 2 на сегодня ⏳")
            matches = await get_dota2_today_matches()
        else:
            await message.answer("Сначала выбери игру 👆")
            return

        if not matches:
            await message.answer("Сегодня матчей нет 😕")
            return

        for match in matches[:5]:
            team1 = match["opponents"][0]["opponent"]["name"] if match["opponents"] else "TBD"
            team2 = match["opponents"][1]["opponent"]["name"] if len(match["opponents"]) > 1 else "TBD"
            time = match["begin_at"]
            tournament = match["tournament"]["name"]

            await message.answer(
                f"🎮 {team1} vs {team2}\n"
                f"🕒 {time}\n"
                f"🏆 {tournament}"
            )

    elif text == "🔙 Назад":
        user_game.pop(user_id, None)
        await message.answer("Главное меню:", reply_markup=main_keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())