import os
import logging
import sqlite3
import asyncio
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
import hashlib

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8296139143:AAGcF2eOli64uTDIFS2-1GdSrQg0btTbVq0"  # Replace with your bot token
ADMIN_ID = 7903239321  # Replace with your admin Telegram ID
LOG_CHANNEL = -1003286276499  # Replace with your log channel ID
TIMEZONE = 'Asia/Dhaka'

# Create data directory
if not os.path.exists('user_data'):
    os.makedirs('user_data')

# Initialize database
def init_db():
    try:
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                password TEXT,
                is_banned BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                suspended_until TIMESTAMP,
                login_attempts INTEGER DEFAULT 0,
                theme TEXT DEFAULT 'light'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                user_id INTEGER PRIMARY KEY,
                base TEXT,
                ltc TEXT,
                xlm_address TEXT,
                xlm_memo TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS balances (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                status TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vouchers (
                code TEXT PRIMARY KEY,
                amount REAL,
                created_by INTEGER,
                created_for INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (created_by) REFERENCES users (user_id),
                FOREIGN KEY (created_for) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                wallet_address TEXT,
                method TEXT,
                status TEXT DEFAULT 'pending',
                txid TEXT,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                withdrawal_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_database_files (
                user_id INTEGER PRIMARY KEY,
                file_path TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        conn.close()

# Database helpers
def get_db_connection():
    return sqlite3.connect('bot_database.db', check_same_thread=False)

def user_exists(user_id: int) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        return exists
    except Exception as e:
        logger.error(f"User exists check error: {e}")
        return False
    finally:
        conn.close()

def create_user(user_id: int, username: str) -> str | None:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        plain_password = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=14))
        hashed_password = hashlib.sha256(plain_password.encode()).hexdigest()
        
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, password) VALUES (?, ?, ?)", 
                       (user_id, username, hashed_password))
        cursor.execute("INSERT OR IGNORE INTO balances (user_id, balance) VALUES (?, 0)", (user_id,))
        
        conn.commit()
        return plain_password
    except Exception as e:
        logger.error(f"Create user error: {e}")
        return None
    finally:
        conn.close()

def get_user_password(user_id: int) -> str | None:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Get user password error: {e}")
        return None
    finally:
        conn.close()

def get_user_theme(user_id: int) -> str:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT theme FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 'light'
    except Exception as e:
        logger.error(f"Get user theme error: {e}")
        return 'light'
    finally:
        conn.close()

def is_user_banned(user_id: int) -> tuple[bool, datetime | None]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_banned, suspended_until FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            is_banned, suspended_until = result
            if suspended_until:
                try:
                    suspended_until_dt = datetime.fromisoformat(suspended_until)
                    if datetime.now() < suspended_until_dt:
                        return True, suspended_until_dt
                except ValueError:
                    pass
            return bool(is_banned), None
        return False, None
    except Exception as e:
        logger.error(f"Ban check error: {e}")
        return False, None
    finally:
        conn.close()

# Advanced animations
async def advanced_loading_animation(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str, duration: int = 4):
    try:
        message_source = update.callback_query.message if update.callback_query else update.message
        message = await message_source.reply_text(f"💎 {message_text}...")
        
        animations = ["💎", "✨", "🌟", "⚡", "🔥", "🚀", "🌈", "🎇"]
        stages = [
            f"🌟 Initializing {message_text.lower()}...",
            f"🔄 Processing request...",
            f"🔒 Securing connection...",
            f"✅ Finalizing..."
        ]
        
        for i in range(duration * 4):
            stage_idx = min(i // 4, len(stages) - 1)
            progress = int((i / (duration * 4)) * 100)
            bar = "█" * (progress // 10) + "─" * (10 - progress // 10)
            current_anim = animations[i % len(animations)]
            loading_text = (
                f"{current_anim} **{stages[stage_idx]}**\n"
                f"[{bar}] {progress}%"
            )
            try:
                await message.edit_text(loading_text)
                await asyncio.sleep(0.25)
            except:
                pass
        
        success_text = f"✅ **{message_text} Complete!** 🎉"
        try:
            await message.edit_text(success_text)
        except:
            pass
        return message
    except Exception as e:
        logger.error(f"Advanced loading animation error: {e}")
        return await message_source.reply_text(f"✅ **{message_text}**")

async def countdown_animation(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str, seconds: int = 5):
    try:
        message_source = update.callback_query.message if update.callback_query else update.message
        message = await message_source.reply_text(f"⏳ **{message_text}**\nCountdown: {seconds}s")
        
        emojis = ["⏳", "⌛", "🕒", "🕕", "🕘"]
        for i in range(seconds - 1, -1, -1):
            emoji = emojis[i % len(emojis)]
            countdown_text = (
                f"{emoji} **{message_text}**\n"
                f"Countdown: {i}s\n"
                f"[{('█' * (seconds - i)) + ('─' * i)}]"
            )
            try:
                await message.edit_text(countdown_text)
                await asyncio.sleep(1)
            except:
                pass
        
        try:
            await message.edit_text(f"🎉 **{message_text} Done!**")
        except:
            pass
        return message
    except Exception as e:
        logger.error(f"Countdown animation error: {e}")
        return await message_source.reply_text(f"🎉 **{message_text}**")

async def cinematic_welcome_animation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        welcome_text = (
            "✨ **Welcome to YourBase Premium** ✨\n\n"
            "Initializing your premium experience..."
        )
        message = await update.message.reply_text(welcome_text)
        
        stages = [
            "🌟 Activating secure protocols...",
            "💎 Loading premium interface...",
            "🚀 Preparing your dashboard...",
            "✅ Access granted!"
        ]
        emojis = ["🌟", "💎", "🚀", "✅"]
        
        for i, stage in enumerate(stages):
            try:
                await message.edit_text(
                    f"{emojis[i]} **Welcome to YourBase Premium** {emojis[i]}\n\n"
                    f"{stage}"
                )
                await asyncio.sleep(1.5)
            except:
                pass
        
        return message
    except Exception as e:
        logger.error(f"Cinematic welcome error: {e}")
        return await update.message.reply_text("✅ **Welcome to YourBase**")

async def feedback_animation(update: Update, context: ContextTypes.DEFAULT_TYPE, success: bool, message_text: str):
    try:
        message_source = update.callback_query.message if update.callback_query else update.message
        emoji = "✅" if success else "❌"
        animations = [emoji, "✨", emoji, "🌟"] if success else [emoji, "⚠️", emoji, "🔴"]
        
        message = await message_source.reply_text(f"{emoji} **{message_text}**")
        
        for anim in animations:
            try:
                await message.edit_text(f"{anim} **{message_text}**")
                await asyncio.sleep(0.3)
            except:
                pass
        
        final_text = f"{emoji} **{message_text}**"
        await message.edit_text(final_text)
        return message
    except Exception as e:
        logger.error(f"Feedback animation error: {e}")
        return await message_source.reply_text(f"{emoji} **{message_text}**")

async def button_transition_effect(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str):
    try:
        query = update.callback_query
        original_text = query.message.text
        animations = ["🖱️", "👆", "✅"]
        
        for anim in animations:
            transition_text = f"{anim} **{button_text} Selected**"
            try:
                await query.message.edit_text(transition_text)
                await asyncio.sleep(0.3)
            except:
                pass
        
        await query.message.edit_text(original_text)
    except Exception as e:
        logger.error(f"Button transition error: {e}")

def get_theme_emojis(user_id: int) -> dict:
    try:
        theme = get_user_theme(user_id)
        return {
            'light': {'main': '💎', 'accent': '✨', 'divider': '═', 'success': '✅', 'error': '❌'},
            'dark': {'main': '🌙', 'accent': '⚡', 'divider': '─', 'success': '✔️', 'error': '🚫'}
        }[theme]
    except:
        return {'main': '💎', 'accent': '✨', 'divider': '═', 'success': '✅', 'error': '❌'}

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception:", exc_info=context.error)
    
    error_message = (
        f"❌ **System Alert: Error Detected** ❌\n\n"
        f"⚠️ An issue occurred while processing your request.\n"
        f"**Details:** {str(context.error)[:100]}...\n\n"
        f"🔄 **Please try again** or contact support at gilchy@zohomail.com."
    )
    
    try:
        message_source = update.callback_query.message if update.callback_query else update.message
        await message_source.reply_text(error_message)
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚨 **Error Report**\n\n{str(context.error)[:3500]}"
        )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"
        
        banned, until = is_user_banned(user_id)
        if banned:
            emojis = get_theme_emojis(user_id)
            if until:
                time_left = until - datetime.now()
                minutes_left = max(1, int(time_left.total_seconds() / 60))
                await update.message.reply_text(
                    f"{emojis['error']} **Account Suspended** {emojis['error']}\n\n"
                    f"**Reason:** Security violation\n"
                    f"**Remaining:** {minutes_left} minutes\n\n"
                    f"📧 Contact support: gilchy@zohomail.com"
                )
            else:
                await update.message.reply_text(
                    f"{emojis['error']} **Account Banned Permanently** {emojis['error']}\n\n"
                    f"📧 Contact support: gilchy@zohomail.com"
                )
            return
        
        if not user_exists(user_id):
            emojis = get_theme_emojis(user_id)
            await update.message.reply_text(
                f"{emojis['error']} **No Account Found** {emojis['error']}\n\n"
                f"Please contact the administrator to create your account.\n"
                f"📧 Support: gilchy@zohomail.com"
            )
            return
        
        await cinematic_welcome_animation(update, context)
        
        num1, num2 = random.randint(10, 99), random.randint(10, 99)
        operator = random.choice(['+', '-', '*'])
        answer = num1 + num2 if operator == '+' else num1 - num2 if operator == '-' else num1 * num2
        
        context.user_data['captcha_answer'] = answer
        context.user_data['captcha_time'] = datetime.now()
        
        emojis = get_theme_emojis(user_id)
        captcha_text = (
            f"{emojis['main']} **Secure Access Challenge** {emojis['main']}\n\n"
            f"Solve to proceed:\n"
            f"**{num1} {operator} {num2} = ?**\n\n"
            f"Enter your answer below:"
        )
        await update.message.reply_text(captcha_text)
    except Exception as e:
        logger.error(f"Start error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Initialization Error** {emojis['error']}\n\n"
            f"Please retry /start or contact support."
        )

# Handle captcha
async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user_input = update.message.text.strip()
        emojis = get_theme_emojis(user_id)
        
        if 'captcha_answer' not in context.user_data:
            await update.message.reply_text(
                f"{emojis['error']} **Session Expired** {emojis['error']}\n\n"
                f"Use /start to begin again."
            )
            return
        
        if not user_exists(user_id):
            await update.message.reply_text(
                f"{emojis['error']} **Account Not Found** {emojis['error']}\n\n"
                f"Contact admin."
            )
            return
        
        banned, until = is_user_banned(user_id)
        if banned:
            await update.message.reply_text(
                f"{emojis['error']} **Account Suspended** {emojis['error']}\n\n"
                f"Contact support."
            )
            return
        
        try:
            user_answer = int(user_input)
            correct_answer = context.user_data['captcha_answer']
            
            if user_answer == correct_answer:
                await advanced_loading_animation(update, context, "Verifying Access", 2)
                await update.message.reply_text(
                    f"{emojis['success']} **Access Granted!** {emojis['success']}\n\n"
                    f"Proceed with /login to enter your premium dashboard."
                )
                context.user_data.pop('captcha_answer', None)
                context.user_data.pop('captcha_time', None)
            else:
                suspend_until = datetime.now() + timedelta(minutes=15)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET suspended_until = ?, login_attempts = login_attempts + 1 WHERE user_id = ?", 
                               (suspend_until.isoformat(), user_id))
                conn.commit()
                conn.close()
                
                await countdown_animation(update, context, 
                                         "Incorrect Answer! Account suspended for 15 minutes.", 3)
        except ValueError:
            await update.message.reply_text(
                f"{emojis['error']} **Invalid Input** {emojis['error']}\n\n"
                f"Please enter a number."
            )
    except Exception as e:
        logger.error(f"Captcha error: {e}")
        emojis = get_theme_emojis(user_id)
        await update.message.reply_text(
            f"{emojis['error']} **Verification Error** {emojis['error']}\n\n"
            f"Retry /start."
        )

