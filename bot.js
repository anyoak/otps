const { Telegraf, Markup } = require('telegraf');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

// ========== CONFIG ==========
const BOT_TOKEN = "8443659336:AAF5Yh1HrBd_bkXCuht4CVrWnFluIK8Bx0o";
const ADMIN_ID = 6083895678;
const DB_PATH = path.join(__dirname, 'bot_users.db');
// ============================

const bot = new Telegraf(BOT_TOKEN);

// ========== DB INIT ==========
const db = new sqlite3.Database(DB_PATH);
db.serialize(() => {
    db.run(`
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
        )
    `);
});

// ========== HELPER FUNCTIONS ==========
function getUser(userId) {
    return new Promise((resolve, reject) => {
        db.get("SELECT * FROM users WHERE user_id = ?", [userId], (err, row) => {
            if (err) reject(err);
            else resolve(row);
        });
    });
}

function getAllUsers() {
    return new Promise((resolve, reject) => {
        db.all("SELECT * FROM users ORDER BY joined_date DESC", (err, rows) => {
            if (err) reject(err);
            else resolve(rows);
        });
    });
}

function getPendingUsers() {
    return new Promise((resolve, reject) => {
        db.all("SELECT * FROM users WHERE approved = 0 ORDER BY joined_date DESC", (err, rows) => {
            if (err) reject(err);
            else resolve(rows);
        });
    });
}

function addOrUpdateUser(user) {
    return new Promise((resolve, reject) => {
        const username = user.username || "";
        const name = user.first_name + (user.last_name ? ` ${user.last_name}` : "");
        const joined = new Date().toUTCString();
        
        db.run(
            `INSERT OR IGNORE INTO users (user_id, username, name, joined_date, country) VALUES (?, ?, ?, ?, ?)`,
            [user.id, username, name, joined, "🇧🇩 Bangladesh (BD)"],
            function(err) {
                if (err) reject(err);
                else {
                    db.run(
                        "UPDATE users SET username = ?, name = ? WHERE user_id = ?",
                        [username, name, user.id],
                        (err) => {
                            if (err) reject(err);
                            else resolve();
                        }
                    );
                }
            }
        );
    });
}

function setUserField(userId, field, value) {
    return new Promise((resolve, reject) => {
        db.run(`UPDATE users SET ${field} = ? WHERE user_id = ?`, [value, userId], (err) => {
            if (err) reject(err);
            else resolve();
        });
    });
}

function getAllApprovedUsers() {
    return new Promise((resolve, reject) => {
        db.all("SELECT user_id FROM users WHERE approved = 1", (err, rows) => {
            if (err) reject(err);
            else resolve(rows.map(row => row.user_id));
        });
    });
}

