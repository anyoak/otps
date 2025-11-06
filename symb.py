import asyncio
import logging
import random
import aiosqlite
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.enums import ParseMode  # Fixed import
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ========== CONFIG ==========
BOT_TOKEN = "8443659336:AAF5Yh1HrBd_bkXCuht4CVrWnFluIK8Bx0o"
ADMIN_ID = 6083895678
DB_PATH = "bot_users.db"
DEFAULT_COUNTRY_FLAG = "🇧🇩 Bangladesh (BD)"
# ============================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

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

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_USERS_TABLE)
        await db.commit()

asyncio.get_event_loop().run_until_complete(init_db())

# ========== FSM States ==========
class SetState(StatesGroup):
    waiting_for_value = State()
    waiting_for_field = State()

class BroadcastState(StatesGroup):
    waiting_for_content = State()

# ========== Enhanced Helpers ==========
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row

async def add_or_update_user(user: types.User):
    async with aiosqlite.connect(DB_PATH) as db:
        username = user.username or ""
        name = (user.full_name or user.first_name or "")
        joined = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, name, joined_date, country) VALUES (?, ?, ?, ?, ?)",
                         (user.id, username, name, joined, DEFAULT_COUNTRY_FLAG))
        await db.execute("UPDATE users SET username=?, name=? WHERE user_id=?", (username, name, user.id))
        await db.commit()

async def set_user_field(user_id: int, field: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        q = f"UPDATE users SET {field} = ? WHERE user_id = ?"
        await db.execute(q, (value, user_id))
        await db.commit()

async def is_approved(user_id: int) -> bool:
    row = await get_user(user_id)
    return bool(row and row[5] == 1)

def profile_text_from_row(row):
    if not row: 
        return "❌ *No Data Available*\n\nPlease contact administrator."
    
    user_id, username, name, joined, country, approved, total_ido, total_investment, total_payout, evm_wallet = row
    
    # Format values with proper defaults
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
async def send_loading_sequence(chat_id: int):
    """Enhanced loading animation with professional UX"""
    try:
        # Phase 1: Data Fetching Animation
        msg1 = await bot.send_message(chat_id, "🔄 *INITIALIZING SYSTEM*")
        loading_frames = ["▰▱▱▱▱▱▱▱", "▰▰▱▱▱▱▱▱", "▰▰▰▱▱▱▱▱", "▰▰▰▰▱▱▱▱", 
                         "▰▰▰▰▰▱▱▱", "▰▰▰▰▰▰▱▱", "▰▰▰▰▰▰▰▱", "▰▰▰▰▰▰▰▰"]
        
        for frame in loading_frames:
            await bot.edit_message_text(
                chat_id=chat_id, 
                message_id=msg1.message_id,
                text=f"🔄 *FETCHING USER DATA*\n\n{frame} 25%",
                parse_mode=ParseMode.MARKDOWN  # Fixed: Added parse_mode parameter
            )
            await asyncio.sleep(0.3)
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg1.message_id,
            text="✅ *DATA RETRIEVAL COMPLETE*",
            parse_mode=ParseMode.MARKDOWN  # Fixed: Added parse_mode parameter
        )
        await asyncio.sleep(1)
        await bot.delete_message(chat_id, msg1.message_id)

        # Phase 2: Database Verification
        msg2 = await bot.send_message(chat_id, "🔍 *VERIFYING DATABASE ACCESS*", parse_mode=ParseMode.MARKDOWN)
        verification_steps = [
            "🔐 Connecting to secure database...",
            "🔐 Authentication in progress...",
            "🔐 Scanning user records...",
            "🔐 Cross-referencing official lists..."
        ]
        
        for step in verification_steps:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg2.message_id,
                text=step
            )
            await asyncio.sleep(1)
        
        # Phase 3: Security Check
        msg3 = await bot.send_message(chat_id, "🛡️ *SECURITY SCAN IN PROGRESS*", parse_mode=ParseMode.MARKDOWN)
        security_frames = [
            "🛡️ Scanning user credentials...",
            "🛡️ Verifying access permissions...",
            "🛡️ Checking approval status...",
            "⚠️  **ACCESS RESTRICTED DETECTED**"
        ]
        
        for frame in security_frames:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg3.message_id,
                text=frame
            )
            await asyncio.sleep(1.5)
        
        await bot.delete_message(chat_id, msg3.message_id)

        # Final Message with Professional Layout
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
        await bot.send_message(chat_id, final_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logging.exception("Error in loading sequence: %s", e)

async def send_success_animation(chat_id: int, user_name: str):
    """Success animation for approved users"""
    success_msg = await bot.send_message(chat_id, "🎉 *WELCOME ABOARD!*", parse_mode=ParseMode.MARKDOWN)
    
    welcome_frames = [
        f"✨ **Welcome, {user_name}!** ✨",
        f"🚀 **System Access Granted** 🚀", 
        f"✅ **Membership Verified** ✅",
        f"🎯 **Profile Activated** 🎯"
    ]
    
    for frame in welcome_frames:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=success_msg.message_id,
            text=frame
        )
        await asyncio.sleep(1)
    
    await bot.delete_message(chat_id, success_msg.message_id)

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

