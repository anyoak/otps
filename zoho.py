import os
import logging
import sqlite3
import asyncio
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import math
import time
import traceback
import hashlib

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8296139143:AAGcF2eOli64uTDIFS2-1GdSrQg0btTbVq0"
ADMIN_ID = 7903239321
LOG_CHANNEL = -1003286276499
TIMEZONE = 'UTC'

# Create data directory if not exists
if not os.path.exists('user_data'):
    os.makedirs('user_data')

# Initialize database
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            password TEXT,
            is_banned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            suspended_until TIMESTAMP,
            login_attempts INTEGER DEFAULT 0
        )
    ''')
    
    # Wallets table
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
    
    # Balances table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS balances (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Transactions table
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
    
    # Vouchers table
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
    
    # Withdrawals table
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
    
    # User database files table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_database_files (
            user_id INTEGER PRIMARY KEY,
            file_path TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception occurred:", exc_info=context.error)
    
    error_message = f"❌ Error occurred:\n{traceback.format_exc()}"
    
    try:
        # Send error to admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=error_message[:4000]
        )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")

# Animation functions - FIXED
async def loading_animation(update, context, message_text, duration=3):
    try:
        if hasattr(update, 'message'):
            message = await update.message.reply_text(message_text)
        else:
            message = await update.callback_query.message.reply_text(message_text)
        
        animations = ["⣼", "⣹", "⢻", "⠿", "⡟", "⣏", "⣧", "⣶"]
        
        for i in range(duration * 2):
            dots = "▪️" * ((i % 4) + 1) + "▫️" * (3 - (i % 4))
            current_anim = animations[i % len(animations)]
            loading_text = f"{current_anim} {message_text}\n{dots}"
            try:
                await message.edit_text(loading_text)
            except:
                pass
            await asyncio.sleep(0.5)
        
        try:
            await message.edit_text(f"✅ {message_text}")
        except:
            pass
        
        return message
    except Exception as e:
        logger.error(f"Loading animation error: {e}")
        try:
            if hasattr(update, 'message'):
                return await update.message.reply_text(f"✅ {message_text}")
            else:
                return await update.callback_query.message.reply_text(f"✅ {message_text}")
        except:
            return None

async def countdown_animation(update, context, message_text, seconds=5):
    try:
        if hasattr(update, 'message'):
            message = await update.message.reply_text(f"{message_text}\n\nTime remaining: {seconds} seconds")
        else:
            message = await update.callback_query.message.reply_text(f"{message_text}\n\nTime remaining: {seconds} seconds")
        
        for i in range(seconds - 1, 0, -1):
            try:
                await message.edit_text(f"{message_text}\n\nTime remaining: {i} seconds")
            except Exception as e:
                logger.error(f"Error editing countdown: {e}")
                break
            await asyncio.sleep(1)
        
        try:
            await message.edit_text(f"⏰ {message_text} - Time's up!")
        except:
            pass
        
        return message
    except Exception as e:
        logger.error(f"Countdown animation error: {e}")
        try:
            if hasattr(update, 'message'):
                return await update.message.reply_text(f"⏰ {message_text}")
            else:
                return await update.callback_query.message.reply_text(f"⏰ {message_text}")
        except:
            return None

# Database helper functions - FIXED
def get_db_connection():
    return sqlite3.connect('bot_database.db', check_same_thread=False)

def user_exists(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error checking user exists: {e}")
        return False

def create_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Generate random password - FIXED
        plain_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        hashed_password = hashlib.sha256(plain_password.encode()).hexdigest()
        
        cursor.execute("INSERT OR IGNORE INTO users (user_id, password) VALUES (?, ?)", (user_id, hashed_password))
        cursor.execute("INSERT OR IGNORE INTO balances (user_id, balance) VALUES (?, 0)", (user_id,))
        
        conn.commit()
        conn.close()
        return plain_password
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None

def get_user_password(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting user password: {e}")
        return None

def is_user_banned(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_banned, suspended_until FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            is_banned, suspended_until = result
            if suspended_until:
                try:
                    suspended_until = datetime.fromisoformat(suspended_until)
                    if datetime.now() < suspended_until:
                        return True, suspended_until
                except:
                    pass
            return bool(is_banned), None
        return False, None
    except Exception as e:
        logger.error(f"Error checking user ban status: {e}")
        return False, None

# Start command with captcha - FIXED
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        # Check if user is temporarily blocked
        banned, until = is_user_banned(user_id)
        if banned:
            if until:
                time_left = until - datetime.now()
                minutes_left = max(1, int(time_left.total_seconds() / 60))
                await update.message.reply_text(f"🚫 Account Temporarily Blocked\nReason: Security violation\nTime remaining: {minutes_left} minutes")
            else:
                await update.message.reply_text("🚫 Your account has been banned. Contact support.")
            return
        
        # Check if user exists
        if not user_exists(user_id):
            await update.message.reply_text(
                "❌ No account found for your Telegram ID.\n\n"
                "Please contact the admin to create an account for you."
            )
            return
        
        # Generate math captcha
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        operator = random.choice(['+', '-', '*'])
        
        if operator == '+':
            answer = num1 + num2
        elif operator == '-':
            # Ensure positive result
            answer = num1 - num2
            while answer <= 0:
                num1 = random.randint(5, 20)
                num2 = random.randint(1, 4)
                answer = num1 - num2
        else:
            answer = num1 * num2
        
        context.user_data['captcha_answer'] = answer
        context.user_data['captcha_time'] = datetime.now()
        
        await update.message.reply_text(
            f"🔐 **Welcome to YourBase Bot!**\n\n"
            f"To continue, please solve this math problem:\n\n"
            f"**{num1} {operator} {num2} = ?**\n\n"
            f"Reply with the answer below:"
        )
    except Exception as e:
        logger.error(f"Start command error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try /start again.")

# Handle captcha response - FIXED
async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user_input = update.message.text
        
        if 'captcha_answer' not in context.user_data:
            await update.message.reply_text("Please use /start to begin.")
            return
        
        # Check if user exists
        if not user_exists(user_id):
            await update.message.reply_text(
                "❌ No account found for your Telegram ID.\n\n"
                "Please contact the admin to create an account for you."
            )
            return
        
        # Check if user is banned
        banned, until = is_user_banned(user_id)
        if banned:
            await update.message.reply_text("🚫 Your account is suspended. Contact support.")
            return
        
        try:
            user_answer = int(user_input.strip())
            correct_answer = context.user_data['captcha_answer']
            
            if user_answer == correct_answer:
                await loading_animation(update, context, "Verifying captcha...", 2)
                await update.message.reply_text("✅ Captcha successful! Use /login to access your account.")
                
                # Clear captcha data
                context.user_data.pop('captcha_answer', None)
                
            else:
                # Wrong captcha
                suspend_until = datetime.now() + timedelta(minutes=30)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET suspended_until = ? WHERE user_id = ?", 
                             (suspend_until.isoformat(), user_id))
                conn.commit()
                conn.close()
                
                await countdown_animation(update, context, 
                                        "❌ Wrong answer! Account temporarily suspended for 30 minutes.", 3)
                
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
    except Exception as e:
        logger.error(f"Captcha handling error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try /start again.")

# Login command - FIXED
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        banned, until = is_user_banned(user_id)
        if banned:
            if until:
                time_left = until - datetime.now()
                minutes_left = max(1, int(time_left.total_seconds() / 60))
                await update.message.reply_text(f"🚫 Account suspended. Try again in {minutes_left} minutes.")
            else:
                await update.message.reply_text("🚫 Account banned. Contact support.")
            return
        
        if not user_exists(user_id):
            await update.message.reply_text(
                "❌ No account found for your Telegram ID.\n\n"
                "Please contact the admin to create an account for you."
            )
            return
        
        context.user_data['awaiting_password'] = True
        await update.message.reply_text(
            "🔐 **Login**\n\n"
            "Please enter your password:"
        )
    except Exception as e:
        logger.error(f"Login command error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Handle password verification - FIXED
async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        if not context.user_data.get('awaiting_password'):
            return
        
        password_attempt = update.message.text.strip()
        hashed_attempt = hashlib.sha256(password_attempt.encode()).hexdigest()
        actual_hashed = get_user_password(user_id)
        
        if actual_hashed and hashed_attempt == actual_hashed:
            # Successful login
            context.user_data['logged_in'] = True
            context.user_data['user_id'] = user_id
            context.user_data['awaiting_password'] = False
            
            # Update last login and reset attempts
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_login = ?, login_attempts = 0 WHERE user_id = ?", 
                         (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()
            
            await loading_animation(update, context, "Logging you in...", 2)
            await show_user_dashboard(update, context)
        else:
            # Wrong password - track attempts
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT login_attempts FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            attempts = result[0] if result else 0
            
            attempts += 1
            cursor.execute("UPDATE users SET login_attempts = ? WHERE user_id = ?", (attempts, user_id))
            
            if attempts >= 3:
                # Suspend for 1 hour after 3 failed attempts
                suspend_until = datetime.now() + timedelta(hours=1)
                cursor.execute("UPDATE users SET suspended_until = ? WHERE user_id = ?", 
                             (suspend_until.isoformat(), user_id))
                conn.commit()
                conn.close()
                
                await countdown_animation(update, context, 
                                        "❌ Too many failed attempts! Account suspended for 1 hour.", 3)
            else:
                conn.commit()
                conn.close()
                remaining_attempts = 3 - attempts
                await update.message.reply_text(f"❌ Wrong password! {remaining_attempts} attempts remaining.")
                
    except Exception as e:
        logger.error(f"Password handling error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try /login again.")

# User dashboard - FIXED
async def show_user_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        user_id = context.user_data['user_id']
        
        # Get user balance
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        balance = result[0] if result else 0
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton("📊 Check Balance", callback_data="balance")],
            [InlineKeyboardButton("💼 Set Wallet", callback_data="setwallet")],
            [InlineKeyboardButton("💰 Withdraw", callback_data="withdraw")],
            [InlineKeyboardButton("🎫 Claim Voucher", callback_data="claim")],
            [InlineKeyboardButton("📜 History", callback_data="history")],
            [InlineKeyboardButton("📋 Today's List", callback_data="database")],
            [InlineKeyboardButton("🆘 Support", callback_data="support")],
            [InlineKeyboardButton("🚪 Logout", callback_data="logout")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🏠 **User Dashboard**\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"💰 Current Balance: `${balance:.2f}`\n\n"
            f"Select an option from below:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try /login again.")

# Balance command - FIXED
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        user_id = context.user_data['user_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        balance_amount = result[0] if result else 0
        
        await loading_animation(update, context, "Checking your balance...", 2)
        await update.message.reply_text(f"💰 **Your Balance:** `${balance_amount:.2f}`")
    except Exception as e:
        logger.error(f"Balance check error: {e}")
        await update.message.reply_text("❌ An error occurred while checking balance.")

# Set wallet command - FIXED
async def setwallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        context.user_data['setting_wallet'] = True
        await update.message.reply_text(
            "💼 **Set Your Wallet**\n\n"
            "Please enter your wallet addresses in the following format:\n\n"
            "**Base:** 0xYourBaseAddress\n"
            "**LTC:** LYourLitecoinAddress\n"
            "**XLM:** YourStellarAddress:Memo (Memo is optional)\n\n"
            "**Example:**\n"
            "Base: 0x742d35Cc6634C0532925a3b8D\n"
            "LTC: LTLnWGpFA9NMYzQpC9ZzK6c\n"
            "XLM: GD5XCRFGBG4PQGYU4XGXW4:123456\n\n"
            "Paste your wallet addresses now:"
        )
    except Exception as e:
        logger.error(f"Setwallet command error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Handle wallet setup - FIXED
async def handle_wallet_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id=None):
    try:
        if target_user_id is None:
            if not context.user_data.get('setting_wallet'):
                return
            user_id = context.user_data['user_id']
        else:
            user_id = target_user_id
        
        wallet_text = update.message.text
        
        # Parse wallet addresses
        lines = [line.strip() for line in wallet_text.split('\n') if line.strip()]
        base_wallet = None
        ltc_wallet = None
        xlm_address = None
        xlm_memo = None
        
        for line in lines:
            line_lower = line.lower()
            if line_lower.startswith('base:'):
                base_wallet = line.split(':', 1)[1].strip()
            elif line_lower.startswith('ltc:'):
                ltc_wallet = line.split(':', 1)[1].strip()
            elif line_lower.startswith('xlm:'):
                xlm_parts = line.split(':', 1)[1].strip()
                if ':' in xlm_parts:
                    xlm_address, xlm_memo = xlm_parts.split(':', 1)
                    xlm_address = xlm_address.strip()
                    xlm_memo = xlm_memo.strip()
                else:
                    xlm_address = xlm_parts
        
        # Validate at least one wallet is provided
        if not any([base_wallet, ltc_wallet, xlm_address]):
            await update.message.reply_text("❌ Please provide at least one valid wallet address.")
            return
        
        # Save to database
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
        
        # Show success message with saved wallets
        wallet_info = "✅ **Wallet Addresses Saved!**\n\n"
        if base_wallet:
            wallet_info += f"• **Base:** `{base_wallet}`\n"
        if ltc_wallet:
            wallet_info += f"• **LTC:** `{ltc_wallet}`\n"
        if xlm_address:
            wallet_info += f"• **XLM:** `{xlm_address}`"
            if xlm_memo:
                wallet_info += f" (Memo: `{xlm_memo}`)"
            wallet_info += "\n"
        
        await loading_animation(update, context, "Saving your wallet addresses...", 2)
        await update.message.reply_text(wallet_info)
        
    except Exception as e:
        logger.error(f"Wallet setup error: {e}")
        await update.message.reply_text("❌ Error saving wallet addresses. Please check the format and try again.")

# Withdraw command - FIXED
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "💰 **Withdraw Funds**\n\n"
                "**Usage:** `/withdraw <amount> <method>`\n"
                "**Methods:** base, ltc, xlm\n\n"
                "**Example:** `/withdraw 50 base`\n"
                "**Example:** `/withdraw 25 ltc`"
            )
            return
        
        try:
            amount = float(context.args[0])
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be greater than 0.")
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a valid number.")
            return
        
        method = context.args[1].lower()
        if method not in ['base', 'ltc', 'xlm']:
            await update.message.reply_text("❌ Invalid method. Use: base, ltc, or xlm")
            return
        
        user_id = context.user_data['user_id']
        
        # Check balance
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
        balance_result = cursor.fetchone()
        
        if not balance_result or balance_result[0] < amount:
            await update.message.reply_text("❌ Insufficient balance!")
            conn.close()
            return
        
        # Check if wallet is set for the method
        cursor.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,))
        wallet = cursor.fetchone()
        
        if not wallet:
            await update.message.reply_text("❌ Please set your wallet first using /setwallet")
            conn.close()
            return
        
        # Get wallet address based on method
        wallet_address = None
        if method == 'base' and wallet[1]:
            wallet_address = wallet[1]
        elif method == 'ltc' and wallet[2]:
            wallet_address = wallet[2]
        elif method == 'xlm' and wallet[3]:
            wallet_address = wallet[3]
        
        if not wallet_address:
            await update.message.reply_text(f"❌ {method.upper()} wallet not set! Please set it using /setwallet")
            conn.close()
            return
        
        # Create withdrawal request
        withdrawal_id = ''.join(random.choices(string.digits, k=8))
        
        cursor.execute('''
            INSERT INTO withdrawals (user_id, amount, wallet_address, method, status, withdrawal_id)
            VALUES (?, ?, ?, ?, 'pending', ?)
        ''', (user_id, amount, wallet_address, method, withdrawal_id))
        
        # Deduct balance
        cursor.execute("UPDATE balances SET balance = balance - ? WHERE user_id = ?", 
                     (amount, user_id))
        
        # Add transaction record
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, status, details)
            VALUES (?, 'withdrawal', ?, 'pending', ?)
        ''', (user_id, amount, f"Withdrawal to {method.upper()}: {wallet_address} | ID: {withdrawal_id}"))
        
        conn.commit()
        conn.close()
        
        # Notify admin
        try:
            await context.bot.send_message(
                LOG_CHANNEL,
                f"🔄 **New Withdrawal Request**\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"💰 Amount: `${amount:.2f}`\n"
                f"📦 Method: {method.upper()}\n"
                f"💼 Wallet: `{wallet_address}`\n"
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🆔 Withdrawal ID: `{withdrawal_id}`"
            )
        except Exception as e:
            logger.error(f"Failed to send log: {e}")
        
        await loading_animation(update, context, "Processing withdrawal request...", 3)
        await update.message.reply_text(
            f"✅ **Withdrawal Request Submitted!**\n\n"
            f"💰 Amount: `${amount:.2f}`\n"
            f"📦 Method: {method.upper()}\n"
            f"💼 Wallet: `{wallet_address}`\n"
            f"📊 Status: ⏳ Pending Approval\n\n"
            f"🆔 Withdrawal ID: `{withdrawal_id}`\n\n"
            f"Your request has been sent for admin approval."
        )
        
    except Exception as e:
        logger.error(f"Withdrawal error: {e}")
        await update.message.reply_text("❌ An error occurred during withdrawal. Please try again.")

