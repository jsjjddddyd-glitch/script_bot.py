import os
import time
import threading
import psycopg2
import psycopg2.extras
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ChatMemberHandler,
)
from telegram.constants import ChatMemberStatus

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8609135979:AAH_owiVbiL7C6IAZ8y-DmnFgq0dhx9_N5c")
DEVELOPER_USERNAME = "c9aac"
DEVELOPER_USERNAME2 = "v_x_vc"
DEVELOPER_LINK = "https://t.me/c9aac"

SUPER_ADMINS = {DEVELOPER_USERNAME.lower(), DEVELOPER_USERNAME2.lower()}

COOLDOWN_SECONDS = 5
user_last_request = {}

GROUP_CHAT_IDS = set()


class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        pass


def run_ping_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    server.serve_forever()


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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hacks (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_chats (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL UNIQUE,
            added_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    load_group_chats()


def load_group_chats():
    global GROUP_CHAT_IDS
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM group_chats")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        GROUP_CHAT_IDS = {r[0] for r in rows}
    except Exception:
        GROUP_CHAT_IDS = set()


def save_group_chat(chat_id: int):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO group_chats (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
        GROUP_CHAT_IDS.add(chat_id)
    except Exception:
        pass


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


def delete_script_from_db(name: str) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM scripts WHERE name = %s", (name,))
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return deleted


def get_all_hacks():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, name, file_id, file_name FROM hacks ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "file_id": r["file_id"], "file_name": r["file_name"]} for r in rows]


def add_hack_to_db(name: str, file_id: str, file_name: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO hacks (name, file_id, file_name) VALUES (%s, %s, %s)", (name, file_id, file_name))
    conn.commit()
    cur.close()
    conn.close()


def delete_hack_from_db(name: str) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM hacks WHERE name = %s", (name,))
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return deleted


def build_owner_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ اضافة سكربت", callback_data="add_script"),
         InlineKeyboardButton("🗑 ازالة سكربت", callback_data="remove_script")],
        [InlineKeyboardButton("👤 اضافة مشرف", callback_data="add_admin"),
         InlineKeyboardButton("❌ ازالة مشرف", callback_data="remove_admin")],
        [InlineKeyboardButton("💀 اضافة هاك", callback_data="add_hack")],
        [InlineKeyboardButton("👨‍💻 المطور", url=DEVELOPER_LINK)],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_group_keyboard(scripts, hacks):
    keyboard = []
    row = []

    if scripts:
        keyboard.append([KeyboardButton("━━━ السكربتات ━━━")])
        for s in scripts:
            row.append(KeyboardButton(s["name"]))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            row = []

    if hacks:
        keyboard.append([KeyboardButton("━━━ الهاكات ━━━")])
        for h in hacks:
            row.append(KeyboardButton(h["name"]))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def push_keyboard_to_groups(context: ContextTypes.DEFAULT_TYPE):
    scripts = get_all_scripts()
    hacks = get_all_hacks()
    if not scripts and not hacks:
        return
    markup = build_group_keyboard(scripts, hacks)
    for chat_id in list(GROUP_CHAT_IDS):
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔄 تم تحديث القائمة:",
                reply_markup=markup
            )
        except Exception:
            pass


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
            await push_keyboard_to_groups(context)
            return

        if step == "remove_script_name":
            deleted = delete_script_from_db(text)
            context.user_data.clear()
            if deleted:
                await update.message.reply_text(f"✅ تم حذف السكربت ({text}) بنجاح!")
                await push_keyboard_to_groups(context)
            else:
                await update.message.reply_text(f"⚠️ لم يتم العثور على سكربت باسم ({text}).")
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

        if step == "add_hack_name":
            context.user_data["hack_name"] = text
            context.user_data["step"] = "add_hack_file"
            await update.message.reply_text("الآن أرسل ملف الهاك:")
            return

        if not is_admin(username):
            return


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    username = user.username or ""

    if chat.type == "private":
        step = context.user_data.get("step")

        if step == "add_hack_file":
            if not is_admin(username):
                return
            doc = update.message.document
            if not doc:
                await update.message.reply_text("⚠️ الرجاء إرسال ملف صالح.")
                return
            hack_name = context.user_data.get("hack_name", "")
            file_id = doc.file_id
            file_name = doc.file_name or hack_name
            add_hack_to_db(hack_name, file_id, file_name)
            context.user_data.clear()
            await update.message.reply_text(f"✅ تم اضافة الهاك ({hack_name}) بنجاح!")
            await push_keyboard_to_groups(context)
            return


