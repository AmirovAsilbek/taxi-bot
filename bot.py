import asyncio
import logging
import sqlite3

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

# Bot va Admin Ma'lumotlari
BOT_TOKEN = "8643693514:AAFvSzfPBXjoAmvt4ltAtlBD_zwLp63e93I"
ADMIN_ID = 8726943857

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- MA'LUMOTLAR BAZASI (SQLITE) BILAN ISHLASH ---

def init_db():
    conn = sqlite3.connect("taxi_bot.db")
    cursor = conn.cursor()
    # Haydovchilar jadvaliga olgan zakazlari sonini ham saqlaydigan ustun qo'shilgan
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            driver_id INTEGER PRIMARY KEY,
            order_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_driver_to_db(driver_id: int):
    conn = sqlite3.connect("taxi_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO drivers (driver_id, order_count) VALUES (?, 0)", (driver_id,))
    conn.commit()
    conn.close()

def remove_driver_from_db(driver_id: int):
    conn = sqlite3.connect("taxi_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM drivers WHERE driver_id = ?", (driver_id,))
    conn.commit()
    conn.close()

def get_all_drivers():
    conn = sqlite3.connect("taxi_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT driver_id, order_count FROM drivers")
    rows = cursor.fetchall()
    conn.close()
    return rows

def increment_driver_order(driver_id: int):
    conn = sqlite3.connect("taxi_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE drivers SET order_count = order_count + 1 WHERE driver_id = ?", (driver_id,))
    conn.commit()
    # Yangilangan zakazlar sonini qaytarish
    cursor.execute("SELECT order_count FROM drivers WHERE driver_id = ?", (driver_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 1

# Bazani ishga tushirish
init_db()

busy_drivers = set()
active_orders = {}

# --- ADMIN BUYRUQLARI ---

# Barcha haydovchilar va ularning zakazlar sonini ko'rish: /drivers
@dp.message(Command("drivers"))
async def list_drivers_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        drivers = get_all_drivers()
        if not drivers:
            await message.answer("Bazada hech qanday haydovchi topilmadi.")
            return
        
        text = f"🚖 **Jami haydovchilar ro'yxati:**\n\n"
        for driver_id, count in drivers:
            text += f"• ID: `{driver_id}` — **{count} ta zakaz** olgan\n"
        
        await message.answer(text, parse_mode="Markdown")

# Haydovchini bazadan o'chirish: /remove 123456789
@dp.message(Command("remove"))
async def remove_driver_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        try:
            driver_id = int(message.text.split()[1])
            remove_driver_from_db(driver_id)
            await message.answer(f"✅ Haydovchi `{driver_id}` bazadan o'chirildi.")
        except (IndexError, ValueError):
            await message.answer("⚠️ Qolip xato! Ishlatish: `/remove 123456789` shaklida ID yuboring.")

# --- START BUYRUG'I VA ASOSIY LOGIKA ---

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚖 Taksi chaqirish")],
            [KeyboardButton(text="👨‍✈️ Taksida ishlash")]
        ],
        resize_keyboard=True
    )
    await message.answer("Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=kb)

# Haydovchi sifatida ro'yxatdan o'tish/taksida ishlash
@dp.message(F.text == "👨‍✈️ Taksida ishlash")
async def register_driver(message: types.Message):
    add_driver_to_db(message.from_user.id)
    await message.answer("✅ Siz haydovchi sifatida bazaga qo'shildingiz. Yangi buyurtmalar kelganda sizga yuboriladi.")

# Buyurtma berish tugmalari uchun callback / zakaz qabul qilish logicasi
@dp.callback_query(F.data.startswith("accept_order_"))
async def accept_order_callback(call: types.CallbackQuery):
    driver_id = call.from_user.id
    # Zakazlar sonini bazada +1 ga oshirish
    count = increment_driver_order(driver_id)

    await call.message.edit_text(f"✅ Buyurtma siz tomonidan qabul qilindi!")
    
    # ADMINGA BILDIRISHNOMA YUBORISH
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚖 **Yangi buyurtma qabul qilindi!**\n\n"
                 f"👤 **Haydovchi:** {call.from_user.full_name}\n"
                 f"🆔 **ID:** `{driver_id}`\n"
                 f"📊 **Jami olgan zakazlari:** {count} ta",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xatolik: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
