import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from pandascore import PandaScore

# ================== Environment ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PANDASCORE_TOKEN = os.environ.get("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

ps = PandaScore(token=PANDASCORE_TOKEN)

# ================== Клавиатура ==================
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("Предстоящие матчи"))
main_kb.add(KeyboardButton("Прошедшие матчи"))
main_kb.add(KeyboardButton("Live счёт"))
main_kb.add(KeyboardButton("Прогноз победы"))
main_kb.add(KeyboardButton("Экспресс"))

# ================== Хендлеры ==================
@dp.message(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Привет! Я бот по киберспорту. Выберите действие:", reply_markup=main_kb)

@dp.message()
async def main_menu(msg: types.Message):
    if msg.text == "Предстоящие матчи":
        await upcoming_matches(msg)
    elif msg.text == "Прошедшие матчи":
        await past_matches(msg)
    elif msg.text == "Live счёт":
        await live_score(msg)
    elif msg.text == "Прогноз победы":
        await match_forecast(msg)
    elif msg.text == "Экспресс":
        await express_forecast(msg)

# ================== Функции ==================
async def upcoming_matches(msg):
    cs2_matches = ps.get_matches(game="cs2", status="upcoming")[:5]
    dota2_matches = ps.get_matches(game="dota2", status="upcoming")[:5]

    text = "<b>Предстоящие матчи CS2:</b>\n"
    for m in cs2_matches:
        text += f"{m['opponents'][0]['opponent']['name']} vs {m['opponents'][1]['opponent']['name']}\n"
        text += f"Начало: {m['scheduled_at']}\n\n"

    text += "<b>Предстоящие матчи Dota2:</b>\n"
    for m in dota2_matches:
        text += f"{m['opponents'][0]['opponent']['name']} vs {m['opponents'][1]['opponent']['name']}\n"
        text += f"Начало: {m['scheduled_at']}\n\n"

    await msg.answer(text)

async def past_matches(msg):
    cs2_matches = ps.get_matches(game="cs2", status="finished")[:5]
    dota2_matches = ps.get_matches(game="dota2", status="finished")[:5]

    text = "<b>Прошедшие матчи CS2:</b>\n"
    for m in cs2_matches:
        score = m.get("results", [])
        score_str = " | ".join([f"{r['score']} : {r['opponent']['name']}" for r in score]) if score else "Нет данных"
        text += f"{m['opponents'][0]['opponent']['name']} vs {m['opponents'][1]['opponent']['name']}\nСчёт: {score_str}\n\n"

    text += "<b>Прошедшие матчи Dota2:</b>\n"
    for m in dota2_matches:
        score = m.get("results", [])
        score_str = " | ".join([f"{r['score']} : {r['opponent']['name']}" for r in score]) if score else "Нет данных"
        text += f"{m['opponents'][0]['opponent']['name']} vs {m['opponents'][1]['opponent']['name']}\nСчёт: {score_str}\n\n"

    await msg.answer(text)

async def live_score(msg):
    live_cs2 = ps.get_matches(game="cs2", status="running")[:5]
    live_dota2 = ps.get_matches(game="dota2", status="running")[:5]

    text = "<b>Live CS2:</b>\n"
    for m in live_cs2:
        score = m.get("results", [])
        score_str = " | ".join([f"{r['score']} : {r['opponent']['name']}" for r in score]) if score else "Нет данных"
        text += f"{m['opponents'][0]['opponent']['name']} vs {m['opponents'][1]['opponent']['name']}\nСчёт: {score_str}\n\n"

    text += "<b>Live Dota2:</b>\n"
    for m in live_dota2:
        score = m.get("results", [])
        score_str = " | ".join([f"{r['score']} : {r['opponent']['name']}" for r in score]) if score else "Нет данных"
        # Pick/ban герои
        picks = m.get("picks_bans", [])
        picks_str = ""
        if picks:
            for pb in picks:
                picks_str += f"{pb['team']['name']} {'пикнул' if pb['pick'] else 'забанил'} {pb['hero']['name']}\n"
        text += f"{m['opponents'][0]['opponent']['name']} vs {m['opponents'][1]['opponent']['name']}\nСчёт: {score_str}\n{picks_str}\n"

    await msg.answer(text)

async def match_forecast(msg):
    # Пример аналитики с вероятностью победы
    text = "<b>Прогноз победы:</b>\n"
    cs2_matches = ps.get_matches(game="cs2", status="upcoming")[:3]
    dota2_matches = ps.get_matches(game="dota2", status="upcoming")[:3]

    for m in cs2_matches:
        team1, team2 = m['opponents'][0]['opponent']['name'], m['opponents'][1]['opponent']['name']
        text += f"CS2: {team1} 60% vs {team2} 40%\n"

    for m in dota2_matches:
        team1, team2 = m['opponents'][0]['opponent']['name'], m['opponents'][1]['opponent']['name']
        text += f"Dota2: {team1} 55% vs {team2} 45%\n"

    await msg.answer(text)

async def express_forecast(msg):
    text = "<b>Экспресс:</b>\n"
    cs2_matches = ps.get_matches(game="cs2", status="upcoming")[:3]
    dota2_matches = ps.get_matches(game="dota2", status="upcoming")[:3]

    for m in cs2_matches:
        text += f"CS2: {m['opponents'][0]['opponent']['name']} победит\n"
    for m in dota2_matches:
        text += f"Dota2: {m['opponents'][0]['opponent']['name']} победит\n"

    await msg.answer(text)

# ================== Запуск ==================
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))