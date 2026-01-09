import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "ВАШ_ТОКЕН_БОТА"  # <-- вставь свой токен бота

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# =======================
# Получение матчей
# =======================
async def fetch_matches(game):
    try:
        with open("matches.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return [m for m in data.get("matches", []) if m["game"] == game]
    except Exception as e:
        print("Ошибка при получении матчей:", e)
        return []

# =======================
# Форматирование матчей
# =======================
def format_match(m):
    return (
        f"🎮 <b>{m['team1']} vs {m['team2']}</b>\n"
        f"🕒 Время: {m['time']}\n"
        f"📊 Статистика: {m['stats']}\n"
        f"💡 Прогноз: {m['prediction']}"
    )

# =======================
# Кнопки матчей
# =======================
def build_matches_keyboard(matches):
    kb = InlineKeyboardBuilder()
    for m in matches:
        kb.button(
            text=f"{m['team1']} vs {m['team2']} 🏆",
            callback_data=f"match_{m['id']}"
        )
    kb.adjust(1)
    return kb.as_markup()

# =======================
# Команда /start
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🎮 CS2", callback_data="game_cs2")
    kb.button(text="🛡 Dota 2", callback_data="game_dota2")
    kb.adjust(2)
    await message.answer("Выберите игру для просмотра матчей:", reply_markup=kb.as_markup())

# =======================
# Обработка кнопок
# =======================
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    data = callback.data

    if data.startswith("game_"):
        game = data.split("_")[1]
        matches = await fetch_matches(game)
        if not matches:
            await callback.message.edit_text("❌ Нет предстоящих матчей для этой игры.")
            return
        await callback.message.edit_text(
            f"📅 Предстоящие матчи {game.upper()}:",
            reply_markup=build_matches_keyboard(matches)
        )

    elif data.startswith("match_"):
        match_id = int(data.split("_")[1])
        with open("matches.json", "r", encoding="utf-8") as f:
            data_json = json.load(f)
        match = next((m for m in data_json["matches"] if m["id"] == match_id), None)
        if match:
            await callback.message.edit_text(format_match(match), parse_mode="HTML")
        else:
            await callback.message.edit_text("❌ Матч не найден.")

# =======================
# Запуск бота
# =======================
if __name__ == "__main__":
    print("Бот запущен!")
    asyncio.run(dp.start_polling(bot))