import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from pandascore import PandaScore
from datetime import datetime

# ====== Environment ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

if not BOT_TOKEN or not PANDASCORE_TOKEN:
    raise RuntimeError("Нужно задать BOT_TOKEN и PANDASCORE_TOKEN в environment!")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# ====== Библиотека Pandascore ======
ps = PandaScore(PANDASCORE_TOKEN)

# ====== Клавиатура ======
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("📅 Предстоящие"))
main_kb.add(KeyboardButton("✅ Прошедшие"))
main_kb.add(KeyboardButton("🔥 Live"))
main_kb.add(KeyboardButton("🔮 Прогноз"))
main_kb.add(KeyboardButton("🎲 Экспресс"))

# ====== Хендлеры ======

@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот аналитики CS2 и Dota2 👇", reply_markup=main_kb)

@dp.message()
async def main_handler(message: types.Message):
    text = message.text.strip()

    if text == "📅 Предстоящие":
        await send_upcoming(message)
    elif text == "✅ Прошедшие":
        await send_finished(message)
    elif text == "🔥 Live":
        await send_live(message)
    elif text == "🔮 Прогноз":
        await send_forecast(message)
    elif text == "🎲 Экспресс":
        await send_express(message)
    else:
        await message.answer("Нажми одну из кнопок ниже 👇", reply_markup=main_kb)

# ====== Функции ======

async def send_upcoming(message: types.Message):
    cs2 = ps.matches(videogame_slug="cs2", filter={"status":"running,not_started"}, sort="begin_at")
    dota2 = ps.matches(videogame_slug="dota2", filter={"status":"running,not_started"}, sort="begin_at")

    text = "<b>📅 Предстоящие матчи CS2:</b>\n"
    for m in cs2[:5]:
        dt = m.get("begin_at")
        when = datetime.fromisoformat(dt.replace("Z","")).strftime("%d.%m %H:%M") if dt else "—"
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        text += f"{when} — {t1} vs {t2}\n"

    text += "\n<b>📅 Предстоящие матчи Dota2:</b>\n"
    for m in dota2[:5]:
        dt = m.get("begin_at")
        when = datetime.fromisoformat(dt.replace("Z","")).strftime("%d.%m %H:%M") if dt else "—"
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        text += f"{when} — {t1} vs {t2}\n"

    await message.answer(text)

async def send_finished(message: types.Message):
    cs2 = ps.matches(videogame_slug="cs2", filter={"status":"finished"}, sort="-begin_at")
    dota2 = ps.matches(videogame_slug="dota2", filter={"status":"finished"}, sort="-begin_at")

    text = "<b>✅ Завершённые CS2:</b>\n"
    for m in cs2[:5]:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        r = m.get("results") or []
        if len(r)>=2:
            s1,s2 = r[0]["score"], r[1]["score"]
            text += f"{t1} {s1}-{s2} {t2}\n"
        else:
            text += f"{t1} vs {t2}\n"

    text += "\n<b>✅ Завершённые Dota2:</b>\n"
    for m in dota2[:5]:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        r = m.get("results") or []
        if len(r)>=2:
            s1,s2 = r[0]["score"], r[1]["score"]
            text += f"{t1} {s1}-{s2} {t2}\n"
        else:
            text += f"{t1} vs {t2}\n"

    await message.answer(text)

async def send_live(message: types.Message):
    cs2 = ps.matches(videogame_slug="cs2", filter={"live":"true"})
    dota2 = ps.matches(videogame_slug="dota2", filter={"live":"true"})

    text = "<b>🔥 Live CS2:</b>\n"
    for m in cs2:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        r = m.get("results") or []
        if len(r)>=2:
            s1,s2 = r[0]["score"], r[1]["score"]
            text += f"{t1} {s1}-{s2} {t2}\n"
        else:
            text += f"{t1} vs {t2}\n"

    text += "\n<b>🔥 Live Dota2:</b>\n"
    for m in dota2:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        r = m.get("results") or []
        if len(r)>=2:
            s1,s2 = r[0]["score"], r[1]["score"]
            text += f"{t1} {s1}-{s2} {t2}\n"
        else:
            text += f"{t1} vs {t2}\n"

    await message.answer(text)

def simple_predict(m):
    # базовый прогноз: если есть odds
    o1 = m["opponents"][0].get("winner_odds")
    o2 = m["opponents"][1].get("winner_odds")
    if o1 and o2:
        return f"{m['opponents'][0]['opponent']['name']} {int(o1*100)}% : {int(o2*100)}% {m['opponents'][1]['opponent']['name']}"
    # иначе равный прогноз
    t1 = m["opponents"][0]["opponent"]["name"]
    t2 = m["opponents"][1]["opponent"]["name"]
    return f"{t1} ~50% : ~50% {t2}"

async def send_forecast(message: types.Message):
    cs2 = ps.matches(videogame_slug="cs2", filter={"status":"not_started"}, sort="begin_at")[:5]
    dota2 = ps.matches(videogame_slug="dota2", filter={"status":"not_started"}, sort="begin_at")[:5]

    text = "<b>🔮 Прогноз победы — CS2:</b>\n"
    for m in cs2:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        text += f"{t1} vs {t2} — {simple_predict(m)}\n"

    text += "\n<b>🔮 Прогноз победы — Dota2:</b>\n"
    for m in dota2:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        text += f"{t1} vs {t2} — {simple_predict(m)}\n"

    await message.answer(text)

async def send_express(message: types.Message):
    cs2 = ps.matches(videogame_slug="cs2", filter={"status":"not_started"}, sort="begin_at")[:3]
    dota2 = ps.matches(videogame_slug="dota2", filter={"status":"not_started"}, sort="begin_at")[:3]

    text = "<b>🎲 Экспресс-прогноз — CS2:</b>\n"
    for m in cs2:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        text += f"{t1} vs {t2} — {simple_predict(m)}\n"

    text += "\n<b>🎲 Экспресс-прогноз — Dota2:</b>\n"
    for m in dota2:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        text += f"{t1} vs {t2} — {simple_predict(m)}\n"

    await message.answer(text)