# Claim voucher command - FIXED
async def claim_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        if len(context.args) < 1:
            await update.message.reply_text(
                "🎫 **Claim Voucher**\n\n"
                "**Usage:** `/claim <voucher_code>`\n\n"
                "**Example:** `/claim ABC123XYZ`"
            )
            return
        
        voucher_code = context.args[0].strip().upper()
        user_id = context.user_data['user_id']
        
        await loading_animation(update, context, "Checking voucher...", 2)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT amount, expires_at, status, created_for 
            FROM vouchers WHERE code = ?
        ''', (voucher_code,))
        voucher = cursor.fetchone()
        
        if not voucher:
            await update.message.reply_text("❌ Invalid voucher code!")
            conn.close()
            return
        
        amount, expires_at, status, created_for = voucher
        
        if status != 'active':
            await update.message.reply_text("❌ Voucher already used or expired!")
            conn.close()
            return
        
        if created_for and created_for != user_id:
            await update.message.reply_text("❌ This voucher is not for your account!")
            conn.close()
            return
        
        # Check expiration
        expires_datetime = datetime.fromisoformat(expires_at)
        if datetime.now() > expires_datetime:
            cursor.execute("UPDATE vouchers SET status = 'expired' WHERE code = ?", (voucher_code,))
            conn.commit()
            await update.message.reply_text("❌ Voucher has expired!")
            conn.close()
            return
        
        # Claim voucher
        cursor.execute("UPDATE vouchers SET status = 'used' WHERE code = ?", (voucher_code,))
        cursor.execute("UPDATE balances SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, status, details)
            VALUES (?, 'voucher_claim', ?, 'completed', ?)
        ''', (user_id, amount, f"Voucher claimed: {voucher_code}"))
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ **Voucher Claimed Successfully!**\n\n"
            f"🎫 Voucher Code: `{voucher_code}`\n"
            f"💰 Amount: `${amount:.2f}`\n"
            f"✅ Status: Added to your balance"
        )
    except Exception as e:
        logger.error(f"Voucher claim error: {e}")
        await update.message.reply_text("❌ An error occurred while claiming voucher. Please try again.")

