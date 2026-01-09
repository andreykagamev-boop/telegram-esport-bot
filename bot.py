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
user_matches_cache = {}
waiting_for_match_choice = set()

# ---------- КЛАВИАТУРЫ ----------

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 CS2"), KeyboardButton(text="🛡 Dota 2")]
    ],
    resize_keyboard=True
)

game_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="📊 Аналитика")],
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

def format_match_short(match: dict, idx: int) -> str:
    opp = match.get("opponents", [])
    t1 = opp[0]["opponent"]["name"] if len(opp) > 0 else "TBD"
    t2 = opp[1]["opponent"]["name"] if len(opp) > 1 else "TBD"
    time = format_msk_time(match.get("begin_at"))
    return f"{idx}️⃣ {t1} vs {t2} ({time})"

def format_match_full(game: str, match: dict) -> str:
    opp = match.get("opponents", [])
    t1 = opp[0]["opponent"]["name"] if len(opp) > 0 else "TBD"
    t2 = opp[1]["opponent"]["name"] if len(opp) > 1 else "TBD"
    time = format_msk_time(match.get("begin_at"))
    tournament = match.get("tournament", {}).get("name", "Неизвестный турнир")

    return (
        f"🎮 {game.upper()}\n\n"
        f"🆚 {t1} vs {t2}\n"
        f"🕒 {time} МСК\n"
        f"🏆 {tournament}"
    )

# ---------- API ----------

async def fetch_matches(game: str):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    url = {
        "cs2": "https://api.pandascore.co/csgo/matches",
        "dota2": "https://api.pandascore.co/dota2/matches"
    }[game]

    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[begin_at]": today, "sort": "begin_at"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as r:
            if r.status != 200:
                return []
            return await r.json()

async def fetch_team_history(team_id: int, limit: int = 10):
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {
        "filter[opponent_id]": team_id,
        "sort": "-begin_at",
        "per_page": limit
    }

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.pandascore.co/matches", headers=headers, params=params) as r:
            if r.status != 200:
                return []
            return await r.json()

# ---------- АНАЛИТИКА ----------

def winrate(team_id, matches):
    wins = total = 0
    for m in matches:
        w = m.get("winner")
        if w:
            total += 1
            if w.get("id") == team_id:
                wins += 1
    return f"{wins}/{total} ({wins/total*100:.1f}%)" if total else "Нет данных"

def form(team_id, matches):
    return " ".join(
        "W" if m.get("winner", {}).get("id") == team_id else "L"
        for m in matches[:5]
    )

async def build_analytics(match):
    t1, t2 = match["opponents"][0]["opponent"], match["opponents"][1]["opponent"]

    h1 = await fetch_team_history(t1["id"])
    h2 = await fetch_team_history(t2["id"])

    return (
        f"📊 Аналитика матча\n\n"
        f"🆚 {t1['name']} vs {t2['name']}\n\n"
        f"📈 Винрейт (10):\n"
        f"{t1['name']}: {winrate(t1['id'], h1)}\n"
        f"{t2['name']}: {winrate(t2['id'], h2)}\n\n"
        f"🧠 Форма (5):\n"
        f"{t1['name']}: {form(t1['id'], h1)}\n"
        f"{t2['name']}: {form(t2['id'], h2)}\n\n"
        f"⚠️ Информация носит аналитический характер"
    )

# ---------- ХЭНДЛЕРЫ ----------

@dp.message(Command("start"))
async def start(msg):
    await msg.answer("Выбери игру 👇", reply_markup=main_keyboard)

@dp.message()
async def handler(msg):
    uid = msg.from_user.id
    text = msg.text.strip()

    # выбор матча цифрой
    if uid in waiting_for_match_choice and text.isdigit():
        idx = int(text) - 1
        matches = user_matches_cache.get(uid, [])
        if 0 <= idx < len(matches):
            waiting_for_match_choice.remove(uid)
            await msg.answer("Собираю аналитику ⏳")
            await msg.answer(await build_analytics(matches[idx]))
        else:
            await msg.answer("Неверный номер матча")
        return

    if text == "🎮 CS2":
        user_game[uid] = "cs2"
        await msg.answer("CS2 выбран", reply_markup=game_keyboard)

    elif text == "🛡 Dota 2":
        user_game[uid] = "dota2"
        await msg.answer("Dota 2 выбрана", reply_markup=game_keyboard)

    elif text == "📅 Сегодня":
        game = user_game.get(uid)
        if not game:
            await msg.answer("Сначала выбери игру")
            return

        matches = await fetch_matches(game)
        if not matches:
            await msg.answer("Сегодня матчей нет")
            return

        for m in matches[:5]:
            await msg.answer(format_match_full(game, m))

    elif text == "📊 Аналитика":
        game = user_game.get(uid)
        if not game:
            await msg.answer("Сначала выбери игру")
            return

        matches = await fetch_matches(game)
        if not matches:
            await msg.answer("Нет матчей для анализа")
            return

        user_matches_cache[uid] = matches[:5]
        waiting_for_match_choice.add(uid)

        msg_text = "Выбери матч для аналитики:\n\n"
        for i, m in enumerate(matches[:5], 1):
            msg_text += format_match_short(m, i) + "\n"

        await msg.answer(msg_text)

    elif text == "🔙 Назад":
        user_game.pop(uid, None)
        waiting_for_match_choice.discard(uid)
        await msg.answer("Главное меню", reply_markup=main_keyboard)

# ---------- WEB ----------

async def health(request):
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()

    logging.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())