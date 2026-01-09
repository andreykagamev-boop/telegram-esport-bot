import os
import asyncio
import aiohttp
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

user_game = {}

# ---------- КЛАВИАТУРЫ ----------

game_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🎮 CS2", callback_data="game_cs2"),
        InlineKeyboardButton(text="🛡 Dota 2", callback_data="game_dota2")
    ]
])

menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📅 Матчи", callback_data="matches"),
        InlineKeyboardButton(text="📊 Аналитика", callback_data="analytics")
    ],
    [
        InlineKeyboardButton(text="🎯 Экспресс", callback_data="express")
    ]
])

# ---------- API ----------

async def api_get(url):
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                return []
            return await r.json()

async def upcoming_matches(game):
    return await api_get(f"https://api.pandascore.io/{game}/matches/upcoming?per_page=5")

async def team_history(game, team_id):
    return await api_get(
        f"https://api.pandascore.io/{game}/matches?filter[opponent_id]={team_id}&per_page=5"
    )

def winrate(matches, team_id):
    if not matches:
        return 50
    wins = 0
    for m in matches:
        w = m.get("winner")
        if w and w.get("id") == team_id:
            wins += 1
    return int(wins / len(matches) * 100)

# ---------- START ----------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "👋 <b>Esport Bot</b>\n\nВыбери игру:",
        reply_markup=game_kb
    )

# ---------- ВЫБОР ИГРЫ ----------

@dp.callback_query(F.data.startswith("game_"))
async def choose_game(call: types.CallbackQuery):
    game = call.data.replace("game_", "")
    user_game[call.from_user.id] = game

    await call.message.edit_text(
        f"✅ Игра выбрана: <b>{game.upper()}</b>",
        reply_markup=menu_kb
    )
    await call.answer()

# ---------- МАТЧИ ----------

@dp.callback_query(F.data == "matches")
async def matches(call: types.CallbackQuery):
    game = user_game.get(call.from_user.id)
    if not game:
        return await call.answer("Сначала выбери игру", show_alert=True)

    data = await upcoming_matches(game)
    if not data:
        return await call.message.answer("Матчей нет 😕")

    for m in data:
        opp = m.get("opponents", [])
        if len(opp) < 2:
            continue

        t1 = opp[0]["opponent"]["name"]
        t2 = opp[1]["opponent"]["name"]
        tour = m.get("tournament", {}).get("name", "—")
        time = m.get("begin_at")

        text = (
            f"🆚 <b>{t1} vs {t2}</b>\n"
            f"🏆 {tour}\n"
            f"🕒 {time}\n"
            f"──────────────"
        )
        await call.message.answer(text)

    await call.answer()

# ---------- АНАЛИТИКА ----------

@dp.callback_query(F.data == "analytics")
async def analytics(call: types.CallbackQuery):
    game = user_game.get(call.from_user.id)
    if not game:
        return await call.answer("Сначала выбери игру", show_alert=True)

    matches = await upcoming_matches(game)
    if not matches:
        return await call.message.answer("Нет данных")

    team = matches[0]["opponents"][0]["opponent"]
    history = await team_history(game, team["id"])
    wr = winrate(history, team["id"])

    bars = "🟩" * (wr // 10) + "🟥" * (10 - wr // 10)

    await call.message.answer(
        f"📊 <b>Аналитика</b>\n\n"
        f"Команда: <b>{team['name']}</b>\n"
        f"Винрейт: <b>{wr}%</b>\n"
        f"{bars}"
    )
    await call.answer()

# ---------- ЭКСПРЕСС ----------

@dp.callback_query(F.data == "express")
async def express(call: types.CallbackQuery):
    game = user_game.get(call.from_user.id)
    if not game:
        return await call.answer("Сначала выбери игру", show_alert=True)

    matches = await upcoming_matches(game)
    if not matches:
        return await call.message.answer("Нет матчей")

    text = "🎯 <b>Экспресс-прогноз</b>\n──────────────\n"
    i = 1

    for m in matches:
        opp = m.get("opponents", [])
        if len(opp) < 2:
            continue

        t1, t2 = opp[0]["opponent"], opp[1]["opponent"]
        wr1 = winrate(await team_history(game, t1["id"]), t1["id"])
        wr2 = winrate(await team_history(game, t2["id"]), t2["id"])

        fav = t1["name"] if wr1 >= wr2 else t2["name"]

        text += (
            f"{i}️⃣ <b>{t1['name']} vs {t2['name']}</b>\n"
            f"⭐ Прогноз: <b>{fav}</b>\n"
            f"📊 {wr1}% / {wr2}%\n"
            f"──────────────\n"
        )
        i += 1

    await call.message.answer(text)
    await call.answer()

# ---------- RUN ----------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())