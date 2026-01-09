import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, Text
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = "YOUR_BOT_TOKEN_HERE"
MATCHES_API = "https://example.com/api/matches"  # Ссылка на JSON с матчами

# --- Инициализация бота ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- Главное меню ---
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🎮 CS2"), KeyboardButton("🛡 Dota 2")],
        [KeyboardButton("📊 Аналитика"), KeyboardButton("🎲 Экспресс")],
    ],
    resize_keyboard=True
)

# --- Получение матчей через API ---
async def fetch_matches(game):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{MATCHES_API}?game={game}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("matches", [])
                else:
                    return []
        except Exception as e:
            print("Ошибка при получении матчей:", e)
            return []

# --- Генерация кнопок для матчей ---
def generate_match_buttons(matches):
    keyboard = InlineKeyboardMarkup(row_width=1)
    for match in matches:
        keyboard.add(
            InlineKeyboardButton(
                text=f"{match['team1']} VS {match['team2']} - {match['time']}",
                callback_data=f"match_{match['id']}"
            )
        )
    return keyboard

# --- Команда /start ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Выбери игру или функцию:", reply_markup=main_menu)

# --- Обработка кнопок главного меню ---
@dp.message(Text(equals="🎮 CS2"))
async def cs2_menu(message: types.Message):
    matches = await fetch_matches("cs2")
    if matches:
        await message.answer("Список предстоящих матчей CS2:", reply_markup=generate_match_buttons(matches))
    else:
        await message.answer("Сейчас нет предстоящих матчей CS2.")

@dp.message(Text(equals="🛡 Dota 2"))
async def dota_menu(message: types.Message):
    matches = await fetch_matches("dota2")
    if matches:
        await message.answer("Список предстоящих матчей Dota 2:", reply_markup=generate_match_buttons(matches))
    else:
        await message.answer("Сейчас нет предстоящих матчей Dota 2.")

@dp.message(Text(equals="📊 Аналитика"))
async def analytics(message: types.Message):
    text = (
        "📊 Аналитика матчей:\n"
        "Team Alpha - победа в 60% последних матчей\n"
        "Team Beta - победа в 45% последних матчей\n"
        "Рекомендуется: CS2 Экспресс с Team Alpha!"
    )
    await message.answer(text)

@dp.message(Text(equals="🎲 Экспресс"))
async def express(message: types.Message):
    text = (
        "🎲 Экспресс на сегодня:\n"
        "1. Team Alpha ✅\n"
        "2. Team Gamma ❌\n"
        "Общая ставка: 2 события"
    )
    await message.answer(text)

# --- Обработка нажатий Inline кнопок ---
@dp.callback_query(lambda c: c.data and c.data.startswith("match_"))
async def process_match(callback_query: types.CallbackQuery):
    match_id = int(callback_query.data.split("_")[1])
    matches_cs2 = await fetch_matches("cs2")
    matches_dota = await fetch_matches("dota2")
    all_matches = matches_cs2 + matches_dota
    match = next((m for m in all_matches if m["id"] == match_id), None)

    if match:
        text = (
            f"Информация о матче:\n"
            f"{match['team1']} VS {match['team2']}\n"
            f"Время: {match['time']}\n"
            f"Статистика:\n"
            f"{match.get('stats', 'Нет данных')}"
        )
        await callback_query.message.answer(text)
        await callback_query.answer()  # Убираем "часики" на кнопке
    else:
        await callback_query.answer("Матч не найден", show_alert=True)

# --- Запуск бота ---
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))