function getUserStats() {
    return new Promise((resolve, reject) => {
        db.get("SELECT COUNT(*) as total FROM users", (err, totalRow) => {
            if (err) reject(err);
            else {
                db.get("SELECT COUNT(*) as approved FROM users WHERE approved = 1", (err, approvedRow) => {
                    if (err) reject(err);
                    else {
                        db.get("SELECT COUNT(*) as pending FROM users WHERE approved = 0", (err, pendingRow) => {
                            if (err) reject(err);
                            else {
                                resolve({
                                    total: totalRow.total,
                                    approved: approvedRow.approved,
                                    pending: pendingRow.pending
                                });
                            }
                        });
                    }
                });
            }
        });
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Escape special characters for Markdown
function escapeMarkdown(text) {
    if (!text) return '';
    return text.toString()
        .replace(/_/g, '\\_')
        .replace(/\*/g, '\\*')
        .replace(/\[/g, '\\[')
        .replace(/\]/g, '\\]')
        .replace(/\(/g, '\\(')
        .replace(/\)/g, '\\)')
        .replace(/~/g, '\\~')
        .replace(/`/g, '\\`')
        .replace(/>/g, '\\>')
        .replace(/#/g, '\\#')
        .replace(/\+/g, '\\+')
        .replace(/-/g, '\\-')
        .replace(/=/g, '\\=')
        .replace(/\|/g, '\\|')
        .replace(/\{/g, '\\{')
        .replace(/\}/g, '\\}')
        .replace(/\./g, '\\.')
        .replace(/!/g, '\\!');
}

function profileTextFromRow(row) {
    if (!row) {
        return "❌ *No Data Available*\n\nPlease contact administrator.";
    }
    
    const user_id = row.user_id;
    const username = row.username;
    const name = row.name;
    const joined = row.joined_date;
    const country = row.country;
    const approved = row.approved;
    const total_ido = row.total_ido || '0';
    const total_investment = row.total_investment || '0';
    const total_payout = row.total_payout || '0';
    const evm_wallet = row.evm_wallet || 'Not Set';
    const username_display = username ? `@${username}` : "Not Set";
    
    return `🎯 *PROFILE DETAILS*

┌──────────────────────────────────
│ 👤 *USER INFORMATION*
├──────────────────────────────────
│ • *ID:* \`${user_id}\`
│ • *Name:* ${escapeMarkdown(name)}
│ • *Username:* ${escapeMarkdown(username_display)}
│ • *Joined:* ${escapeMarkdown(joined)}
│ • *Country:* ${escapeMarkdown(country)}
├──────────────────────────────────
│ 💰 *FINANCIAL OVERVIEW*
├──────────────────────────────────
│ • *Total IDO:* ${escapeMarkdown(total_ido)}
│ • *Total Investment:* $${escapeMarkdown(total_investment)}
│ • *Total Payout:* $${escapeMarkdown(total_payout)}
├──────────────────────────────────
│ 🔗 *WALLET INFORMATION*
├──────────────────────────────────
│ • *EVM Wallet:* \`${escapeMarkdown(evm_wallet)}\`
└──────────────────────────────────

✅ *Status:* ${approved ? 'Approved ✅' : 'Pending Review ⏳'}`;
}

// ========== PREMIUM ANIMATIONS ==========
async function sendLoadingSequence(ctx) {
    try {
        let message = await ctx.reply("🔄 *INITIALIZING SYSTEM*", { parse_mode: 'Markdown' });
        
        const loadingFrames = [
            "🔄 *INITIALIZING SYSTEM*\n\n▰▱▱▱▱▱▱▱ 10%",
            "🔄 *INITIALIZING SYSTEM*\n\n▰▰▱▱▱▱▱▱ 20%", 
            "🔄 *INITIALIZING SYSTEM*\n\n▰▰▰▱▱▱▱▱ 30%",
            "🔄 *INITIALIZING SYSTEM*\n\n▰▰▰▰▱▱▱▱ 40%",
            "🔄 *INITIALIZING SYSTEM*\n\n▰▰▰▰▰▱▱▱ 50%",
            "🔄 *INITIALIZING SYSTEM*\n\n▰▰▰▰▰▰▱▱ 60%",
            "🔄 *INITIALIZING SYSTEM*\n\n▰▰▰▰▰▰▰▱ 70%",
            "🔄 *INITIALIZING SYSTEM*\n\n▰▰▰▰▰▰▰▰ 80%"
        ];
        
        for (let frame of loadingFrames) {
            await ctx.telegram.editMessageText(ctx.chat.id, message.message_id, null, frame, { parse_mode: 'Markdown' });
            await sleep(200);
        }
        
        await ctx.telegram.editMessageText(ctx.chat.id, message.message_id, null, "🔍 *VERIFYING DATABASE ACCESS*", { parse_mode: 'Markdown' });
        await sleep(800);
        
        const verificationSteps = [
            "🔍 *VERIFYING DATABASE ACCESS*\n\n🔐 Connecting to secure database...",
            "🔍 *VERIFYING DATABASE ACCESS*\n\n🔐 Authentication in progress...", 
            "🔍 *VERIFYING DATABASE ACCESS*\n\n🔐 Scanning user records...",
            "🔍 *VERIFYING DATABASE ACCESS*\n\n🔐 Cross-referencing official lists..."
        ];
        
        for (let step of verificationSteps) {
            await ctx.telegram.editMessageText(ctx.chat.id, message.message_id, null, step, { parse_mode: 'Markdown' });
            await sleep(800);
        }
        
        await ctx.telegram.editMessageText(ctx.chat.id, message.message_id, null, "🛡️ *SECURITY SCAN IN PROGRESS*", { parse_mode: 'Markdown' });
        await sleep(800);
        
        const securityFrames = [
            "🛡️ *SECURITY SCAN IN PROGRESS*\n\n🛡️ Scanning user credentials...",
            "🛡️ *SECURITY SCAN IN PROGRESS*\n\n🛡️ Verifying access permissions...",
            "🛡️ *SECURITY SCAN IN PROGRESS*\n\n🛡️ Checking approval status...",
            "🛡️ *SECURITY SCAN IN PROGRESS*\n\n⚠️ *ACCESS RESTRICTED DETECTED*"
        ];
        
        for (let frame of securityFrames) {
            await ctx.telegram.editMessageText(ctx.chat.id, message.message_id, null, frame, { parse_mode: 'Markdown' });
            await sleep(1000);
        }
        
        await ctx.deleteMessage(message.message_id);
        
        const finalText = `❌ *MEMBERSHIP STATUS: PENDING*

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

🛡️ *Secured by Advanced Verification System*`;
        
        await ctx.reply(finalText, { parse_mode: 'Markdown' });

    } catch (error) {
        console.error("Animation error:", error);
    }
}

async function sendSuccessAnimation(ctx, userName) {
    try {
        let message = await ctx.reply("🎉 *WELCOME ABOARD!*", { parse_mode: 'Markdown' });
        
        const welcomeFrames = [
            `✨ *Welcome, ${escapeMarkdown(userName)}!* ✨\n\nInitializing your account...`,
            `🚀 *System Access Granted* 🚀\n\nLoading dashboard...`,
            `✅ *Membership Verified* ✅\n\nFinalizing setup...`,
            `🎯 *Profile Activated* 🎯\n\nYou're all set!`
        ];
        
        for (let frame of welcomeFrames) {
            await ctx.telegram.editMessageText(ctx.chat.id, message.message_id, null, frame, { parse_mode: 'Markdown' });
            await sleep(1000);
        }
        
        await ctx.deleteMessage(message.message_id);
        
    } catch (error) {
        console.error("Success animation error:", error);
    }
}

async function sendProfileLoading(ctx) {
    try {
        let message = await ctx.reply("🔄 *LOADING PROFILE DATA*", { parse_mode: 'Markdown' });
        
        const frames = [
            "🔄 *LOADING PROFILE DATA*\n\n▰▱▱▱▱▱▱▱",
            "🔄 *LOADING PROFILE DATA*\n\n▰▰▱▱▱▱▱▱",
            "🔄 *LOADING PROFILE DATA*\n\n▰▰▰▱▱▱▱▱",
            "🔄 *LOADING PROFILE DATA*\n\n▰▰▰▰▱▱▱▱",
            "🔄 *LOADING PROFILE DATA*\n\n▰▰▰▰▰▱▱▱",
            "🔄 *LOADING PROFILE DATA*\n\n▰▰▰▰▰▰▱▱",
            "🔄 *LOADING PROFILE DATA*\n\n▰▰▰▰▰▰▰▱",
            "🔄 *LOADING PROFILE DATA*\n\n▰▰▰▰▰▰▰▰"
        ];
        
        for (let frame of frames) {
            await ctx.telegram.editMessageText(ctx.chat.id, message.message_id, null, frame, { parse_mode: 'Markdown' });
            await sleep(150);
        }
        
        await ctx.deleteMessage(message.message_id);
        
    } catch (error) {
        console.error("Profile loading error:", error);
    }
}

// ========== CAPTCHA SYSTEM ==========
const captchaStore = new Map();

function generateMathCaptcha() {
    const a = Math.floor(Math.random() * 41) + 10;
    const b = Math.floor(Math.random() * 26) + 5;
    const op = Math.random() > 0.5 ? '+' : '-';
    const ans = op === '+' ? a + b : a - b;
    const question = `${a} ${op} ${b} = ?`;
    return { question, answer: ans.toString() };
}

// ========== BROADCAST STATE ==========
let broadcastState = new Map();

// ========== BOT COMMANDS ==========
bot.start(async (ctx) => {
    const user = ctx.from;
    await addOrUpdateUser(user);
    const row = await getUser(user.id);
    const approved = row && row.approved === 1;
    
    const welcomeText = `🤖 *WELCOME TO SYMBIOTIC AI BOT* 

━━━━━━━━━━━━━━━━━━━━━━━━

👋 Hello *${escapeMarkdown(user.first_name)}*!

Thank you for joining our exclusive community.

🔒 *Security Level:* Enterprise Grade
🎯 *Platform:* AI-Powered Investment  
🌟 *Community:* Verified Members Only

━━━━━━━━━━━━━━━━━━━━━━━━

Please complete the security verification below to continue.`;
    
    await ctx.reply(welcomeText, { parse_mode: 'Markdown' });
    
    if (approved) {
        await sendSuccessAnimation(ctx, user.first_name);
        const text = profileTextFromRow(row);
        await ctx.reply(text, { parse_mode: 'Markdown' });
        return;
    }

    const { question, answer } = generateMathCaptcha();
    captchaStore.set(user.id, answer);
    
    const captchaText = `🧮 *SECURITY VERIFICATION*

━━━━━━━━━━━━━━━━━━━━━━━━

To ensure you're human, please solve this math problem:

*${question}*

📝 *Instructions:*
• Type only the numerical answer
• You have 3 attempts  
• Use /start to restart if needed

━━━━━━━━━━━━━━━━━━━━━━━━

🔐 This helps us prevent automated access.`;
    
    await ctx.reply(captchaText, { parse_mode: 'Markdown' });
});

// Captcha answer handler
bot.on('text', async (ctx) => {
    const userId = ctx.from.id;
    const expected = captchaStore.get(userId);
    
    if (!expected) {
        // Check if this is a broadcast message from admin
        if (broadcastState.get(ctx.from.id) && ctx.from.id === ADMIN_ID) {
            await handleBroadcastContent(ctx);
        }
        return;
    }
    
    const userAnswer = ctx.message.text.trim();
    
    if (userAnswer === expected) {
        captchaStore.delete(userId);
        
        const successText = `✅ *VERIFICATION SUCCESSFUL*

━━━━━━━━━━━━━━━━━━━━━━━━

🎉 Excellent! You've passed the security check.

Now accessing our member database to verify your status...

🛡️ *Security Status:* Verified Human`;
        
        await ctx.reply(successText, { parse_mode: 'Markdown' });
        await sleep(2000);
        
        await sendLoadingSequence(ctx);
        
        // FIXED: Admin notification with escaped characters
        const user = ctx.from;
        const adminText = `👤 *NEW MEMBER REQUEST*

━━━━━━━━━━━━━━━━━━━━━━━━

🆔 *User ID:* \`${user.id}\`
📛 *Name:* ${escapeMarkdown(user.first_name + (user.last_name ? ` ${user.last_name}` : ''))}
📧 *Username:* @${escapeMarkdown(user.username || 'N/A')}
🌐 *Language:* ${escapeMarkdown(user.language_code || 'N/A')}
🕒 *Request Time:* ${escapeMarkdown(new Date().toUTCString())}

━━━━━━━━━━━━━━━━━━━━━━━━

*Security Check:* ✅ Passed
*Captcha Score:* 🎯 Excellent

Please review and approve/reject this membership request.`;
        
        const keyboard = Markup.inlineKeyboard([
            [
                Markup.button.callback("✅ Approve Member", `approve_user_${user.id}`),
                Markup.button.callback("❌ Reject Request", `reject_user_${user.id}`)
            ],
            [Markup.button.callback("👁️ View Profile", `view_profile_${user.id}`)]
        ]);
        
        await ctx.telegram.sendMessage(ADMIN_ID, adminText, {
            parse_mode: 'Markdown',
            reply_markup: keyboard
        });
    } else {
        await ctx.reply(`❌ *VERIFICATION FAILED*

━━━━━━━━━━━━━━━━━━━━━━━━

Incorrect answer. Please try again or type /start for a new security challenge.

💡 *Tip:* Double-check your calculation and enter only the numerical result.`, { parse_mode: 'Markdown' });
    }
});

// Profile command
bot.command('profile', async (ctx) => {
    const user = ctx.from;
    const row = await getUser(user.id);
    
    if (!row) {
        await ctx.reply("❌ Profile not found. Please use /start to initialize.");
        return;
    }
    
    await sendProfileLoading(ctx);
    
    const profileText = profileTextFromRow(row);
    
    const keyboard = Markup.inlineKeyboard([
        [
            Markup.button.callback("🔄 Refresh", "refresh_profile"),
            Markup.button.callback("📊 Statistics", "view_stats")
        ],
        [Markup.button.url("💬 Support", "https://t.me/Symbioticl")]
    ]);
    
    await ctx.reply(profileText, {
        parse_mode: 'Markdown',
        reply_markup: keyboard
    });
});

// Help command
bot.command('help', async (ctx) => {
    const helpText = `🎯 *SYMBIOTIC AI BOT - HELP GUIDE*

━━━━━━━━━━━━━━━━━━━━━━━━

🤖 *Available Commands:*

• /start - Initialize bot & verification
• /profile - View your member profile  
• /help - Show this help message

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ *Security Features:*
• Advanced captcha verification
• Administrator approval system
• Real-time monitoring
• Secure data handling

━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Need Assistance?*
Contact: @Symbioticl

🔒 *Your security and privacy are our top priorities.*`;
    
    await ctx.reply(helpText, { parse_mode: 'Markdown' });
});

// ========== ADMIN COMMANDS ==========

// Admin panel command
bot.command('admin', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.reply("🔒 Administrator access required.");
        return;
    }
    
    const stats = await getUserStats();
    
    const adminText = `👑 *ADMIN PANEL*

━━━━━━━━━━━━━━━━━━━━━━━━

📊 *System Statistics:*
• Total Users: ${stats.total}
• Approved: ${stats.approved}
• Pending: ${stats.pending}

🛠️ *Admin Tools:*
• /users - View all users
• /pending - View pending approvals  
• /broadcast - Send message to all users
• /set [user_id] - Modify user data
• /stats - Detailed statistics`;
    
    await ctx.reply(adminText, { parse_mode: 'Markdown' });
});

// View all users command
bot.command('users', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) return;
    
    const users = await getAllUsers();
    
    if (users.length === 0) {
        await ctx.reply("❌ No users found in database.");
        return;
    }
    
    let userList = `📋 *ALL USERS (${users.length})*

━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    users.slice(0, 20).forEach((user, index) => {
        userList += `${index + 1}. ${user.name} (@${user.username || 'N/A'}) - ${user.approved ? '✅' : '⏳'}\nID: ${user.user_id}\n━━━━━━━━━━━━━━━━━━━━━━━━\n`;
    });
    
    if (users.length > 20) {
        userList += `\n... and ${users.length - 20} more users.`;
    }
    
    await ctx.reply(userList, { parse_mode: 'Markdown' });
});

// View pending users command
bot.command('pending', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) return;
    
    const pendingUsers = await getPendingUsers();
    
    if (pendingUsers.length === 0) {
        await ctx.reply("✅ No pending users. All users are approved!");
        return;
    }
    
    let pendingList = `⏳ *PENDING APPROVALS (${pendingUsers.length})*

━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    pendingUsers.forEach((user, index) => {
        pendingList += `${index + 1}. ${user.name} (@${user.username || 'N/A'})\nID: \`${user.user_id}\`\nJoined: ${user.joined_date}\n`;
        
        const keyboard = Markup.inlineKeyboard([
            [
                Markup.button.callback("✅ Approve", `approve_user_${user.user_id}`),
                Markup.button.callback("❌ Reject", `reject_user_${user.user_id}`)
            ]
        ]);
        
        ctx.reply(pendingList, { 
            parse_mode: 'Markdown',
            reply_markup: keyboard 
        });
        
        pendingList = ''; // Reset for next user
    });
});

bot.command('set', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.reply(`🔒 *ACCESS DENIED*

━━━━━━━━━━━━━━━━━━━━━━━━

This command requires administrator privileges.

🛡️ *Security Notice:* Unauthorized access attempts are logged.`, { parse_mode: 'Markdown' });
        return;
    }
    
    const parts = ctx.message.text.split(' ');
    if (parts.length < 2) {
        const usageText = `🎯 *ADMIN TOOL: USER MANAGEMENT*

━━━━━━━━━━━━━━━━━━━━━━━━

📝 *Usage:* \`/set <user_id>\`

📋 *Example:* \`/set 123456789\`

🔍 *Description:* Modify user profile fields and financial data.

━━━━━━━━━━━━━━━━━━━━━━━━

💡 Use /users to see registered user IDs`;
        
        await ctx.reply(usageText, { parse_mode: 'Markdown' });
        return;
    }
    
    const targetId = parseInt(parts[1]);
    if (isNaN(targetId)) {
        await ctx.reply("❌ Invalid user ID format. Must be numeric.");
        return;
    }
    
    const row = await getUser(targetId);
    if (!row) {
        await ctx.reply("❌ User not found in database. User must /start first.");
        return;
    }
    
    const keyboard = Markup.inlineKeyboard([
        [
            Markup.button.callback("💰 Total IDO", `setfield_${targetId}_total_ido`),
            Markup.button.callback("💵 Investment", `setfield_${targetId}_total_investment`)
        ],
        [
            Markup.button.callback("🎯 Payout", `setfield_${targetId}_total_payout`),
            Markup.button.callback("🔗 EVM Wallet", `setfield_${targetId}_evm_wallet`)
        ],
        [Markup.button.callback("👑 Approval Status", `setfield_${targetId}_approved`)]
    ]);
    
    const userInfo = `👤 *USER MANAGEMENT PANEL*

━━━━━━━━━━━━━━━━━━━━━━━━

🆔 *User ID:* \`${targetId}\`
📛 *Name:* ${escapeMarkdown(row.name)}
📧 *Username:* @${escapeMarkdown(row.username || 'N/A')}
✅ *Approved:* ${row.approved ? 'Yes ✅' : 'No ❌'}

━━━━━━━━━━━━━━━━━━━━━━━━

Select field to modify:`;
    
    await ctx.reply(userInfo, {
        parse_mode: 'Markdown',
        reply_markup: keyboard
    });
});

