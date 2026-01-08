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

# Главное меню
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 CS2"), KeyboardButton(text="🛡 Dota 2")],
        [KeyboardButton(text="📊 Аналитика")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message):
    await message.answer(
        "Привет! Выбери игру 👇",
        reply_markup=main_keyboard
    )

@dp.message()
async def handle_buttons(message):
    if message.text == "🎮 CS2":
        await message.answer("CS2 — скоро здесь будут матчи 👀")
    elif message.text == "🛡 Dota 2":
        await message.answer("Dota 2 — скоро здесь будут матчи 👀")
    elif message.text == "📊 Аналитика":
        await message.answer("Аналитика появится на следующем этапе 📈")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())