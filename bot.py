import os
import sqlite3
import random
import time
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

DB = "game.db"
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set.")


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        coins INTEGER NOT NULL DEFAULT 10000,
        bank INTEGER NOT NULL DEFAULT 0,
        level INTEGER NOT NULL DEFAULT 1,
        pet TEXT,
        pet_level INTEGER NOT NULL DEFAULT 1,
        spouse_id INTEGER,
        insurance_until INTEGER NOT NULL DEFAULT 0,
        last_hop INTEGER NOT NULL DEFAULT 0,
        last_bank_rob INTEGER NOT NULL DEFAULT 0,
        last_date INTEGER NOT NULL DEFAULT 0,
        last_daily INTEGER NOT NULL DEFAULT 0,
        last_trade INTEGER NOT NULL DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS businesses (
        user_id INTEGER,
        business TEXT,
        quantity INTEGER NOT NULL DEFAULT 1,
        stored_income INTEGER NOT NULL DEFAULT 0,
        last_update INTEGER NOT NULL,
        PRIMARY KEY (user_id, business)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cars (
        user_id INTEGER,
        car TEXT,
        PRIMARY KEY (user_id, car)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item TEXT,
        price INTEGER,
        quantity INTEGER NOT NULL DEFAULT 1
    )
    """)

    con.commit()
    con.close()


def ensure_user(tg_user):
    con = db()
    cur = con.cursor()
    row = cur.execute(
        "SELECT * FROM users WHERE user_id = ?", (tg_user.id,)
    ).fetchone()

    if row is None:
        count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        start_money = 1_000_000_000 if count == 0 else 10_000
        cur.execute(
            """INSERT INTO users
            (user_id, username, first_name, coins)
            VALUES (?, ?, ?, ?)""",
            (tg_user.id, tg_user.username or "", tg_user.first_name or "کاربر", start_money),
        )
    else:
        cur.execute(
            "UPDATE users SET username=?, first_name=? WHERE user_id=?",
            (tg_user.username or "", tg_user.first_name or "کاربر", tg_user.id),
        )

    con.commit()
    con.close()


def get_user(user_id):
    con = db()
    row = con.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row


def fmt(n):
    return f"{int(n):,}"


def cooldown_text(last, seconds):
    left = seconds - (int(time.time()) - int(last))
    if left <= 0:
        return None
    m, s = divmod(left, 60)
    if m:
        return f"{m} دقیقه و {s} ثانیه"
    return f"{s} ثانیه"


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 پروفایل", callback_data="profile"),
         InlineKeyboardButton("🛒 فروشگاه", callback_data="shop")],
        [InlineKeyboardButton("🏠 کسب درآمد", callback_data="business"),
         InlineKeyboardButton("🏦 بانک", callback_data="bank")],
        [InlineKeyboardButton("📈 ترید", callback_data="trade"),
         InlineKeyboardButton("🏁 ماشین‌ها", callback_data="cars")],
        [InlineKeyboardButton("💱 صرافی رمزارز", callback_data="crypto"),
         InlineKeyboardButton("📦 انبار", callback_data="inventory")],
        [InlineKeyboardButton("🕶️ بازار سیاه", callback_data="black"),
         InlineKeyboardButton("🕸️ دارک وب", callback_data="dark")],
        [InlineKeyboardButton("🏳️ کلن", callback_data="clan"),
         InlineKeyboardButton("❓ راهنما", callback_data="help")],
    ])


def profile_text(user_id):
    u = get_user(user_id)
    spouse = "ندارد"
    if u["spouse_id"]:
        s = get_user(u["spouse_id"])
        spouse = s["first_name"] if s else "ندارد"

    car_count = 0
    con = db()
    car_count = con.execute(
        "SELECT COUNT(*) FROM cars WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    con.close()

    return (
        f"👤 {u['first_name']}\n\n"
        f"💰 موجودی: {fmt(u['coins'])}\n"
        f"🏦 بانک: {fmt(u['bank'])}\n"
        f"🏷️ سطح: {u['level']}\n"
        f"🚗 ماشین: {car_count}\n"
        f"💍 همسر: {spouse}\n"
        f"🐾 پت: {u['pet'] or 'ندارد'}\n"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    await update.message.reply_text(
        f"👋 سلام {update.effective_user.first_name}\n\n"
        "🎮 به بازی خوش اومدی!\n"
        "از منوی زیر شروع کن:",
        reply_markup=main_keyboard(),
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ensure_user(q.from_user)
    uid = q.from_user.id

    if q.data == "profile":
        await q.message.reply_text(profile_text(uid))

    elif q.data == "shop":
        await q.message.reply_text(
            "🛒 فروشگاه\n\n"
            "🐺 گرگ — 100,000\n"
            "🐯 ببر — 250,000\n\n"
            "برای خرید:\n"
            "پت گرگ\n"
            "پت ببر"
        )

    elif q.data == "business":
        lines = ["🏠 کسب درآمد\n"]
        for name, price, income in BUSINESSES:
            lines.append(
                f"🏠 {name}\n"
                f"💵 قیمت: {fmt(price)}\n"
                f"📈 درآمد هر ۵ دقیقه: {fmt(income)}\n"
            )
        lines.append("برای خرید: خرید کسب و کار [نام]")
        lines.append("برای دریافت درآمد: برداشت درآمد")
        await q.message.reply_text("\n".join(lines))

    elif q.data == "bank":
        await q.message.reply_text(
            "🏦 بانک\n\n"
            "سپرده 1000\n"
            "برداشت 1000\n"
            "بیمه بانک\n"
            "دزدی از بانک\n\n"
            "بیمه بانک: 3,200 سکه برای ۷ روز"
        )

    elif q.data == "trade":
        await q.message.reply_text(
            "📈 ترید\n\n"
            "با دستور زیر ترید کن:\n"
            "ترید 10000\n\n"
            "⏱️ هر ۵ دقیقه یک بار\n"
            "📊 نتیجه تصادفی بین ۳۰٪ ضرر تا ۵۰٪ سود"
        )

    elif q.data == "cars":
        await q.message.reply_text(
            "🏁 ماشین‌ها\n\n" +
            "\n".join(f"🚗 {n} — {fmt(p)}" for n, p in CARS) +
            "\n\nخرید: خرید ماشین [نام]\nمشاهده: ماشین های من"
        )

    elif q.data == "crypto":
        await q.message.reply_text(
            "💱 صرافی رمزارز\n\n"
            "🌊 OceanCoin: 12,500\n"
            "🖤 DarkCoin: 28,000\n"
            "🔥 FireCoin: 7,800\n\n"
            "قیمت‌ها نمونه بازی هستند."
        )

    elif q.data == "inventory":
        await show_inventory(q.message, uid)

    elif q.data == "black":
        await q.message.reply_text(
            "🕶️ بازار سیاه\n\n" +
            "\n".join(f"{i+1}. {n} — {fmt(p)}" for i, (n, p) in enumerate(BLACK_ITEMS)) +
            "\n\nخرید: خرید آیتم [نام]"
        )

    elif q.data == "dark":
        await q.message.reply_text(
            "🕸️ دارک وب\n\n"
            "این بخش فقط یک فضای کاملاً خیالی داخل بازی است.\n"
            "فعلاً قابلیت فعال دیگری ندارد."
        )

    elif q.data == "clan":
        await q.message.reply_text("🏳️ کلن\n\nاین بخش هنوز فعال نشده.")

    elif q.data == "help":
        await q.message.reply_text(
            "❓ راهنما\n\n"
            "/start — شروع بازی\n"
            "هاپ — +20 سکه، هر ۱۰ دقیقه\n"
            "روزانه — جایزه روزانه\n"
            "انتقال 1000 — با ریپلای به یک نفر\n"
            "ازدواج — با ریپلای\n"
            "طلاق — با ریپلای به همسر\n"
            "قرار — با ریپلای به همسر\n"
            "سپرده / برداشت — بانک\n"
            "دزدی از بانک — سرقت خیالی بانک\n"
            "ماشین های من — ماشین‌ها\n"
            "برداشت درآمد — درآمد کسب‌وکارها"
        )


BUSINESSES = [
    ("سوپرمارکت", 200_000, 8_000),
    ("رستوران", 400_000, 16_000),
    ("نانوایی", 700_000, 28_000),
    ("مزرعه آرد", 1_200_000, 48_000),
    ("کارخانه", 1_800_000, 74_000),
    ("جنده‌خونه", 2_500_000, 105_000),
    ("معدن آهن", 3_500_000, 150_000),
    ("مزرعه تریاک", 5_000_000, 220_000),
    ("فلافلی", 7_000_000, 300_000),
    ("اکبر جوجه", 13_000_000, 420_000),
]

CARS = [
    ("پراید", 80_000),
    ("پژو 206", 250_000),
    ("سمند", 400_000),
    ("شاهین", 800_000),
    ("BMW", 2_500_000),
    ("مرسدس بنز", 4_000_000),
    ("فراری", 10_000_000),
    ("بوگاتی", 30_000_000),
]

BLACK_ITEMS = [
    ("🔩 دریل گاوصندوق", 5_000), ("🪖 کلاه ایمنی", 6_000),
    ("💸 جعل‌کننده کارت", 6_000), ("🧪 اکسیر شفا", 6_000),
    ("🧪 اکسیر قدرت", 8_000), ("📷 مسدودکننده دوربین", 8_000),
    ("🏍️ خودروی فرار", 10_000), ("🔫 کلت", 10_000),
    ("🧪 معجون قدرت", 10_000), ("💣 بمب دستی", 12_000),
    ("⚔️ شمشیر آهنی", 12_000), ("🦺 جلیقه ضدگلوله", 16_000),
    ("📿 طلسم شانس", 20_000), ("⚔️ شمشیر", 20_000),
    ("🛡️ زره آهنی", 24_000), ("🏹 کمان بلند", 28_000),
    ("🧪 معجون نامرئی", 30_000), ("🔫 تپانچه کوچک", 32_000),
    ("🪓 تبر جنگی", 36_000), ("💍 حلقه طلا", 36_000),
    ("🐺 گرگ وحشی", 40_000), ("🔫 تفنگ کلاسیک", 48_000),
    ("🔨 پتک آهنی", 52_000), ("💎 الماس خام", 60_000),
    ("🛡️ زره سنگین", 60_000), ("🕶️ دستگاه جاسوسی", 72_000),
    ("🎯 تفنگ تک‌تیرانداز", 80_000), ("💣 بمب C4", 80_000),
    ("💻 ابزار هک", 100_000), ("⚔️ شمشیر الماسی", 100_000),
    ("🛡️ سپر روئین", 120_000), ("🚀 پدافند موشکی", 120_000),
    ("🐺 گرگ سیاه", 120_000), ("⚔️ کاتانا", 140_000),
    ("🛡️ نگهبان", 150_000), ("💎 شمشیر الماسی", 160_000),
    ("🦅 عقاب طلایی", 180_000), ("🛡️ زره تیتانیوم", 200_000),
    ("🔑 کلید گاوصندوق", 200_000), ("🛡️ زره طلایی", 320_000),
    ("🔭 تفنگ لیزری", 360_000), ("⚡ شمشیر صاعقه", 480_000),
    ("🐯 ببر سفید", 520_000), ("🎯 اسنایپر", 600_000),
    ("👑 تاج پادشاهی", 800_000), ("⚔️ شمشیر افسانه‌ای", 800_000),
    ("💥 RPG", 1_000_000), ("🐉 زره اژدها", 1_200_000),
    ("🐉 اژدها", 1_200_000), ("👁️ طلسم بدشانسی", 2_000_000),
    ("🛡️ بادیگارد شخصی", 2_000_000), ("👑 تاج پادشاهی", 2_000_000),
    ("👨‍💻 هکر اخلاقی", 3_200_000), ("🚀 موشک کوچک", 7_000_000),
    ("🚀 موشک متوسط", 10_000_000), ("🚀 موشک قاره‌پیما", 15_000_000),
]


async def show_inventory(message, uid):
    con = db()
    rows = con.execute(
        "SELECT item, quantity FROM inventory WHERE user_id=? ORDER BY item",
        (uid,),
    ).fetchall()
    con.close()

    if not rows:
        await message.reply_text("📦 انبارت خالیه.")
        return

    text = "📦 انبار:\n\n" + "\n".join(
        f"{r['item']} × {r['quantity']}" for r in rows
    )
    await message.reply_text(text)


async def hop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    u = get_user(uid)
    left = cooldown_text(u["last_hop"], 600)
    if left:
        await update.message.reply_text(f"⏳ هنوز {left} مونده.")
        return

    con = db()
    con.execute(
        "UPDATE users SET coins=coins+20,last_hop=? WHERE user_id=?",
        (int(time.time()), uid),
    )
    con.commit()
    con.close()
    await update.message.reply_text("🐇 هاپ! +20 سکه")


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    u = get_user(uid)
    left = cooldown_text(u["last_daily"], 86400)
    if left:
        await update.message.reply_text(f"⏳ جایزه روزانه هنوز آماده نیست: {left}")
        return

    reward = random.randint(3000, 7000)
    con = db()
    con.execute(
        "UPDATE users SET coins=coins+?,last_daily=? WHERE user_id=?",
        (reward, int(time.time()), uid),
    )
    con.commit()
    con.close()
    await update.message.reply_text(f"🎁 جایزه روزانه: +{fmt(reward)} سکه")


async def bank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    text = (update.message.text or "").strip()
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "🏦 نمونه:\nسپرده 1000\nبرداشت 1000\nبیمه بانک"
        )
        return

    action = parts[0]
    if action in ("بیمه", "بیمه بانک"):
        return

    try:
        amount = int(parts[1].replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ مبلغ نامعتبره.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشه.")
        return

    uid = update.effective_user.id
    con = db()
    u = con.execute("SELECT coins,bank FROM users WHERE user_id=?", (uid,)).fetchone()

    if action == "سپرده":
        if u["coins"] < amount:
            con.close()
            await update.message.reply_text("❌ موجودی کافی نیست.")
            return
        con.execute(
            "UPDATE users SET coins=coins-?,bank=bank+? WHERE user_id=?",
            (amount, amount, uid),
        )
        msg = f"🏦 {fmt(amount)} سکه به بانک سپرده شد."

    elif action == "برداشت":
        if u["bank"] < amount:
            con.close()
            await update.message.reply_text("❌ موجودی بانک کافی نیست.")
            return
        con.execute(
            "UPDATE users SET coins=coins+?,bank=bank-? WHERE user_id=?",
            (amount, amount, uid),
        )
        msg = f"💰 {fmt(amount)} سکه از بانک برداشت شد."

    else:
        con.close()
        return

    con.commit()
    con.close()
    await update.message.reply_text(msg)


async def insurance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    now = int(time.time())
    con = db()
    u = con.execute("SELECT coins FROM users WHERE user_id=?", (uid,)).fetchone()
    if u["coins"] < 3200:
        con.close()
        await update.message.reply_text("❌ برای بیمه 3,200 سکه لازم داری.")
        return
    con.execute(
        "UPDATE users SET coins=coins-3200,insurance_until=? WHERE user_id=?",
        (now + 7 * 86400, uid),
    )
    con.commit()
    con.close()
    await update.message.reply_text("🛡️ بیمه بانک برای ۷ روز فعال شد.")


async def bank_rob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    u = get_user(uid)
    left = cooldown_text(u["last_bank_rob"], 1200)
    if left:
        await update.message.reply_text(f"⏳ دزدی بعدی: {left}")
        return

    now = int(time.time())
    con = db()
    con.execute("UPDATE users SET last_bank_rob=? WHERE user_id=?", (now, uid))
    con.commit()

    if u["insurance_until"] > now:
        con.close()
        await update.message.reply_text("🛡️ بیمه فعاله؛ دزدی خنثی شد و جایزه‌ای نگرفتی.")
        return

    if random.random() < 0.5:
        reward = random.randint(3460, 7000)
        while reward % 10 == 0:
            reward = random.randint(3460, 7000)
        con.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (reward, uid))
        con.commit()
        con.close()
        await update.message.reply_text(f"💰 دزدی موفق بود!\n+{fmt(reward)} سکه")
    else:
        con.close()
        await update.message.reply_text("🚨 گیر افتادی! دزدی ناموفق بود.")


def target_from_reply(update):
    if not update.message.reply_to_message:
        return None
    return update.message.reply_to_message.from_user


async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    target = target_from_reply(update)
    if not target:
        await update.message.reply_text("❌ باید روی پیام شخص موردنظر ریپلای کنی.\nمثال: انتقال 1000")
        return

    if target.id == update.effective_user.id:
        await update.message.reply_text("❌ نمی‌تونی به خودت انتقال بدی.")
        return

    parts = (update.message.text or "").split()
    if len(parts) != 2:
        await update.message.reply_text("❌ مثال درست: انتقال 1000")
        return

    try:
        amount = int(parts[1].replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ مبلغ نامعتبره.")
        return

    if amount < 100 or amount > 1_000_000_000:
        await update.message.reply_text("❌ مبلغ انتقال باید بین 100 تا 1,000,000,000 باشه.")
        return

    ensure_user(target)

    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        sender = con.execute(
            "SELECT coins FROM users WHERE user_id=?", (update.effective_user.id,)
        ).fetchone()

        if sender is None or sender["coins"] < amount:
            con.rollback()
            await update.message.reply_text("❌ موجودی کافی نیست.")
            return

        con.execute(
            "UPDATE users SET coins=coins-? WHERE user_id=?",
            (amount, update.effective_user.id),
        )
        con.execute(
            "UPDATE users SET coins=coins+? WHERE user_id=?",
            (amount, target.id),
        )
        con.commit()

    except Exception:
        con.rollback()
        await update.message.reply_text("❌ هنگام انتقال خطایی رخ داد.")
        return
    finally:
        con.close()

    await update.message.reply_text(
        f"✅ انتقال با موفقیت انجام شد.\n\n"
        f"💸 مبلغ: {fmt(amount)} سکه\n"
        f"👤 گیرنده: {target.first_name}"
    )


async def marriage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    target = target_from_reply(update)
    if not target:
        await update.message.reply_text("❌ برای ازدواج باید روی پیام طرف مقابل ریپلای کنی.")
        return
    if target.id == update.effective_user.id:
        await update.message.reply_text("❌ نمی‌تونی با خودت ازدواج کنی.")
        return

    ensure_user(target)
    con = db()
    a = con.execute("SELECT spouse_id FROM users WHERE user_id=?", (update.effective_user.id,)).fetchone()
    b = con.execute("SELECT spouse_id FROM users WHERE user_id=?", (target.id,)).fetchone()

    if a["spouse_id"] or b["spouse_id"]:
        con.close()
        await update.message.reply_text("❌ یکی از شما قبلاً ازدواج کرده.")
        return

    con.execute("UPDATE users SET spouse_id=? WHERE user_id=?", (target.id, update.effective_user.id))
    con.execute("UPDATE users SET spouse_id=? WHERE user_id=?", (update.effective_user.id, target.id))
    con.commit()
    con.close()

    await update.message.reply_text(
        f"💍 {update.effective_user.first_name} و {target.first_name} با هم ازدواج کردند!"
    )


async def divorce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    target = target_from_reply(update)
    if not target:
        await update.message.reply_text("❌ باید روی پیام همسرت ریپلای کنی.")
        return

    uid = update.effective_user.id
    con = db()
    u = con.execute("SELECT spouse_id,coins FROM users WHERE user_id=?", (uid,)).fetchone()

    if u["spouse_id"] != target.id:
        con.close()
        await update.message.reply_text("❌ این شخص همسر تو نیست.")
        return
    if u["coins"] < 500:
        con.close()
        await update.message.reply_text("❌ برای طلاق 500 سکه لازم داری.")
        return

    con.execute("UPDATE users SET spouse_id=NULL,coins=coins-500 WHERE user_id=?", (uid,))
    con.execute("UPDATE users SET spouse_id=NULL,coins=coins+500 WHERE user_id=?", (target.id,))
    con.commit()
    con.close()

    await update.message.reply_text(
        f"💔 طلاق انجام شد.\n500 سکه به {target.first_name} منتقل شد."
    )


async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    target = target_from_reply(update)
    if not target:
        await update.message.reply_text("❌ باید روی پیام همسرت ریپلای کنی.")
        return

    uid = update.effective_user.id
    con = db()
    u = con.execute(
        "SELECT spouse_id,last_date FROM users WHERE user_id=?", (uid,)
    ).fetchone()

    if u["spouse_id"] != target.id:
        con.close()
        await update.message.reply_text("❌ این شخص همسر تو نیست.")
        return

    left = cooldown_text(u["last_date"], 3600)
    if left:
        con.close()
        await update.message.reply_text(f"⏳ قرار بعدی: {left}")
        return

    con.execute(
        "UPDATE users SET coins=coins+500,last_date=? WHERE user_id=?",
        (int(time.time()), uid),
    )
    con.execute(
        "UPDATE users SET coins=coins+500 WHERE user_id=?",
        (target.id,),
    )
    con.commit()
    con.close()

    await update.message.reply_text(
        f"❤️ قرار با {target.first_name} انجام شد!\n"
        "💰 هر دو نفر +500 سکه گرفتند."
    )


async def buy_pet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    text = (update.message.text or "").strip()
    pet = text.replace("پت ", "", 1).strip()
    prices = {"گرگ": 100_000, "ببر": 250_000}

    if pet not in prices:
        await update.message.reply_text("❌ پت موجود نیست. فقط: گرگ یا ببر")
        return

    uid = update.effective_user.id
    con = db()
    u = con.execute("SELECT coins,pet FROM users WHERE user_id=?", (uid,)).fetchone()
    if u["pet"]:
        con.close()
        await update.message.reply_text("❌ فقط یک پت می‌تونی داشته باشی.")
        return
    if u["coins"] < prices[pet]:
        con.close()
        await update.message.reply_text("❌ موجودی کافی نیست.")
        return

    con.execute(
        "UPDATE users SET coins=coins-?,pet=?,pet_level=1 WHERE user_id=?",
        (prices[pet], pet, uid),
    )
    con.commit()
    con.close()
    await update.message.reply_text(f"🐾 پت {pet} خریداری شد.")


def find_business(name):
    for b, price, income in BUSINESSES:
        if b == name:
            return price, income
    return None


async def buy_business(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    name = (update.message.text or "").replace("خرید کسب و کار", "", 1).strip()
    found = find_business(name)
    if not found:
        await update.message.reply_text("❌ اسم کسب‌وکار درست نیست.")
        return

    price, income = found
    uid = update.effective_user.id
    now = int(time.time())
    con = db()
    u = con.execute("SELECT coins FROM users WHERE user_id=?", (uid,)).fetchone()
    if u["coins"] < price:
        con.close()
        await update.message.reply_text("❌ موجودی کافی نیست.")
        return

    row = con.execute(
        "SELECT quantity FROM businesses WHERE user_id=? AND business=?",
        (uid, name),
    ).fetchone()

    if row:
        con.execute(
            "UPDATE businesses SET quantity=quantity+1 WHERE user_id=? AND business=?",
            (uid, name),
        )
    else:
        con.execute(
            """INSERT INTO businesses
            (user_id,business,quantity,stored_income,last_update)
            VALUES (?,?,?,?,?)""",
            (uid, name, 1, 0, now),
        )

    con.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (price, uid))
    con.commit()
    con.close()

    await update.message.reply_text(
        f"🏠 {name} خریداری شد.\n"
        f"💵 قیمت: {fmt(price)}\n"
        f"📈 درآمد هر ۵ دقیقه: {fmt(income)}"
    )


def update_business_income(con, uid, row):
    now = int(time.time())
    elapsed = max(0, now - row["last_update"])
    cycles = elapsed // 300
    if cycles <= 0:
        return row["stored_income"]

    info = find_business(row["business"])
    if not info:
        return row["stored_income"]

    income = info[1] if False else info[1]
    # info = (price, income)
    income_per_cycle = info[1]
    add = cycles * income_per_cycle * row["quantity"]

    con.execute(
        "UPDATE businesses SET stored_income=stored_income+?,last_update=? "
        "WHERE user_id=? AND business=?",
        (add, row["last_update"] + cycles * 300, uid, row["business"]),
    )
    return row["stored_income"] + add


async def withdraw_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    con = db()
    rows = con.execute(
        "SELECT * FROM businesses WHERE user_id=?", (uid,)
    ).fetchall()

    total = 0
    for row in rows:
        total += update_business_income(con, uid, row)

    con.commit()

    if total <= 0:
        con.close()
        await update.message.reply_text("📭 فعلاً درآمدی برای برداشت نداری.")
        return

    con.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (total, uid))
    con.execute("UPDATE businesses SET stored_income=0 WHERE user_id=?", (uid,))
    con.commit()
    con.close()

    await update.message.reply_text(f"💰 {fmt(total)} سکه از کسب‌وکارها برداشت شد.")


async def buy_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    name = (update.message.text or "").replace("خرید ماشین", "", 1).strip()
    price = None
    for car, p in CARS:
        if car == name:
            price = p
            break

    if price is None:
        await update.message.reply_text("❌ ماشین پیدا نشد.")
        return

    uid = update.effective_user.id
    con = db()
    exists = con.execute(
        "SELECT 1 FROM cars WHERE user_id=? AND car=?", (uid, name)
    ).fetchone()
    if exists:
        con.close()
        await update.message.reply_text("❌ این ماشین رو قبلاً خریدی.")
        return

    u = con.execute("SELECT coins FROM users WHERE user_id=?", (uid,)).fetchone()
    if u["coins"] < price:
        con.close()
        await update.message.reply_text("❌ موجودی کافی نیست.")
        return

    con.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (price, uid))
    con.execute("INSERT INTO cars(user_id,car) VALUES(?,?)", (uid, name))
    con.commit()
    con.close()

    await update.message.reply_text(f"🏁 {name} خریداری شد.")


async def my_cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    con = db()
    rows = con.execute(
        "SELECT car FROM cars WHERE user_id=? ORDER BY car", (update.effective_user.id,)
    ).fetchall()
    con.close()

    if not rows:
        await update.message.reply_text("🚗 هنوز ماشینی نداری.")
        return

    await update.message.reply_text(
        "🚗 ماشین‌های من:\n\n" + "\n".join(f"• {r['car']}" for r in rows)
    )


async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    parts = (update.message.text or "").split()
    if len(parts) != 2:
        await update.message.reply_text("❌ مثال: ترید 10000")
        return

    try:
        amount = int(parts[1].replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ مبلغ نامعتبره.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشه.")
        return

    uid = update.effective_user.id
    u = get_user(uid)
    left = cooldown_text(u["last_trade"], 300)
    if left:
        await update.message.reply_text(f"⏳ ترید بعدی: {left}")
        return

    if u["coins"] < amount:
        await update.message.reply_text("❌ موجودی کافی نیست.")
        return

    percent = random.randint(-30, 50)
    result = int(amount * (1 + percent / 100))

    con = db()
    con.execute(
        "UPDATE users SET coins=coins-?+?,last_trade=? WHERE user_id=?",
        (amount, result, int(time.time()), uid),
    )
    con.commit()
    con.close()

    if percent >= 0:
        await update.message.reply_text(
            f"📈 ترید موفق!\nسود: +{percent}%\n💰 مبلغ نهایی: {fmt(result)}"
        )
    else:
        await update.message.reply_text(
            f"📉 ترید ناموفق!\nضرر: {abs(percent)}%\n💰 مبلغ نهایی: {fmt(result)}"
        )


async def black_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    name = (update.message.text or "").replace("خرید آیتم", "", 1).strip()

    found = None
    for item, price in BLACK_ITEMS:
        if item == name:
            found = (item, price)
            break

    if not found:
        await update.message.reply_text("❌ آیتم پیدا نشد.")
        return

    item, price = found
    uid = update.effective_user.id
    con = db()
    u = con.execute("SELECT coins FROM users WHERE user_id=?", (uid,)).fetchone()
    if u["coins"] < price:
        con.close()
        await update.message.reply_text("❌ موجودی کافی نیست.")
        return

    row = con.execute(
        "SELECT id FROM inventory WHERE user_id=? AND item=? AND price=?",
        (uid, item, price),
    ).fetchone()

    if row:
        con.execute(
            "UPDATE inventory SET quantity=quantity+1 WHERE id=?", (row["id"],)
        )
    else:
        con.execute(
            "INSERT INTO inventory(user_id,item,price,quantity) VALUES(?,?,?,1)",
            (uid, item, price),
        )

    con.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (price, uid))
    con.commit()
    con.close()

    await update.message.reply_text(f"📦 {item} خریداری شد.")


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    ensure_user(update.effective_user)

    if text == "هاپ":
        await hop(update, context)
    elif text == "روزانه":
        await daily(update, context)
    elif text == "بیمه بانک":
        await insurance(update, context)
    elif text == "دزدی از بانک":
        await bank_rob(update, context)
    elif text.startswith("سپرده ") or text.startswith("برداشت "):
        await bank_command(update, context)
    elif text.startswith("انتقال "):
        await transfer(update, context)
    elif text == "ازدواج":
        await marriage(update, context)
    elif text == "طلاق":
        await divorce(update, context)
    elif text == "قرار":
        await date_command(update, context)
    elif text.startswith("پت "):
        await buy_pet(update, context)
    elif text.startswith("خرید کسب و کار "):
        await buy_business(update, context)
    elif text == "برداشت درآمد":
        await withdraw_income(update, context)
    elif text.startswith("خرید ماشین "):
        await buy_car(update, context)
    elif text == "ماشین های من":
        await my_cars(update, context)
    elif text.startswith("ترید "):
        await trade(update, context)
    elif text.startswith("خرید آیتم "):
        await black_buy(update, context)
    elif text == "پروفایل":
        await update.message.reply_text(profile_text(update.effective_user.id))
    elif text == "انبار":
        await show_inventory(update.message, update.effective_user.id)
    elif text == "راهنما":
        await update.message.reply_text(
            "❓ راهنما\n\n"
            "هاپ | روزانه | انتقال 1000 (با ریپلای)\n"
            "ازدواج | طلاق | قرار (با ریپلای)\n"
            "سپرده 1000 | برداشت 1000 | بیمه بانک\n"
            "دزدی از بانک | ترید 10000\n"
            "خرید کسب و کار [نام]\n"
            "خرید ماشین [نام]\n"
            "ماشین های من | انبار | برداشت درآمد"
        )


async def error_handler(update, context):
    print("ERROR:", context.error)


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_error_handler(error_handler)

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
