import asyncio
import os
import logging
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, Text
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

HEADERS = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}

USER_GAMES = {}  # user_id -> "cs2" или "dota2"
CACHE = {
    "matches": {},  # game -> список матчей
    "analytics": {},  # match_id -> текст аналитики
    "notified": set()  # match_id для уведомлений
}

# ----------------- КЛАВИАТУРЫ -----------------
main_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="🎮 CS2"), types.KeyboardButton(text="🛡 Dota 2")],
        [types.KeyboardButton(text="🔥 Экспресс"), types.KeyboardButton(text="🔴 Live-матчи")]
    ],
    resize_keyboard=True
)

game_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="📅 Сегодня")],
        [types.KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# ----------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -----------------
async def fetch(url, params=None):
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=HEADERS, params=params) as r:
            if r.status != 200:
                return []
            return await r.json()


async def get_matches(game, live=False):
    key = f"{game}_{'live' if live else 'today'}"
    if key in CACHE["matches"]:
        return CACHE["matches"][key]

    today = datetime.utcnow().strftime("%Y-%m-%d")
    endpoint = "csgo" if game == "cs2" else "dota2"
    url = f"https://api.pandascore.co/{endpoint}/matches"

    params = {"filter[begin_at]": today, "sort": "begin_at", "per_page": 20}
    if live:
        params = {"filter[live]": True, "per_page": 10}

    matches = await fetch(url, params)
    CACHE["matches"][key] = matches
    return matches


def format_time(utc_time):
    if not utc_time:
        return "TBD"
    dt = datetime.fromisoformat(utc_time.replace("Z", ""))
    dt += timedelta(hours=3)  # МСК
    return dt.strftime("%H:%M")


def format_match(match):
    opponents = match.get("opponents", [])
    if len(opponents) < 2:
        return "TBD"
    t1 = opponents[0]["opponent"]["name"]
    t2 = opponents[1]["opponent"]["name"]
    time = format_time(match.get("begin_at"))
    tournament = match.get("tournament", {}).get("name", "Неизвестный турнир")
    return f"🎮 {t1} vs {t2}\n🕒 {time} МСК\n🏆 {tournament}"


# ----------------- АНАЛИТИКА -----------------
async def get_team_history(team_id, game):
    endpoint = "csgo" if game == "cs2" else "dota2"
    url = f"https://api.pandascore.co/{endpoint}/matches"
    data = await fetch(url, {"filter[opponent_id]": team_id, "per_page": 10})
    return data


def winrate(matches, team_id):
    total = wins = 0
    for m in matches:
        if not m or not m.get("winner"):
            continue
        total += 1
        if m["winner"]["id"] == team_id:
            wins += 1
    return round((wins / total) * 100, 1) if total else 0


def form(matches, team_id):
    res = ""
    for m in matches[:5]:
        if not m or not m.get("winner"):
            continue
        res += "W" if m["winner"]["id"] == team_id else "L"
    return res or "N/A"


def probability(wr1, wr2):
    return round((wr1 / (wr1 + wr2)) * 100) if wr1 + wr2 else 50


async def analytics(match, game):
    mid = match["id"]
    if mid in CACHE["analytics"]:
        return CACHE["analytics"][mid]

    t1, t2 = match["opponents"][0]["opponent"], match["opponents"][1]["opponent"]
    h1 = await get_team_history(t1["id"], game)
    h2 = await get_team_history(t2["id"], game)

    wr1, wr2 = winrate(h1, t1["id"]), winrate(h2, t2["id"])
    p1, p2 = probability(wr1, wr2), 100 - probability(wr1, wr2)
    fav = t1["name"] if p1 > p2 else t2["name"]

    text = (
        f"📊 <b>АНАЛИТИКА МАТЧА</b>\n\n"
        f"🆚 {t1['name']} vs {t2['name']}\n\n"
        f"Вероятность победы:\n"
        f"🟢 {t1['name']} — {p1}%\n"
        f"🔴 {t2['name']} — {p2}%\n\n"
        f"Форма последних матчей:\n"
        f"{t1['name']}: {form(h1, t1['id'])}\n"
        f"{t2['name']}: {form(h2, t2['id'])}\n\n"
        f"⭐ Фаворит: {fav}\n"
        f"──────────────\n"
        f"⚠️ Данные только для статистики, не гарантия исхода."
    )

    CACHE["analytics"][mid] = text
    return text