bot.command('stats', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) return;
    
    const stats = await getUserStats();
    const approvalRate = ((stats.approved / stats.total) * 100).toFixed(1);
    
    const statsText = `📊 *SYSTEM STATISTICS*

━━━━━━━━━━━━━━━━━━━━━━━━

👥 *User Analytics:*
• 👤 Total Users: \`${stats.total}\`
• ✅ Approved: \`${stats.approved}\`
• ⏳ Pending: \`${stats.pending}\`

📈 *Platform Metrics:*
• 🎯 Approval Rate: \`${approvalRate}%\`
• 🔄 Growth: Monitoring
• 🛡️ Security: Active

━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Admin Tools:*
• /admin - Admin panel
• /users - View all users
• /pending - Pending approvals
• /broadcast - Send announcements
• /set - Manage user data`;
    
    await ctx.reply(statsText, { parse_mode: 'Markdown' });
});

// Broadcast system
bot.command('broadcast', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.reply("🔒 Administrator access required.");
        return;
    }
    
    const broadcastInfo = `📢 *BROADCAST MANAGEMENT*

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

Please send your broadcast content now...`;
    
    await ctx.reply(broadcastInfo, { parse_mode: 'Markdown' });
    broadcastState.set(ctx.from.id, true);
});

async function handleBroadcastContent(ctx) {
    if (ctx.from.id !== ADMIN_ID) {
        broadcastState.delete(ctx.from.id);
        return;
    }
    
    broadcastState.delete(ctx.from.id);
    
    const processingMsg = await ctx.reply("🚀 *Starting broadcast process...*", { parse_mode: 'Markdown' });
    
    const userIds = await getAllApprovedUsers();
    
    const contactKeyboard = Markup.inlineKeyboard([
        [Markup.button.url("💬 Contact Support", "https://t.me/Symbioticl")]
    ]);
    
    let success = 0;
    let failed = 0;
    const totalUsers = userIds.length;
    
    let progressMsg = await ctx.reply(`📊 *Broadcast Progress:* 0/${totalUsers}`, { parse_mode: 'Markdown' });
    
    for (let i = 0; i < userIds.length; i++) {
        const uid = userIds[i];
        try {
            if (ctx.message.text) {
                await ctx.telegram.sendMessage(uid, ctx.message.text, {
                    parse_mode: 'Markdown',
                    reply_markup: contactKeyboard.reply_markup
                });
            } else if (ctx.message.photo) {
                await ctx.telegram.sendPhoto(uid, ctx.message.photo[ctx.message.photo.length - 1].file_id, {
                    caption: ctx.message.caption || "",
                    parse_mode: 'Markdown',
                    reply_markup: contactKeyboard.reply_markup
                });
            } else if (ctx.message.video) {
                await ctx.telegram.sendVideo(uid, ctx.message.video.file_id, {
                    caption: ctx.message.caption || "",
                    parse_mode: 'Markdown',
                    reply_markup: contactKeyboard.reply_markup
                });
            } else if (ctx.message.document) {
                await ctx.telegram.sendDocument(uid, ctx.message.document.file_id, {
                    caption: ctx.message.caption || "",
                    parse_mode: 'Markdown',
                    reply_markup: contactKeyboard.reply_markup
                });
            } else if (ctx.message.audio) {
                await ctx.telegram.sendAudio(uid, ctx.message.audio.file_id, {
                    caption: ctx.message.caption || "",
                    parse_mode: 'Markdown',
                    reply_markup: contactKeyboard.reply_markup
                });
            } else {
                await ctx.forwardMessage(uid);
            }
            
            success++;
            
            if (i % 10 === 0 || i === userIds.length - 1) {
                await ctx.telegram.editMessageText(
                    ctx.chat.id,
                    progressMsg.message_id,
                    null,
                    `📊 *Broadcast Progress:* ${i + 1}/${totalUsers}\n✅ Success: ${success} | ❌ Failed: ${failed}`,
                    { parse_mode: 'Markdown' }
                );
            }
            
            await sleep(100);
        } catch (error) {
            failed++;
            await sleep(200);
        }
    }
    
    const reportText = `📢 *BROADCAST COMPLETED*

━━━━━━━━━━━━━━━━━━━━━━━━

📊 *Delivery Report:*
• ✅ Successful: ${success}
• ❌ Failed: ${failed} 
• 📈 Success Rate: ${((success / totalUsers) * 100).toFixed(1)}%

🎯 *Target Audience:* Approved Members
🕒 *Completion Time:* ${new Date().toLocaleTimeString()}

━━━━━━━━━━━━━━━━━━━━━━━━

📋 *Next Steps:*
• Monitor engagement metrics
• Respond to member inquiries
• Plan follow-up communications`;
    
    await ctx.deleteMessage(progressMsg.message_id);
    await ctx.deleteMessage(processingMsg.message_id);
    await ctx.reply(reportText, { parse_mode: 'Markdown' });
}

