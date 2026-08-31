import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

BOT_TOKEN = "8643693514:AAFvSzfPBXjoAmvt4ltAtlBD_zwLp63e93I"
ADMIN_ID = [8726943857, 2020402]
WEBAPP_CLIENT_URL = "https://amirovasilbek.github.io/taxi-bot/index.html"
WEBAPP_DRIVER_URL = "https://amirovasilbek.github.io/taxi-bot/driver.html"
WEBAPP_ADMIN_URL = "https://amirovasilbek.github.io/taxi-bot/admin.html"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("taxi_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_main_keyboard(user_id: int):
    buttons = [
        [KeyboardButton(text="🚖 Taksi chaqirish", web_app=WebAppInfo(url=WEBAPP_CLIENT_URL))],
        [KeyboardButton(text="🚗 Haydovchi kabineti", web_app=WebAppInfo(url=WEBAPP_DRIVER_URL))]
    ]
    if user_id in ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Admin Dispetcher", web_app=WebAppInfo(url=WEBAPP_ADMIN_URL))])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user = message.from_user
    conn = sqlite3.connect("taxi_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)", (user.id, user.full_name))
    conn.commit()
    conn.close()

    text = f"Assalomu alaykum, <b>{user.first_name}</b>! Express Taxi tizimiga xush kelibsiz."
    if user.id in ADMIN_ID:
        text += "\n\n👑 <i>Siz tizim administratori sifatida tanildingiz.</i>"

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user.id))

@dp.message(Command("admin"))
async def admin_handler(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("❌ Bu bo'lim faqat admin uchun.")
        return
    await message.answer("Dispetcherlik panelini pastki menyudagi tugma orqali ochishingiz mumkin.")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
