import logging
import random
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# ========== CONFIG ==========
BOT_TOKEN = "8443659336:AAF5Yh1HrBd_bkXCuht4CVrWnFluIK8Bx0o"
ADMIN_ID = 6083895678
DB_PATH = "bot_users.db"
DEFAULT_COUNTRY_FLAG = "🇧🇩 Bangladesh (BD)"
# ============================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== DB ==========
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    joined_date TEXT,
    country TEXT,
    approved INTEGER DEFAULT 0,
    total_ido TEXT DEFAULT '0',
    total_investment TEXT DEFAULT '0',
    total_payout TEXT DEFAULT '0',
    evm_wallet TEXT DEFAULT 'Not Set'
);
"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE)
    conn.commit()
    conn.close()

init_db()

# ========== Conversation States ==========
WAITING_FOR_BROADCAST = 1

# ========== Enhanced Helpers ==========
def get_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def add_or_update_user(user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    username = user.username or ""
    name = (user.full_name or user.first_name or "")
    joined = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, name, joined_date, country) VALUES (?, ?, ?, ?, ?)",
                   (user.id, username, name, joined, DEFAULT_COUNTRY_FLAG))
    cursor.execute("UPDATE users SET username=?, name=? WHERE user_id=?", (username, name, user.id))
    conn.commit()
    conn.close()

def set_user_field(user_id: int, field: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def is_approved(user_id: int) -> bool:
    row = get_user(user_id)
    return bool(row and row[5] == 1)

def profile_text_from_row(row):
    if not row: 
        return "❌ *No Data Available*\n\nPlease contact administrator."
    
    user_id, username, name, joined, country, approved, total_ido, total_investment, total_payout, evm_wallet = row
    
    total_ido = total_ido or '0'
    total_investment = total_investment or '0' 
    total_payout = total_payout or '0'
    evm_wallet = evm_wallet or 'Not Set'
    username_display = f"@{username}" if username else "Not Set"
    
    return f"""
🎯 *PROFILE DETAILS*

┌──────────────────────────────────
│ 👤 **USER INFORMATION**
├──────────────────────────────────
│ • **ID:** `{user_id}`
│ • **Name:** {name}
│ • **Username:** {username_display}
│ • **Joined:** {joined}
│ • **Country:** {country}
├──────────────────────────────────
│ 💰 **FINANCIAL OVERVIEW**
├──────────────────────────────────
│ • **Total IDO:** ${total_ido}
│ • **Total Investment:** ${total_investment}
│ • **Total Payout:** ${total_payout}
├──────────────────────────────────
│ 🔗 **WALLET INFORMATION**
├──────────────────────────────────
│ • **EVM Wallet:** `{evm_wallet}`
└──────────────────────────────────

✅ *Status:* {'Approved ✅' if approved else 'Pending Review ⏳'}
"""

# ========== Captcha System ==========
def generate_math_captcha():
    a = random.randint(10, 50)
    b = random.randint(5, 30)
    op = random.choice(['+', '-'])
    if op == '+':
        ans = a + b
    else:
        ans = a - b
    question = f"**{a} {op} {b}** = ?"
    return question, str(ans)

captcha_store = {}

# ========== Handlers ==========
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_or_update_user(user)
    row = get_user(user.id)
    approved = bool(row and row[5] == 1)
    
    welcome_text = f"""
🤖 *WELCOME TO SYMBIOTIC AI BOT* 

━━━━━━━━━━━━━━━━━━━━━━━━

👋 Hello *{user.first_name}*!

Thank you for joining our exclusive community.

🔒 *Security Level:* **Enterprise Grade**
🎯 *Platform:* **AI-Powered Investment**
🌟 *Community:* **Verified Members Only**

━━━━━━━━━━━━━━━━━━━━━━━━

Please complete the security verification below to continue.
"""
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    if approved:
        text = profile_text_from_row(row)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    question, ans = generate_math_captcha()
    captcha_store[user.id] = ans
    
    captcha_text = f"""
🧮 *SECURITY VERIFICATION*

━━━━━━━━━━━━━━━━━━━━━━━━

To ensure you're human, please solve this math problem:

{question}

📝 *Instructions:*
• Type only the numerical answer
• You have 3 attempts
• Use /start to restart if needed

━━━━━━━━━━━━━━━━━━━━━━━━

🔐 This helps us prevent automated access.
"""
    await update.message.reply_text(captcha_text, parse_mode=ParseMode.MARKDOWN)

async def handle_captcha_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in captcha_store:
        return
    
    user_answer = update.message.text.strip()
    expected = captcha_store[user_id]
    
    if user_answer == expected:
        del captcha_store[user_id]
        success_text = """
✅ *VERIFICATION SUCCESSFUL*

━━━━━━━━━━━━━━━━━━━━━━━━

🎉 Excellent! You've passed the security check.

Your request has been sent to admin for approval.

🛡️ *Security Status:* **Verified Human**
"""
        await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        
        user = update.effective_user
        admin_text = f"""
👤 *NEW MEMBER REQUEST*

━━━━━━━━━━━━━━━━━━━━━━━━

🆔 **User ID:** `{user.id}`
📛 **Name:** {user.full_name}
📧 **Username:** @{user.username or 'N/A'}
🕒 **Request Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

━━━━━━━━━━━━━━━━━━━━━━━━

*Security Check:* ✅ Passed
*Captcha Score:* 🎯 Excellent

Please review this membership request.
"""
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
            ]
        ])
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await update.message.reply_text("""
❌ *VERIFICATION FAILED*

Incorrect answer. Please try again or use /start for a new challenge.
""", parse_mode=ParseMode.MARKDOWN)

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user(user.id)
    
    if not row:
        await update.message.reply_text("❌ Profile not found. Please use /start first.")
        return
    
    profile_text = profile_text_from_row(row)
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 *SYMBIOTIC AI BOT - HELP*