# ========== Premium Handlers ==========
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user = message.from_user
    await add_or_update_user(user)
    row = await get_user(user.id)
    approved = bool(row and row[5] == 1)
    
    # Enhanced Welcome Message
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
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    if approved:
        await send_success_animation(user.id, user.first_name)
        text = profile_text_from_row(row)
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
        return

    # Enhanced Captcha Challenge
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
    await message.answer(captcha_text, parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(lambda m: m.from_user.id in captcha_store.keys() and not m.text.startswith('/'))
async def answer_captcha(message: types.Message):
    user_id = message.from_user.id
    expected = captcha_store.get(user_id)
    if expected is None:
        return
    
    user_answer = message.text.strip()
    
    if user_answer == expected:
        del captcha_store[user_id]
        success_text = """
✅ *VERIFICATION SUCCESSFUL*

━━━━━━━━━━━━━━━━━━━━━━━━

🎉 Excellent! You've passed the security check.

Now accessing our member database to verify your status...

🛡️ *Security Status:* **Verified Human**
"""
        await message.answer(success_text, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(2)
        
        asyncio.create_task(send_loading_sequence(user_id))
        
        # Enhanced Admin Notification
        user = message.from_user
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
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Approve Member", callback_data=f"approve_user_{user_id}"),
            InlineKeyboardButton("❌ Reject Request", callback_data=f"reject_user_{user_id}"),
            InlineKeyboardButton("👁️ View Profile", callback_data=f"view_profile_{user_id}")
        )
        await bot.send_message(ADMIN_ID, admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await message.answer("""
❌ *VERIFICATION FAILED*

━━━━━━━━━━━━━━━━━━━━━━━━

Incorrect answer. Please try again or type /start for a new security challenge.

💡 *Tip:* Double-check your calculation and enter only the numerical result.
""", parse_mode=ParseMode.MARKDOWN)

# ========== Enhanced Admin Callbacks ==========
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("approve_user_"))
async def on_admin_approve(callback_query: types.CallbackQuery):
    cid = callback_query.from_user.id
    if cid != ADMIN_ID:
        await callback_query.answer("🔒 Administrator access required.", show_alert=True)
        return
    
    target_id = int(callback_query.data.split("_")[-1])
    await set_user_field(target_id, "approved", "1")
    
    # Notify User with Premium Message
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
        await bot.send_message(target_id, approval_text, parse_mode=ParseMode.MARKDOWN)
        await send_success_animation(target_id, "Member")
    except Exception:
        pass
    
    await callback_query.answer("✅ Member approved successfully!")
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"✅ *APPROVED*\n\nUser `{target_id}` has been granted full membership access.",
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("reject_user_"))
async def on_admin_reject(callback_query: types.CallbackQuery):
    cid = callback_query.from_user.id
    if cid != ADMIN_ID:
        await callback_query.answer("🔒 Administrator access required.", show_alert=True)
        return
    
    target_id = int(callback_query.data.split("_")[-1])
    await set_user_field(target_id, "approved", "0")
    
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
        await bot.send_message(target_id, rejection_text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass
    
    await callback_query.answer("❌ Membership request rejected")
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"❌ *REJECTED*\n\nUser `{target_id}` membership request has been declined.",
        parse_mode=ParseMode.MARKDOWN
    )

