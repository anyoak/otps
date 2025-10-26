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
            text=error_message[:4000]  # Telegram message limit
        )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")

# Animation functions
async def loading_animation(update, context, message_text, duration=3):
    try:
        if hasattr(update, 'message'):
            message = await update.message.reply_text(message_text)
        else:
            message = await update.callback_query.message.reply_text(message_text)
        
        for i in range(duration):
            dots = "▪️" * (i % 4) + "▫️" * (3 - (i % 4))
            loading_text = f"{dots}\nLoading{'.' * ((i % 3) + 1)}"
            try:
                await message.edit_text(loading_text)
            except:
                pass
            await asyncio.sleep(1)
        
        return message
    except Exception as e:
        logger.error(f"Loading animation error: {e}")
        return None

async def countdown_animation(update, context, message_text, seconds=5):
    try:
        if hasattr(update, 'message'):
            message = await update.message.reply_text(message_text)
        else:
            message = await update.callback_query.message.reply_text(message_text)
        
        for i in range(seconds, 0, -1):
            try:
                await message.edit_text(f"{message_text}\n\nTime remaining: {i} seconds")
            except:
                pass
            await asyncio.sleep(1)
        
        return message
    except Exception as e:
        logger.error(f"Countdown animation error: {e}")
        return None

# Database helper functions
def get_db_connection():
    return sqlite3.connect('bot_database.db')

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
        
        # Generate random password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        cursor.execute("INSERT OR IGNORE INTO users (user_id, password) VALUES (?, ?)", (user_id, password))
        cursor.execute("INSERT OR IGNORE INTO balances (user_id, balance) VALUES (?, 0)", (user_id,))
        
        conn.commit()
        conn.close()
        return password
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
                suspended_until = datetime.fromisoformat(suspended_until)
                if datetime.now() < suspended_until:
                    return True, suspended_until
            return bool(is_banned), None
        return False, None
    except Exception as e:
        logger.error(f"Error checking user ban status: {e}")
        return False, None

