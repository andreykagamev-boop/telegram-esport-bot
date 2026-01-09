import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from pandascore_client import Pandascore

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ps = Pandascore(access_token=PANDASCORE_TOKEN)

# ——— Клавиатуры ———

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🎮 CS2"), KeyboardButton("🛡 Dota 2")],
        [KeyboardButton("📊 Аналитика"), KeyboardButton("📈 Экспресс")],
    ], resize_keyboard=True
)

game_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📅 Сегодня"), KeyboardButton("⏭ Завтра")],
        [KeyboardButton("🔴 Live")],
        [KeyboardButton("🔙 Назад")],
    ], resize_keyboard=True
)

# ——— Утилиты ———

def format_time(utc: str):
    if not utc:
        return "TBD"
    # UTC → MSK
    try:
        from datetime import datetime, timedelta
        dt = datetime.fromisoformat(utc.replace("Z", ""))
        return (dt + timedelta(hours=3)).strftime("%H:%M")
    except:
        return utc

def match_lines(game: str, m: dict):
    teams = m.get("opponents", [])
    t1 = teams[0]["opponent"]["name"] if teams else "?"
    t2 = teams[1]["opponent"]["name"] if len(teams) > 1 else "?"
    time = format_time(m.get("begin_at"))
    tour = m.get("tournament", {}).get("name", "")
    return f"🕒 {time} — {t1} vs {t2} ({tour})"

# ——— API ———

async def get_matches(videogame: str, when: str):
    # PandaScore
    try:
        return await ps.matches.list(
            filter=[f"videogame={videogame}", f"filter[begin_at]={when}"]
        )
    except Exception as e:
        logging.error("Pandascore error: %s", e)
        return []

async def get_live(videogame: str):
    try:
        return await ps.matches.list(
            filter=[f"videogame={videogame}", "status=running"]
        )
    except:
        return []

async def get_historical(team: dict, videogame: str):
    # past matches for analytics
    try:
        t = team["opponent"]["id"]
        return await ps.matches.list(
            filter=[f"videogame={videogame}", f"filter[opponents.id]={t}", "sort=-begin_at"]
        )
    except:
        return []

# ——— Обработчики ———

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет! Выбери игру 👇", reply_markup=main_kb)

@dp.message()
async def menu(message: types.Message):
    text = message.text
    user = message.from_user.id

    # Выбор игры
    if text in ["🎮 CS2", "🛡 Dota 2"]:
        await message.answer("Выбери действие:", reply_markup=game_kb)
        dp.current_game = "cs2" if "CS2" in text else "dota2"
        return

    # Сегодня
    if text == "📅 Сегодня":
        vg = dp.current_game
        await message.answer("Загружаю…")
        matches = await get_matches(vg, date.today().isoformat())
        if not matches:
            await message.answer("Матчей нет 😕")
            return
        msg = "\n\n".join(match_lines(vg, m) for m in matches[:5])
        await message.answer(f"📅 Сегодня:\n{msg}")

    # Завтра
    if text == "⏭ Завтра":
        vg = dp.current_game
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        matches = await get_matches(vg, tomorrow)
        if not matches:
            await message.answer("Завтра ничего 😕")
            return
        msg = "\n\n".join(match_lines(vg, m) for m in matches[:5])
        await message.answer(f"⏭ Завтра:\n{msg}")

    # Live
    if text == "🔴 Live":
        vg = dp.current_game
        live = await get_live(vg)
        if live:
            out = "\n".join(match_lines(vg, m) for m in live)
            await message.answer(f"🔴 Live матчи:\n{out}")
        else:
            await message.answer("Нет live‑матчей сейчас.")

    # Аналитика
    if text == "📊 Аналитика":
        vg = dp.current_game
        # простейшая — взять ближайший матч
        all_matches = await get_matches(vg, date.today().isoformat())
        if not all_matches:
            await message.answer("Нет матчей.")
            return
        m = all_matches[0]
        teams = m.get("opponents", [])
        if len(teams) < 2:
            await message.answer("Недостаточно данных.")
            return

        # winrate прошлые
        h1 = await get_historical(teams[0], vg)
        h2 = await get_historical(teams[1], vg)
        wr1 = sum(1 for g in h1[:10] if g.get("winner"))/len(h1[:10]) if h1 else 0
        wr2 = sum(1 for g in h2[:10] if g.get("winner"))/len(h2[:10]) if h2 else 0

        text = (
            f"📊 Аналитика {teams[0]['opponent']['name']} vs {teams[1]['opponent']['name']}:\n"
            f"🏆 Winrate {teams[0]['opponent']['name']}: {wr1*100:.1f}%\n"
            f"🏆 Winrate {teams[1]['opponent']['name']}: {wr2*100:.1f}%\n"
            "💡 Общий тренд: более сильная команда имеет выше winrate."
        )
        await message.answer(text)

    # Экспресс‑прогноз
    if text == "📈 Экспресс":
        vg = dp.current_game
        all_matches = await get_matches(vg, date.today().isoformat())
        if not all_matches:
            await message.answer("Нет матчей для экспресса.")
            return
        # простой: берем все матчи и предлагаем победы (половина случайно 😄)
        expr = "\n".join(
            f"{m['opponents'][0]['opponent']['name']} — победа" for m in all_matches[:3]
        )
        await message.answer(f"🎯 Экспресс прогноз:\n{expr}")

    if text == "🔙 Назад":
        await message.answer("Главное меню:", reply_markup=main_kb)

# ——— Запуск ———

import asyncio
async def run_bot():
    await dp.start_polling(bot)

asyncio.run(run_bot())