# Login command
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        emojis = get_theme_emojis(user_id)
        
        banned, until = is_user_banned(user_id)
        if banned:
            if until:
                time_left = until - datetime.now()
                minutes_left = max(1, int(time_left.total_seconds() / 60))
                await update.message.reply_text(
                    f"{emojis['error']} **Account Suspended** {emojis['error']}\n\n"
                    f"Retry in {minutes_left} minutes."
                )
            else:
                await update.message.reply_text(
                    f"{emojis['error']} **Account Banned** {emojis['error']}\n\n"
                    f"Contact support."
                )
            return
        
        if not user_exists(user_id):
            await update.message.reply_text(
                f"{emojis['error']} **No Account** {emojis['error']}\n\n"
                f"Contact admin for setup."
            )
            return
        
        context.user_data['awaiting_password'] = True
        await update.message.reply_text(
            f"{emojis['main']} **Secure Login Portal** {emojis['main']}\n\n"
            f"Enter your premium password:"
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        emojis = get_theme_emojis(user_id)
        await update.message.reply_text(
            f"{emojis['error']} **Login Error** {emojis['error']}\n\n"
            f"Retry /login."
        )

# Handle password
async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('awaiting_password'):
            return
        
        user_id = update.effective_user.id
        emojis = get_theme_emojis(user_id)
        password_attempt = update.message.text.strip()
        hashed_attempt = hashlib.sha256(password_attempt.encode()).hexdigest()
        actual_hashed = get_user_password(user_id)
        
        if actual_hashed and hashed_attempt == actual_hashed:
            context.user_data['logged_in'] = True
            context.user_data['user_id'] = user_id
            context.user_data['awaiting_password'] = False
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_login = ?, login_attempts = 0 WHERE user_id = ?", 
                           (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()
            
            await advanced_loading_animation(update, context, "Authenticating", 2)
            await show_user_dashboard(update, context)
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT login_attempts FROM users WHERE user_id = ?", (user_id,))
            attempts = cursor.fetchone()[0]
            
            attempts += 1
            cursor.execute("UPDATE users SET login_attempts = ? WHERE user_id = ?", (attempts, user_id))
            
            if attempts >= 3:
                suspend_until = datetime.now() + timedelta(hours=1)
                cursor.execute("UPDATE users SET suspended_until = ? WHERE user_id = ?", 
                               (suspend_until.isoformat(), user_id))
                conn.commit()
                conn.close()
                
                await countdown_animation(update, context, 
                                         "Authentication Failed! Suspended for 1 hour.", 3)
            else:
                conn.commit()
                conn.close()
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid Password** {emojis['error']}\n\n"
                    f"{3 - attempts} attempts remaining."
                )
    except Exception as e:
        logger.error(f"Password error: {e}")
        emojis = get_theme_emojis(user_id)
        await update.message.reply_text(
            f"{emojis['error']} **Authentication Error** {emojis['error']}\n\n"
            f"Retry /login."
        )

# User dashboard
async def show_user_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            emojis = get_theme_emojis(0)
            message_source = update.callback_query.message if update.callback_query else update.message
            await message_source.reply_text(
                f"{emojis['error']} **Login Required** {emojis['error']}\n\n"
                f"Use /login to access."
            )
            return
        
        user_id = context.user_data['user_id']
        username = update.effective_user.username or "User"
        emojis = get_theme_emojis(user_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]
        cursor.execute("SELECT last_login FROM users WHERE user_id = ?", (user_id,))
        last_login = cursor.fetchone()[0]
        conn.close()
        
        keyboard = [
            [
                InlineKeyboardButton(f"{emojis['accent']} Balance", callback_data="balance"),
                InlineKeyboardButton(f"{emojis['accent']} Wallet", callback_data="setwallet")
            ],
            [
                InlineKeyboardButton(f"{emojis['accent']} Withdraw", callback_data="withdraw"),
                InlineKeyboardButton(f"{emojis['accent']} Voucher", callback_data="claim")
            ],
            [
                InlineKeyboardButton(f"{emojis['accent']} History", callback_data="history"),
                InlineKeyboardButton(f"{emojis['accent']} Database", callback_data="database")
            ],
            [
                InlineKeyboardButton(f"{emojis['accent']} Support", callback_data="support"),
                InlineKeyboardButton(f"{emojis['accent']} Theme", callback_data="toggle_theme")
            ],
            [InlineKeyboardButton(f"{emojis['accent']} Logout", callback_data="logout")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        dashboard_text = (
            f"{emojis['main']} **YourBase Premium Dashboard** {emojis['main']}\n\n"
            f"👤 **{username}** (ID: `{user_id}`)\n"
            f"💰 **Balance:** ${balance:.2f}\n"
            f"📅 **Last Login:** {last_login[:16] if last_login else 'N/A'}\n"
            f"{emojis['divider']*10}\n"
            f"Navigate your premium features below:"
        )
        
        message_source = update.callback_query.message if update.callback_query else update.message
        try:
            await message_source.edit_text(dashboard_text, reply_markup=reply_markup)
        except:
            await message_source.reply_text(dashboard_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        emojis = get_theme_emojis(user_id)
        message_source = update.callback_query.message if update.callback_query else update.message
        await message_source.reply_text(
            f"{emojis['error']} **Dashboard Error** {emojis['error']}\n\n"
            f"Retry /login."
        )

# Balance command
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            emojis = get_theme_emojis(0)
            message_source = update.callback_query.message if update.callback_query else update.message
            await message_source.reply_text(
                f"{emojis['error']} **Login Required** {emojis['error']}\n\n"
                f"Use /login."
            )
            return
        
        user_id = context.user_data['user_id']
        emojis = get_theme_emojis(user_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]
        conn.close()
        
        await button_transition_effect(update, context, "Balance")
        await advanced_loading_animation(update, context, "Fetching Balance", 2)
        
        balance_text = (
            f"{emojis['main']} **Balance Overview** {emojis['main']}\n\n"
            f"💰 **Available:** ${balance:.2f}\n"
            f"📅 **Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Use dashboard for more options."
        )
        
        message_source = update.callback_query.message if update.callback_query else update.message
        await message_source.reply_text(balance_text)
    except Exception as e:
        logger.error(f"Balance error: {e}")
        emojis = get_theme_emojis(user_id)
        message_source = update.callback_query.message if update.callback_query else update.message
        await message_source.reply_text(
            f"{emojis['error']} **Balance Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Set wallet command
async def setwallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            emojis = get_theme_emojis(0)
            message_source = update.callback_query.message if update.callback_query else update.message
            await message_source.reply_text(
                f"{emojis['error']} **Login Required** {emojis['error']}\n\n"
                f"Use /login."
            )
            return
        
        user_id = context.user_data['user_id']
        emojis = get_theme_emojis(user_id)
        
        context.user_data['setting_wallet'] = True
        wallet_prompt = (
            f"{emojis['main']} **Premium Wallet Setup** {emojis['main']}\n\n"
            f"Enter wallet details:\n\n"
            f"**Format:**\n"
            f"Base: 0xYourBaseWallet\n"
            f"LTC: LYourLTCWallet\n"
            f"XLM: YourXLMWallet:Memo (optional)\n\n"
            f"**Example:**\n"
            f"Base: 0x123abc...\n"
            f"LTC: LT123abc...\n"
            f"XLM: G123abc...:memo123"
        )
        message_source = update.callback_query.message if update.callback_query else update.message
        await button_transition_effect(update, context, "Wallet")
        await message_source.reply_text(wallet_prompt)
    except Exception as e:
        logger.error(f"Setwallet error: {e}")
        emojis = get_theme_emojis(user_id)
        message_source = update.callback_query.message if update.callback_query else update.message
        await message_source.reply_text(
            f"{emojis['error']} **Wallet Setup Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Handle wallet setup
async def handle_wallet_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: int = None):
    try:
        if target_user_id is None:
            if not context.user_data.get('setting_wallet'):
                return
            user_id = context.user_data['user_id']
        else:
            user_id = target_user_id
        
        emojis = get_theme_emojis(user_id)
        wallet_text = update.message.text
        lines = [line.strip() for line in wallet_text.split('\n') if line.strip()]
        base_wallet, ltc_wallet, xlm_address, xlm_memo = None, None, None, None
        
        for line in lines:
            line_lower = line.lower()
            if line_lower.startswith('base:'):
                base_wallet = line[5:].strip()
            elif line_lower.startswith('ltc:'):
                ltc_wallet = line[4:].strip()
            elif line_lower.startswith('xlm:'):
                xlm_parts = line[4:].strip().split(':', 1)
                xlm_address = xlm_parts[0].strip()
                xlm_memo = xlm_parts[1].strip() if len(xlm_parts) > 1 else None
        
        if not any([base_wallet, ltc_wallet, xlm_address]):
            await update.message.reply_text(
                f"{emojis['error']} **Invalid Wallet Format** {emojis['error']}\n\n"
                f"Provide at least one wallet."
            )
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO wallets (user_id, base, ltc, xlm_address, xlm_memo)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, base_wallet, ltc_wallet, xlm_address, xlm_memo))
        conn.commit()
        conn.close()
        
        if target_user_id is None:
            context.user_data['setting_wallet'] = False
        
        wallet_info = (
            f"{emojis['main']} **Wallets Configured** {emojis['main']}\n\n"
        )
        if base_wallet:
            wallet_info += f"• **Base:** `{base_wallet}`\n"
        if ltc_wallet:
            wallet_info += f"• **LTC:** `{ltc_wallet}`\n"
        if xlm_address:
            wallet_info += f"• **XLM:** `{xlm_address}`{f' (Memo: {xlm_memo})' if xlm_memo else ''}\n"
        
        await advanced_loading_animation(update, context, "Securing Wallets", 2)
        await update.message.reply_text(wallet_info)
    except Exception as e:
        logger.error(f"Wallet setup error: {e}")
        emojis = get_theme_emojis(user_id)
        await update.message.reply_text(
            f"{emojis['error']} **Wallet Configuration Failed** {emojis['error']}\n\n"
            f"Check format and retry."
        )

# Withdraw command
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            emojis = get_theme_emojis(0)
            message_source = update.callback_query.message if update.callback_query else update.message
            await message_source.reply_text(
                f"{emojis['error']} **Login Required** {emojis['error']}\n\n"
                f"Use /login."
            )
            return
        
        user_id = context.user_data['user_id']
        emojis = get_theme_emojis(user_id)
        
        if len(context.args) < 2:
            withdraw_prompt = (
                f"{emojis['main']} **Initiate Withdrawal** {emojis['main']}\n\n"
                f"**Format:** /withdraw <amount> <method>\n"
                f"**Methods:** base, ltc, xlm\n\n"
                f"**Examples:**\n"
                f"/withdraw 50 base\n"
                f"/withdraw 25 ltc"
            )
            message_source = update.callback_query.message if update.callback_query else update.message
            await button_transition_effect(update, context, "Withdraw")
            await message_source.reply_text(withdraw_prompt)
            return
        
        amount = float(context.args[0])
        if amount <= 0:
            await update.message.reply_text(
                f"{emojis['error']} **Invalid Amount** {emojis['error']}\n\n"
                f"Must be positive."
            )
            return
        
        method = context.args[1].lower()
        if method not in ['base', 'ltc', 'xlm']:
            await update.message.reply_text(
                f"{emojis['error']} **Invalid Method** {emojis['error']}\n\n"
                f"Use base, ltc, or xlm."
            )
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
        balance_result = cursor.fetchone()
        
        if not balance_result or balance_result[0] < amount:
            await update.message.reply_text(
                f"{emojis['error']} **Insufficient Balance** {emojis['error']}\n\n"
                f"Check your balance."
            )
            conn.close()
            return
        
        cursor.execute("SELECT base, ltc, xlm_address FROM wallets WHERE user_id = ?", (user_id,))
        wallet = cursor.fetchone()
        
        if not wallet:
            await update.message.reply_text(
                f"{emojis['error']} **No Wallet Set** {emojis['error']}\n\n"
                f"Use /setwallet."
            )
            conn.close()
            return
        
        wallet_address = wallet[{'base': 0, 'ltc': 1, 'xlm': 2}[method]]
        if not wallet_address:
            await update.message.reply_text(
                f"{emojis['error']} **{method.upper()} Wallet Missing** {emojis['error']}\n\n"
                f"Configure with /setwallet."
            )
            conn.close()
            return
        
        withdrawal_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        
        cursor.execute('''
            INSERT INTO withdrawals (user_id, amount, wallet_address, method, status, withdrawal_id)
            VALUES (?, ?, ?, ?, 'pending', ?)
        ''', (user_id, amount, wallet_address, method, withdrawal_id))
        
        cursor.execute("UPDATE balances SET balance = balance - ? WHERE user_id = ?", 
                       (amount, user_id))
        
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, status, details)
            VALUES (?, 'withdrawal', ?, 'pending', ?)
        ''', (user_id, amount, f"Withdrawal via {method.upper()} to {wallet_address} | ID: {withdrawal_id}"))
        
        conn.commit()
        conn.close()
        
        try:
            await context.bot.send_message(
                LOG_CHANNEL,
                f"📢 **Withdrawal Request** 📢\n\n"
                f"👤 **User:** `{user_id}`\n"
                f"💰 **Amount:** ${amount:.2f}\n"
                f"📦 **Method:** {method.upper()}\n"
                f"💼 **Address:** `{wallet_address}`\n"
                f"📅 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🆔 **ID:** `{withdrawal_id}`\n\n"
                f"/approve_withdrawal {withdrawal_id}\n/reject_withdrawal {withdrawal_id}"
            )
        except Exception as e:
            logger.error(f"Log channel error: {e}")
        
        await advanced_loading_animation(update, context, "Processing Withdrawal", 3)
        withdraw_confirm = (
            f"{emojis['main']} **Withdrawal Requested** {emojis['main']}\n\n"
            f"💰 **Amount:** ${amount:.2f}\n"
            f"📦 **Method:** {method.upper()}\n"
            f"💼 **Address:** `{wallet_address}`\n"
            f"⏳ **Status:** Pending Approval\n"
            f"🆔 **ID:** `{withdrawal_id}`\n\n"
            f"Awaiting admin review."
        )
        message_source = update.callback_query.message if update.callback_query else update.message
        await message_source.reply_text(withdraw_confirm)
        
    except ValueError:
        emojis = get_theme_emojis(user_id)
        await update.message.reply_text(
            f"{emojis['error']} **Invalid Amount** {emojis['error']}\n\n"
            f"Use a number."
        )
    except Exception as e:
        logger.error(f"Withdraw error: {e}")
        emojis = get_theme_emojis(user_id)
        await update.message.reply_text(
            f"{emojis['error']} **Withdrawal Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Claim voucher command
async def claim_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            emojis = get_theme_emojis(0)
            message_source = update.callback_query.message if update.callback_query else update.message
            await message_source.reply_text(
                f"{emojis['error']} **Login Required** {emojis['error']}\n\n"
                f"Use /login."
            )
            return
        
        user_id = context.user_data['user_id']
        emojis = get_theme_emojis(user_id)
        
        if len(context.args) < 1:
            claim_prompt = (
                f"{emojis['main']} **Redeem Voucher** {emojis['main']}\n\n"
                f"**Format:** /claim <voucher_code>\n"
                f"**Example:** /claim ABC123XYZ789"
            )
            message_source = update.callback_query.message if update.callback_query else update.message
            await button_transition_effect(update, context, "Voucher")
            await message_source.reply_text(claim_prompt)
            return
        
        voucher_code = context.args[0].strip().upper()
        
        await advanced_loading_animation(update, context, "Validating Voucher", 2)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT amount, expires_at, status, created_for 
            FROM vouchers WHERE code = ?
        ''', (voucher_code,))
        voucher = cursor.fetchone()
        
        if not voucher:
            await update.message.reply_text(
                f"{emojis['error']} **Invalid Voucher** {emojis['error']}\n\n"
                f"Check code and retry."
            )
            conn.close()
            return
        
        amount, expires_at, status, created_for = voucher
        
        if status != 'active':
            await update.message.reply_text(
                f"{emojis['error']} **Voucher Used/Expired** {emojis['error']}\n\n"
                f"Try another code."
            )
            conn.close()
            return
        
        if created_for and created_for != user_id:
            await update.message.reply_text(
                f"{emojis['error']} **Voucher Not Yours** {emojis['error']}\n\n"
                f"Assigned to another user."
            )
            conn.close()
            return
        
        expires_datetime = datetime.fromisoformat(expires_at)
        if datetime.now() > expires_datetime:
            cursor.execute("UPDATE vouchers SET status = 'expired' WHERE code = ?", (voucher_code,))
            conn.commit()
            await update.message.reply_text(
                f"{emojis['error']} **Voucher Expired** {emojis['error']}\n\n"
                f"Validity ended."
            )
            conn.close()
            return
        
        cursor.execute("UPDATE vouchers SET status = 'used' WHERE code = ?", (voucher_code,))
        cursor.execute("UPDATE balances SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, status, details)
            VALUES (?, 'voucher', ?, 'completed', ?)
        ''', (user_id, amount, f"Voucher: {voucher_code}"))
        
        conn.commit()
        conn.close()
        
        await feedback_animation(update, context, True, f"Voucher Redeemed: ${amount:.2f}")
    except Exception as e:
        logger.error(f"Voucher error: {e}")
        emojis = get_theme_emojis(user_id)
        await update.message.reply_text(
            f"{emojis['error']} **Voucher Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Transaction history command
async def transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            emojis = get_theme_emojis(0)
            message_source = update.callback_query.message if update.callback_query else update.message
            await message_source.reply_text(
                f"{emojis['error']} **Login Required** {emojis['error']}\n\n"
                f"Use /login."
            )
            return
        
        user_id = context.user_data['user_id']
        emojis = get_theme_emojis(user_id)
        
        await button_transition_effect(update, context, "History")
        await advanced_loading_animation(update, context, "Loading Transactions", 2)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT type, amount, status, timestamp, details 
            FROM transactions WHERE user_id = ? 
            ORDER BY timestamp DESC LIMIT 25
        ''', (user_id,))
        transactions = cursor.fetchall()
        
        cursor.execute('''
            SELECT amount, method, status, requested_at, withdrawal_id 
            FROM withdrawals WHERE user_id = ? AND status = 'pending' 
            ORDER BY requested_at DESC
        ''', (user_id,))
        pending_withdrawals = cursor.fetchall()
        conn.close()
        
        history_text = f"{emojis['main']} **Transaction Ledger** {emojis['main']}\n\n"
        
        if transactions:
            history_text += f"📜 **Recent Transactions:**\n"
            for trans in transactions:
                type_emoji = {'deposit': '📥', 'withdrawal': '📤', 'voucher': '🎫', 'admin_deposit': '💸', 'admin_adjustment': '⚖️'}.get(trans[0], '⚙️')
                status_emoji = {'completed': emojis['success'], 'pending': '⏳', 'rejected': emojis['error']}.get(trans[2], '❓')
                history_text += (
                    f"{type_emoji} **{trans[0].replace('_', ' ').title()}:** ${abs(trans[1]):.2f} {status_emoji}\n"
                    f"   📅 {trans[3][:16]}\n"
                    f"   📝 {trans[4][:50]}...\n\n"
                )
        else:
            history_text += f"No recent transactions.\n\n"
        
        if pending_withdrawals:
            history_text += f"⏳ **Pending Withdrawals:**\n"
            for withdraw in pending_withdrawals:
                history_text += (
                    f"💰 ${withdraw[0]:.2f} via {withdraw[1].upper()} ({withdraw[2]})\n"
                    f"   📅 {withdraw[3][:16]}\n"
                    f"   🆔 {withdraw[4]}\n\n"
                )
        
        message_source = update.callback_query.message if update.callback_query else update.message
        await message_source.reply_text(history_text)
    except Exception as e:
        logger.error(f"History error: {e}")
        emojis = get_theme_emojis(user_id)
        message_source = update.callback_query.message if update.callback_query else update.message
        await message_source.reply_text(
            f"{emojis['error']} **Ledger Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Check database command
async def check_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            emojis = get_theme_emojis(0)
            message_source = update.callback_query.message if update.callback_query else update.message
            await message_source.reply_text(
                f"{emojis['error']} **Login Required** {emojis['error']}\n\n"
                f"Use /login."
            )
            return
        
        user_id = context.user_data['user_id']
        emojis = get_theme_emojis(user_id)
        
        await button_transition_effect(update, context, "Database")
        await advanced_loading_animation(update, context, "Accessing Database", 2)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, last_updated FROM user_database_files WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            file_path, last_updated = result
            try:
                with open(file_path, 'r') as file:
                    content = file.read().strip()
                
                if content:
                    db_text = (
                        f"{emojis['main']} **Daily Operations** {emojis['main']}\n\n"
                        f"{content}\n\n"
                        f"**Last Updated:** {last_updated[:16]}"
                    )
                    message_source = update.callback_query.message if update.callback_query else update.message
                    await message_source.reply_text(db_text)
                else:
                    await update.message.reply_text(
                        f"{emojis['main']} **No Operations** {emojis['main']}\n\n"
                        f"Check later."
                    )
            except FileNotFoundError:
                await update.message.reply_text(
                    f"{emojis['error']} **File Missing** {emojis['error']}\n\n"
                    f"Contact admin."
                )
        else:
            await update.message.reply_text(
                f"{emojis['main']} **No Database** {emojis['main']}\n\n"
                f"Contact admin."
            )
    except Exception as e:
        logger.error(f"Database error: {e}")
        emojis = get_theme_emojis(user_id)
        await update.message.reply_text(
            f"{emojis['error']} **Database Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Support command
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = context.user_data.get('user_id', 0)
        emojis = get_theme_emojis(user_id)
        support_text = (
            f"{emojis['main']} **Premium Support** {emojis['main']}\n\n"
            f"📧 **Email:** gilchy@zohomail.com\n"
            f"🕒 **Response:** Within 24 hours\n\n"
            f"We're here for you!"
        )
        message_source = update.callback_query.message if update.callback_query else update.message
        await button_transition_effect(update, context, "Support")
        await message_source.reply_text(support_text)
    except Exception as e:
        logger.error(f"Support error: {e}")
        emojis = get_theme_emojis(0)
        await message_source.reply_text(
            f"{emojis['error']} **Support Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Toggle theme command
async def toggle_theme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            emojis = get_theme_emojis(0)
            await update.callback_query.message.reply_text(
                f"{emojis['error']} **Login Required** {emojis['error']}\n\n"
                f"Use /login."
            )
            return
        
        user_id = context.user_data['user_id']
        current_theme = get_user_theme(user_id)
        new_theme = 'dark' if current_theme == 'light' else 'light'
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET theme = ? WHERE user_id = ?", (new_theme, user_id))
        conn.commit()
        conn.close()
        
        emojis = get_theme_emojis(user_id)
        await button_transition_effect(update, context, "Theme")
        await advanced_loading_animation(update, context, f"Switching to {new_theme.capitalize()} Theme", 2)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **Theme Updated** {emojis['main']}\n\n"
            f"Now using {new_theme.capitalize()} mode."
        )
    except Exception as e:
        logger.error(f"Theme toggle error: {e}")
        emojis = get_theme_emojis(user_id)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Theme Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Logout command
async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('logged_in'):
            user_id = context.user_data.get('user_id', 0)
            emojis = get_theme_emojis(user_id)
            context.user_data.clear()
            await button_transition_effect(update, context, "Logout")
            await countdown_animation(update, context, "Logging Out", 2)
            message_source = update.callback_query.message if update.callback_query else update.message
            await message_source.reply_text(
                f"{emojis['main']} **Logged Out** {emojis['main']}\n\n"
                f"Session terminated. Use /start to return."
            )
        else:
            emojis = get_theme_emojis(0)
            await update.message.reply_text(
                f"{emojis['error']} **No Active Session** {emojis['error']}\n\n"
                f"Use /start."
            )
    except Exception as e:
        logger.error(f"Logout error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Logout Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            emojis = get_theme_emojis(0)
            await update.message.reply_text(
                f"{emojis['error']} **Access Denied** {emojis['error']}\n\n"
                f"Admin only."
            )
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
        pending_count = cursor.fetchone()[0]
        conn.close()
        
        keyboard = [
            [
                InlineKeyboardButton("👥 Users", callback_data="admin_users"),
                InlineKeyboardButton("💰 Finances", callback_data="admin_finances")
            ],
            [
                InlineKeyboardButton("📁 Databases", callback_data="admin_databases"),
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        emojis = get_theme_emojis(ADMIN_ID)
        admin_text = (
            f"{emojis['main']} **Admin Control Suite** {emojis['main']}\n\n"
            f"📊 **Stats:**\n"
            f"• Users: {user_count}\n"
            f"• Pending Withdrawals: {pending_count}\n"
            f"{emojis['divider']*10}\n"
            f"Select an option:"
        )
        await update.message.reply_text(admin_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Admin panel error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Admin Panel Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin sub-menus
async def admin_users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        keyboard = [
            [InlineKeyboardButton("➕ Create User", callback_data="admin_generate_login")],
            [InlineKeyboardButton("🔨 Ban/Unban", callback_data="admin_ban_user")],
            [InlineKeyboardButton("🔑 Reset Password", callback_data="admin_manage_passwords")],
            [InlineKeyboardButton("📊 User Details", callback_data="admin_user_details")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(
            f"{emojis['main']} **User Management** {emojis['main']}\n\nSelect an action:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Admin users menu error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.edit_text(
            f"{emojis['error']} **Menu Error** {emojis['error']}"
        )

async def admin_finances_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        keyboard = [
            [InlineKeyboardButton("💰 Manage Balance", callback_data="admin_manage_balance")],
            [InlineKeyboardButton("🎫 Create Voucher", callback_data="admin_create_voucher")],
            [InlineKeyboardButton("⏳ Pending Withdrawals", callback_data="admin_pending_withdrawals")],
            [InlineKeyboardButton("💼 Update Wallet", callback_data="admin_change_wallet")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(
            f"{emojis['main']} **Financial Tools** {emojis['main']}\n\nSelect an action:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Admin finances menu error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.edit_text(
            f"{emojis['error']} **Menu Error** {emojis['error']}"
        )

async def admin_databases_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        keyboard = [
            [InlineKeyboardButton("📁 Set Database", callback_data="admin_set_database")],
            [InlineKeyboardButton("🗑️ Clear Database", callback_data="admin_clear_database")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(
            f"{emojis['main']} **Database Management** {emojis['main']}\n\nSelect an action:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Admin databases menu error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.edit_text(
            f"{emojis['error']} **Menu Error** {emojis['error']}"
        )

# Generate user login
async def generate_user_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **Create User** {emojis['main']}\n\n"
            f"Enter Telegram User ID:"
        )
        context.user_data['awaiting_user_id_for_login'] = True
    except Exception as e:
        logger.error(f"Generate login error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_user_id_for_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_user_id_for_login'):
            user_input = update.message.text.strip()
            emojis = get_theme_emojis(ADMIN_ID)
            
            try:
                user_id = int(user_input)
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid ID** {emojis['error']}\n\n"
                    f"Use a number."
                )
                return
            
            if user_exists(user_id):
                await update.message.reply_text(
                    f"{emojis['success']} **User Exists** {emojis['success']}\n\n"
                    f"ID: `{user_id}`\nUse password reset if needed."
                )
            else:
                username = update.effective_user.username or "User"
                plain_password = create_user(user_id, username)
                if plain_password:
                    await feedback_animation(update, context, True, f"User Created: ID {user_id}")
                    create_text = (
                        f"{emojis['main']} **User Created** {emojis['main']}\n\n"
                        f"👤 **ID:** `{user_id}`\n"
                        f"🔑 **Password:** `{plain_password}`\n\n"
                        f"User can access via /start."
                    )
                    await update.message.reply_text(create_text)
                else:
                    await update.message.reply_text(
                        f"{emojis['error']} **Creation Failed** {emojis['error']}\n\n"
                        f"Check logs."
                    )
            
            context.user_data['awaiting_user_id_for_login'] = False
    except Exception as e:
        logger.error(f"Handle user ID error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Processing Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Create voucher
async def create_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        voucher_prompt = (
            f"{emojis['main']} **Generate Voucher** {emojis['main']}\n\n"
            f"**Format:** <amount> [user_id]\n\n"
            f"**Examples:**\n"
            f"50.0 - Global voucher\n"
            f"50.0 123456789 - User-specific"
        )
        await update.callback_query.message.reply_text(voucher_prompt)
        context.user_data['awaiting_voucher_creation'] = True
    except Exception as e:
        logger.error(f"Create voucher error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_voucher_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_voucher_creation'):
            parts = update.message.text.strip().split()
            emojis = get_theme_emojis(ADMIN_ID)
            
            if len(parts) < 1:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid Format** {emojis['error']}\n\n"
                    f"Use <amount> [user_id]"
                )
                return
            
            try:
                amount = float(parts[0])
                if amount <= 0:
                    await update.message.reply_text(
                        f"{emojis['error']} **Invalid Amount** {emojis['error']}\n\n"
                        f"Must be positive."
                    )
                    return
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Amount Error** {emojis['error']}\n\n"
                    f"Use a number."
                )
                return
            
            user_id = None
            if len(parts) > 1:
                try:
                    user_id = int(parts[1])
                    if not user_exists(user_id):
                        await update.message.reply_text(
                            f"{emojis['error']} **User Not Found** {emojis['error']}"
                        )
                        return
                except ValueError:
                    await update.message.reply_text(
                        f"{emojis['error']} **ID Error** {emojis['error']}\n\n"
                        f"Use a number."
                    )
                    return
            
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            expires_at = datetime.now() + timedelta(days=1)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO vouchers (code, amount, created_by, created_for, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (code, amount, ADMIN_ID, user_id, expires_at.isoformat()))
            
            conn.commit()
            conn.close()
            
            voucher_text = (
                f"{emojis['success']} **Voucher Created** {emojis['success']}\n\n"
                f"🎫 **Code:** `{code}`\n"
                f"💰 **Amount:** ${amount:.2f}\n"
                f"⏰ **Expires:** {expires_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            if user_id:
                voucher_text += f"👤 **For User:** `{user_id}`"
            
            await feedback_animation(update, context, True, "Voucher Generated")
            await update.message.reply_text(voucher_text)
            context.user_data['awaiting_voucher_creation'] = False
    except Exception as e:
        logger.error(f"Voucher creation error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Voucher Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin set database
async def admin_set_database_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **Set Database** {emojis['main']}\n\n"
            f"Enter user ID:"
        )
        context.user_data['awaiting_db_user_id'] = True
    except Exception as e:
        logger.error(f"Set database error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_database_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_db_user_id'):
            emojis = get_theme_emojis(ADMIN_ID)
            try:
                user_id = int(update.message.text.strip())
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid ID** {emojis['error']}\n\n"
                    f"Use a number."
                )
                return
            
            if not user_exists(user_id):
                await update.message.reply_text(
                    f"{emojis['error']} **User Not Found** {emojis['error']}"
                )
                return
            
            context.user_data['target_user_id_for_db'] = user_id
            context.user_data['awaiting_db_user_id'] = False
            context.user_data['awaiting_db_content'] = True
            await update.message.reply_text(
                f"{emojis['main']} **Enter Database Content for User {user_id}** {emojis['main']}"
            )
    except Exception as e:
        logger.error(f"Database user ID error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Processing Error** {emojis['error']}\n\n"
            f"Retry."
        )

async def handle_database_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_db_content'):
            user_id = context.user_data.get('target_user_id_for_db')
            emojis = get_theme_emojis(ADMIN_ID)
            content = update.message.text.strip()
            
            file_path = f"user_data/database_{user_id}.txt"
            with open(file_path, 'w') as file:
                file.write(content)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_database_files (user_id, file_path, last_updated)
                VALUES (?, ?, ?)
            ''', (user_id, file_path, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            
            context.user_data['awaiting_db_content'] = False
            context.user_data['target_user_id_for_db'] = None
            
            await feedback_animation(update, context, True, f"Database Set for User {user_id}")
    except Exception as e:
        logger.error(f"Database content error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Database Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin manage balance
async def admin_manage_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        balance_prompt = (
            f"{emojis['main']} **Manage Balance** {emojis['main']}\n\n"
            f"**Format:** add/subtract <user_id> <amount>\n"
            f"**Examples:**\n"
            f"add 123456789 50.0\n"
            f"subtract 123456789 25.0"
        )
        await update.callback_query.message.reply_text(balance_prompt)
        context.user_data['awaiting_balance_manage'] = True
    except Exception as e:
        logger.error(f"Manage balance error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_balance_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_balance_manage'):
            parts = update.message.text.strip().split()
            emojis = get_theme_emojis(ADMIN_ID)
            
            if len(parts) != 3:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid Format** {emojis['error']}\n\n"
                    f"Use add/subtract <user_id> <amount>"
                )
                return
            
            action = parts[0].lower()
            if action not in ['add', 'subtract']:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid Action** {emojis['error']}\n\n"
                    f"Use add or subtract."
                )
                return
            
            try:
                user_id = int(parts[1])
                amount = float(parts[2])
                if amount <= 0:
                    await update.message.reply_text(
                        f"{emojis['error']} **Invalid Amount** {emojis['error']}\n\n"
                        f"Must be positive."
                    )
                    return
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Input Error** {emojis['error']}\n\n"
                    f"Use numbers."
                )
                return
            
            if not user_exists(user_id):
                await update.message.reply_text(
                    f"{emojis['error']} **User Not Found** {emojis['error']}"
                )
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if action == 'add':
                cursor.execute("UPDATE balances SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                details = f"Admin added ${amount:.2f}"
                trans_type = 'admin_deposit'
            else:
                cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
                if cursor.fetchone()[0] < amount:
                    await update.message.reply_text(
                        f"{emojis['error']} **Insufficient Balance** {emojis['error']}"
                    )
                    conn.close()
                    return
                cursor.execute("UPDATE balances SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
                details = f"Admin subtracted ${amount:.2f}"
                trans_type = 'admin_adjustment'
            
            cursor.execute('''
                INSERT INTO transactions (user_id, type, amount, status, details)
                VALUES (?, ?, ?, 'completed', ?)
            ''', (user_id, trans_type, amount if action == 'add' else -amount, details))
            
            conn.commit()
            conn.close()
            
            await feedback_animation(update, context, True, f"Balance {action.capitalize()}ed: ${amount:.2f}")
            context.user_data['awaiting_balance_manage'] = False
    except Exception as e:
        logger.error(f"Balance manage error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Balance Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin user details
async def admin_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **User Details** {emojis['main']}\n\n"
            f"Enter user ID:"
        )
        context.user_data['awaiting_user_details'] = True
    except Exception as e:
        logger.error(f"User details error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_user_details'):
            emojis = get_theme_emojis(ADMIN_ID)
            try:
                user_id = int(update.message.text.strip())
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid ID** {emojis['error']}\n\n"
                    f"Use a number."
                )
                return
            
            if not user_exists(user_id):
                await update.message.reply_text(
                    f"{emojis['error']} **User Not Found** {emojis['error']}"
                )
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT username, is_banned, created_at, last_login, suspended_until, login_attempts FROM users WHERE user_id = ?", (user_id,))
            user_info = cursor.fetchone()
            
            cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
            balance = cursor.fetchone()[0]
            
            cursor.execute("SELECT base, ltc, xlm_address, xlm_memo FROM wallets WHERE user_id = ?", (user_id,))
            wallet = cursor.fetchone()
            
            cursor.execute("SELECT file_path, last_updated FROM user_database_files WHERE user_id = ?", (user_id,))
            db_file = cursor.fetchone()
            
            conn.close()
            
            details = (
                f"{emojis['main']} **User Report: {user_id}** {emojis['main']}\n\n"
                f"👤 **Username:** @{user_info[0] or 'N/A'}\n"
                f"🚫 **Ban Status:** {'Banned' if user_info[1] else 'Active'}\n"
                f"📅 **Created:** {user_info[2][:16]}\n"
                f"🔑 **Last Login:** {user_info[3][:16] if user_info[3] else 'N/A'}\n"
                f"⏳ **Suspended Until:** {user_info[4][:16] if user_info[4] else 'None'}\n"
                f"🔄 **Login Attempts:** {user_info[5]}\n"
                f"💰 **Balance:** ${balance:.2f}\n\n"
            )
            
            if wallet and any(wallet):
                details += f"💼 **Wallets:**\n"
                if wallet[0]: details += f"• Base: `{wallet[0]}`\n"
                if wallet[1]: details += f"• LTC: `{wallet[1]}`\n"
                if wallet[2]: details += f"• XLM: `{wallet[2]}`{f' (Memo: {wallet[3]})' if wallet[3] else ''}\n"
                                                                
            if db_file:
                details += f"📁 **Database File:** `{db_file[0]}`\n"
                details += f"   **Last Updated:** {db_file[1][:16]}\n"
            
            await feedback_animation(update, context, True, f"User Details Fetched")
            await update.message.reply_text(details)
            context.user_data['awaiting_user_details'] = False
    except Exception as e:
        logger.error(f"Handle user details error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Details Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin ban/unban user
async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **Ban/Unban User** {emojis['main']}\n\n"
            f"**Format:** ban/unban <user_id> [duration_minutes]\n"
            f"**Examples:**\n"
            f"ban 123456789 60\n"
            f"unban 123456789"
        )
        context.user_data['awaiting_ban_action'] = True
    except Exception as e:
        logger.error(f"Ban user error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_ban_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_ban_action'):
            parts = update.message.text.strip().split()
            emojis = get_theme_emojis(ADMIN_ID)
            
            if len(parts) < 2:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid Format** {emojis['error']}\n\n"
                    f"Use ban/unban <user_id> [duration_minutes]"
                )
                return
            
            action = parts[0].lower()
            if action not in ['ban', 'unban']:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid Action** {emojis['error']}\n\n"
                    f"Use ban or unban."
                )
                return
            
            try:
                user_id = int(parts[1])
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid ID** {emojis['error']}\n\n"
                    f"Use a number."
                )
                return
            
            if not user_exists(user_id):
                await update.message.reply_text(
                    f"{emojis['error']} **User Not Found** {emojis['error']}"
                )
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if action == 'ban':
                duration = int(parts[2]) if len(parts) > 2 else None
                if duration:
                    suspend_until = datetime.now() + timedelta(minutes=duration)
                    cursor.execute("UPDATE users SET is_banned = ?, suspended_until = ? WHERE user_id = ?", 
                                   (True, suspend_until.isoformat(), user_id))
                else:
                    cursor.execute("UPDATE users SET is_banned = ?, suspended_until = NULL WHERE user_id = ?", 
                                   (True, user_id))
                action_text = f"User {user_id} Banned"
                if duration:
                    action_text += f" for {duration} minutes"
            else:
                cursor.execute("UPDATE users SET is_banned = ?, suspended_until = NULL WHERE user_id = ?", 
                               (False, user_id))
                action_text = f"User {user_id} Unbanned"
            
            conn.commit()
            conn.close()
            
            await feedback_animation(update, context, True, action_text)
            context.user_data['awaiting_ban_action'] = False
    except Exception as e:
        logger.error(f"Ban action error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Ban Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin reset password
async def admin_manage_passwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **Reset Password** {emojis['main']}\n\n"
            f"Enter user ID:"
        )
        context.user_data['awaiting_password_reset'] = True
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_password_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_password_reset'):
            emojis = get_theme_emojis(ADMIN_ID)
            try:
                user_id = int(update.message.text.strip())
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid ID** {emojis['error']}\n\n"
                    f"Use a number."
                )
                return
            
            if not user_exists(user_id):
                await update.message.reply_text(
                    f"{emojis['error']} **User Not Found** {emojis['error']}"
                )
                return
            
            plain_password = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=14))
            hashed_password = hashlib.sha256(plain_password.encode()).hexdigest()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ?, login_attempts = 0, suspended_until = NULL WHERE user_id = ?", 
                           (hashed_password, user_id))
            conn.commit()
            conn.close()
            
            reset_text = (
                f"{emojis['success']} **Password Reset** {emojis['success']}\n\n"
                f"👤 **User ID:** `{user_id}`\n"
                f"🔑 **New Password:** `{plain_password}`\n\n"
                f"Share with user securely."
            )
            await feedback_animation(update, context, True, f"Password Reset for User {user_id}")
            await update.message.reply_text(reset_text)
            context.user_data['awaiting_password_reset'] = False
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Reset Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin change wallet
async def admin_change_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **Update User Wallet** {emojis['main']}\n\n"
            f"Enter user ID:"
        )
        context.user_data['awaiting_wallet_user_id'] = True
    except Exception as e:
        logger.error(f"Change wallet error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_wallet_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_wallet_user_id'):
            emojis = get_theme_emojis(ADMIN_ID)
            try:
                user_id = int(update.message.text.strip())
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid ID** {emojis['error']}\n\n"
                    f"Use a number."
                )
                return
            
            if not user_exists(user_id):
                await update.message.reply_text(
                    f"{emojis['error']} **User Not Found** {emojis['error']}"
                )
                return
            
            context.user_data['target_wallet_user_id'] = user_id
            context.user_data['awaiting_wallet_user_id'] = False
            context.user_data['setting_wallet'] = True
            await update.message.reply_text(
                f"{emojis['main']} **Enter Wallet Details for User {user_id}** {emojis['main']}\n\n"
                f"**Format:**\n"
                f"Base: 0xYourBaseWallet\n"
                f"LTC: LYourLTCWallet\n"
                f"XLM: YourXLMWallet:Memo (optional)"
            )
    except Exception as e:
        logger.error(f"Wallet user ID error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Processing Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin clear database
async def admin_clear_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **Clear Database** {emojis['main']}\n\n"
            f"Enter user ID:"
        )
        context.user_data['awaiting_db_clear_user_id'] = True
    except Exception as e:
        logger.error(f"Clear database error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_clear_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_db_clear_user_id'):
            emojis = get_theme_emojis(ADMIN_ID)
            try:
                user_id = int(update.message.text.strip())
            except ValueError:
                await update.message.reply_text(
                    f"{emojis['error']} **Invalid ID** {emojis['error']}\n\n"
                    f"Use a number."
                )
                return
            
            if not user_exists(user_id):
                await update.message.reply_text(
                    f"{emojis['error']} **User Not Found** {emojis['error']}"
                )
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM user_database_files WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result:
                file_path = result[0]
                try:
                    os.remove(file_path)
                except FileNotFoundError:
                    pass
                cursor.execute("DELETE FROM user_database_files WHERE user_id = ?", (user_id,))
                conn.commit()
                await feedback_animation(update, context, True, f"Database Cleared for User {user_id}")
            else:
                await update.message.reply_text(
                    f"{emojis['error']} **No Database Found** {emojis['error']}"
                )
            
            conn.close()
            context.user_data['awaiting_db_clear_user_id'] = False
    except Exception as e:
        logger.error(f"Clear database error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Clear Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin pending withdrawals
async def admin_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, amount, method, wallet_address, withdrawal_id, requested_at
            FROM withdrawals WHERE status = 'pending'
            ORDER BY requested_at DESC
        ''')
        withdrawals = cursor.fetchall()
        conn.close()
        
        if not withdrawals:
            await update.callback_query.message.reply_text(
                f"{emojis['main']} **No Pending Withdrawals** {emojis['main']}"
            )
            return
        
        withdraw_text = f"{emojis['main']} **Pending Withdrawals** {emojis['main']}\n\n"
        for w in withdrawals:
            withdraw_text += (
                f"🆔 **ID:** `{w[5]}`\n"
                f"👤 **User:** `{w[1]}`\n"
                f"💰 **Amount:** ${w[2]:.2f}\n"
                f"📦 **Method:** {w[3].upper()}\n"
                f"💼 **Address:** `{w[4]}`\n"
                f"📅 **Requested:** {w[6][:16]}\n"
                f"**Actions:** /approve_withdrawal {w[5]}\n/reject_withdrawal {w[5]}\n\n"
            )
        
        await button_transition_effect(update, context, "Pending Withdrawals")
        await update.callback_query.message.reply_text(withdraw_text)
    except Exception as e:
        logger.error(f"Pending withdrawals error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Withdrawals Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Approve withdrawal
async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            emojis = get_theme_emojis(0)
            await update.message.reply_text(
                f"{emojis['error']} **Access Denied** {emojis['error']}\n\n"
                f"Admin only."
            )
            return
        
        if len(context.args) < 1:
            emojis = get_theme_emojis(ADMIN_ID)
            await update.message.reply_text(
                f"{emojis['error']} **Invalid Format** {emojis['error']}\n\n"
                f"Use /approve_withdrawal <withdrawal_id>"
            )
            return
        
        withdrawal_id = context.args[0].strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, amount, method, wallet_address
            FROM withdrawals WHERE withdrawal_id = ? AND status = 'pending'
        ''', (withdrawal_id,))
        withdrawal = cursor.fetchone()
        
        if not withdrawal:
            await update.message.reply_text(
                f"{emojis['error']} **Withdrawal Not Found** {emojis['error']}\n\n"
                f"Check ID."
            )
            conn.close()
            return
        
        withdrawal_id_db, user_id, amount, method, wallet_address = withdrawal
        txid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))
        
        cursor.execute('''
            UPDATE withdrawals SET status = 'completed', txid = ?, processed_at = ?
            WHERE id = ?
        ''', (txid, datetime.now().isoformat(), withdrawal_id_db))
        
        cursor.execute('''
            UPDATE transactions SET status = 'completed'
            WHERE user_id = ? AND type = 'withdrawal' AND details LIKE ?
        ''', (user_id, f"%{withdrawal_id}%"))
        
        conn.commit()
        conn.close()
        
        await context.bot.send_message(
            user_id,
            f"{emojis['success']} **Withdrawal Approved** {emojis['success']}\n\n"
            f"💰 **Amount:** ${amount:.2f}\n"
            f"📦 **Method:** {method.upper()}\n"
            f"💼 **Address:** `{wallet_address}`\n"
            f"📅 **Processed:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"🆔 **TXID:** `{txid}`"
        )
        
        await feedback_animation(update, context, True, f"Withdrawal {withdrawal_id} Approved")
    except Exception as e:
        logger.error(f"Approve withdrawal error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Approval Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Reject withdrawal
async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            emojis = get_theme_emojis(0)
            await update.message.reply_text(
                f"{emojis['error']} **Access Denied** {emojis['error']}\n\n"
                f"Admin only."
            )
            return
        
        if len(context.args) < 1:
            emojis = get_theme_emojis(ADMIN_ID)
            await update.message.reply_text(
                f"{emojis['error']} **Invalid Format** {emojis['error']}\n\n"
                f"Use /reject_withdrawal <withdrawal_id>"
            )
            return
        
        withdrawal_id = context.args[0].strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, amount
            FROM withdrawals WHERE withdrawal_id = ? AND status = 'pending'
        ''', (withdrawal_id,))
        withdrawal = cursor.fetchone()
        
        if not withdrawal:
            await update.message.reply_text(
                f"{emojis['error']} **Withdrawal Not Found** {emojis['error']}\n\n"
                f"Check ID."
            )
            conn.close()
            return
        
        withdrawal_id_db, user_id, amount = withdrawal
        
        cursor.execute('''
            UPDATE withdrawals SET status = 'rejected', processed_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), withdrawal_id_db))
        
        cursor.execute('''
            UPDATE transactions SET status = 'rejected'
            WHERE user_id = ? AND type = 'withdrawal' AND details LIKE ?
        ''', (user_id, f"%{withdrawal_id}%"))
        
        cursor.execute("UPDATE balances SET balance = balance + ? WHERE user_id = ?", 
                       (amount, user_id))
        
        conn.commit()
        conn.close()
        
        await context.bot.send_message(
            user_id,
            f"{emojis['error']} **Withdrawal Rejected** {emojis['error']}\n\n"
            f"💰 **Amount:** ${amount:.2f}\n"
            f"📅 **Processed:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"📧 Contact support: gilchy@zohomail.com"
        )
        
        await feedback_animation(update, context, False, f"Withdrawal {withdrawal_id} Rejected")
    except Exception as e:
        logger.error(f"Reject withdrawal error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Rejection Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Admin broadcast
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emojis = get_theme_emojis(ADMIN_ID)
        await update.callback_query.message.reply_text(
            f"{emojis['main']} **Broadcast Message** {emojis['main']}\n\n"
            f"Enter message to send to all users:"
        )
        context.user_data['awaiting_broadcast'] = True
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        emojis = get_theme_emojis(0)
        await update.callback_query.message.reply_text(
            f"{emojis['error']} **Error** {emojis['error']}\n\nRetry."
        )

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_broadcast'):
            message = update.message.text.strip()
            emojis = get_theme_emojis(ADMIN_ID)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            conn.close()
            
            sent_count = 0
            for user in users:
                user_id = user[0]
                try:
                    await context.bot.send_message(
                        user_id,
                        f"{emojis['main']} **Admin Broadcast** {emojis['main']}\n\n{message}"
                    )
                    sent_count += 1
                    await asyncio.sleep(0.05)  # Avoid rate limits
                except Exception as e:
                    logger.error(f"Broadcast to {user_id} failed: {e}")
            
            await feedback_animation(update, context, True, f"Broadcast Sent to {sent_count} Users")
            context.user_data['awaiting_broadcast'] = False
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        emojis = get_theme_emojis(0)
        await update.message.reply_text(
            f"{emojis['error']} **Broadcast Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Callback query handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        data = query.data
        emojis = get_theme_emojis(context.user_data.get('user_id', 0))
        
        await query.answer()
        
        if data == "balance":
            await balance(update, context)
        elif data == "setwallet":
            await setwallet(update, context)
        elif data == "withdraw":
            await withdraw(update, context)
        elif data == "claim":
            await claim_voucher(update, context)
        elif data == "history":
            await transaction_history(update, context)
        elif data == "database":
            await check_database(update, context)
        elif data == "support":
            await support(update, context)
        elif data == "toggle_theme":
            await toggle_theme(update, context)
        elif data == "logout":
            await logout(update, context)
        elif data == "admin_main":
            await admin_panel(update, context)
        elif data == "admin_users":
            await admin_users_menu(update, context)
        elif data == "admin_finances":
            await admin_finances_menu(update, context)
        elif data == "admin_databases":
            await admin_databases_menu(update, context)
        elif data == "admin_generate_login":
            await generate_user_login(update, context)
        elif data == "admin_ban_user":
            await admin_ban_user(update, context)
        elif data == "admin_manage_passwords":
            await admin_manage_passwords(update, context)
        elif data == "admin_user_details":
            await admin_user_details(update, context)
        elif data == "admin_manage_balance":
            await admin_manage_balance(update, context)
        elif data == "admin_create_voucher":
            await create_voucher(update, context)
        elif data == "admin_set_database":
            await admin_set_database_menu(update, context)
        elif data == "admin_clear_database":
            await admin_clear_database(update, context)
        elif data == "admin_change_wallet":
            await admin_change_wallet(update, context)
        elif data == "admin_pending_withdrawals":
            await admin_pending_withdrawals(update, context)
        elif data == "admin_back":
            await admin_panel(update, context)
        elif data == "admin_broadcast":
            await admin_broadcast(update, context)
        else:
            await query.message.reply_text(
                f"{emojis['error']} **Invalid Selection** {emojis['error']}\n\n"
                f"Try again."
            )
    except Exception as e:
        logger.error(f"Button callback error: {e}")
        emojis = get_theme_emojis(0)
        await query.message.reply_text(
            f"{emojis['error']} **Callback Error** {emojis['error']}\n\n"
            f"Retry."
        )

# Main function
def main():
    try:
        init_db()
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("login", login))
        application.add_handler(CommandHandler("withdraw", withdraw))
        application.add_handler(CommandHandler("claim", claim_voucher))
        application.add_handler(CommandHandler("admin", admin_panel))
        application.add_handler(CommandHandler("approve_withdrawal", approve_withdrawal))
        application.add_handler(CommandHandler("reject_withdrawal", reject_withdrawal))
        
        application.add_handler(CallbackQueryHandler(button_callback))
        
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'), 
            handle_captcha
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^(Base:|LTC:|XLM:)', flags=re.IGNORECASE), 
            handle_wallet_setup
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'), 
            handle_user_id_for_login,
            lambda update, context: context.user_data.get('awaiting_user_id_for_login')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^(add|subtract)\s+\d+\s+\d+(\.\d+)?$'), 
            handle_balance_manage,
            lambda update, context: context.user_data.get('awaiting_balance_manage')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+(\.\d+)?(\s+\d+)?$'), 
            handle_voucher_creation,
            lambda update, context: context.user_data.get('awaiting_voucher_creation')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'), 
            handle_user_details,
            lambda update, context: context.user_data.get('awaiting_user_details')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^(ban|unban)\s+\d+(\s+\d+)?$'), 
            handle_ban_action,
            lambda update, context: context.user_data.get('awaiting_ban_action')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'), 
            handle_password_reset,
            lambda update, context: context.user_data.get('awaiting_password_reset')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'), 
            handle_wallet_user_id,
            lambda update, context: context.user_data.get('awaiting_wallet_user_id')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'), 
            handle_database_user_id,
            lambda update, context: context.user_data.get('awaiting_db_user_id')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            handle_database_content,
            lambda update, context: context.user_data.get('awaiting_db_content')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            handle_broadcast,
            lambda update, context: context.user_data.get('awaiting_broadcast')
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            handle_password,
            lambda update, context: context.user_data.get('awaiting_password')
        ))
        
        application.add_error_handler(error_handler)
        
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Main loop error: {e}")

if __name__ == '__main__':
    main()