// ========== CALLBACK HANDLERS ==========
bot.action(/approve_user_(\d+)/, async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.answerCbQuery("🔒 Administrator access required.");
        return;
    }
    
    const targetId = parseInt(ctx.match[1]);
    await setUserField(targetId, "approved", "1");
    
    try {
        const approvalText = `🎉 *MEMBERSHIP APPROVED!*

━━━━━━━━━━━━━━━━━━━━━━━━

✅ *Congratulations!* Your membership has been approved by our administration team.

🚀 *What's Next:*
• Full access to platform features
• Real-time announcements  
• Investment opportunities
• Community privileges

📊 Use /profile to view your complete dashboard

💬 Need help? Contact: @Symbioticl`;
        
        await ctx.telegram.sendMessage(targetId, approvalText, { parse_mode: 'Markdown' });
        await sendSuccessAnimation({ ...ctx, chat: { id: targetId } }, "Member");
    } catch (error) {
        console.error("Failed to notify user:", error);
    }
    
    await ctx.answerCbQuery("✅ Member approved successfully!");
    await ctx.editMessageText(
        `✅ *APPROVED*\n\nUser \`${targetId}\` has been granted full membership access.`,
        { parse_mode: 'Markdown' }
    );
});

bot.action(/reject_user_(\d+)/, async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.answerCbQuery("🔒 Administrator access required.");
        return;
    }
    
    const targetId = parseInt(ctx.match[1]);
    await setUserField(targetId, "approved", "0");
    
    try {
        const rejectionText = `❌ *MEMBERSHIP DECLINED*

━━━━━━━━━━━━━━━━━━━━━━━━

We regret to inform you that your membership request has been declined.

📋 *Possible Reasons:*
• Incomplete profile information
• Security concerns
• Platform capacity limits

💡 *Note:* You may reapply after 30 days or contact support for clarification.

💬 Support: @Symbioticl`;
        
        await ctx.telegram.sendMessage(targetId, rejectionText, { parse_mode: 'Markdown' });
    } catch (error) {
        console.error("Failed to notify user:", error);
    }
    
    await ctx.answerCbQuery("❌ Membership request rejected");
    await ctx.editMessageText(
        `❌ *REJECTED*\n\nUser \`${targetId}\` membership request has been declined.`,
        { parse_mode: 'Markdown' }
    );
});

