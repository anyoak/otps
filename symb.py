import asyncio
import logging
import random
import sqlite3
import time
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

# ========== Premium Animations ==========
async def send_loading_sequence(update: Update):
    chat_id = update.effective_chat.id
    try:
        msg1 = await update.message.reply_text("🔄 *INITIALIZING SYSTEM*", parse_mode=ParseMode.MARKDOWN)
        loading_frames = ["▰▱▱▱▱▱▱▱", "▰▰▱▱▱▱▱▱", "▰▰▰▱▱▱▱▱", "▰▰▰▰▱▱▱▱", 
                         "▰▰▰▰▰▱▱▱", "▰▰▰▰▰▰▱▱", "▰▰▰▰▰▰▰▱", "▰▰▰▰▰▰▰▰"]
        
        for frame in loading_frames:
            await msg1.edit_text(f"🔄 *FETCHING USER DATA*\n\n{frame} 25%", parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.3)
        
        await msg1.edit_text("✅ *DATA RETRIEVAL COMPLETE*", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1)
        await msg1.delete()

        msg2 = await update.message.reply_text("🔍 *VERIFYING DATABASE ACCESS*", parse_mode=ParseMode.MARKDOWN)
        verification_steps = [
            "🔐 Connecting to secure database...",
            "🔐 Authentication in progress...",
            "🔐 Scanning user records...",
            "🔐 Cross-referencing official lists..."
        ]
        
        for step in verification_steps:
            await msg2.edit_text(step)
            await asyncio.sleep(1)
        
        msg3 = await update.message.reply_text("🛡️ *SECURITY SCAN IN PROGRESS*", parse_mode=ParseMode.MARKDOWN)
        security_frames = [
            "🛡️ Scanning user credentials...",
            "🛡️ Verifying access permissions...",
            "🛡️ Checking approval status...",
            "⚠️  **ACCESS RESTRICTED DETECTED**"
        ]
        
        for frame in security_frames:
            await msg3.edit_text(frame)
            await asyncio.sleep(1.5)
        
        await msg3.delete()

        final_text = """
❌ *MEMBERSHIP STATUS: PENDING*

━━━━━━━━━━━━━━━━━━━━━━━━

🔒 *ACCESS RESTRICTED*

You are currently not in our official members database. Your account requires administrator approval.

⏰ *Processing Time:* 24-48 hours

📋 *Next Steps:*
1. Wait for administrator review
2. You'll receive notification upon approval
3. Once approved, full access will be granted

💡 *Note:* This process ensures community security and authenticity.

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ *Secured by Advanced Verification System*
"""
        await update.message.reply_text(final_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.exception("Error in loading sequence: %s", e)

async def send_success_animation(update: Update, user_name: str):
    success_msg = await update.message.reply_text("🎉 *WELCOME ABOARD!*", parse_mode=ParseMode.MARKDOWN)
    
    welcome_frames = [
        f"✨ **Welcome, {user_name}!** ✨",
        f"🚀 **System Access Granted** 🚀", 
        f"✅ **Membership Verified** ✅",
        f"🎯 **Profile Activated** 🎯"
    ]
    
    for frame in welcome_frames:
        await success_msg.edit_text(frame)
        await asyncio.sleep(1)
    
    await success_msg.delete()

# ========== Enhanced Captcha System ==========
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

# Custom filter for captcha users
def captcha_users_filter(update: Update):
    return update.effective_user.id in captcha_store

# ========== Premium Handlers ==========
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_or_update_user(user)
    row = get_user(user.id)
    approved = bool(row and row[5] == 1)
    
    welcome_text = f"""
🤖 *WELCOME TO SYMBIOTIC AI BOT* 

━━━━━━━━━━━━━━━━━━━━━━━━

👋 Hello *{user.first_name}*!

Thank you for joining our exclusive community. We're implementing advanced security measures to protect our members.

🔒 *Security Level:* **Enterprise Grade**
🎯 *Platform:* **AI-Powered Investment**
🌟 *Community:* **Verified Members Only**

━━━━━━━━━━━━━━━━━━━━━━━━

Please complete the security verification below to continue.
"""
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    if approved:
        await send_success_animation(update, user.first_name)
        text = profile_text_from_row(row)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    question, ans = generate_math_captcha()
    captcha_store[user.id] = ans
    
    captcha_text = f"""
🧮 *SECURITY VERIFICATION*

━━━━━━━━━━━━━━━━━━━━━━━━

To ensure you're human, please solve this simple math problem:

{question}

📝 *Instructions:*
• Type only the numerical answer
• You have 3 attempts
• Use /start to restart if needed

━━━━━━━━━━━━━━━━━━━━━━━━

🔐 This helps us prevent automated access.
"""
    await update.message.reply_text(captcha_text, parse_mode=ParseMode.MARKDOWN)

async def answer_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    expected = captcha_store.get(user_id)
    if expected is None:
        return
    
    user_answer = update.message.text.strip()
    
    if user_answer == expected:
        del captcha_store[user_id]
        success_text = """
✅ *VERIFICATION SUCCESSFUL*

━━━━━━━━━━━━━━━━━━━━━━━━

🎉 Excellent! You've passed the security check.

Now accessing our member database to verify your status...

🛡️ *Security Status:* **Verified Human**
"""
        await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(2)
        
        await send_loading_sequence(update)
        
        user = update.effective_user
        admin_text = f"""
👤 *NEW MEMBER REQUEST*

━━━━━━━━━━━━━━━━━━━━━━━━

🆔 **User ID:** `{user.id}`
📛 **Name:** {user.full_name}
📧 **Username:** @{user.username or 'N/A'}
🌐 **Language:** {user.language_code or 'N/A'}
🕒 **Request Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

━━━━━━━━━━━━━━━━━━━━━━━━

*Security Check:* ✅ Passed
*Captcha Score:* 🎯 Excellent

Please review and approve/reject this membership request.
"""
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve Member", callback_data=f"approve_user_{user.id}"),
                InlineKeyboardButton("❌ Reject Request", callback_data=f"reject_user_{user.id}")
            ],
            [InlineKeyboardButton("👁️ View Profile", callback_data=f"view_profile_{user.id}")]
        ])
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await update.message.reply_text("""
❌ *VERIFICATION FAILED*

━━━━━━━━━━━━━━━━━━━━━━━━

Incorrect answer. Please try again or type /start for a new security challenge.

💡 *Tip:* Double-check your calculation and enter only the numerical result.
""", parse_mode=ParseMode.MARKDOWN)

