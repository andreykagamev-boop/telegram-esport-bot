import os
import asyncio
import aiohttp
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

user_game: dict[int, str] = {}

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

async def api_get(url: str):
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                return []
            return await r.json()

async def get_upcoming_matches(game: str):
    return await api_get(f"https://api.pandascore.io/{game}/matches/upcoming?per_page=5")

async def get_team_matches(game: str, team_id: int):
    return await api_get(
        f"https://api.pandascore.io/{game}/matches?filter[opponent_id]={team_id}&per_page=5"
    )

# ---------- ХЭЛПЕРЫ ----------

def msk_time(utc: str):
    if not utc:
        return "TBD"
    dt = datetime.fromisoformat(utc.replace("Z", ""))
    return (dt.hour + 3) % 24, dt.minute

def winrate(matches, team_id):
    if not matches:
        return 50
    wins = 0
    for m in matches:
        winner = m.get("winner")
        if winner and winner.get("id") == team_id:
            wins += 1
    return int(wins / len(matches) * 100)

# ---------- ХЭНДЛЕРЫ ----------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "👋 <b>Esport Bot</b>\n\nВыбери игру:",
        reply_markup=game_kb
    )

@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    uid = call.from_user.id
    data = call.data

    # --- выбор игры ---
    if data.startswith("game_"):
        user_game[uid] = data.replace("game_", "")
        await call.message.edit_text(
            f"✅ Игра выбрана: <b>{user_game[uid].upper()}</b>",
            reply_markup=menu_kb
        )
        return await call.answer()

    game = user_game.get(uid)
    if not game:
        return await call.answer("Сначала выбери игру", show_alert=True)

    # --- МАТЧИ ---
    if data == "matches":
        matches = await get_upcoming_matches(game)
        if not matches:
            return await call.message.answer("Матчей нет 😕")

        for m in matches:
            opp = m.get("opponents", [])
            if len(opp) < 2:
                continue

            t1 = opp[0]["opponent"]["name"]
            t2 = opp[1]["opponent"]["name"]
            tour = m.get("tournament", {}).get("name", "—")
            h, mn = msk_time(m.get("begin_at"))

            text = (
                f"🆚 <b>{t1} vs {t2}</b>\n"
                f"🏆 {tour}\n"
                f"🕒 {h:02d}:{mn:02d} МСК\n"
                f"──────────────"
            )
            await call.message.answer(text)

        return await call.answer()

    # --- АНАЛИТИКА ---
    if data == "analytics":
        matches = await get_upcoming_matches(game)
        if not matches:
            return await call.message.answer("Нет данных 😕")

        team = matches[0]["opponents"][0]["opponent"]
        team_id = team["id"]
        team_name = team["name"]

        history = await get_team_matches(game, team_id)
        wr = winrate(history, team_id)

        bars = "🟩" * (wr // 10) + "🟥" * (10 - wr // 10)

        text = (
            f"📊 <b>Аналитика команды</b>\n"
            f"Команда: <b>{team_name}</b>\n\n"
            f"Винрейт (5 матчей): <b>{wr}%</b>\n"
            f"{bars}\n\n"
            f"📌 Основано на последних играх"
        )
        return await call.message.answer(text)

    # --- ЭКСПРЕСС ---
    if data == "express":
        matches = await get_upcoming_matches(game)
        if not matches:
            return await call.message.answer("Нет матчей 😕")

        text = "🎯 <b>Экспресс-прогноз</b>\n──────────────\n"
        idx = 1

        for m in matches:
            opp = m.get("opponents", [])
            if len(opp) < 2:
                continue

            t1, t2 = opp[0]["opponent"], opp[1]["opponent"]
            h1 = await get_team_matches(game, t1["id"])
            h2 = await get_team_matches(game, t2["id"])

            wr1 = winrate(h1, t1["id"])
            wr2 = winrate(h2, t2["id"])

            fav = t1["name"] if wr1 >= wr2 else t2["name"]

            text += (
                f"{idx}️⃣ <b>{t1['name']} vs {t2['name']}</b>\n"
                f"⭐ Прогноз: <b>{fav}</b>\n"
                f"📊 {wr1}% / {wr2}%\n"
                f"──────────────\n"
            )
            idx += 1

        return await call.message.answer(text)

# ---------- ЗАПУСК ----------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())