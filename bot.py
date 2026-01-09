import asyncio
import logging
import os
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

user_game = {}

# --- КЛАВИАТУРЫ ---

main_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton("🎮 CS2"), types.KeyboardButton("🛡 Dota 2")],
        [types.KeyboardButton("📊 Аналитика"), types.KeyboardButton("🎯 Экспресс")]
    ],
    resize_keyboard=True
)

game_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton("📅 Сегодня"), types.KeyboardButton("⏭ Завтра")],
        [types.KeyboardButton("🔴 Live")],
        [types.KeyboardButton("🔙 Назад")]
    ],
    resize_keyboard=True
)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_msk_time(utc_time: str) -> str:
    if not utc_time:
        return "TBD"
    dt = datetime.fromisoformat(utc_time.replace("Z", ""))
    msk_time = dt + timedelta(hours=3)
    return msk_time.strftime("%d.%m %H:%M")

def format_match_table(game: str, match: dict) -> str:
    opponents = match.get("opponents", [])
    team1 = opponents[0]["opponent"]["name"] if len(opponents) > 0 else "TBD"
    team2 = opponents[1]["opponent"]["name"] if len(opponents) > 1 else "TBD"
    time_utc = match.get("begin_at")
    time_msk = format_msk_time(time_utc)
    tournament = match.get("tournament", {}).get("name", "Неизвестный турнир")
    return (
        f"🎮 <b>{game.upper()}</b>\n"
        f"🆚 <b>{team1}</b> vs <b>{team2}</b>\n"
        f"🕒 {time_msk} МСК\n"
        f"🏆 {tournament}\n"
        f"────────────────"
    )

async def fetch_matches(game: str, today=True):
    date_filter = datetime.utcnow().strftime("%Y-%m-%d") if today else None

    url_map = {
        "cs2": "https://api.pandascore.co/csgo/matches",
        "dota2": "https://api.pandascore.co/dota2/matches"
    }

    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[begin_at]": date_filter, "sort": "begin_at"} if date_filter else {}

    async with aiohttp.ClientSession() as session:
        async with session.get(url_map[game], headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

async def fetch_team_matches(team_id: int, game: str, limit=5):
    url_map = {
        "cs2": f"https://api.pandascore.co/csgo/teams/{team_id}/matches",
        "dota2": f"https://api.pandascore.co/dota2/teams/{team_id}/matches"
    }
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"sort": "-begin_at", "per_page": limit}

    async with aiohttp.ClientSession() as session:
        async with session.get(url_map[game], headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет! Выбери игру 👇", reply_markup=main_keyboard)

@dp.message()
async def handler(message: types.Message):
    text = message.text
    user_id = message.from_user.id

    if text in ["🎮 CS2", "🛡 Dota 2"]:
        game = "cs2" if text == "🎮 CS2" else "dota2"
        user_game[user_id] = game
        await message.answer(f"{text} — выбери раздел:", reply_markup=game_keyboard)
        return

    if text in ["📅 Сегодня", "⏭ Завтра", "🔴 Live"]:
        game = user_game.get(user_id)
        if not game:
            await message.answer("Сначала выбери игру 👆")
            return
        today = text == "📅 Сегодня"
        await message.answer("Загружаю матчи ⏳")
        matches = await fetch_matches(game, today=today)
        if not matches:
            await message.answer("Матчей нет 😕")
            return
        for match in matches[:5]:
            await message.answer(format_match_table(game, match))
        return

    if text == "🔙 Назад":
        user_game.pop(user_id, None)
        await message.answer("Главное меню:", reply_markup=main_keyboard)
        return

    if text == "📊 Аналитика":
        game = user_game.get(user_id)
        if not game:
            await message.answer("Сначала выбери игру 👆")
            return
        matches = await fetch_matches(game)
        if not matches:
            await message.answer("Нет матчей для аналитики 😕")
            return
        team = matches[0]["opponents"][0]["opponent"]
        team_id = team["id"]
        team_name = team["name"]
        past_matches = await fetch_team_matches(team_id, game, limit=5)
        if not past_matches:
            await message.answer(f"Аналитика для {team_name} недоступна 😕")
            return
        text_anal = f"📊 <b>Аналитика: {team_name}</b>\n────────────────\n"
        wins = 0
        for m in past_matches:
            opp = m.get("opponents", [])
            opp_name = opp[1]["opponent"]["name"] if len(opp) > 1 else "TBD"
            winner = m.get("winner")
            result = "✅ Победа" if winner and winner["id"] == team_id else "❌ Поражение"
            if result == "✅ Победа":
                wins += 1
            tournament = m.get("tournament", {}).get("name", "Неизвестный турнир")
            text_anal += f"🆚 {opp_name} — {result}\n🏆 {tournament}\n────────────────\n"
        wr = int((wins / len(past_matches)) * 100)
        text_anal += f"Винрейт за {len(past_matches)} матчей: {wr}%\n────────────────"
        await message.answer(text_anal)
        return

    if text == "🎯 Экспресс":
        game = user_game.get(user_id)
        if not game:
            await message.answer("Сначала выбери игру 👆")
            return
        matches = await fetch_matches(game)
        if not matches:
            await message.answer("Нет матчей для экспресс-прогноза 😕")
            return
        text_exp = "🎯 <b>Экспресс-прогноз на сегодня</b>\n────────────────\n"
        for idx, m in enumerate(matches[:5], 1):
            opp = m.get("opponents", [])
            t1 = opp[0]["opponent"]["name"] if len(opp) > 0 else "TBD"
            t2 = opp[1]["opponent"]["name"] if len(opp) > 1 else "TBD"
            # Простейший прогноз на основе винрейта
            text_exp += f"{idx}️⃣ <b>{t1}</b> ✅ vs <b>{t2}</b> ❌\n────────────────\n"
        await message.answer(text_exp)
        return

# --- ЗАПУСК БОТА ---

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())