// Set field handlers
bot.action(/setfield_(\d+)_(.+)/, async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.answerCbQuery("Access denied");
        return;
    }
    
    const targetId = parseInt(ctx.match[1]);
    const field = ctx.match[2];
    
    // Store the field we're setting
    ctx.session = ctx.session || {};
    ctx.session.setField = { targetId, field };
    
    let fieldName = '';
    switch(field) {
        case 'total_ido': fieldName = 'Total IDO'; break;
        case 'total_investment': fieldName = 'Total Investment'; break;
        case 'total_payout': fieldName = 'Total Payout'; break;
        case 'evm_wallet': fieldName = 'EVM Wallet'; break;
        case 'approved': fieldName = 'Approval Status'; break;
    }
    
    await ctx.reply(`Please enter the new value for *${fieldName}* for user ${targetId}:`, { 
        parse_mode: 'Markdown' 
    });
    
    await ctx.answerCbQuery();
});

// Handle set field values
bot.on('text', async (ctx) => {
    // Check if we're in set field mode
    if (ctx.session && ctx.session.setField && ctx.from.id === ADMIN_ID) {
        const { targetId, field } = ctx.session.setField;
        const value = ctx.message.text;
        
        await setUserField(targetId, field, value);
        
        delete ctx.session.setField;
        
        await ctx.reply(`✅ Successfully updated user ${targetId}'s ${field} to: ${value}`);
        return;
    }
});

