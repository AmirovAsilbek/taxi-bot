import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = "8643693514:AAFvSzFPBXjoAmvt4ltAtlBD_zwLp63e93I"
ADMIN_ID = 8726943857

# --- MA'LUMOTLAR BAZASI (SQLITE) BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect("taxi_bot.db")
    cursor = conn.cursor()
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
    cursor.execute("SELECT order_count FROM drivers WHERE driver_id = ?", (driver_id,))
    res = cursor.fetchone()
    conn.commit()
    conn.close()
    return res[0] if res else 1

init_db()

busy_drivers = set()
active_orders = {}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class TaxiOrder(StatesGroup):
    waiting_for_phone = State()
    waiting_for_location = State()

class DriverReg(StatesGroup):
    waiting_for_id = State()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚖 Taksi chaqirish")],
        [KeyboardButton(text="👨‍✈️ Taksida ishlash")]
    ],
    resize_keyboard=True
)

phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
    ],
    resize_keyboard=True
)

location_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=main_keyboard)

# --- ADMIN BUYRUQLARI ---
@dp.message(Command("drivers"))
async def list_drivers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    drivers = get_all_drivers()
    if not drivers:
        await message.answer("Bazada hech qanday haydovchi topilmadi.")
        return
    text = "📊 **Bazasidagi haydovchilar ro'yxati:**\n\n"
    for d_id, count in drivers:
        text += f"🆔 ID: `{d_id}` | 🚖 Zakazlar: {count} ta\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("remove"))
async def remove_driver_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Xato! Buyruqni to'g'ri kiriting: `/remove ID_RAQAM`", parse_mode="Markdown")
        return
    try:
        d_id = int(args[1])
        remove_driver_from_db(d_id)
        await message.answer(f"✅ Haydovchi ID: `{d_id}` bazadan o'chirildi.", parse_mode="Markdown")
    except ValueError:
        await message.answer("ID raqam faqat sonlardan iborat bo'lishi kerak!")

# --- 1. TAKSIDA ISHLASH BO'LIMI ---
@dp.message(F.text == "👨‍✈️ Taksida ishlash")
async def driver_work(message: types.Message, state: FSMContext):
    text = (
        "👨‍✈️ **Haydovchilar bo'limi!**\n\n"
        "ID raqamingizni aniqlash uchun @userinfobot botiga kiring va u bergan **ID** raqamni nusxalab oling.\n\n"
        "So'ngra o'sha ID raqamingizni ushbu chatga yozib yuboring:"
    )
    await state.set_state(DriverReg.waiting_for_id)
    await message.answer(text, parse_mode="Markdown")

@dp.message(DriverReg.waiting_for_id)
async def process_driver_id(message: types.Message, state: FSMContext):
    driver_id_text = message.text.strip()
    user_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"

    await message.answer(
        f"✅ ID raqamingiz (`{driver_id_text}`) adminga yuborildi. Admin tasdiqlagach, buyurtmalarni qabul qilishingiz mumkin.",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )
    await state.clear()

    admin_msg = (
        "👨‍✈️ **Yangi haydovchi ariza topshirdi!**\n\n"
        f"👤 **Ismi:** {user_name}\n"
        f"🌐 **Username:** {username}\n"
        f"🆔 **Haydovchi ID:** `{driver_id_text}`"
    )
    
    add_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Bazaga qo'shish", callback_data=f"add_driver_{driver_id_text}")]
    ])

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=add_btn, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xatolik: {e}")

# --- ADMIN HAYDOVCHINI BAZAGA QO'SHGANDA ---
@dp.callback_query(F.data.startswith("add_driver_"))
async def add_driver_callback(callback: types.CallbackQuery):
    new_driver_id = int(callback.data.split("_")[2])
    drivers_list = [d[0] for d in get_all_drivers()]

    if new_driver_id not in drivers_list:
        add_driver_to_db(new_driver_id)
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ **Haydovchi bazaga saqlandi!**",
            parse_mode="Markdown"
        )
        await callback.answer("Haydovchi qo'shildi!")

        try:
            await bot.send_message(chat_id=new_driver_id, text="🎉 **Arizangiz tasdiqlandi!** Endi siz yangi buyurtmalarni qabul qilishingiz mumkin.")
        except Exception as e:
            logging.error(f"Haydovchiga bildirishnoma yuborishda xatolik: {e}")
    else:
        await callback.answer("Bu haydovchi allaqachon bazada bor!", show_alert=True)

# --- BUYURTMANI BO'SH HAYDOVCHIGA YUBORISH ---
async def send_order_to_available_driver(client_id, skip_drivers=None):
    if skip_drivers is None:
        skip_drivers = set()

    order_info = active_orders.get(client_id)
    if not order_info:
        return False

    drivers = [d[0] for d in get_all_drivers()]
    target_driver = None
    for d_id in drivers:
        if d_id not in busy_drivers and d_id not in skip_drivers:
            target_driver = d_id
            break

    if target_driver:
        order_text = (
            "🚖 **Yangi buyurtma!**\n\n"
            f"👤 **Mijoz:** {order_info['user_name']}\n"
            f"🌐 **Username:** {order_info['username']}\n"
            f"📞 **Tel:** {order_info['phone_number']}"
        )
        
        skip_str = ",".join(map(str, skip_drivers)) if skip_drivers else "none"
        action_btn = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept_{client_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{client_id}_{skip_str}")
            ]
        ])

        try:
            await bot.send_message(chat_id=target_driver, text=order_text, reply_markup=action_btn, parse_mode="Markdown")
            await bot.send_location(chat_id=target_driver, latitude=order_info['lat'], longitude=order_info['lon'])
            return True
        except Exception as e:
            logging.error(f"Haydovchiga yuborishda xatolik: {e}")
            return False
    else:
        return False