async def button_step_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    username = user.username or ""
    await query.answer()

    data = query.data

    if not is_admin(username):
        await query.message.reply_text("ليس لديك صلاحية.")
        return

    if data == "add_script":
        context.user_data["step"] = "add_script_name"
        await query.message.reply_text("أرسل اسم السكربت:")

    elif data == "remove_script":
        context.user_data["step"] = "remove_script_name"
        await query.message.reply_text("أرسل اسم السكربت المراد حذفه:")

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

    elif data == "add_hack":
        context.user_data["step"] = "add_hack_name"
        await query.message.reply_text("أرسل اسم الهاك:")


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

            save_group_chat(chat.id)

            scripts = get_all_scripts()
            hacks = get_all_hacks()
            if scripts or hacks:
                try:
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text="مرحباً! اختر السكربت أو الهاك المطلوب:",
                        reply_markup=build_group_keyboard(scripts, hacks)
                    )
                except Exception:
                    pass


async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text or ""

    if chat.type not in ["group", "supergroup"]:
        return

    save_group_chat(chat.id)

    if text.startswith("━━━"):
        return

    user_id = user.id
    now = time.time()
    last_time = user_last_request.get(user_id, 0)
    remaining = COOLDOWN_SECONDS - (now - last_time)
    if remaining > 0:
        try:
            await update.message.reply_text(
                f"⏳ انتظر {remaining:.0f} ثواني قبل الطلب التالي.",
                reply_to_message_id=update.message.message_id
            )
        except Exception:
            pass
        return

    scripts = get_all_scripts()
    for s in scripts:
        if s["name"] == text:
            user_last_request[user_id] = now
            await update.message.reply_text(
                s["content"],
                reply_to_message_id=update.message.message_id
            )
            return

    hacks = get_all_hacks()
    for h in hacks:
        if h["name"] == text:
            user_last_request[user_id] = now
            try:
                await context.bot.send_document(
                    chat_id=chat.id,
                    document=h["file_id"],
                    caption=f"🔓 {h['name']}",
                    reply_to_message_id=update.message.message_id
                )
            except Exception as e:
                await update.message.reply_text(f"⚠️ حدث خطأ أثناء إرسال الهاك: {e}")
            return


async def send_scripts_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    username = user.username or ""

    if chat.type not in ["group", "supergroup"]:
        return

    if not is_admin(username):
        return

    scripts = get_all_scripts()
    hacks = get_all_hacks()
    if not scripts and not hacks:
        await update.message.reply_text("لا يوجد سكربتات أو هاكات مضافة بعد.")
        return

    await update.message.reply_text(
        "اختر السكربت أو الهاك المطلوب:",
        reply_markup=build_group_keyboard(scripts, hacks)
    )


def main():
    init_db()

    ping_thread = threading.Thread(target=run_ping_server, daemon=True)
    ping_thread.start()
    print(f"Ping server running on port {os.environ.get('PORT', 8080)}")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scripts", send_scripts_keyboard))
    app.add_handler(CallbackQueryHandler(button_step_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_message
    ))
    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.ChatType.PRIVATE,
        handle_document
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP) & ~filters.COMMAND,
        group_message_handler
    ))
    app.add_handler(ChatMemberHandler(new_group_member, ChatMemberHandler.MY_CHAT_MEMBER))

    print("البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
