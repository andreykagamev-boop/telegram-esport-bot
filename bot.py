import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
user_game = {}

# ---------- HTTP SERVER (ДЛЯ RENDER) ----------

async def healthcheck(request):
    return web.Response(text="OK")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# ---------- КЛАВИАТУРЫ ----------

game_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🎮 CS2", callback_data="game_cs2"),
        InlineKeyboardButton(text="🛡 Dota 2", callback_data="game_dota2")
    ]
])

menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📅 Матчи", callback_data="matches"),
        InlineKeyboardButton(text="📊 Аналитика", callback_data="analytics")
    ],
    [
        InlineKeyboardButton(text="🎯 Экспресс", callback_data="express")
    ]
])

# ---------- API ----------

async def api_get(url):
    headers = {"Authorization": f"Bearer {PANDASCORE_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                return []
            return await r.json()

async def upcoming_matches(game):
    return await api_get(f"https://api.pandascore.io/{game}/matches/upcoming?per_page=5")

async def team_history(game, team_id):
    return await api_get(
        f"https://api.pandascore.io/{game}/matches?filter[opponent_id]={team_id}&per_page=5"
    )

def winrate(matches, team_id):
    if not matches:
        return 50
    wins = sum(1 for m in matches if m.get("winner") and m["winner"]["id"] == team_id)
    return int(wins / len(matches) * 100)

# ---------- START ----------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("👋 <b>Esport Bot</b>\n\nВыбери игру:", reply_markup=game_kb)

# ---------- CALLBACKS ----------

@dp.callback_query(F.data.startswith("game_"))
async def choose_game(call: types.CallbackQuery):
    user_game[call.from_user.id] = call.data.replace("game_", "")
    await call.message.edit_text("✅ Игра выбрана", reply_markup=menu_kb)
    await call.answer()

@dp.callback_query(F.data == "matches")
async def matches(call: types.CallbackQuery):
    game = user_game.get(call.from_user.id)
    if not game:
        return await call.answer("Выбери игру", show_alert=True)

    for m in await upcoming_matches(game):
        opp = m.get("opponents", [])
        if len(opp) < 2:
            continue
        await call.message.answer(
            f"🆚 <b>{opp[0]['opponent']['name']} vs {opp[1]['opponent']['name']}</b>\n"
            f"🏆 {m.get('tournament', {}).get('name','—')}"
        )
    await call.answer()

@dp.callback_query(F.data == "analytics")
async def analytics(call: types.CallbackQuery):
    game = user_game.get(call.from_user.id)
    if not game:
        return await call.answer("Выбери игру", show_alert=True)

    m = (await upcoming_matches(game))[0]
    team = m["opponents"][0]["opponent"]
    wr = winrate(await team_history(game, team["id"]), team["id"])

    bars = "🟩" * (wr // 10) + "🟥" * (10 - wr // 10)
    await call.message.answer(
        f"📊 <b>{team['name']}</b>\nВинрейт: {wr}%\n{bars}"
    )
    await call.answer()

@dp.callback_query(F.data == "express")
async def express(call: types.CallbackQuery):
    game = user_game.get(call.from_user.id)
    if not game:
        return await call.answer("Выбери игру", show_alert=True)

    text = "🎯 <b>Экспресс</b>\n"
    for m in await upcoming_matches(game):
        opp = m.get("opponents", [])
        if len(opp) < 2:
            continue
        t1, t2 = opp[0]["opponent"], opp[1]["opponent"]
        wr1 = winrate(await team_history(game, t1["id"]), t1["id"])
        wr2 = winrate(await team_history(game, t2["id"]), t2["id"])
        fav = t1["name"] if wr1 >= wr2 else t2["name"]
        text += f"\n<b>{t1['name']} vs {t2['name']}</b>\nПрогноз: {fav}"
    await call.message.answer(text)
    await call.answer()

# ---------- RUN ----------

async def main():
    await start_webserver()      # 👈 ВАЖНО
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())