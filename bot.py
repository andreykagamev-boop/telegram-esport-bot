import asyncio
import logging
import os
from datetime import datetime, timedelta

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ---------- НАСТРОЙКИ ----------

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_game = {}

# ---------- КЛАВИАТУРЫ ----------

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 CS2"), KeyboardButton(text="🛡 Dota 2")],
        [KeyboardButton(text="📊 Аналитика")]
    ],
    resize_keyboard=True
)

game_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Сегодня")],
        [KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------

def format_msk_time(utc_time: str) -> str:
    if not utc_time:
        return "TBD"
    dt = datetime.fromisoformat(utc_time.replace("Z", ""))
    return (dt + timedelta(hours=3)).strftime("%H:%M")

def format_match_text(game: str, match: dict) -> str:
    opponents = match.get("opponents", [])
    team1 = opponents[0]["opponent"]["name"] if len(opponents) > 0 else "TBD"
    team2 = opponents[1]["opponent"]["name"] if len(opponents) > 1 else "TBD"

    time_msk = format_msk_time(match.get("begin_at"))
    tournament = match.get("tournament", {}).get("name", "Неизвестный турнир")

    return (
        f"🎮 {game.upper()}\n\n"
        f"🆚 {team1} vs {team2}\n"
        f"🕒 {time_msk} МСК\n"
        f"🏆 {tournament}\n"
        f"──────────────"
    )

# ---------- API ----------

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

async def fetch_team_recent_matches(team_id: int, limit: int = 10):
    url = "https://api.pandascore.co/matches"
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {
        "filter[opponent_id]": team_id,
        "sort": "-begin_at",
        "per_page": limit
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

# ---------- АНАЛИТИКА ----------

def calculate_winrate(team_id: int, matches: list):
    wins, total = 0, 0

    for m in matches:
        winner = m.get("winner")
        if winner:
            total += 1
            if winner.get("id") == team_id:
                wins += 1

    if total == 0:
        return "Нет данных"

    return f"{wins}/{total} ({wins / total * 100:.1f}%)"

def build_form(team_id: int, matches: list):
    form = []
    for m in matches[:5]:
        winner = m.get("winner")
        form.append("W" if winner and winner.get("id") == team_id else "L")
    return " ".join(form) if form else "–"

async def build_analytics(match: dict):
    opponents = match.get("opponents", [])
    if len(opponents) < 2:
        return "Недостаточно данных для аналитики ❌"

    t1 = opponents[0]["opponent"]
    t2 = opponents[1]["opponent"]

    t1_history = await fetch_team_recent_matches(t1["id"])
    t2_history = await fetch_team_recent_matches(t2["id"])

    return (
        f"📊 Аналитика матча\n\n"
        f"🆚 {t1['name']} vs {t2['name']}\n\n"
        f"📈 Винрейт (10 матчей):\n"
        f"{t1['name']}: {calculate_winrate(t1['id'], t1_history)}\n"
        f"{t2['name']}: {calculate_winrate(t2['id'], t2_history)}\n\n"
        f"🧠 Форма (5 матчей):\n"
        f"{t1['name']}: {build_form(t1['id'], t1_history)}\n"
        f"{t2['name']}: {build_form(t2['id'], t2_history)}\n\n"
        f"⚠️ Аналитика носит информационный характер"
    )

# ---------- ХЭНДЛЕРЫ ----------

@dp.message(Command("start"))
async def start(message):
    await message.answer("Привет! Выбери игру 👇", reply_markup=main_keyboard)

@dp.message()
async def menu(message):
    text = message.text
    user_id = message.from_user.id

    if text == "🎮 CS2":
        user_game[user_id] = "cs2"
        await message.answer("CS2 выбран", reply_markup=game_keyboard)

    elif text == "🛡 Dota 2":
        user_game[user_id] = "dota2"
        await message.answer("Dota 2 выбрана", reply_markup=game_keyboard)

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

        for m in matches[:5]:
            await message.answer(format_match_text(game, m))

    elif text == "📊 Аналитика":
        game = user_game.get(user_id)
        if not game:
            await message.answer("Сначала выбери игру 👆")
            return

        await message.answer("Собираю аналитику ⏳")
        matches = await fetch_matches(game)

        if not matches:
            await message.answer("Нет матчей для анализа 😕")
            return

        analytics = await build_analytics(matches[0])
        await message.answer(analytics)

    elif text == "🔙 Назад":
        user_game.pop(user_id, None)
        await message.answer("Главное меню", reply_markup=main_keyboard)

# ---------- WEB (Blue Tunes) ----------

async def health(request):
    return web.Response(text="OK")

# ---------- ЗАПУСК ----------

async def main():
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logging.info(f"Web server started on port {port}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())