# Start command with captcha
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        # Check if user is temporarily blocked
        banned, until = is_user_banned(user_id)
        if banned:
            if until:
                time_left = until - datetime.now()
                minutes_left = int(time_left.total_seconds() / 60)
                await countdown_animation(update, context, 
                                        f"🚫 Account Temporarily Blocked\nReason: Failed captcha attempt\nTime remaining: {minutes_left} minutes")
            else:
                await update.message.reply_text("🚫 Your account has been banned. Contact support.")
            return
        
        # Generate math captcha
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        operator = random.choice(['+', '-', '*'])
        
        if operator == '+':
            answer = num1 + num2
        elif operator == '-':
            answer = num1 - num2
        else:
            answer = num1 * num2
        
        context.user_data['captcha_answer'] = answer
        context.user_data['captcha_time'] = datetime.now()
        
        await update.message.reply_text(
            f"🔐 Welcome! Please solve this math problem to continue:\n\n"
            f"**{num1} {operator} {num2} = ?**\n\n"
            f"Reply with the answer below:"
        )
    except Exception as e:
        logger.error(f"Start command error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Handle captcha response
async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user_input = update.message.text
        
        if 'captcha_answer' not in context.user_data:
            await update.message.reply_text("Please use /start to begin.")
            return
        
        try:
            if int(user_input) == context.user_data['captcha_answer']:
                # Captcha passed
                await loading_animation(update, context, "✅ Captcha verified! Checking account...")
                
                if user_exists(user_id):
                    await update.message.reply_text("✅ Captcha successful! Please use /login to access your account.")
                else:
                    await update.message.reply_text("❌ Account not found. Please contact support.")
            else:
                # Wrong captcha - suspend for 30 minutes
                suspend_until = datetime.now() + timedelta(minutes=30)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET suspended_until = ? WHERE user_id = ?", 
                             (suspend_until.isoformat(), user_id))
                conn.commit()
                conn.close()
                
                await countdown_animation(update, context, 
                                        "❌ Wrong answer! Account temporarily suspended for 30 minutes.")
                
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
    except Exception as e:
        logger.error(f"Captcha handling error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Login command
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        banned, until = is_user_banned(user_id)
        if banned:
            if until:
                time_left = until - datetime.now()
                minutes_left = int(time_left.total_seconds() / 60)
                await update.message.reply_text(f"🚫 Account suspended. Try again in {minutes_left} minutes.")
            else:
                await update.message.reply_text("🚫 Account banned. Contact support.")
            return
        
        if not user_exists(user_id):
            # Auto-create user if not exists (for admin testing)
            password = create_user(user_id)
            if password:
                await update.message.reply_text(f"✅ Account created automatically!\nYour password: {password}\nPlease login again with /login")
            else:
                await update.message.reply_text("❌ Account not found. Please contact support.")
            return
        
        context.user_data['awaiting_password'] = True
        await update.message.reply_text("🔐 Please enter your password:")
    except Exception as e:
        logger.error(f"Login command error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Handle password verification
async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        if not context.user_data.get('awaiting_password'):
            return
        
        password_attempt = update.message.text
        actual_password = get_user_password(user_id)
        
        if password_attempt == actual_password:
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
            
            await loading_animation(update, context, "✅ Login successful!")
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
                                        "❌ Too many failed attempts! Account suspended for 1 hour.")
            else:
                conn.commit()
                conn.close()
                await update.message.reply_text(f"❌ Wrong password! {3-attempts} attempts remaining.")
                
    except Exception as e:
        logger.error(f"Password handling error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# User dashboard
async def show_user_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
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
            "🏠 **User Dashboard**\n\n"
            "Select an option from below:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Set wallet command
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
            "Example:\n"
            "Base: 0x742d35Cc6634C0532925a3b8D\n"
            "LTC: LTLnWGpFA9NMYzQpC9ZzK6c\n"
            "XLM: GD5XCRFGBG4PQGYU4XGXW4:123456"
        )
    except Exception as e:
        logger.error(f"Setwallet command error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Handle wallet setup
async def handle_wallet_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('setting_wallet'):
            return
        
        user_id = context.user_data['user_id']
        wallet_text = update.message.text
        
        # Parse wallet addresses
        lines = wallet_text.split('\n')
        base_wallet = None
        ltc_wallet = None
        xlm_address = None
        xlm_memo = None
        
        for line in lines:
            if line.lower().startswith('base:'):
                base_wallet = line.split(':', 1)[1].strip()
            elif line.lower().startswith('ltc:'):
                ltc_wallet = line.split(':', 1)[1].strip()
            elif line.lower().startswith('xlm:'):
                xlm_parts = line.split(':', 1)[1].strip()
                if ':' in xlm_parts:
                    xlm_address, xlm_memo = xlm_parts.split(':', 1)
                else:
                    xlm_address = xlm_parts
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO wallets (user_id, base, ltc, xlm_address, xlm_memo)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, base_wallet, ltc_wallet, xlm_address, xlm_memo))
        conn.commit()
        conn.close()
        
        context.user_data['setting_wallet'] = False
        
        await loading_animation(update, context, "💼 Saving wallet addresses...")
        await update.message.reply_text("✅ Wallet addresses saved successfully!")
    except Exception as e:
        logger.error(f"Wallet setup error: {e}")
        await update.message.reply_text("❌ Error saving wallet addresses. Please check the format.")

# Check database command (Today's List)
async def check_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        user_id = context.user_data['user_id']
        
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
                    content = file.read()
                await update.message.reply_text(f"📋 **Today's List for You:**\n\n{content}")
            except FileNotFoundError:
                await update.message.reply_text("📋 No database file found for today.")
        else:
            await update.message.reply_text("📋 No database file set for your account yet.")
    except Exception as e:
        logger.error(f"Database check error: {e}")
        await update.message.reply_text("❌ An error occurred while fetching your database.")

# Balance command
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
        
        await loading_animation(update, context, "📊 Checking balance...")
        await update.message.reply_text(f"💰 **Your Balance:** ${balance_amount:.2f}")
    except Exception as e:
        logger.error(f"Balance check error: {e}")
        await update.message.reply_text("❌ An error occurred while checking balance.")