bot.action('refresh_profile', async (ctx) => {
    const userId = ctx.from.id;
    const row = await getUser(userId);
    const profileText = profileTextFromRow(row);
    
    const keyboard = Markup.inlineKeyboard([
        [
            Markup.button.callback("🔄 Refresh", "refresh_profile"),
            Markup.button.callback("📊 Statistics", "view_stats")
        ],
        [Markup.button.url("💬 Support", "https://t.me/Symbioticl")]
    ]);
    
    await ctx.editMessageText(profileText, {
        parse_mode: 'Markdown',
        reply_markup: keyboard
    });
    await ctx.answerCbQuery("✅ Profile refreshed!");
});

bot.action('view_stats', async (ctx) => {
    const statsText = `📊 *PERSONAL STATISTICS*

━━━━━━━━━━━━━━━━━━━━━━━━

🎯 *Coming Soon:*
• Investment portfolio
• ROI analytics  
• Performance metrics
• Growth charts

━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *Premium features are under development and will be available soon!*

💡 Stay tuned for updates!`;
    
    await ctx.answerCbQuery();
    await ctx.reply(statsText, { parse_mode: 'Markdown' });
});

// ========== START BOT ==========
console.log("🚀 Symbiotic AI Bot Starting...");
console.log("📊 Database Initialized");
console.log("🛡️ Security Systems Active");

// Add session support for admin commands
bot.use((ctx, next) => {
    ctx.session = ctx.session || {};
    return next();
});

bot.launch().then(() => {
    console.log('🤖 Bot is running successfully!');
}).catch(err => {
    console.error('❌ Error starting bot:', err);
});

// Enable graceful stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
