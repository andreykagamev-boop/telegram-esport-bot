import asyncio
import logging
import os
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_msk_time(utc_time: str) -> str:
    if not utc_time:
        return "TBD"
    dt = datetime.fromisoformat(utc_time.replace("Z", ""))
    msk_time = dt + timedelta(hours=3)
    return msk_time.strftime("%H:%M")

def format_match_text(game: str, match: dict) -> str:
    opponents = match.get("opponents", [])
    team1 = opponents[0]["opponent"]["name"] if len(opponents) > 0 else "TBD"
    team2 = opponents[1]["opponent"]["name"] if len(opponents) > 1 else "TBD"

    time_utc = match.get("begin_at")
    time_msk = format_msk_time(time_utc)

    tournament = match.get("tournament", {}).get("name", "Неизвестный турнир")

    return (
        f"🎮 {game.upper()} — матч сегодня\n\n"
        f"🆚 {team1} vs {team2}\n"
        f"🕒 {time_msk} МСК\n"
        f"🏆 {tournament}\n"
        f"──────────────"
    )

# --- API ---

async def fetch_matches(game: str):
    today = datetime.utcnow().strftime("%Y-%m-%d")

    url_map = {
        "cs2": "https://api.pandascore.co/csgo/matches",
        "dota2": "https://api.pandascore.co/dota2/matches"
    }

    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[begin_at]": today, "sort": "begin_at"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url_map[game], headers=headers, params=params) as resp:
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

        if not game:
            await message.answer("Сначала выбери игру 👆")
            return

        await message.answer("Загружаю матчи ⏳")
        matches = await fetch_matches(game)

        if not matches:
            await message.answer("Сегодня матчей нет 😕")
            return

        for match in matches[:5]:
            text = format_match_text(game, match)
            await message.answer(text)

    elif text == "🔙 Назад":
        user_game.pop(user_id, None)
        await message.answer("Главное меню:", reply_markup=main_keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())