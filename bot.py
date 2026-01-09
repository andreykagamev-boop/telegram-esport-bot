import asyncio
import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- ХРАНИЛИЩЕ ----------

user_game = {}
cache_matches = {}   # key: game -> {"data": [], "ts": datetime}
cache_analytics = {} # key: match_id -> {"text": str, "ts": datetime}

CACHE_TTL = 300  # 5 минут

# ---------- КЛАВИАТУРЫ ----------

main_kb = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton("🎮 CS2"), types.KeyboardButton("🛡 Dota 2")]],
    resize_keyboard=True
)

game_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton("📅 Сегодня"), types.KeyboardButton("📊 Аналитика")],
        [types.KeyboardButton("🔙 Назад")]
    ],
    resize_keyboard=True
)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------

def format_msk(utc_time: str) -> str:
    if not utc_time:
        return "TBD"
    dt = datetime.fromisoformat(utc_time.replace("Z",""))
    return (dt + timedelta(hours=3)).strftime("%H:%M")

def winrate(team_id, matches):
    wins=total=0
    for m in matches:
        w = m.get("winner")
        if w:
            total+=1
            if w.get("id")==team_id: wins+=1
    return f"{wins}/{total} ({wins/total*100:.1f}%)" if total else "Нет данных"

def form(team_id, matches):
    return " ".join("W" if m.get("winner", {}).get("id")==team_id else "L" for m in matches[:5])

# ---------- API ----------

async def fetch_matches(game):
    # кеш
    now = datetime.utcnow()
    if game in cache_matches and (now - cache_matches[game]["ts"]).total_seconds() < CACHE_TTL:
        return cache_matches[game]["data"]

    url = {
        "cs2":"https://api.pandascore.co/csgo/matches",
        "dota2":"https://api.pandascore.co/dota2/matches"
    }[game]

    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[begin_at]": now.strftime("%Y-%m-%d"), "sort":"begin_at"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as r:
            if r.status != 200: return []
            data = await r.json()
            cache_matches[game] = {"data": data, "ts": now}
            return data

async def fetch_team_history(team_id, limit=10):
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[opponent_id]": team_id, "sort":"-begin_at","per_page":limit}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.pandascore.co/matches", headers=headers, params=params) as r:
            if r.status != 200: return []
            return await r.json()

# ---------- АНАЛИТИКА ----------

async def build_analytics(match):
    match_id = match.get("id")
    now = datetime.utcnow()
    if match_id in cache_analytics and (now - cache_analytics[match_id]["ts"]).total_seconds() < CACHE_TTL:
        return cache_analytics[match_id]["text"]

    t1, t2 = match["opponents"][0]["opponent"], match["opponents"][1]["opponent"]
    h1 = await fetch_team_history(t1["id"])
    h2 = await fetch_team_history(t2["id"])

    # H2H
    h2h_matches = [m for m in h1 if any(o["opponent"]["id"]==t2["id"] for o in m.get("opponents",[]))]
    h2h_score = sum(1 for m in h2h_matches if m.get("winner",{}).get("id")==t1["id"])
    h2h_text = f"{t1['name']} {h2h_score} — {len(h2h_matches)-h2h_score} {t2['name']}" if h2h_matches else "Нет данных"

    text = (
        f"📊 Аналитика матча\n\n"
        f"🆚 {t1['name']} vs {t2['name']}\n\n"
        f"📈 Винрейт (10 матчей):\n"
        f"{t1['name']}: {winrate(t1['id'], h1)}\n"
        f"{t2['name']}: {winrate(t2['id'], h2)}\n\n"
        f"🧠 Форма (5 матчей):\n"
        f"{t1['name']}: {form(t1['id'], h1)}\n"
        f"{t2['name']}: {form(t2['id'], h2)}\n\n"
        f"🤝 H2H (последние 5): {h2h_text}\n"
        f"⚠️ Информация носит справочный характер"
    )

    cache_analytics[match_id] = {"text": text, "ts": now}
    return text

# ---------- ХЭНДЛЕРЫ ----------

@dp.message(Command("start"))
async def start(msg):
    await msg.answer("Выбери игру 👇", reply_markup=main_kb)

@dp.message()
async def handler(msg):
    uid = msg.from_user.id
    text = msg.text.strip()

    if text == "🎮 CS2":
        user_game[uid] = "cs2"
        await msg.answer("CS2 выбран", reply_markup=game_kb)
    elif text == "🛡 Dota 2":
        user_game[uid] = "dota2"
        await msg.answer("Dota 2 выбрана", reply_markup=game_kb)
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
            t1, t2 = m["opponents"][0]["opponent"]["name"], m["opponents"][1]["opponent"]["name"]
            await msg.answer(f"{t1} vs {t2} ({format_msk(m.get('begin_at'))})")
    elif text == "📊 Аналитика":
        game = user_game.get(uid)
        if not game:
            await msg.answer("Сначала выбери игру")
            return
        matches = await fetch_matches(game)
        if not matches:
            await msg.answer("Нет матчей для анализа")
            return

        # создаём inline кнопки
        buttons = [types.InlineKeyboardButton(
            text=f"{m['opponents'][0]['opponent']['name']} vs {m['opponents'][1]['opponent']['name']}", 
            callback_data=f"analyze_{m['id']}"
        ) for m in matches[:5]]
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(*buttons)
        await msg.answer("Выберите матч для аналитики:", reply_markup=kb)

    elif text == "🔙 Назад":
        user_game.pop(uid, None)
        await msg.answer("Главное меню", reply_markup=main_kb)

# ---------- CALLBACKS ----------

@dp.callback_query()
async def cb_handler(cb: types.CallbackQuery):
    data = cb.data
    if data.startswith("analyze_"):
        match_id = int(data.split("_")[1])
        # ищем матч в кеше
        match = None
        for mlist in cache_matches.values():
            for m in mlist["data"]:
                if m["id"]==match_id: match=m
        if not match:
            await cb.message.answer("Не удалось найти матч")
            return
        await cb.message.answer("Собираю аналитику ⏳")
        text = await build_analytics(match)
        await cb.message.answer(text)
        await cb.answer()  # чтобы кнопка перестала "крутить"

# ---------- WEB ----------

async def health(request):
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT",10000))
    await web.TCPSite(runner,"0.0.0.0",port).start()
    logging.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())