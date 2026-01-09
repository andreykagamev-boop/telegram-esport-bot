import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
PANDASCORE_TOKEN = os.environ.get("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
user_game = {}

# Кнопки выбора игры
game_keyboard = InlineKeyboardMarkup(row_width=2)
game_keyboard.add(
    InlineKeyboardButton(text="🎮 CS2", callback_data="game_cs2"),
    InlineKeyboardButton(text="🛡 Dota 2", callback_data="game_dota")
)

def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 Аналитика", callback_data="analytics"),
        InlineKeyboardButton(text="🎯 Экспресс", callback_data="express")
    )
    return kb.as_markup()

async def fetch_matches(game):
    url = f"https://api.pandascore.io/{game}/matches/upcoming"
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                return []
            return await r.json()

async def fetch_team_matches(team_id, game, limit=5):
    if not team_id:
        return []
    url = f"https://api.pandascore.io/{game}/teams/{team_id}/matches?per_page={limit}"
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                return []
            return await r.json()

def format_match_card(match, game):
    opp = match.get("opponents", [])
    t1 = opp[0]["opponent"]["name"] if len(opp) > 0 else "TBD"
    t2 = opp[1]["opponent"]["name"] if len(opp) > 1 else "TBD"
    tournament = match.get("tournament", {}).get("name", "Неизвестный турнир")
    start_time = match.get("begin_at")
    date = datetime.fromisoformat(start_time).strftime("%d.%m %H:%M") if start_time else "TBD"
    return f"🆚 <b>{t1}</b> vs <b>{t2}</b>\n🏆 {tournament}\n📅 {date}\n────────────────"

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("Привет! Выбери игру:", reply_markup=game_keyboard)

@dp.callback_query()
async def callback_handler(query: types.CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if data.startswith("game_"):
        user_game[user_id] = data.split("_")[1]
        await query.message.edit_text(
            f"Выбрана игра: <b>{user_game[user_id].upper()}</b>",
            reply_markup=main_keyboard()
        )
        await query.answer()
        return

    game = user_game.get(user_id)
    if not game:
        await query.answer("Сначала выбери игру!", show_alert=True)
        return

    if data == "analytics":
        matches = await fetch_matches(game)
        if not matches:
            await query.message.answer("Нет матчей для аналитики 😕")
            await query.answer()
            return
        team = matches[0]["opponents"][0]["opponent"]
        past_matches = await fetch_team_matches(team["id"], game, limit=5)
        text = f"📊 <b>Аналитика: {team['name']}</b>\n────────────────\n"
        wins = 0
        for m in past_matches:
            opps = m.get("opponents", [])
            opp_name = opps[1]["opponent"]["name"] if len(opps) > 1 else "TBD"
            winner = m.get("winner")
            result = "✅ Победа" if winner and winner["id"] == team["id"] else "❌ Поражение"
            if result == "✅ Победа":
                wins += 1
            tournament = m.get("tournament", {}).get("name", "Неизвестный турнир")
            text += f"🆚 {opp_name} — {result}\n🏆 {tournament}\n"
        wr = int((wins / len(past_matches)) * 100) if past_matches else 0
        green_blocks = "🟩" * (wr // 10)
        red_blocks = "🟥" * (10 - (wr // 10))
        text += f"\nВинрейт за {len(past_matches)} матчей: {wr}%\n{green_blocks}{red_blocks}\n────────────────"
        await query.message.answer(text)
        await query.answer()
        return

    if data == "express":
        matches = await fetch_matches(game)
        if not matches:
            await query.message.answer("Нет матчей для экспресс-прогноза 😕")
            await query.answer()
            return
        text_exp = "🎯 <b>Экспресс-прогноз на сегодня</b>\n────────────────\n"
        for idx, m in enumerate(matches[:5], 1):
            card = format_match_card(m, game)
            text_exp += f"{idx}️⃣ {card}\n"
        await query.message.answer(text_exp)
        await query.answer()

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))