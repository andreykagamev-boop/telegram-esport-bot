import os
import asyncio
import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart
from aiogram.router import Router

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")
PORT = int(os.getenv("PORT", 10000))  # Render требует порт

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ---------- KEYBOARDS ----------

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 CS2", callback_data="game_cs2")],
        [InlineKeyboardButton(text="🛡 Dota 2", callback_data="game_dota2")]
    ])

def game_kb(game):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Аналитика", callback_data=f"analytics_{game}")],
        [InlineKeyboardButton(text="🔥 Экспресс", callback_data=f"express_{game}")],
        [InlineKeyboardButton(text="📅 Матчи", callback_data=f"matches_{game}")]
    ])

# ---------- API ----------

async def upcoming_matches(game: str) -> list:
    url = "https://api.pandascore.co/matches/upcoming"
    params = {
        "filter[videogame.slug]": game,
        "sort": "begin_at",
        "per_page": 5
    }
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                return []

            try:
                data = await resp.json()
            except:
                return []

            return data if isinstance(data, list) else []

# ---------- HANDLERS ----------

@router.message(CommandStart())
async def start(msg: Message):
    await msg.answer(
        "👋 Привет! Я eSports бот\n\nВыбери игру:",
        reply_markup=main_kb()
    )

@router.callback_query(F.data.startswith("game_"))
async def choose_game(call: CallbackQuery):
    await call.answer()
    game = call.data.split("_")[1]
    await call.message.answer(
        f"🎯 {game.upper()}",
        reply_markup=game_kb(game)
    )

@router.callback_query(F.data.startswith("matches_"))
async def matches(call: CallbackQuery):
    await call.answer()
    game = call.data.split("_")[1]
    matches = await upcoming_matches(game)

    if not matches:
        await call.message.answer("❌ Матчи не найдены")
        return

    text = "📅 Ближайшие матчи:\n\n"
    for m in matches:
        opp = m.get("opponents", [])
        if len(opp) >= 2:
            text += f"🏆 {opp[0]['opponent']['name']} vs {opp[1]['opponent']['name']}\n"

    await call.message.answer(text)

@router.callback_query(F.data.startswith("analytics_"))
async def analytics(call: CallbackQuery):
    await call.answer()
    game = call.data.split("_")[1]
    matches = await upcoming_matches(game)

    if not matches:
        await call.message.answer("❌ Нет данных")
        return

    m = matches[0]
    opp = m.get("opponents", [])
    if len(opp) < 2:
        await call.message.answer("❌ Недостаточно данных")
        return

    await call.message.answer(
        f"📊 Аналитика\n\n"
        f"{opp[0]['opponent']['name']} vs {opp[1]['opponent']['name']}\n\n"
        f"📈 Форма • 💥 Карты • 🧠 Стабильность\n"
        f"⚠️ Не является финансовой рекомендацией"
    )

@router.callback_query(F.data.startswith("express_"))
async def express(call: CallbackQuery):
    await call.answer()
    game = call.data.split("_")[1]
    matches = await upcoming_matches(game)

    picks = []
    for m in matches[:3]:
        opp = m.get("opponents", [])
        if len(opp) >= 2:
            picks.append(f"✅ {opp[0]['opponent']['name']}")

    if not picks:
        await call.message.answer("❌ Экспресс недоступен")
        return

    await call.message.answer("🔥 Экспресс:\n\n" + "\n".join(picks))

# ---------- WEB SERVER (Render hack) ----------

async def handle(request):
    return web.Response(text="Bot is running")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())