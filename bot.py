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

user_game = {}
cached_matches = {}  # кеш последних матчей для быстрого отклика

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

def format_match_text(game: str, match: dict, live=False) -> str:
    opponents = match.get("opponents", [])
    team1 = opponents[0]["opponent"]["name"] if len(opponents) > 0 else "TBD"
    team2 = opponents[1]["opponent"]["name"] if len(opponents) > 1 else "TBD"
    time_utc = match.get("begin_at")
    time_msk = format_msk_time(time_utc)
    tournament = match.get("tournament", {}).get("name", "Неизвестный турнир")
    text = (
        f"🎮 <b>{game.upper()}</b>\n"
        f"🆚 <b>{team1}</b> vs <b>{team2}</b>\n"
        f"🕒 <b>{time_msk} МСК</b>\n"
        f"🏆 <i>{tournament}</i>\n"
        f"──────────────"
    )
    if live:
        text += "\n🔥 <i>Сейчас в прямом эфире!</i>"
    return text

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

async def fetch_last_matches(game: str, team_id: int, limit: int = 5):
    url_map = {"cs2": "https://api.pandascore.co/csgo/matches", "dota2": "https://api.pandascore.co/dota2/matches"}
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    params = {"filter[opponents]": team_id, "sort": "-begin_at", "page[size]": limit}
    async with aiohttp.ClientSession() as session:
        async with session.get(url_map[game], headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

def calculate_win_rate(team_matches, team_id):
    wins = sum(1 for m in team_matches if m.get("winner") and m.get("winner").get("id") == team_id)
    total = len(team_matches) if team_matches else 1
    return int((wins / total) * 100)

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

@dp.message(Text(text=["📅 Сегодня", "⏭ Завтра", "🔴 Live"]))
async def show_matches(message: types.Message):
    user_id = message.from_user.id
    game = user_game.get(user_id)
    if not game:
        await message.answer("Сначала выбери игру 👆")
        return

    if message.text == "📅 Сегодня":
        day = datetime.utcnow().strftime("%Y-%m-%d")
    elif message.text == "⏭ Завтра":
        day = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        day = None

    await message.answer("Загружаю матчи ⏳")
    matches = await fetch_matches(game, day)
    cached_matches[game] = matches  # кешируем матчи

    if not matches:
        await message.answer("Матчей нет 😕")
        return

    for match in matches[:5]:
        live = message.text == "🔴 Live"
        text = format_match_text(game, match, live=live)
        markup = types.InlineKeyboardMarkup()
        for opp in match.get("opponents", []):
            team = opp["opponent"]
            markup.add(types.InlineKeyboardButton(text=f"📈 {team['name']}", callback_data=f"team_{team['id']}"))
        await message.answer(text, parse_mode="HTML", reply_markup=markup)

@dp.callback_query(lambda c: c.data.startswith("team_"))
async def team_analytics(call: types.CallbackQuery):
    team_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    game = user_game.get(user_id)
    if not game:
        await call.message.answer("Сначала выбери игру 👆")
        return

    last_matches = await fetch_last_matches(game, team_id)
    text = f"<b>📊 Последние матчи команды</b>\n\n"
    for m in last_matches[:5]:
        opponents = m.get("opponents", [])
        teams_text = " vs ".join([o["opponent"]["name"] for o in opponents])
        winner = m.get("winner", {}).get("name", "TBD")
        text += f"{teams_text} — Победитель: <b>{winner}</b>\n"
    await call.message.answer(text, parse_mode="HTML")

@dp.message(Text(text="📊 Аналитика"))
async def analytics(message: types.Message):
    user_id = message.from_user.id
    game = user_game.get(user_id)
    if not game:
        await message.answer("Сначала выбери игру 👆")
        return

    await message.answer("Загружаю аналитику ⏳")
    matches = cached_matches.get(game) or await fetch_matches(game)

    if not matches:
        await message.answer("Нет данных для аналитики 😕")
        return

    text = "<b>📊 Аналитика последних матчей</b>\n\n"
    for match in matches[:3]:
        opponents = match.get("opponents", [])
        if len(opponents) < 2:
            continue
        team1 = opponents[0]["opponent"]
        team2 = opponents[1]["opponent"]
        h1 = await fetch_last_matches(game, team1["id"])
        h2 = await fetch_last_matches(game, team2["id"])
        wr1 = calculate_win_rate(h1, team1["id"])
        wr2 = calculate_win_rate(h2, team2["id"])
        text += f"{team1['name']} — {wr1}% побед\n"
        text += f"{team2['name']} — {wr2}% побед\n\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Text(text="🎯 Экспресс"))
async def express(message: types.Message):
    user_id = message.from_user.id
    game = user_game.get(user_id)
    if not game:
        await message.answer("Сначала выбери игру 👆")
        return

    matches = cached_matches.get(game) or await fetch_matches(game)
    if not matches:
        await message.answer("Нет данных для экспресса 😕")
        return

    text = "<b>🎯 Возможный экспресс с вероятностями побед</b>\n\n"
    for match in matches[:5]:
        opponents = match.get("opponents", [])
        if len(opponents) < 2:
            continue
        team1 = opponents[0]["opponent"]
        team2 = opponents[1]["opponent"]
        h1 = await fetch_last_matches(game, team1["id"])
        h2 = await fetch_last_matches(game, team2["id"])
        prob1 = calculate_win_rate(h1, team1["id"])
        prob2 = calculate_win_rate(h2, team2["id"])
        winner = team1['name'] if prob1 >= prob2 else team2['name']
        text += f"{team1['name']} vs {team2['name']} — прогноз: <b>{winner}</b> ({prob1}% vs {prob2}%)\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Text(text="🔙 Назад"))
async def back_menu(message: types.Message):
    user_id = message.from_user.id
    user_game.pop(user_id, None)
    await message.answer("Главное меню:", reply_markup=main_keyboard)

# --- АВТО-ОБНОВЛЕНИЕ LIVE ---
async def live_update():
    while True:
        for game, matches in cached_matches.items():
            live_matches = [m for m in matches if m.get("status") == "running"]
            for match in live_matches:
                text = format_match_text(game, match, live=True)
                # Здесь можно отправлять всем пользователям, которые смотрят Live
        await asyncio.sleep(60)  # обновление каждые 60 секунд

# --- RUN ---
async def main():
    asyncio.create_task(live_update())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())