# --- 2. TAKSI CHAQIRISH BO'LIMI ---
@dp.message(F.text == "🚖 Taksi chaqirish")
async def taxi_order(message: types.Message, state: FSMContext):
    await state.set_state(TaxiOrder.waiting_for_phone)
    await message.answer("Taksi chaqirish uchun pastdagi tugmani bosib telefon raqamingizni yuboring:", reply_markup=phone_keyboard)

@dp.message(TaxiOrder.waiting_for_phone, F.contact)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(TaxiOrder.waiting_for_location)
    await message.answer("Raqamingiz qabul qilindi! Endi turgan joyingizni (lokatsiya) yuboring:", reply_markup=location_keyboard)

@dp.message(TaxiOrder.waiting_for_phone, F.text)
async def process_text_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(TaxiOrder.waiting_for_location)
    await message.answer("Raqamingiz qabul qilindi! Endi turgan joyingizni (lokatsiya) yuboring:", reply_markup=location_keyboard)

@dp.message(TaxiOrder.waiting_for_location, F.location)
async def process_location(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    client_id = message.from_user.id
    
    active_orders[client_id] = {
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas",
        "phone_number": user_data.get("phone"),
        "lat": message.location.latitude,
        "lon": message.location.longitude
    }

    sent = await send_order_to_available_driver(client_id=client_id)

    if sent:
        await message.answer("✅ Buyurtmangiz qabul qilindi! Haydovchi qidirilmoqda...", reply_markup=main_keyboard)
    else:
        await message.answer("⚠️ Hozirda barcha haydovchilar band yoki bazada haydovchi yo'q. Birozdan so'ng qayta urinib ko'ring.", reply_markup=main_keyboard)

    await state.clear()

# --- 3. BUYURTMANI QABUL QILISH ---
@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    driver_id = callback.from_user.id
    client_id = int(callback.data.split("_")[1])

    if driver_id in busy_drivers:
        await callback.answer("Siz allaqachon band holatdasiz!", show_alert=True)
        return

    busy_drivers.add(driver_id)
    count = increment_driver_order(driver_id)
    
    finish_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Manzilga yetib borildi", callback_data=f"finish_{client_id}")]
    ])

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ **Buyurtma qabul qilindi! Siz band holatdasiz.**",
        reply_markup=finish_btn,
        parse_mode="Markdown"
    )
    await callback.answer("Buyurtma qabul qilindi!")

    try:
        driver_name = callback.from_user.full_name
        await bot.send_message(
            chat_id=client_id,
            text=f"🚖 **Buyurtmangiz qabul qilindi!**\n\n👨‍✈️ Haydovchi: {driver_name}\nTez orada siz bilan bog'lanadi va yetib boradi.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Mijozga xabar yuborishda xatolik: {e}")

    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚖 **Yangi buyurtma qabul qilindi!**\n\n"
                 f"👨‍✈️ **Haydovchi:** {callback.from_user.full_name}\n"
                 f"🆔 **ID:** `{driver_id}`\n"
                 f"📊 **Jami olgan zakazlari:** {count} ta",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xatolik: {e}")

# --- 4. BUYURTMANI RAD ETISH ---
@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: types.CallbackQuery):
    driver_id = callback.from_user.id
    parts = callback.data.split("_")
    client_id = int(parts[1])
    skip_str = parts[2]
    
    skip_drivers = set()
    if skip_str != "none":
        skip_drivers = set(map(int, skip_str.split(",")))
    
    skip_drivers.add(driver_id)

    await callback.message.edit_text(callback.message.text + "\n\n❌ **Siz bu buyurtmani rad etdingiz.**", parse_mode="Markdown")
    await callback.answer("Buyurtma rad etildi.")

    sent = await send_order_to_available_driver(
        client_id=client_id,
        skip_drivers=skip_drivers
    )

    if not sent:
        try:
            await bot.send_message(chat_id=client_id, text="⚠️ Afsuski, hozirda barcha haydovchilar band yoki buyurtmani rad etishdi. Birozdan so'ng qayta urinib ko'ring.")
        except Exception as e:
            logging.error(f"Mijozga ogohlantirish yuborishda xatolik: {e}")

# --- 5. MANZILGA YETIB BORILGANDA ---
@dp.callback_query(F.data.startswith("finish_"))
async def finish_order(callback: types.CallbackQuery):
    driver_id = callback.from_user.id
    client_id = int(callback.data.split("_")[1])

    if driver_id in busy_drivers:
        busy_drivers.remove(driver_id)
    
    if client_id in active_orders:
        del active_orders[client_id]

    await callback.message.edit_text(
        callback.message.text + "\n\n🏁 **Buyurtma yakunlandi! Siz qayta bo'sh holatdasiz.**",
        parse_mode="Markdown"
    )
    await callback.answer("Siz bo'shatildingiz!")

    try:
        await bot.send_message(chat_id=client_id, text="🏁 Manzilga yetib kelindi. Xizmatimizdan foydalanganingiz uchun rahmat!")
    except Exception as e:
        logging.error(f"Mijozga xabar yuborishda xatolik: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
