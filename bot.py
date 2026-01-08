import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- КЛАВИАТУРЫ ---

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 CS2"), KeyboardButton(text="🛡 Dota 2")],
        [KeyboardButton(text="📊 Аналитика")]
    ],
    resize_keyboard=True
)

game_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="⏭ Завтра")],
        [KeyboardButton(text="🔴 Live")],
        [KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def start(message):
    await message.answer(
        "Привет! Выбери игру 👇",
        reply_markup=main_keyboard
    )

@dp.message()
async def handle_menu(message):
    text = message.text

    if text == "🎮 CS2":
        await message.answer("CS2 — выбери раздел:", reply_markup=game_keyboard)

    elif text == "🛡 Dota 2":
        await message.answer("Dota 2 — выбери раздел:", reply_markup=game_keyboard)

    elif text == "📊 Аналитика":
        await message.answer("Общая аналитика появится позже 📈")

    elif text == "📅 Сегодня":
        await message.answer("Матчи на сегодня (скоро подключим данные)")

    elif text == "⏭ Завтра":
        await message.answer("Матчи на завтра (скоро подключим данные)")

    elif text == "🔴 Live":
        await message.answer("Live матчи (в разработке)")

    elif text == "🔙 Назад":
        await message.answer("Главное меню:", reply_markup=main_keyboard)

async def main():
    await asyncio.sleep(10)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())