━━━━━━━━━━━━━━━━━━━━━━━━

**Available Commands:**
• /start - Start bot & verification
• /profile - View your profile  
• /help - Show this help message

━━━━━━━━━━━━━━━━━━━━━━━━

💡 **Need Help?**
Contact: @Symbioticl
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# ========== Admin Handlers ==========
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    admin_text = """
👑 *ADMIN PANEL*

━━━━━━━━━━━━━━━━━━━━━━━━

**Available Commands:**
• /users - View user statistics
• /broadcast - Send message to all users
• /set [user_id] - Modify user data

━━━━━━━━━━━━━━━━━━━━━━━━

Use the buttons below for quick actions.
"""
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 User Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 Manage Users", callback_data="admin_manage")]
    ])
    
    await update.message.reply_text(admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE approved=1")
    approved = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE approved=0")
    pending = cursor.fetchone()[0]
    conn.close()
    
    stats_text = f"""
📊 *USER STATISTICS*

━━━━━━━━━━━━━━━━━━━━━━━━

👥 **Total Users:** `{total}`
✅ **Approved:** `{approved}`
⏳ **Pending:** `{pending}`
📈 **Approval Rate:** `{(approved/total)*100:.1f}%`

━━━━━━━━━━━━━━━━━━━━━━━━

💡 Use /broadcast to send announcements
"""
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
        
    broadcast_info = """
📢 *BROADCAST MESSAGE*

━━━━━━━━━━━━━━━━━━━━━━━━

Please send the message you want to broadcast to all approved users.

You can send:
• Text messages
• Photos with captions
• Videos with captions

Type /cancel to stop.
"""
    await update.message.reply_text(broadcast_info, parse_mode=ParseMode.MARKDOWN)
    return WAITING_FOR_BROADCAST

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
        
    processing_msg = await update.message.reply_text("🔄 Starting broadcast...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE approved=1")
    rows = cursor.fetchall()
    user_ids = [r[0] for r in rows]
    conn.close()
    
    success = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            if update.message.text:
                await context.bot.send_message(user_id, update.message.text, parse_mode=ParseMode.MARKDOWN)
            elif update.message.photo:
                await context.bot.send_photo(user_id, update.message.photo[-1].file_id, 
                                           caption=update.message.caption or "",
                                           parse_mode=ParseMode.MARKDOWN)
            elif update.message.video:
                await context.bot.send_video(user_id, update.message.video.file_id,
                                           caption=update.message.caption or "",
                                           parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.forward(user_id)
            success += 1
            await asyncio.sleep(0.1)
        except Exception:
            failed += 1
    
    await processing_msg.delete()
    report_text = f"""
📢 *BROADCAST COMPLETE*

━━━━━━━━━━━━━━━━━━━━━━━━

✅ **Successful:** {success}
❌ **Failed:** {failed}
📊 **Success Rate:** {(success/(success+failed))*100:.1f}%

🎯 Sent to approved users only.
"""
    await update.message.reply_text(report_text, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END

async def cmd_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
        
    if len(context.args) < 2:
        await update.message.reply_text("""
❌ *Usage:* `/set [user_id]`

Example: `/set 123456789`
""", parse_mode=ParseMode.MARKDOWN)
        return
        
    try:
        target_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID.")
        return
        
    row = get_user(target_id)
    if not row:
        await update.message.reply_text("❌ User not found.")
        return
        
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Total IDO", callback_data=f"set_{target_id}_ido"),
            InlineKeyboardButton("💵 Investment", callback_data=f"set_{target_id}_investment")
        ],
        [
            InlineKeyboardButton("🎯 Payout", callback_data=f"set_{target_id}_payout"),
            InlineKeyboardButton("🔗 Wallet", callback_data=f"set_{target_id}_wallet")
        ],
        [InlineKeyboardButton("👑 Approval", callback_data=f"set_{target_id}_approve")]
    ])
    
    user_info = f"""
👤 *MANAGE USER*

🆔 **ID:** `{target_id}`
📛 **Name:** {row[2]}
📧 **Username:** @{row[1] or 'N/A'}
✅ **Approved:** {'Yes' if row[5] else 'No'}

Select field to modify:
"""
    await update.message.reply_text(user_info, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ========== Callback Handlers ==========
async def handle_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
        
    target_id = int(query.data.split('_')[1])
    set_user_field(target_id, "approved", "1")
    
    try:
        await context.bot.send_message(target_id, """
🎉 *MEMBERSHIP APPROVED!*

Your account has been approved by admin. You now have full access to the bot.

Use /profile to view your dashboard.
""", parse_mode=ParseMode.MARKDOWN)
    except:
        pass
        
    await query.edit_message_text(f"✅ User `{target_id}` approved successfully!", parse_mode=ParseMode.MARKDOWN)

async def handle_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
        
    target_id = int(query.data.split('_')[1])
    set_user_field(target_id, "approved", "0")
    
    try:
        await context.bot.send_message(target_id, """
❌ *MEMBERSHIP REJECTED*

Your membership request has been declined. Contact admin for more information.
""", parse_mode=ParseMode.MARKDOWN)
    except:
        pass
        
    await query.edit_message_text(f"❌ User `{target_id}` rejected.", parse_mode=ParseMode.MARKDOWN)

async def handle_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE approved=1")
    approved = cursor.fetchone()[0]
    conn.close()
    
    stats_text = f"""
📊 *REAL-TIME STATS*

👥 Total Users: `{total}`
✅ Approved: `{approved}`
⏳ Pending: `{total - approved}`
📈 Rate: `{(approved/total)*100:.1f}%`
"""
    await query.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

# ========== Main Function ==========
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("profile", cmd_profile))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("admin", cmd_admin))
    application.add_handler(CommandHandler("users", cmd_users))
    application.add_handler(CommandHandler("set", cmd_set))
    
    # Broadcast handler
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", cmd_broadcast)],
        states={
            WAITING_FOR_BROADCAST: [
                MessageHandler(filters.ALL & ~filters.COMMAND, handle_broadcast)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)]
    )
    application.add_handler(broadcast_handler)
    
    # Captcha handler - simple approach
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha_answer))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(handle_approve, pattern="^approve_"))
    application.add_handler(CallbackQueryHandler(handle_reject, pattern="^reject_"))
    application.add_handler(CallbackQueryHandler(handle_admin_stats, pattern="^admin_stats"))
    
    # Start the bot
    logger.info("🤖 Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()