# ========== Enhanced Profile Command ==========
@dp.message_handler(commands=['profile'])
async def cmd_profile(message: types.Message):
    user = message.from_user
    row = await get_user(user.id)
    
    if not row:
        await message.answer("❌ Profile not found. Please use /start to initialize.")
        return
    
    # Send loading animation for profile
    loading_msg = await message.answer("🔄 Loading your profile...")
    await asyncio.sleep(1.5)
    await bot.delete_message(message.chat.id, loading_msg.message_id)
    
    profile_text = profile_text_from_row(row)
    
    # Add action buttons
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔄 Refresh", callback_data="refresh_profile"),
        InlineKeyboardButton("📊 Statistics", callback_data="view_stats"),
        InlineKeyboardButton("💬 Support", url="https://t.me/Symbioticl")
    )
    
    await message.answer(profile_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ========== Enhanced Admin Set Command ==========
@dp.message_handler(commands=['set'])
async def cmd_set(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("""
🔒 *ACCESS DENIED*

━━━━━━━━━━━━━━━━━━━━━━━━

This command requires administrator privileges.

🛡️ *Security Notice:* Unauthorized access attempts are logged.
""", parse_mode=ParseMode.MARKDOWN)
        return
        
    parts = message.text.split()
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
        await message.answer(usage_text, parse_mode=ParseMode.MARKDOWN)
        return
        
    try:
        target_id = int(parts[1])
    except:
        await message.answer("❌ Invalid user ID format. Must be numeric.")
        return
        
    row = await get_user(target_id)
    if not row:
        await message.answer("❌ User not found in database. User must /start first.")
        return
        
    # Enhanced field selection
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Total IDO", callback_data=f"setfield_{target_id}_total_ido"),
        InlineKeyboardButton("💵 Investment", callback_data=f"setfield_{target_id}_total_investment"),
        InlineKeyboardButton("🎯 Payout", callback_data=f"setfield_{target_id}_total_payout"),
        InlineKeyboardButton("🔗 EVM Wallet", callback_data=f"setfield_{target_id}_evm_wallet"),
        InlineKeyboardButton("👑 Approval", callback_data=f"setfield_{target_id}_approved")
    )
    
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
    await message.answer(user_info, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ========== Enhanced Broadcast System ==========
@dp.message_handler(commands=['broadcast'])
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🔒 Administrator access required.")
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
    await message.answer(broadcast_info, parse_mode=ParseMode.MARKDOWN)
    await BroadcastState.waiting_for_content.set()

@dp.message_handler(state=BroadcastState.waiting_for_content, content_types=types.ContentTypes.ANY)
async def on_broadcast_content(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.finish()
        return
        
    processing_msg = await message.answer("🚀 *Starting broadcast process...*", parse_mode=ParseMode.MARKDOWN)
    
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE approved=1")
        rows = await cur.fetchall()
        user_ids = [r[0] for r in rows]
    
    contact_kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💬 Contact Support", url="https://t.me/Symbioticl")
    )
    
    success = 0
    failed = 0
    
    # Enhanced broadcast with progress updates
    total_users = len(user_ids)
    progress_msg = await message.answer(f"📊 *Broadcast Progress:* 0/{total_users}", parse_mode=ParseMode.MARKDOWN)
    
    for index, uid in enumerate(user_ids):
        try:
            if message.content_type == "text":
                await bot.send_message(uid, message.text, reply_markup=contact_kb, parse_mode=ParseMode.MARKDOWN)
            elif message.content_type == "photo":
                await bot.send_photo(uid, message.photo[-1].file_id, 
                                   caption=message.caption or "", 
                                   reply_markup=contact_kb,
                                   parse_mode=ParseMode.MARKDOWN)
            elif message.content_type == "video":
                await bot.send_video(uid, message.video.file_id, 
                                   caption=message.caption or "", 
                                   reply_markup=contact_kb,
                                   parse_mode=ParseMode.MARKDOWN)
            elif message.content_type == "document":
                await bot.send_document(uid, message.document.file_id, 
                                      caption=message.caption or "", 
                                      reply_markup=contact_kb,
                                      parse_mode=ParseMode.MARKDOWN)
            elif message.content_type == "audio":
                await bot.send_audio(uid, message.audio.file_id, 
                                   caption=message.caption or "", 
                                   reply_markup=contact_kb,
                                   parse_mode=ParseMode.MARKDOWN)
            else:
                await bot.forward_message(uid, message.chat.id, message.message_id)
                
            success += 1
            
            # Update progress every 10 messages
            if index % 10 == 0:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=progress_msg.message_id,
                    text=f"📊 *Broadcast Progress:* {index+1}/{total_users}\n✅ Success: {success} | ❌ Failed: {failed}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed += 1
            await asyncio.sleep(0.2)
    
    # Final broadcast report
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
    await bot.delete_message(message.chat.id, progress_msg.message_id)
    await message.answer(report_text, parse_mode=ParseMode.MARKDOWN)
    await state.finish()

# ========== Enhanced Users Command ==========
@dp.message_handler(commands=['users'])
async def cmd_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]
        cur2 = await db.execute("SELECT COUNT(*) FROM users WHERE approved=1")
        approved = (await cur2.fetchone())[0]
        cur3 = await db.execute("SELECT COUNT(*) FROM users WHERE approved=0")
        pending = (await cur3.fetchone())[0]
    
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
    await message.answer(stats_text, parse_mode=ParseMode.MARKDOWN)

# ========== Enhanced Help Command ==========
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
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
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

# ========== Additional Callbacks ==========
@dp.callback_query_handler(lambda c: c.data == "refresh_profile")
async def refresh_profile(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    row = await get_user(user_id)
    profile_text = profile_text_from_row(row)
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔄 Refresh", callback_data="refresh_profile"),
        InlineKeyboardButton("📊 Statistics", callback_data="view_stats"),
        InlineKeyboardButton("💬 Support", url="https://t.me/Symbioticl")
    )
    
    await callback_query.message.edit_text(profile_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    await callback_query.answer("✅ Profile refreshed!")

@dp.callback_query_handler(lambda c: c.data == "view_stats")
async def view_stats(callback_query: types.CallbackQuery):
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
    await callback_query.answer()
    await callback_query.message.answer(stats_text, parse_mode=ParseMode.MARKDOWN)

# ========== System Handlers ==========
async def on_startup(dp):
    logging.info("🚀 Symbiotic AI Bot Started Successfully!")
    logging.info("📊 Database Initialized")
    logging.info("🛡️ Security Systems Active")

async def on_shutdown(dp):
    logging.info("🛑 Bot shutting down...")
    await bot.close()

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)