# Transaction history command - FIXED
async def transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        user_id = context.user_data['user_id']
        
        await loading_animation(update, context, "Loading your history...", 2)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT type, amount, status, timestamp, details 
            FROM transactions WHERE user_id = ? 
            ORDER BY timestamp DESC LIMIT 10
        ''', (user_id,))
        transactions = cursor.fetchall()
        
        cursor.execute('''
            SELECT amount, method, status, requested_at 
            FROM withdrawals WHERE user_id = ? AND status = 'pending' 
            ORDER BY requested_at DESC
        ''', (user_id,))
        pending_withdrawals = cursor.fetchall()
        conn.close()
        
        history_text = "📜 **Transaction History**\n\n"
        
        if transactions:
            for trans in transactions:
                type_emoji = "📥" if "deposit" in trans[0] else "📤" if "withdrawal" in trans[0] else "🎫"
                status_emoji = "✅" if trans[2] == "completed" else "⏳" if trans[2] == "pending" else "❌"
                history_text += f"{type_emoji} **{trans[0].replace('_', ' ').title()}:** `${trans[1]:.2f}` {status_emoji}\n"
                history_text += f"   📅 {trans[3][:16]}\n"
                if trans[4]:
                    history_text += f"   📝 {trans[4][:50]}\n"
                history_text += "\n"
        else:
            history_text += "No transactions found.\n\n"
        
        if pending_withdrawals:
            history_text += "⏳ **Pending Withdrawals**\n\n"
            for withdraw in pending_withdrawals:
                history_text += f"💰 `${withdraw[0]:.2f}` via {withdraw[1].upper()}\n"
                history_text += f"   📅 {withdraw[3][:16]}\n\n"
        
        await update.message.reply_text(history_text)
    except Exception as e:
        logger.error(f"History error: {e}")
        await update.message.reply_text("❌ An error occurred while fetching history.")

# Check database command (Today's List) - FIXED
async def check_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        user_id = context.user_data['user_id']
        
        await loading_animation(update, context, "Loading today's list...", 2)
        
        # Check if user has a database file
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM user_database_files WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            file_path = result[0]
            try:
                with open(file_path, 'r') as file:
                    content = file.read().strip()
                
                if content:
                    await update.message.reply_text(f"📋 **Today's List for You:**\n\n{content}")
                else:
                    await update.message.reply_text("📋 No data available for today.")
            except FileNotFoundError:
                await update.message.reply_text("📋 Database file not found. Contact admin.")
        else:
            await update.message.reply_text("📋 No database file set for your account yet.")
    except Exception as e:
        logger.error(f"Database check error: {e}")
        await update.message.reply_text("❌ An error occurred while fetching your database.")

# Support command
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 **Support**\n\n"
        "For any issues or questions, contact us via email:\n"
        "📧 **Email:** gilchy@zohomail.com\n\n"
        "We'll get back to you as soon as possible."
    )

# Logout command - FIXED
async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('logged_in'):
            user_id = context.user_data['user_id']
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ **Logged out successfully!**\n\n"
                f"Thank you for using YourBase Bot.\n"
                f"Use /start to login again."
            )
        else:
            await update.message.reply_text("You are not currently logged in.")
    except Exception as e:
        logger.error(f"Logout error: {e}")
        await update.message.reply_text("❌ An error occurred during logout.")

# ===============================
# ADMIN FUNCTIONS - FIXED AND WORKING
# ===============================

# Admin panel - FIXED
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Access denied.")
            return
        
        keyboard = [
            [InlineKeyboardButton("👥 Generate User Login", callback_data="admin_generate_login")],
            [InlineKeyboardButton("📁 Set User Database", callback_data="admin_set_database")],
            [InlineKeyboardButton("💰 Manage Balances", callback_data="admin_manage_balance")],
            [InlineKeyboardButton("🎫 Create Voucher", callback_data="admin_create_voucher")],
            [InlineKeyboardButton("📊 User Details", callback_data="admin_user_details")],
            [InlineKeyboardButton("⏳ Pending Withdrawals", callback_data="admin_pending_withdrawals")],
            [InlineKeyboardButton("🔨 Ban/Unban User", callback_data="admin_ban_user")],
            [InlineKeyboardButton("🗑️ Clear Database", callback_data="admin_clear_database")],
            [InlineKeyboardButton("🔑 Manage Passwords", callback_data="admin_manage_passwords")],
            [InlineKeyboardButton("💼 Change User Wallet", callback_data="admin_change_wallet")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👑 **Admin Panel**\n\n"
            "Select an option below:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Admin panel error: {e}")
        await update.message.reply_text("❌ An error occurred.")

# Generate user login - FIXED
async def generate_user_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "👥 **Generate User Login**\n\n"
            "Send the Telegram User ID to generate login credentials:"
        )
        context.user_data['awaiting_user_id_for_login'] = True
    except Exception as e:
        logger.error(f"Generate login error: {e}")

# Handle user ID for login generation - FIXED
async def handle_user_id_for_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_user_id_for_login'):
            user_input = update.message.text.strip()
            
            try:
                user_id = int(user_input)
            except ValueError:
                await update.message.reply_text("❌ User ID must be a number.")
                return
            
            # Check if user exists
            if user_exists(user_id):
                await update.message.reply_text(
                    f"✅ **User Already Exists**\n\n"
                    f"👤 User ID: `{user_id}`\n"
                    f"Use reset password if needed."
                )
            else:
                # Create new user
                plain_password = create_user(user_id)
                if plain_password:
                    await update.message.reply_text(
                        f"✅ **New User Created**\n\n"
                        f"👤 User ID: `{user_id}`\n"
                        f"🔑 Password: `{plain_password}`\n\n"
                        f"The user can now login with /start"
                    )
                else:
                    await update.message.reply_text("❌ Failed to create user.")
            
            context.user_data['awaiting_user_id_for_login'] = False
    except Exception as e:
        logger.error(f"Handle user ID for login error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Create voucher - FIXED
async def create_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "🎫 **Create Voucher**\n\n"
            "Send in format: `<amount> <user_id (optional)>`\n\n"
            "**Examples:**\n"
            "`50.0` - For all users\n"
            "`50.0 123456789` - For specific user\n"
            "`1 6577308099` - $1 for user 6577308099"
        )
        context.user_data['awaiting_voucher_creation'] = True
    except Exception as e:
        logger.error(f"Create voucher error: {e}")

# Handle voucher creation - FIXED
async def handle_voucher_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_voucher_creation'):
            user_input = update.message.text.strip()
            parts = user_input.split()
            
            if len(parts) < 1:
                await update.message.reply_text("❌ Invalid format. Use: <amount> <user_id (optional)>")
                return
            
            # Parse amount (accept both int and float)
            try:
                amount = float(parts[0])
                if amount <= 0:
                    await update.message.reply_text("❌ Amount must be greater than 0.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Amount must be a valid number.")
                return
            
            # Parse user_id if provided
            user_id = None
            if len(parts) > 1:
                try:
                    user_id = int(parts[1])
                    if not user_exists(user_id):
                        await update.message.reply_text("❌ User not found.")
                        return
                except ValueError:
                    await update.message.reply_text("❌ User ID must be a number.")
                    return
            
            # Generate voucher code
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            expires_at = datetime.now() + timedelta(hours=12)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO vouchers (code, amount, created_by, created_for, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (code, amount, ADMIN_ID, user_id, expires_at.isoformat()))
            
            conn.commit()
            conn.close()
            
            # Send success message
            if user_id:
                message = (
                    f"✅ **Voucher Created for Specific User**\n\n"
                    f"👤 User ID: `{user_id}`\n"
                    f"🎫 Voucher Code: `{code}`\n"
                    f"💰 Amount: `${amount:.2f}`\n"
                    f"⏰ Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                message = (
                    f"✅ **Voucher Created for All Users**\n\n"
                    f"🎫 Voucher Code: `{code}`\n"
                    f"💰 Amount: `${amount:.2f}`\n"
                    f"⏰ Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            
            await update.message.reply_text(message)
            context.user_data['awaiting_voucher_creation'] = False
            
    except Exception as e:
        logger.error(f"Handle voucher creation error: {e}")
        await update.message.reply_text("❌ An error occurred while creating voucher. Please try again.")

# Admin set user database - FIXED
async def admin_set_database_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "📁 **Set User Database**\n\n"
            "Send user_id first, then in next message the content."
        )
        context.user_data['awaiting_db_user_id'] = True
    except Exception as e:
        logger.error(f"Admin set database menu error: {e}")

# Handle database user id and content
async def handle_database_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_db_user_id'):
            user_input = update.message.text.strip()
            try:
                user_id = int(user_input)
            except ValueError:
                await update.message.reply_text("❌ User ID must be a number.")
                return
            
            if not user_exists(user_id):
                await update.message.reply_text("❌ User not found.")
                return
            
            context.user_data['target_user_id_for_db'] = user_id
            context.user_data['awaiting_db_user_id'] = False
            context.user_data['awaiting_db_content'] = True
            await update.message.reply_text("Now send the database content.")
    except Exception as e:
        logger.error(f"Handle database user id error: {e}")

async def handle_database_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_db_content'):
            user_id = context.user_data.get('target_user_id_for_db')
            content = update.message.text
            
            # Save to file
            file_path = f"user_data/database_{user_id}.txt"
            with open(file_path, 'w') as file:
                file.write(content)
            
            # Update database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_database_files (user_id, file_path)
                VALUES (?, ?)
            ''', (user_id, file_path))
            conn.commit()
            conn.close()
            
            context.user_data['awaiting_db_content'] = False
            context.user_data['target_user_id_for_db'] = None
            
            await update.message.reply_text(f"✅ Database file set for user `{user_id}`")
    except Exception as e:
        logger.error(f"Database content handling error: {e}")
        await update.message.reply_text("❌ Error setting user database.")

