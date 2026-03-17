import os
import psycopg2
import psycopg2.extras
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    ChatMemberHandler,
)
from telegram.constants import ChatMemberStatus

BOT_TOKEN = "8609135979:AAH_owiVbiL7C6IAZ8y-DmnFgq0dhx9_N5c"
DEVELOPER_USERNAME = "c9aac"
DEVELOPER_USERNAME2 = "v_x_vc"
DEVELOPER_LINK = "https://t.me/c9aac"

SUPER_ADMINS = {DEVELOPER_USERNAME.lower(), DEVELOPER_USERNAME2.lower()}

ADD_SCRIPT_NAME, ADD_SCRIPT_CONTENT = range(2)
ADD_ADMIN_USERNAME = 10
REMOVE_ADMIN_SELECT = 11


def get_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not set")
    conn = psycopg2.connect(db_url)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scripts (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            added_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def is_bot_owner(username: str) -> bool:
    if not username:
        return False
    return username.lower() in SUPER_ADMINS


def is_admin(username: str) -> bool:
    if not username:
        return False
    if username.lower() in SUPER_ADMINS:
        return True
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username FROM admins WHERE LOWER(username) = %s", (username.lower(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def get_all_admins():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username FROM admins ORDER BY added_at")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


def add_admin_to_db(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO admins (username) VALUES (%s) ON CONFLICT (username) DO NOTHING", (username.lower(),))
    conn.commit()
    cur.close()
    conn.close()


def remove_admin_from_db(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE LOWER(username) = %s", (username.lower(),))
    conn.commit()
    cur.close()
    conn.close()


def get_all_scripts():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, name, content FROM scripts ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "content": r["content"]} for r in rows]


def add_script_to_db(name: str, content: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO scripts (name, content) VALUES (%s, %s)", (name, content))
    conn.commit()
    cur.close()
    conn.close()


def get_script_content(name: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT content FROM scripts WHERE name = %s", (name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0]
    return None


def build_owner_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ اضافة سكربت", callback_data="add_script")],
        [InlineKeyboardButton("👤 اضافة مشرف", callback_data="add_admin"),
         InlineKeyboardButton("❌ ازالة مشرف", callback_data="remove_admin")],
        [InlineKeyboardButton("👨‍💻 المطور", url=DEVELOPER_LINK)],
    ]
    return InlineKeyboardMarkup(keyboard) def build_scripts_group_keyboard(scripts):
    keyboard = []
    row = []
    for i, s in enumerate(scripts):
        row.append(KeyboardButton(s["name"]))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        return

    username = user.username or ""

    if is_admin(username):
        role = "المالك" if is_bot_owner(username) else "المشرف"
        msg = (
            f"اهلا عزيزي {role} ({username}) 🎉\n"
            f"هنا يمكنك اضافه السكربتات الي تريدها\n"
            f"ولا تنسه عمك لول 🤪"
        )
        await update.message.reply_text(msg, reply_markup=build_owner_keyboard())
    else:
        keyboard = [[InlineKeyboardButton("👨‍💻 المطور", url=DEVELOPER_LINK)]]
        await update.message.reply_text(
            "ليس لديك صلاحية الوصول.\nلطلب بوت مشابه راسل المطور:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    username = user.username or ""
    text = update.message.text or ""

    if chat.type == "private":
        step = context.user_data.get("step")

        if step == "add_script_name":
            context.user_data["script_name"] = text
            context.user_data["step"] = "add_script_content"
            await update.message.reply_text("أرسل محتوى السكربت:")
            return

        if step == "add_script_content":
            script_name = context.user_data.get("script_name", "")
            add_script_to_db(script_name, text)
            context.user_data.clear()
            await update.message.reply_text(f"✅ تم اضافة السكربت ({script_name}) بنجاح!")
            return

        if step == "add_admin":
            target_username = text.lstrip("@").strip()
            if not target_username:
                await update.message.reply_text("يوزر غير صالح.")
                context.user_data.clear()
                return
            add_admin_to_db(target_username)
            context.user_data.clear()
            await update.message.reply_text(f"✅ تم رفع @{target_username} كمشرف في البوت!")
            return

        if not is_admin(username):
            return


async def button_step_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    username = user.username or ""
    await query.answer()

    if not is_admin(username):
        await query.message.reply_text("ليس لديك صلاحية.")
        return

    data = query.data

    if data == "add_script":
        context.user_data["step"] = "add_script_name"
        await query.message.reply_text("أرسل اسم السكربت:")

    elif data == "add_admin":
        if not is_bot_owner(username):
            await query.message.reply_text("هذه الصلاحية للمالك فقط.")
            return
        context.user_data["step"] = "add_admin"
        await query.message.reply_text("أرسل يوزر الشخص المراد اضافته كمشرف (بدون @):")

    elif data == "remove_admin":
        if not is_bot_owner(username):
            await query.message.reply_text("هذه الصلاحية للمالك فقط.")
            return
        admins = get_all_admins()
        if not admins:
            await query.message.reply_text("لا يوجد مشرفين لإزالتهم.")
            return
        keyboard = [[InlineKeyboardButton(f"@{a}", callback_data=f"del_admin_{a}")] for a in admins]
        await query.message.reply_text("اختر المشرف المراد إزالته:", reply_markup=InlineKeyboardMarkup(keyboard))

elif data.startswith("del_admin_"):
        if not is_bot_owner(username):
            await query.message.reply_text("هذه الصلاحية للمالك فقط.")
            return
        target = data.replace("del_admin_", "")
        remove_admin_from_db(target)
        await query.message.edit_text(f"تم إزالة @{target} من الإشراف ✅")


async def new_group_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return

    new_status = result.new_chat_member.status
    chat = result.chat
    added_by = result.from_user

    if chat.type in ["group", "supergroup", "channel"]:
        if new_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
            added_username = added_by.username or ""
            if not is_bot_owner(added_username):
                keyboard = [[InlineKeyboardButton("👨‍💻 المطور", url=DEVELOPER_LINK)]]
                try:
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text="عذراً، لا يمكن إضافتي بدون إذن المالك.\nلطلب بوت مشابه راسل المطور:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception:
                    pass
                try:
                    await context.bot.leave_chat(chat.id)
                except Exception:
                    pass
                return

        if new_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
            scripts = get_all_scripts()
            if scripts:
                try:
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text="مرحباً! اختر السكربت المطلوب:",
                        reply_markup=build_scripts_group_keyboard(scripts)
                    )
                except Exception:
                    pass


async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    text = update.message.text or ""

    if chat.type not in ["group", "supergroup"]:
        return

    scripts = get_all_scripts()
    for s in scripts:
        if s["name"] == text:
            await update.message.reply_text(
                s["content"],
                reply_to_message_id=update.message.message_id
            )
            return


def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_step_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_message
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP) & ~filters.COMMAND,
        group_message_handler
    ))
    app.add_handler(ChatMemberHandler(new_group_member, ChatMemberHandler.MY_CHAT_MEMBER))

    print("البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if name == "main":
    main()