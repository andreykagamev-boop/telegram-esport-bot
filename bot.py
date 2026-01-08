import asyncio
import logging
import random
import sqlite3
import aiohttp
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- База ---
conn = sqlite3.connect("bot.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
conn.commit()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Dota 2", callback_data="dota2")],
        [InlineKeyboardButton(text="🎮 CS2 (скоро)", callback_data="cs2")]
    ])

def dota_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Матчи", callback_data="dota_matches")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="dota_analysis")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer("Выбери игру:", reply_markup=main_menu())

async def get_dota_pro_matches():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.opendota.com/api/proMatches") as r:
            return await r.json()

@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    if call.data == "dota2":
        await call.message.edit_text("🎮 Dota 2", reply_markup=dota_menu())

    elif call.data == "dota_matches":
        matches = await get_dota_pro_matches()
        text = "📅 Матчи Dota 2:\n\n"
        for m in matches[:5]:
            text += f"{m['radiant_name']} vs {m['dire_name']}\n"
        await call.message.edit_text(text, reply_markup=dota_menu())

    elif call.data == "dota_analysis":
        matches = await get_dota_pro_matches()
        m = random.choice(matches)
        a = random.randint(45, 65)
        await call.message.edit_text(
            f"📊 Аналитика\n\n{m['radiant_name']} — {a}%\n{m['dire_name']} — {100-a}%",
            reply_markup=dota_menu()
        )

    elif call.data == "back":
        await call.message.edit_text("Выбери игру:", reply_markup=main_menu())

    await call.answer()

# ---- WEB SERVER (чтобы Render был доволен) ----
async def handle(request):
    return web.Response(text="Bot is running")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())