# Admin manage balance
async def admin_manage_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "💰 **Manage Balances**\n\n"
            "Send: add/subtract <user_id> <amount>"
        )
        context.user_data['awaiting_balance_manage'] = True
    except Exception as e:
        logger.error(f"Admin manage balance error: {e}")

async def handle_balance_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_balance_manage'):
            user_input = update.message.text.strip()
            parts = user_input.split()
            
            if len(parts) != 3:
                await update.message.reply_text("❌ Invalid format. Use: add/subtract <user_id> <amount>")
                return
            
            action = parts[0].lower()
            if action not in ['add', 'subtract']:
                await update.message.reply_text("❌ Invalid action. Use add or subtract.")
                return
            
            try:
                user_id = int(parts[1])
                amount = float(parts[2])
                if amount <= 0:
                    await update.message.reply_text("❌ Amount must be positive.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Invalid user_id or amount.")
                return
            
            if not user_exists(user_id):
                await update.message.reply_text("❌ User not found.")
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if action == 'add':
                cursor.execute("UPDATE balances SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                details = f"Admin added {amount}"
                trans_type = 'deposit'
            else:
                cursor.execute("UPDATE balances SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
                details = f"Admin subtracted {amount}"
                trans_type = 'adjustment'
            
            cursor.execute('''
                INSERT INTO transactions (user_id, type, amount, status, details)
                VALUES (?, ?, ?, 'completed', ?)
            ''', (user_id, trans_type, amount if action == 'add' else -amount, details))
            
            conn.commit()
            conn.close()
            
            await update.message.reply_text(f"✅ Balance {action}ed ${amount:.2f} for user {user_id}")
            context.user_data['awaiting_balance_manage'] = False
    except Exception as e:
        logger.error(f"Handle balance manage error: {e}")
        await update.message.reply_text("❌ Error managing balance.")

# Admin user details
async def admin_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "📊 **User Details**\n\n"
            "Send the user_id to get details."
        )
        context.user_data['awaiting_user_details'] = True
    except Exception as e:
        logger.error(f"Admin user details error: {e}")

async def handle_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_user_details'):
            user_input = update.message.text.strip()
            try:
                user_id = int(user_input)
            except ValueError:
                await update.message.reply_text("❌ User ID must be a number.")
                return
            
            if not user_exists(user_id):
                await update.message.reply_text("❌ User not found.")
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT is_banned, created_at, last_login, suspended_until, login_attempts FROM users WHERE user_id = ?", (user_id,))
            user_info = cursor.fetchone()
            
            cursor.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
            balance = cursor.fetchone()[0]
            
            cursor.execute("SELECT base, ltc, xlm_address, xlm_memo FROM wallets WHERE user_id = ?", (user_id,))
            wallet = cursor.fetchone()
            
            cursor.execute("SELECT file_path FROM user_database_files WHERE user_id = ?", (user_id,))
            db_file = cursor.fetchone()
            
            conn.close()
            
            details = f"📊 **User Details for {user_id}**\n\n"
            details += f"🚫 Banned: {'Yes' if user_info[0] else 'No'}\n"
            details += f"📅 Created: {user_info[1][:16]}\n"
            details += f"🔑 Last Login: {user_info[2][:16] if user_info[2] else 'Never'}\n"
            details += f"⏳ Suspended Until: {user_info[3][:16] if user_info[3] else 'None'}\n"
            details += f"🔄 Login Attempts: {user_info[4]}\n"
            details += f"💰 Balance: ${balance:.2f}\n\n"
            
            if wallet:
                details += "💼 Wallets:\n"
                if wallet[0]: details += f"• Base: {wallet[0]}\n"
                if wallet[1]: details += f"• LTC: {wallet[1]}\n"
                if wallet[2]: details += f"• XLM: {wallet[2]} {f'(Memo: {wallet[3]})' if wallet[3] else ''}\n"
            else:
                details += "💼 No wallets set.\n"
            
            details += f"\n📋 Database File: {'Set' if db_file else 'Not set'}\n"
            
            await update.message.reply_text(details)
            context.user_data['awaiting_user_details'] = False
    except Exception as e:
        logger.error(f"Handle user details error: {e}")
        await update.message.reply_text("❌ Error fetching user details.")

# Admin pending withdrawals
async def admin_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, amount, method, wallet_address, withdrawal_id, requested_at 
            FROM withdrawals WHERE status = 'pending' 
            ORDER BY requested_at DESC
        ''')
        pendings = cursor.fetchall()
        conn.close()
        
        if not pendings:
            await query.message.reply_text("⏳ No pending withdrawals.")
            return
        
        for p in pendings:
            text = f"⏳ **Pending Withdrawal**\n\n"
            text += f"🆔 ID: {p[5]}\n"
            text += f"👤 User: {p[1]}\n"
            text += f"💰 Amount: ${p[2]:.2f}\n"
            text += f"📦 Method: {p[3].upper()}\n"
            text += f"💼 Address: {p[4]}\n"
            text += f"📅 Requested: {p[6][:16]}\n"
            
            keyboard = [
                [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{p[0]}")],
                [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{p[0]}")]
            ]
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Admin pending withdrawals error: {e}")
        await update.callback_query.message.reply_text("❌ Error fetching pending withdrawals.")

# Handle withdrawal approve/reject
async def handle_withdrawal_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action, wid):
    try:
        query = update.callback_query
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT withdrawal_id, user_id, amount FROM withdrawals WHERE id = ?", (wid,))
        result = cursor.fetchone()
        if not result:
            await query.edit_message_text("❌ Withdrawal not found.")
            conn.close()
            return
        
        w_id, user_id, amount = result
        
        if action == 'approve':
            context.user_data['awaiting_txid'] = wid
            await query.edit_message_text(query.message.text + "\n\nSend TXID to approve:")
            conn.close()
            return
        
        elif action == 'reject':
            cursor.execute("UPDATE withdrawals SET status = 'rejected', processed_at = ? WHERE id = ?", 
                           (datetime.now().isoformat(), wid))
            cursor.execute("UPDATE balances SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            cursor.execute("UPDATE transactions SET status = 'rejected' WHERE details LIKE ?", (f"%ID: {w_id}%",))
            conn.commit()
            conn.close()
            await query.edit_message_text(query.message.text + "\n\n❌ Rejected")
            
    except Exception as e:
        logger.error(f"Handle withdrawal action error: {e}")
        await update.callback_query.edit_message_text("❌ Error processing withdrawal.")

async def handle_txid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if 'awaiting_txid' in context.user_data:
            txid = update.message.text.strip()
            wid = context.user_data['awaiting_txid']
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT withdrawal_id FROM withdrawals WHERE id = ?", (wid,))
            w_id = cursor.fetchone()[0]
            
            cursor.execute("UPDATE withdrawals SET status = 'approved', txid = ?, processed_at = ? WHERE id = ?", 
                           (txid, datetime.now().isoformat(), wid))
            cursor.execute("UPDATE transactions SET status = 'completed' WHERE details LIKE ?", (f"%ID: {w_id}%",))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(f"✅ Approved with TXID: {txid}")
            context.user_data.pop('awaiting_txid')
    except Exception as e:
        logger.error(f"Handle txid error: {e}")
        await update.message.reply_text("❌ Error approving withdrawal.")

# Admin ban user
async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "🔨 **Ban/Unban User**\n\n"
            "Send: ban/unban <user_id> [reason]"
        )
        context.user_data['awaiting_ban'] = True
    except Exception as e:
        logger.error(f"Admin ban user error: {e}")

async def handle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_ban'):
            user_input = update.message.text.strip()
            parts = user_input.split()
            
            if len(parts) < 2:
                await update.message.reply_text("❌ Invalid format. Use: ban/unban <user_id> [reason]")
                return
            
            action = parts[0].lower()
            if action not in ['ban', 'unban']:
                await update.message.reply_text("❌ Invalid action. Use ban or unban.")
                return
            
            try:
                user_id = int(parts[1])
            except ValueError:
                await update.message.reply_text("❌ Invalid user_id.")
                return
            
            reason = ' '.join(parts[2:]) if len(parts) > 2 else "No reason provided"
            
            if not user_exists(user_id):
                await update.message.reply_text("❌ User not found.")
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if action == 'ban':
                cursor.execute("UPDATE users SET is_banned = TRUE WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("UPDATE users SET is_banned = FALSE, suspended_until = NULL WHERE user_id = ?", (user_id,))
            
            conn.commit()
            conn.close()
            
            await update.message.reply_text(f"✅ User {user_id} {action}ed. Reason: {reason}")
            context.user_data['awaiting_ban'] = False
    except Exception as e:
        logger.error(f"Handle ban error: {e}")
        await update.message.reply_text("❌ Error banning/unbanning user.")

# Admin clear database
async def admin_clear_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "🗑️ **Clear User Database**\n\n"
            "Send the user_id to clear."
        )
        context.user_data['awaiting_clear_db'] = True
    except Exception as e:
        logger.error(f"Admin clear database error: {e}")

async def handle_clear_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_clear_db'):
            user_input = update.message.text.strip()
            try:
                user_id = int(user_input)
            except ValueError:
                await update.message.reply_text("❌ User ID must be a number.")
                return
            
            if not user_exists(user_id):
                await update.message.reply_text("❌ User not found.")
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_database_files WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            file_path = f"user_data/database_{user_id}.txt"
            if os.path.exists(file_path):
                os.remove(file_path)
            
            await update.message.reply_text(f"✅ Database cleared for user {user_id}")
            context.user_data['awaiting_clear_db'] = False
    except Exception as e:
        logger.error(f"Handle clear db error: {e}")
        await update.message.reply_text("❌ Error clearing database.")

# Admin manage passwords
async def admin_manage_passwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "🔑 **Manage Passwords**\n\n"
            "Send: reset <user_id>"
        )
        context.user_data['awaiting_password_manage'] = True
    except Exception as e:
        logger.error(f"Admin manage passwords error: {e}")

async def handle_password_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_password_manage'):
            user_input = update.message.text.strip()
            parts = user_input.split()
            
            if len(parts) != 2 or parts[0].lower() != 'reset':
                await update.message.reply_text("❌ Invalid format. Use: reset <user_id>")
                return
            
            try:
                user_id = int(parts[1])
            except ValueError:
                await update.message.reply_text("❌ Invalid user_id.")
                return
            
            if not user_exists(user_id):
                await update.message.reply_text("❌ User not found.")
                return
            
            plain_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            hashed_password = hashlib.sha256(plain_password.encode()).hexdigest()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ? WHERE user_id = ?", (hashed_password, user_id))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(f"✅ Password reset for user {user_id}\nNew Password: `{plain_password}`")
            context.user_data['awaiting_password_manage'] = False
    except Exception as e:
        logger.error(f"Handle password manage error: {e}")
        await update.message.reply_text("❌ Error managing password.")

# Admin change user wallet
async def admin_change_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "💼 **Change User Wallet**\n\n"
            "Send the user_id first."
        )
        context.user_data['awaiting_user_for_wallet'] = True
    except Exception as e:
        logger.error(f"Admin change wallet error: {e}")

async def handle_user_for_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_user_for_wallet'):
            user_input = update.message.text.strip()
            try:
                user_id = int(user_input)
            except ValueError:
                await update.message.reply_text("❌ User ID must be a number.")
                return
            
            if not user_exists(user_id):
                await update.message.reply_text("❌ User not found.")
                return
            
            context.user_data['awaiting_wallet_for'] = user_id
            context.user_data['awaiting_user_for_wallet'] = False
            await update.message.reply_text("Now send the wallet addresses in the format.")
    except Exception as e:
        logger.error(f"Handle user for wallet error: {e}")

# Handle wallet for admin is in handle_wallet_setup with target_user_id

# Admin broadcast
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.reply_text(
            "📢 **Broadcast Message**\n\n"
            "Send the message to broadcast to all users."
        )
        context.user_data['awaiting_broadcast'] = True
    except Exception as e:
        logger.error(f"Admin broadcast error: {e}")

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_broadcast'):
            message = update.message.text
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            users = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            sent_count = 0
            for user_id in users:
                try:
                    await context.bot.send_message(chat_id=user_id, text=message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send broadcast to {user_id}: {e}")
            
            await update.message.reply_text(f"✅ Broadcast sent to {sent_count} users.")
            context.user_data['awaiting_broadcast'] = False
    except Exception as e:
        logger.error(f"Handle broadcast error: {e}")
        await update.message.reply_text("❌ Error sending broadcast.")

# Handle callback queries - FIXED
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # User callbacks
        if data == "balance":
            await balance(update, context)
        elif data == "setwallet":
            await setwallet(update, context)
        elif data == "withdraw":
            await query.message.reply_text("Use: /withdraw <amount> <method>")
        elif data == "claim":
            await query.message.reply_text("Use: /claim <voucher_code>")
        elif data == "history":
            await transaction_history(update, context)
        elif data == "database":
            await check_database(update, context)
        elif data == "support":
            await support(update, context)
        elif data == "logout":
            await logout(update, context)
        
        # Admin callbacks
        elif data.startswith("admin_"):
            if update.effective_user.id != ADMIN_ID:
                await query.message.reply_text("❌ Access denied.")
                return
            
            if data == "admin_generate_login":
                await generate_user_login(update, context)
            elif data == "admin_set_database":
                await admin_set_database_menu(update, context)
            elif data == "admin_manage_balance":
                await admin_manage_balance(update, context)
            elif data == "admin_create_voucher":
                await create_voucher(update, context)
            elif data == "admin_user_details":
                await admin_user_details(update, context)
            elif data == "admin_pending_withdrawals":
                await admin_pending_withdrawals(update, context)
            elif data == "admin_ban_user":
                await admin_ban_user(update, context)
            elif data == "admin_clear_database":
                await admin_clear_database(update, context)
            elif data == "admin_manage_passwords":
                await admin_manage_passwords(update, context)
            elif data == "admin_change_wallet":
                await admin_change_wallet(update, context)
            elif data == "admin_broadcast":
                await admin_broadcast(update, context)
        
        # Withdrawal actions
        elif data.startswith("approve_") or data.startswith("reject_"):
            if update.effective_user.id != ADMIN_ID:
                return
            
            parts = data.split("_")
            action = parts[0]
            wid = int(parts[1])
            await handle_withdrawal_action(update, context, action, wid)
                
    except Exception as e:
        logger.error(f"Callback handling error: {e}")
        try:
            await update.callback_query.message.reply_text("❌ An error occurred.")
        except:
            pass

# Handle all text messages - FIXED
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        # Check what state the user is in
        if context.user_data.get('awaiting_password'):
            await handle_password(update, context)
        elif context.user_data.get('setting_wallet'):
            await handle_wallet_setup(update, context)
        elif context.user_data.get('awaiting_user_id_for_login'):
            await handle_user_id_for_login(update, context)
        elif context.user_data.get('awaiting_voucher_creation'):
            await handle_voucher_creation(update, context)
        elif context.user_data.get('awaiting_db_user_id'):
            await handle_database_user_id(update, context)
        elif context.user_data.get('awaiting_db_content'):
            await handle_database_content(update, context)
        elif context.user_data.get('awaiting_balance_manage'):
            await handle_balance_manage(update, context)
        elif context.user_data.get('awaiting_user_details'):
            await handle_user_details(update, context)
        elif context.user_data.get('awaiting_txid'):
            await handle_txid(update, context)
        elif context.user_data.get('awaiting_ban'):
            await handle_ban(update, context)
        elif context.user_data.get('awaiting_clear_db'):
            await handle_clear_db(update, context)
        elif context.user_data.get('awaiting_password_manage'):
            await handle_password_manage(update, context)
        elif context.user_data.get('awaiting_user_for_wallet'):
            await handle_user_for_wallet(update, context)
        elif context.user_data.get('awaiting_wallet_for'):
            await handle_wallet_setup(update, context, context.user_data['awaiting_wallet_for'])
            context.user_data.pop('awaiting_wallet_for')
        elif context.user_data.get('awaiting_broadcast'):
            await handle_broadcast(update, context)
        elif 'captcha_answer' in context.user_data:
            await handle_captcha(update, context)
        else:
            # If no specific state, check if it's a math answer for captcha
            try:
                int(text.strip())
                if 'captcha_answer' in context.user_data:
                    await handle_captcha(update, context)
            except ValueError:
                pass
            await update.message.reply_text("Please use commands or select options.")
                
    except Exception as e:
        logger.error(f"Handle all messages error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

def main():
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("setwallet", setwallet))
    application.add_handler(CommandHandler("withdraw", withdraw))
    application.add_handler(CommandHandler("claim", claim_voucher))
    application.add_handler(CommandHandler("history", transaction_history))
    application.add_handler(CommandHandler("database", check_database))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("logout", logout))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # Add message handler for all text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Start bot
    print("🤖 YourBase Bot is running...")
    print("✅ Database initialized")
    print("👑 Admin ID:", ADMIN_ID)
    print("📊 Log Channel:", LOG_CHANNEL)
    print("⏰ Timezone:", TIMEZONE)
    print("🚀 Bot is ready!")
    
    application.run_polling()

if __name__ == '__main__':
    main()