# Withdraw command
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "💰 **Withdraw Funds**\n\n"
                "Usage: /withdraw <amount> <method>\n"
                "Methods: base, ltc, xlm\n\n"
                "Example: /withdraw 50 base"
            )
            return
        
        amount = float(context.args[0])
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
        
        wallet_methods = ['base', 'ltc', 'xlm_address']
        method_index = wallet_methods.index(method) if method in wallet_methods else -1
        
        if method_index == -1 or not wallet[method_index + 1]:
            await update.message.reply_text(f"❌ {method.upper()} wallet not set!")
            conn.close()
            return
        
        # Create withdrawal request
        withdrawal_id = ''.join(random.choices(string.digits, k=8))
        wallet_address = wallet[method_index + 1]
        
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
        ''', (user_id, amount, f"Withdrawal to {method}: {wallet_address} | ID: {withdrawal_id}"))
        
        conn.commit()
        conn.close()
        
        # Notify admin
        try:
            await context.bot.send_message(
                LOG_CHANNEL,
                f"🔄 **New Withdrawal Request**\n\n"
                f"User ID: {user_id}\n"
                f"Amount: ${amount:.2f}\n"
                f"Method: {method.upper()}\n"
                f"Wallet: {wallet_address}\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Withdrawal ID: {withdrawal_id}"
            )
        except Exception as e:
            logger.error(f"Failed to send log: {e}")
        
        await loading_animation(update, context, "💰 Processing withdrawal...")
        await update.message.reply_text(
            f"✅ Withdrawal request submitted!\n\n"
            f"Amount: ${amount:.2f}\n"
            f"Method: {method.upper()}\n"
            f"Status: ⏳ Pending\n\n"
            f"Withdrawal ID: {withdrawal_id}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a valid number.")
    except Exception as e:
        logger.error(f"Withdrawal error: {e}")
        await update.message.reply_text("❌ An error occurred during withdrawal.")

# Claim voucher command
async def claim_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        if len(context.args) < 1:
            await update.message.reply_text("Usage: /claim <voucher_code>")
            return
        
        voucher_code = context.args[0]
        user_id = context.user_data['user_id']
        
        await loading_animation(update, context, "🎫 Claiming voucher...")
        
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
            await update.message.reply_text("❌ This voucher is not for you!")
            conn.close()
            return
        
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
        ''', (user_id, amount, f"Voucher: {voucher_code}"))
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Voucher claimed! ${amount:.2f} added to your balance.")
    except Exception as e:
        logger.error(f"Voucher claim error: {e}")
        await update.message.reply_text("❌ An error occurred while claiming voucher.")

