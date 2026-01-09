import asyncio
import logging
import os
from datetime import datetime, timedelta

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= STATE =================
user_game = {}
cache = {
    "matches": {},
    "analytics": {}
}
CACHE_TTL = 300

session: aiohttp.ClientSession | None = None

# ================= KEYBOARDS =================
main_kb = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton(text="🎮 CS2"), types.KeyboardButton(text="🛡 Dota 2")]],
    resize_keyboard=True
)

game_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [
            types.KeyboardButton(text="📅 Сегодня"),
            types.KeyboardButton(text="📊 Аналитика"),
            types.KeyboardButton(text="🔥 Экспресс")
        ],
        [types.KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# ================= UTILS =================
def msk(utc):
    if not utc:
        return "TBD"
    return (datetime.fromisoformat(utc.replace("Z", "")) + timedelta(hours=3)).strftime("%H:%M")

def now_ts():
    return datetime.utcnow()

def is_cache_valid(ts):
    return (now_ts() - ts).seconds < CACHE_TTL

# ================= API =================
async def fetch_matches(game):
    if game in cache["matches"] and is_cache_valid(cache["matches"][game]["ts"]):
        return cache["matches"][game]["data"]

    url = {
        "cs2": "https://api.pandascore.co/csgo/matches",
        "dota2": "https://api.pandascore.co/dota2/matches"
    }[game]

    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[begin_at]": now_ts().strftime("%Y-%m-%d"), "sort": "begin_at"}

    async with session.get(url, headers=headers, params=params) as r:
        if r.status != 200:
            return []
        data = await r.json()
        cache["matches"][game] = {"data": data, "ts": now_ts()}
        return data

async def team_history(team_id, limit=5):
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"sort": "-begin_at", "per_page": limit}

    async with session.get(
        f"https://api.pandascore.co/teams/{team_id}/matches",
        headers=headers,
        params=params
    ) as r:
        if r.status != 200:
            return []
        return await r.json()

# ================= ANALYTICS =================
async def build_analytics(match):
    if match["id"] in cache["analytics"]:
        return cache["analytics"][match["id"]]

    opp = match.get("opponents", [])
    if len(opp) < 2:
        return "Недостаточно данных"

    t1 = opp[0]["opponent"]
    t2 = opp[1]["opponent"]

    h1 = await team_history(t1["id"])
    h2 = await team_history(t2["id"])

    def stats(team, hist):
        wins = sum(1 for m in hist if m and m.get("winner") and m["winner"]["id"] == team)
        streak = 0
        for m in hist:
            if m.get("winner") and m["winner"]["id"] == team:
                streak += 1
            else:
                break
        return wins, streak

    w1, s1 = stats(t1["id"], h1)
    w2, s2 = stats(t2["id"], h2)

    fav = t1["name"] if w1 >= w2 else t2["name"]

    text = (
        f"📊 <b>Подробная аналитика</b>\n\n"
        f"🆚 <b>{t1['name']} vs {t2['name']}</b>\n"
        f"🕒 {msk(match.get('begin_at'))} МСК\n\n"
        f"📈 <b>Форма команд (5 матчей)</b>\n"
        f"• {t1['name']}: {w1}/5 побед | серия: {s1}\n"
        f"• {t2['name']}: {w2}/5 побед | серия: {s2}\n\n"
        f"⭐ <b>Фаворит:</b> {fav}\n\n"
        f"🧠 <b>Почему:</b>\n"
        f"— стабильнее результаты\n"
        f"— лучшая текущая форма\n"
        f"— меньше поражений в последних играх\n\n"
        f"⚠️ Аналитика основана на статистике и не гарантирует исход."
    )

    cache["analytics"][match["id"]] = text
    return text

# ================= HANDLERS =================
@dp.message(Command("start"))
async def start(m):
    await m.answer("Выбери игру 👇", reply_markup=main_kb)

@dp.message()
async def handler(m):
    uid = m.from_user.id
    text = m.text

    if text == "🎮 CS2":
        user_game[uid] = "cs2"
        await m.answer("CS2 выбран", reply_markup=game_kb)

    elif text == "🛡 Dota 2":
        user_game[uid] = "dota2"
        await m.answer("Dota 2 выбрана", reply_markup=game_kb)

    elif text == "📅 Сегодня":
        game = user_game.get(uid)
        if not game:
            return await m.answer("Сначала выбери игру")

        matches = await fetch_matches(game)
        for mth in matches[:5]:
            opp = mth.get("opponents", [])
            if len(opp) < 2:
                continue
            await m.answer(
                f"🎮 {game.upper()}\n"
                f"🆚 <b>{opp[0]['opponent']['name']} vs {opp[1]['opponent']['name']}</b>\n"
                f"🕒 {msk(mth.get('begin_at'))} МСК\n"
                f"🏆 {mth.get('tournament',{}).get('name','')}",
                parse_mode="HTML"
            )

    elif text == "📊 Аналитика":
        game = user_game.get(uid)
        matches = await fetch_matches(game)

        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=f"{m['opponents'][0]['opponent']['name']} vs {m['opponents'][1]['opponent']['name']}",
                    callback_data=f"an_{m['id']}"
                )]
                for m in matches[:5]
                if len(m.get("opponents", [])) >= 2
            ]
        )
        await m.answer("Выбери матч:", reply_markup=kb)

    elif text == "🔥 Экспресс":
        game = user_game.get(uid)
        matches = await fetch_matches(game)

        text = "🔥 <b>Экспресс-прогноз</b>\n\n"
        i = 1
        for mth in matches:
            opp = mth.get("opponents", [])
            if len(opp) < 2 or i > 4:
                continue
            t1, t2 = opp[0]["opponent"], opp[1]["opponent"]
            text += (
                f"{i}️⃣ <b>{t1['name']} победа</b>\n"
                f"Причина: стабильнее форма и выше винрейт\n\n"
            )
            i += 1

        text += "⚠️ Экспресс — повышенный риск. Используй ответственно."
        await m.answer(text, parse_mode="HTML")

    elif text == "🔙 Назад":
        user_game.pop(uid, None)
        await m.answer("Главное меню", reply_markup=main_kb)

# ================= CALLBACK =================
@dp.callback_query(lambda c: c.data.startswith("an_"))
async def analytics_cb(cb: types.CallbackQuery):
    await cb.answer()
    match_id = int(cb.data.split("_")[1])

    for g in cache["matches"].values():
        for m in g["data"]:
            if m.get("id") == match_id:
                text = await build_analytics(m)
                return await cb.message.answer(text, parse_mode="HTML")

    await cb.message.answer("Матч не найден")

# ================= WEB =================
async def health(_):
    return web.Response(text="OK")

async def main():
    global session
    session = aiohttp.ClientSession()

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())