# ----------------- ЭКСПРЕСС -----------------
async def express(game):
    matches = await get_matches(game)
    picks = []
    for m in matches:
        if len(m.get("opponents", [])) < 2:
            continue
        text = await analytics(m, game)
        for line in text.splitlines():
            if "🟢" in line:
                prob = int(line.split("—")[1].replace("%", "").strip())
                if prob >= 60:
                    picks.append(line.strip())
        if len(picks) >= 3:
            break
    if not picks:
        return "❌ Нет матчей с достаточной уверенностью"
    msg = "🔥 <b>УМНЫЙ ЭКСПРЕСС</b>\n\n"
    for i, p in enumerate(picks, 1):
        msg += f"{i}️⃣ {p}\n"
    msg += "\nРиск: 🟡 Средний\nОсновано на статистике"
    return msg


# ----------------- LIVE -----------------
async def live_matches(game):
    matches = await get_matches(game, live=True)
    if not matches:
        return "❌ Live матчей нет"
    msg = "🔴 <b>LIVE МАТЧИ</b>\n\n"
    for m in matches[:5]:
        t1 = m["opponents"][0]["opponent"]["name"]
        t2 = m["opponents"][1]["opponent"]["name"]
        time = format_time(m.get("begin_at"))
        msg += f"🆚 {t1} vs {t2}\n🕒 {time} МСК\n\n"
    return msg


# ----------------- ХЭНДЛЕРЫ -----------------
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Выбери игру 👇", reply_markup=main_kb)


@dp.message(Text(text=["🎮 CS2", "🛡 Dota 2"]))
async def choose_game(m: types.Message):
    USER_GAMES[m.from_user.id] = "cs2" if "CS2" in m.text else "dota2"
    await m.answer("Выбери действие:", reply_markup=game_kb)


@dp.message(Text(text="📅 Сегодня"))
async def today(m: types.Message):
    game = USER_GAMES.get(m.from_user.id, "cs2")
    matches = await get_matches(game)
    if not matches:
        await m.answer("❌ Сегодня матчей нет")
        return
    for match in matches[:5]:
        text = format_match(match)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📊 Аналитика", callback_data=f"a_{match['id']}")]
            ]
        )
        await m.answer(text, reply_markup=kb)


@dp.callback_query(lambda c: c.data.startswith("a_"))
async def cb_analytics(cb: types.CallbackQuery):
    await cb.answer()
    mid = int(cb.data.split("_")[1])
    game = "cs2"  # предполагаем CS2, можно добавить логику для Dota
    for m_ in CACHE["matches"].get(game, []):
        if m_["id"] == mid:
            text = await analytics(m_, game)
            await cb.message.answer(text, parse_mode="HTML")
            return


@dp.message(Text(text="🔥 Экспресс"))
async def cb_express(m: types.Message):
    game = USER_GAMES.get(m.from_user.id, "cs2")
    await m.answer("Собираю экспресс ⏳")
    await m.answer(await express(game), parse_mode="HTML")


@dp.message(Text(text="🔴 Live-матчи"))
async def cb_live(m: types.Message):
    game = USER_GAMES.get(m.from_user.id, "cs2")
    await m.answer(await live_matches(game), parse_mode="HTML")


@dp.message(Text(text="🔙 Назад"))
async def cb_back(m: types.Message):
    await m.answer("Главное меню:", reply_markup=main_kb)


# ----------------- УВЕДОМЛЕНИЯ -----------------
async def notifier():
    while True:
        for game in ["cs2", "dota2"]:
            matches = await get_matches(game)
            for match in matches:
                match_id = match["id"]
                begin = match.get("begin_at")
                if not begin or match_id in CACHE["notified"]:
                    continue
                begin_dt = datetime.fromisoformat(begin.replace("Z", "")) + timedelta(hours=3)
                delta = (begin_dt - datetime.utcnow() - timedelta(hours=3)).total_seconds()
                if 0 < delta <= 900:  # за 15 минут
                    for user_id, g in USER_GAMES.items():
                        if g == game:
                            await bot.send_message(
                                user_id,
                                f"⏰ Матч начнется через 15 минут!\n{format_match(match)}"
                            )
                    CACHE["notified"].add(match_id)
        await asyncio.sleep(300)  # каждые 5 минут проверяем


# ----------------- RUN -----------------
async def main():
    asyncio.create_task(notifier())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())