# Transaction history command
async def transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('logged_in'):
            await update.message.reply_text("Please login first using /login")
            return
        
        user_id = context.user_data['user_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT type, amount, status, timestamp, details 
            FROM transactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10
        ''', (user_id,))
        transactions = cursor.fetchall()
        
        cursor.execute('''
            SELECT amount, method, status, requested_at 
            FROM withdrawals WHERE user_id = ? AND status = 'pending' ORDER BY requested_at DESC
        ''', (user_id,))
        pending_withdrawals = cursor.fetchall()
        conn.close()
        
        history_text = "📜 **Transaction History**\n\n"
        
        if transactions:
            for trans in transactions:
                type_emoji = "📥" if "deposit" in trans[0] else "📤" if "withdrawal" in trans[0] else "🎫"
                status_emoji = "✅" if trans[2] == "completed" else "⏳" if trans[2] == "pending" else "❌"
                history_text += f"{type_emoji} {trans[0]}: ${trans[1]:.2f} {status_emoji}\n"
                history_text += f"   📅 {trans[3]}\n\n"
        else:
            history_text += "No transactions found.\n\n"
        
        if pending_withdrawals:
            history_text += "⏳ **Pending Withdrawals**\n\n"
            for withdraw in pending_withdrawals:
                history_text += f"💰 ${withdraw[0]:.2f} via {withdraw[1].upper()}\n"
                history_text += f"   📅 {withdraw[3]}\n\n"
        
        await loading_animation(update, context, "📜 Loading history...")
        await update.message.reply_text(history_text)
    except Exception as e:
        logger.error(f"History error: {e}")
        await update.message.reply_text("❌ An error occurred while fetching history.")

# Support command
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 **Support**\n\nContact us via email: gilchy@zohomail.com")

# Logout command
async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('logged_in'):
            context.user_data.clear()
            await update.message.reply_text("✅ Logged out successfully!")
        else:
            await update.message.reply_text("You are not logged in.")
    except Exception as e:
        logger.error(f"Logout error: {e}")
        await update.message.reply_text("❌ An error occurred during logout.")

# Admin panel
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
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👑 **Admin Panel**\n\n"
            "Select an option:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Admin panel error: {e}")
        await update.message.reply_text("❌ An error occurred.")

# Admin set user database
async def admin_set_user_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Access denied.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "📁 **Set User Database File**\n\n"
                "Usage: /setuserdb <user_id> <file_content>\n"
                "Or send: /setuserdb <user_id> and then the file content in next message"
            )
            context.user_data['awaiting_db_content'] = True
            if len(context.args) == 1:
                context.user_data['target_user_id'] = context.args[0]
            return
        
        user_id = context.args[0]
        content = ' '.join(context.args[1:])
        
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
        
        await update.message.reply_text(f"✅ Database file set for user {user_id}")
        
    except Exception as e:
        logger.error(f"Admin set database error: {e}")
        await update.message.reply_text("❌ Error setting user database.")

# Handle database content input
async def handle_database_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_db_content') and context.user_data.get('target_user_id'):
            user_id = context.user_data['target_user_id']
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
            context.user_data['target_user_id'] = None
            
            await update.message.reply_text(f"✅ Database file set for user {user_id}")
    except Exception as e:
        logger.error(f"Database content handling error: {e}")
        await update.message.reply_text("❌ Error setting user database.")

# Handle callback queries
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "balance":
            await balance(update, context)
        elif data == "setwallet":
            await setwallet(update, context)
        elif data == "withdraw":
            await query.message.reply_text("Use: /withdraw <amount> <method>")
        elif data == "claim":
            await claim_voucher(update, context)
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
                await manage_balance(update, context)
            elif data == "admin_create_voucher":
                await create_voucher(update, context)
            elif data == "admin_user_details":
                await user_details(update, context)
            elif data == "admin_pending_withdrawals":
                await pending_withdrawals(update, context)
            elif data == "admin_ban_user":
                await ban_user(update, context)
            elif data == "admin_clear_database":
                await clear_database(update, context)
            elif data == "admin_manage_passwords":
                await manage_passwords(update, context)
            elif data == "admin_broadcast":
                await broadcast_message(update, context)
                
    except Exception as e:
        logger.error(f"Callback handling error: {e}")
        try:
            await update.callback_query.message.reply_text("❌ An error occurred.")
        except:
            pass

# Placeholder admin functions (to be implemented)
async def generate_user_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("👥 User login generation - Feature coming soon")

async def admin_set_database_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📁 Use /setuserdb <user_id> <content> to set user database")

async def manage_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("💰 Balance management - Feature coming soon")

async def create_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("🎫 Voucher creation - Feature coming soon")

async def user_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📊 User details - Feature coming soon")

async def pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("⏳ Pending withdrawals - Feature coming soon")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("🔨 Ban user - Feature coming soon")

async def clear_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("🗑️ Clear database - Feature coming soon")

async def manage_passwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("🔑 Manage passwords - Feature coming soon")

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📢 Broadcast - Feature coming soon")

def main():
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Add handlers
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
    application.add_handler(CommandHandler("setuserdb", admin_set_user_database))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_setup))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_database_content))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Start bot
    print("Bot is running with enhanced error handling...")
    application.run_polling()

if __name__ == '__main__':
    main()