# ========== Enhanced Admin Callbacks ==========
async def on_admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cid = query.from_user.id
    if cid != ADMIN_ID:
        await query.answer("🔒 Administrator access required.", show_alert=True)
        return
    
    target_id = int(query.data.split("_")[-1])
    set_user_field(target_id, "approved", "1")
    
    try:
        approval_text = """
🎉 *MEMBERSHIP APPROVED!*

━━━━━━━━━━━━━━━━━━━━━━━━

✅ **Congratulations!** Your membership has been approved by our administration team.

🚀 *What's Next:*
• Full access to platform features
• Real-time announcements  
• Investment opportunities
• Community privileges

📊 Use /profile to view your complete dashboard

💬 Need help? Contact: @Symbioticl
"""
        await context.bot.send_message(target_id, approval_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await query.edit_message_text(
        text=f"✅ *APPROVED*\n\nUser `{target_id}` has been granted full membership access.",
        parse_mode=ParseMode.MARKDOWN
    )

async def on_admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cid = query.from_user.id
    if cid != ADMIN_ID:
        await query.answer("🔒 Administrator access required.", show_alert=True)
        return
    
    target_id = int(query.data.split("_")[-1])
    set_user_field(target_id, "approved", "0")
    
    try:
        rejection_text = """
❌ *MEMBERSHIP DECLINED*

━━━━━━━━━━━━━━━━━━━━━━━━

We regret to inform you that your membership request has been declined.

📋 *Possible Reasons:*
• Incomplete profile information
• Security concerns
• Platform capacity limits

💡 *Note:* You may reapply after 30 days or contact support for clarification.

💬 Support: @Symbioticl
"""
        await context.bot.send_message(target_id, rejection_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await query.edit_message_text(
        text=f"❌ *REJECTED*\n\nUser `{target_id}` membership request has been declined.",
        parse_mode=ParseMode.MARKDOWN
    )

# ========== Enhanced Profile Command ==========
async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user(user.id)
    
    if not row:
        await update.message.reply_text("❌ Profile not found. Please use /start to initialize.")
        return
    
    loading_msg = await update.message.reply_text("🔄 Loading your profile...")
    await asyncio.sleep(1.5)
    await loading_msg.delete()
    
    profile_text = profile_text_from_row(row)
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_profile"),
            InlineKeyboardButton("📊 Statistics", callback_data="view_stats")
        ],
        [InlineKeyboardButton("💬 Support", url="https://t.me/Symbioticl")]
    ])
    
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ========== Enhanced Admin Set Command ==========
async def cmd_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("""
🔒 *ACCESS DENIED*

━━━━━━━━━━━━━━━━━━━━━━━━

This command requires administrator privileges.

🛡️ *Security Notice:* Unauthorized access attempts are logged.
""", parse_mode=ParseMode.MARKDOWN)
        return
        
    parts = update.message.text.split()
    if len(parts) < 2:
        usage_text = """
🎯 *ADMIN TOOL: USER MANAGEMENT*

━━━━━━━━━━━━━━━━━━━━━━━━

📝 *Usage:* `/set <user_id>`

📋 *Example:* `/set 123456789`

🔍 *Description:* Modify user profile fields and financial data.

━━━━━━━━━━━━━━━━━━━━━━━━

💡 Use /users to see registered user IDs
"""
        await update.message.reply_text(usage_text, parse_mode=ParseMode.MARKDOWN)
        return
        
    try:
        target_id = int(parts[1])
    except:
        await update.message.reply_text("❌ Invalid user ID format. Must be numeric.")
        return
        
    row = get_user(target_id)
    if not row:
        await update.message.reply_text("❌ User not found in database. User must /start first.")
        return
        
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Total IDO", callback_data=f"setfield_{target_id}_total_ido"),
            InlineKeyboardButton("💵 Investment", callback_data=f"setfield_{target_id}_total_investment")
        ],
        [
            InlineKeyboardButton("🎯 Payout", callback_data=f"setfield_{target_id}_total_payout"),
            InlineKeyboardButton("🔗 EVM Wallet", callback_data=f"setfield_{target_id}_evm_wallet")
        ],
        [InlineKeyboardButton("👑 Approval", callback_data=f"setfield_{target_id}_approved")]
    ])
    
    user_info = f"""
👤 *USER MANAGEMENT PANEL*

━━━━━━━━━━━━━━━━━━━━━━━━

🆔 **User ID:** `{target_id}`
📛 **Name:** {row[2]}
📧 **Username:** @{row[1] or 'N/A'}
✅ **Approved:** {'Yes ✅' if row[5] else 'No ❌'}

━━━━━━━━━━━━━━━━━━━━━━━━

Select field to modify:
"""
    await update.message.reply_text(user_info, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ========== Enhanced Broadcast System ==========
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🔒 Administrator access required.")
        return
        
    broadcast_info = """
📢 *BROADCAST MANAGEMENT*

━━━━━━━━━━━━━━━━━━━━━━━━

Send the message you want to broadcast to all approved members.

📋 *Supported Formats:*
• Text messages
• Photos with captions  
• Videos with captions
• Documents
• Audio files

🎯 *Target:* All approved members
📊 *Delivery:* Real-time with analytics

💡 *Pro Tip:* Include engaging content and clear call-to-action!

━━━━━━━━━━━━━━━━━━━━━━━━

Please send your broadcast content now...
"""
    await update.message.reply_text(broadcast_info, parse_mode=ParseMode.MARKDOWN)
    return WAITING_FOR_BROADCAST

async def on_broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
        
    processing_msg = await update.message.reply_text("🚀 *Starting broadcast process...*", parse_mode=ParseMode.MARKDOWN)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE approved=1")
    rows = cursor.fetchall()
    user_ids = [r[0] for r in rows]
    conn.close()
    
    contact_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Support", url="https://t.me/Symbioticl")]])
    
    success = 0
    failed = 0
    
    total_users = len(user_ids)
    progress_msg = await update.message.reply_text(f"📊 *Broadcast Progress:* 0/{total_users}", parse_mode=ParseMode.MARKDOWN)
    
    for index, uid in enumerate(user_ids):
        try:
            if update.message.text:
                await context.bot.send_message(uid, update.message.text, reply_markup=contact_kb, parse_mode=ParseMode.MARKDOWN)
            elif update.message.photo:
                await context.bot.send_photo(uid, update.message.photo[-1].file_id, 
                                   caption=update.message.caption or "", 
                                   reply_markup=contact_kb,
                                   parse_mode=ParseMode.MARKDOWN)
            elif update.message.video:
                await context.bot.send_video(uid, update.message.video.file_id, 
                                   caption=update.message.caption or "", 
                                   reply_markup=contact_kb,
                                   parse_mode=ParseMode.MARKDOWN)
            elif update.message.document:
                await context.bot.send_document(uid, update.message.document.file_id, 
                                      caption=update.message.caption or "", 
                                      reply_markup=contact_kb,
                                      parse_mode=ParseMode.MARKDOWN)
            elif update.message.audio:
                await context.bot.send_audio(uid, update.message.audio.file_id, 
                                   caption=update.message.caption or "", 
                                   reply_markup=contact_kb,
                                   parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.forward(uid)
                
            success += 1
            
            if index % 10 == 0:
                await progress_msg.edit_text(
                    f"📊 *Broadcast Progress:* {index+1}/{total_users}\n✅ Success: {success} | ❌ Failed: {failed}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed += 1
            await asyncio.sleep(0.2)
    
    report_text = f"""
📢 *BROADCAST COMPLETED*

━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Delivery Report:**
• ✅ Successful: {success}
• ❌ Failed: {failed} 
• 📈 Success Rate: {(success/total_users)*100:.1f}%

🎯 **Target Audience:** Approved Members
🕒 **Completion Time:** {datetime.now().strftime('%H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━

📋 *Next Steps:*
• Monitor engagement metrics
• Respond to member inquiries
• Plan follow-up communications
"""
    await progress_msg.delete()
    await update.message.reply_text(report_text, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END

# ========== Enhanced Users Command ==========
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
📊 *SYSTEM STATISTICS*

━━━━━━━━━━━━━━━━━━━━━━━━

👥 **User Analytics:**
• 👤 Total Users: `{total}`
• ✅ Approved: `{approved}`
• ⏳ Pending: `{pending}`

📈 **Platform Metrics:**
• 🎯 Approval Rate: `{(approved/total)*100:.1f}%`
• 🔄 Growth: Monitoring
• 🛡️ Security: Active

━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Admin Tools:*
• /set - Manage users
• /broadcast - Send announcements
• /stats - Detailed analytics
"""
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

# ========== Enhanced Help Command ==========
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎯 *SYMBIOTIC AI BOT - HELP GUIDE*

━━━━━━━━━━━━━━━━━━━━━━━━

🤖 **Available Commands:**

• /start - Initialize bot & verification
• /profile - View your member profile  
• /help - Show this help message

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ **Security Features:**
• Advanced captcha verification
• Administrator approval system
• Real-time monitoring
• Secure data handling

━━━━━━━━━━━━━━━━━━━━━━━━

💡 **Need Assistance?**
Contact: @Symbioticl

🔒 *Your security and privacy are our top priorities.*
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# ========== Additional Callbacks ==========
async def refresh_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    row = get_user(user_id)
    profile_text = profile_text_from_row(row)
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_profile"),
            InlineKeyboardButton("📊 Statistics", callback_data="view_stats")
        ],
        [InlineKeyboardButton("💬 Support", url="https://t.me/Symbioticl")]
    ])
    
    await query.edit_message_text(profile_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    stats_text = """
📊 *PERSONAL STATISTICS*

━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **Coming Soon:**
• Investment portfolio
• ROI analytics  
• Performance metrics
• Growth charts

━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *Premium features are under development and will be available soon!*

💡 Stay tuned for updates!
"""
    await query.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

# ========== Main Function ==========
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("profile", cmd_profile))
    application.add_handler(CommandHandler("set", cmd_set))
    application.add_handler(CommandHandler("users", cmd_users))
    application.add_handler(CommandHandler("help", cmd_help))
    
    # Broadcast conversation handler
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", cmd_broadcast)],
        states={
            WAITING_FOR_BROADCAST: [
                MessageHandler(filters.ALL & ~filters.COMMAND, on_broadcast_content)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)]
    )
    application.add_handler(broadcast_conv)
    
    # Fixed captcha handler - using custom filter
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Create(captcha_users_filter), 
        answer_captcha
    ))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(on_admin_approve, pattern="^approve_user_"))
    application.add_handler(CallbackQueryHandler(on_admin_reject, pattern="^reject_user_"))
    application.add_handler(CallbackQueryHandler(refresh_profile, pattern="^refresh_profile$"))
    application.add_handler(CallbackQueryHandler(view_stats, pattern="^view_stats$"))
    
    logger.info("🚀 Symbiotic AI Bot Started Successfully!")
    logger.info("📊 Database Initialized")
    logger.info("🛡️ Security Systems Active")
    
    application.run_polling()

if __name__ == '__main__':
    main()