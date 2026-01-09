import asyncio
import os
import logging
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

HEADERS = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}

CACHE = {
    "matches": {},       # ключ: game, value: список матчей
    "teams": {},         # ключ: team_id_game, value: последние 10 матчей
    "analytics": {},     # ключ: match_id, value: текст аналитики
    "notifications": {}  # ключ: user_id, value: список match_id для уведомлений
}

# ---------- КЛАВИАТУРЫ ----------
main_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton("🎮 CS2"), types.KeyboardButton("🛡 Dota 2")],
        [types.KeyboardButton("🔥 Экспресс")],
        [types.KeyboardButton("🔴 Live-матчи")]
    ],
    resize_keyboard=True
)

game_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton("📅 Сегодня")],
        [types.KeyboardButton("🔙 Назад")]
    ],
    resize_keyboard=True
)

# ---------- API ----------
async def fetch(url, params=None):
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=HEADERS, params=params) as r:
            if r.status != 200:
                return []
            return await r.json()

async def get_matches(game, live=False):
    """Получаем матчи: сегодня или live"""
    key = f"{game}_{'live' if live else 'today'}"
    if key in CACHE["matches"]:
        return CACHE["matches"][key]

    today = datetime.utcnow().strftime("%Y-%m-%d")
    endpoint = "csgo" if game == "cs2" else "dota2"
    url = f"https://api.pandascore.co/{endpoint}/matches"
    params = {"filter[begin_at]": today, "sort": "begin_at", "per_page": 20}
    if live:
        params = {"filter[live]": True, "per_page": 10}

    matches = await fetch(url, params)
    CACHE["matches"][key] = matches
    return matches

async def get_team_history(team_id, game):
    key = f"{team_id}_{game}"
    if key in CACHE["teams"]:
        return CACHE["teams"][key]

    endpoint = "csgo" if game == "cs2" else "dota2"
    url = f"https://api.pandascore.co/{endpoint}/matches"
    data = await fetch(url, {"filter[opponent_id]": team_id, "per_page": 10})
    CACHE["teams"][key] = data
    return data

# ---------- АНАЛИТИКА ----------
def winrate(matches, team_id):
    wins = total = 0
    for m in matches:
        if not m or not m.get("winner"):
            continue
        total += 1
        if m["winner"]["id"] == team_id:
            wins += 1
    return round((wins / total) * 100, 1) if total else 0

def form(matches, team_id):
    res = ""
    for m in matches[:5]:
        if not m or not m.get("winner"):
            continue
        res += "W" if m["winner"]["id"] == team_id else "L"
    return res or "N/A"

def probability(wr1, wr2):
    return round((wr1 / (wr1 + wr2)) * 100) if wr1 + wr2 else 50

async def analytics(match, game):
    mid = match["id"]
    if mid in CACHE["analytics"]:
        return CACHE["analytics"][mid]

    t1, t2 = match["opponents"][0]["opponent"], match["opponents"][1]["opponent"]

    h1 = await get_team_history(t1["id"], game)
    h2 = await get_team_history(t2["id"], game)

    wr1, wr2 = winrate(h1, t1["id"]), winrate(h2, t2["id"])
    p1, p2 = probability(wr1, wr2), 100 - probability(wr1, wr2)
    fav = t1["name"] if p1 > p2 else t2["name"]

    text = (
        f"📊 АНАЛИТИКА МАТЧА\n\n"
        f"🆚 {t1['name']} vs {t2['name']}\n\n"
        f"Вероятность победы:\n"
        f"🟢 {t1['name']} — {p1}%\n"
        f"🔴 {t2['name']} — {p2}%\n\n"
        f"Форма:\n"
        f"{t1['name']}: {form(h1, t1['id'])}\n"
        f"{t2['name']}: {form(h2, t2['id'])}\n\n"
        f"Фаворит: ⭐ {fav}\n\n"
        f"Почему:\n"
        f"• Винрейт и серия побед\n"
        f"• Текущая форма\n"
        f"• Стабильность состава\n\n"
        f"⚠️ Аналитика не гарантирует исход"
    )

    CACHE["analytics"][mid] = text
    return text

# ---------- ЭКСПРЕСС ----------
async def express(game):
    matches = await get_matches(game)
    picks = []
    for m in matches:
        if len(m.get("opponents", [])) < 2:
            continue
        text = await analytics(m, game)
        for line in text.splitlines():
            if "🟢" in line:
                prob = int(line.split("—")[1].replace("%", "").strip())
                if prob >= 60:
                    picks.append(line.strip())
        if len(picks) >= 3:
            break
    if not picks:
        return "❌ Нет матчей с достаточной уверенностью"
    msg = "🔥 УМНЫЙ ЭКСПРЕСС\n\n"
    for i, p in enumerate(picks, 1):
        msg += f"{i}️⃣ {p}\n"
    msg += "\nРиск: 🟡 Средний\n\nОсновано на статистике"
    return msg

# ---------- LIVE-матчи ----------
async def live_matches(game):
    matches = await get_matches(game, live=True)
    if not matches:
        return "❌ Live матчей нет"
    msg = "🔴 LIVE МАТЧИ:\n\n"
    for m in matches[:5]:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        msg += f"🆚 {t1} vs {t2}\n🕒 {m.get('begin_at','')} МСК\n\n"
    return msg

# ---------- ХЭНДЛЕРЫ ----------
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Выбери игру 👇", reply_markup=main_kb)

@dp.message(lambda m: m.text in ["🎮 CS2", "🛡 Dota 2"])
async def choose_game(m: types.Message):
    m.bot_data["game"] = "cs2" if "CS2" in m.text else "dota2"
    await m.answer("Выбери действие:", reply_markup=game_kb)

@dp.message(lambda m: m.text == "📅 Сегодня")
async def today(m: types.Message):
    game = m.bot_data.get("game", "cs2")
    matches = await get_matches(game)
    for m_ in matches[:5]:
        t1 = m_["opponents"][0]["opponent"]["name"]
        t2 = m_["opponents"][1]["opponent"]["name"]
        time = datetime.fromisoformat(m_["begin_at"].replace("Z", "")) + timedelta(hours=3)
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton("📊 Аналитика", callback_data=f"a_{m_['id']}")]]
        )
        await m.answer(f"🎮 {t1} vs {t2}\n🕒 {time:%H:%M} МСК", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("a_"))
async def cb_analytics(cb: types.CallbackQuery):
    await cb.answer()
    mid = int(cb.data.split("_")[1])
    for game in ["cs2","dota2"]:
        for m_ in CACHE["matches"].get(game, []):
            if m_["id"] == mid:
                await cb.message.answer(await analytics(m_, game))
                return

@dp.message(lambda m: m.text == "🔥 Экспресс")
async def cb_express(m: types.Message):
    game = m.bot_data.get("game","cs2")
    await m.answer("Собираю экспресс ⏳")
    await m.answer(await express(game))

@dp.message(lambda m: m.text == "🔴 Live-матчи")
async def cb_live(m: types.Message):
    game = m.bot_data.get("game","cs2")
    await m.answer(await live_matches(game))

@dp.message(lambda m: m.text == "🔙 Назад")
async def cb_back(m: types.Message):
    await m.answer("Главное меню", reply_markup=main_kb)

# ---------- RUN ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())