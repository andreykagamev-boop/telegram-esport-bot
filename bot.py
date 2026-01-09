import asyncio
import logging
import os
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.filters.text import Text

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ХРАНЕНИЕ СОСТОЯНИЙ ---
user_game = {}
live_messages = {}

# --- КЛАВИАТУРЫ ---
main_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="🎮 CS2"), types.KeyboardButton(text="🛡 Dota 2")],
        [types.KeyboardButton(text="📊 Аналитика"), types.KeyboardButton(text="🎯 Экспресс")]
    ],
    resize_keyboard=True
)

game_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="📅 Сегодня"), types.KeyboardButton(text="⏭ Завтра")],
        [types.KeyboardButton(text="🔴 Live")],
        [types.KeyboardButton(text="🔙 Назад")]
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
        f"🎮 <b>{game.upper()}</b>\n"
        f"🆚 <b>{team1}</b> vs <b>{team2}</b>\n"
        f"🕒 <b>{time_msk} МСК</b>\n"
        f"🏆 <i>{tournament}</i>\n"
        f"──────────────"
    )

async def fetch_matches(game: str, day: str = None):
    today = datetime.utcnow().strftime("%Y-%m-%d") if not day else day
    url_map = {"cs2": "https://api.pandascore.co/csgo/matches", "dota2": "https://api.pandascore.co/dota2/matches"}
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[begin_at]": today, "sort": "begin_at"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url_map[game], headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

async def calculate_analytics(game: str):
    matches = await fetch_matches(game)
    analytics = ""
    for match in matches[:5]:  # последние 5 матчей
        opponents = match.get("opponents", [])
        if len(opponents) < 2:
            continue
        t1 = opponents[0]["opponent"]["name"]
        t2 = opponents[1]["opponent"]["name"]
        winner = match.get("winner", {}).get("name", "TBD")
        analytics += f"🆚 <b>{t1}</b> vs <b>{t2}</b> — Победитель: <b>{winner}</b>\n"
    return analytics or "Нет данных для аналитики."

async def generate_express(game: str):
    matches = await fetch_matches(game)
    express = "🎯 <b>Возможная комбинация побед (экспресс)</b>\n"
    for match in matches[:3]:  # берем первые 3 матча
        opponents = match.get("opponents", [])
        if len(opponents) < 2:
            continue
        winner_guess = opponents[0]["opponent"]["name"]
        express += f"🆚 <b>{opponents[0]['opponent']['name']}</b> vs <b>{opponents[1]['opponent']['name']}</b> — предполагаемый победитель: <b>{winner_guess}</b>\n"
    return express

# --- LIVE-ОБНОВЛЕНИЕ ---
async def update_live(user_id: int, chat_id: int, game: str):
    while True:
        matches = await fetch_matches(game)
        live_text = "<b>🔴 Live-матчи</b>\n\n"
        for match in matches:
            live_text += format_match_text(game, match) + "\n"

        msg_id = live_messages.get(user_id)
        try:
            if msg_id:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=live_text, parse_mode="HTML")
            else:
                msg = await bot.send_message(chat_id, live_text, parse_mode="HTML")
                live_messages[user_id] = msg.message_id
        except Exception as e:
            logging.error(f"Ошибка обновления live: {e}")

        await asyncio.sleep(30)

# --- ХЭНДЛЕРЫ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет! Выбери игру 👇", reply_markup=main_keyboard)

@dp.message(Text(text=["🎮 CS2", "🛡 Dota 2"]))
async def select_game(message: types.Message):
    user_id = message.from_user.id
    game = "cs2" if message.text == "🎮 CS2" else "dota2"
    user_game[user_id] = game
    await message.answer(f"{message.text} — выбери раздел:", reply_markup=game_keyboard)

@dp.message(Text(text=["📊 Аналитика"]))
async def show_analytics(message: types.Message):
    user_id = message.from_user.id
    game = user_game.get(user_id)
    if not game:
        await message.answer("Сначала выбери игру 👆")
        return
    analytics_text = await calculate_analytics(game)
    await message.answer(analytics_text, parse_mode="HTML")

@dp.message(Text(text=["🎯 Экспресс"]))
async def show_express(message: types.Message):
    user_id = message.from_user.id
    game = user_game.get(user_id)
    if not game:
        await message.answer("Сначала выбери игру 👆")
        return
    express_text = await generate_express(game)
    await message.answer(express_text, parse_mode="HTML")

@dp.message(Text(text=["🔴 Live"]))
async def live_matches(message: types.Message):
    user_id = message.from_user.id
    game = user_game.get(user_id)
    if not game:
        await message.answer("Сначала выбери игру 👆")
        return
    await message.answer("Запускаю Live-обновления ⏳")
    asyncio.create_task(update_live(user_id, message.chat.id, game))

@dp.message(Text(text=["🔙 Назад"]))
async def back_menu(message: types.Message):
    user_id = message.from_user.id
    user_game.pop(user_id, None)
    live_messages.pop(user_id, None)
    await message.answer("Главное меню:", reply_markup=main_keyboard)

# --- RUN ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())