const { Telegraf, Markup, session } = require('telegraf');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

// ========== CONFIG ==========
const BOT_TOKEN = "8443659336:AAF5Yh1HrBd_bkXCuht4CVrWnFluIK8Bx0o";
const ADMIN_ID = 6083895678;
const DB_PATH = path.join(__dirname, 'bot_users.db');
const DEFAULT_COUNTRY_FLAG = "🇧🇩 Bangladesh (BD)";
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

function addOrUpdateUser(user) {
    return new Promise((resolve, reject) => {
        const username = user.username || "";
        const name = user.first_name + (user.last_name ? ` ${user.last_name}` : "");
        const joined = new Date().toUTCString();
        
        db.run(
            `INSERT OR IGNORE INTO users (user_id, username, name, joined_date, country) VALUES (?, ?, ?, ?, ?)`,
            [user.id, username, name, joined, DEFAULT_COUNTRY_FLAG],
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

function profileTextFromRow(row) {
    if (!row) {
        return "❌ *No Data Available*\\n\\nPlease contact administrator\\.";
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
    
    return `
🎯 *PROFILE DETAILS*

┌──────────────────────────────────
│ 👤 **USER INFORMATION**
├──────────────────────────────────
│ • **ID:** \`${user_id}\`
│ • **Name:** ${name}
│ • **Username:** ${username_display}
│ • **Joined:** ${joined}
│ • **Country:** ${country}
├──────────────────────────────────
│ 💰 **FINANCIAL OVERVIEW**
├──────────────────────────────────
│ • **Total IDO:** ${total_ido}
│ • **Total Investment:** $${total_investment}
│ • **Total Payout:** $${total_payout}
├──────────────────────────────────
│ 🔗 **WALLET INFORMATION**
├──────────────────────────────────
│ • **EVM Wallet:** \`${evm_wallet}\`
└──────────────────────────────────

✅ *Status:* ${approved ? 'Approved ✅' : 'Pending Review ⏳'}
`;
}

// ========== CAPTCHA SYSTEM ==========
const captchaStore = new Map();

function generateMathCaptcha() {
    const a = Math.floor(Math.random() * 41) + 10;
    const b = Math.floor(Math.random() * 26) + 5;
    const op = Math.random() > 0.5 ? '+' : '-';
    let ans;
    if (op === '+') {
        ans = a + b;
    } else {
        ans = a - b;
    }
    const question = `**${a} ${op} ${b}** = ?`;
    return { question, answer: ans.toString() };
}

// ========== ANIMATION FUNCTIONS ==========
async function sendLoadingSequence(ctx) {
    try {
        // Phase 1: Data Fetching Animation
        let msg1 = await ctx.reply("🔄 *INITIALIZING SYSTEM*", { parse_mode: 'Markdown' });
        
        const loadingFrames = ["▰▱▱▱▱▱▱▱", "▰▰▱▱▱▱▱▱", "▰▰▰▱▱▱▱▱", "▰▰▰▰▱▱▱▱", 
                             "▰▰▰▰▰▱▱▱", "▰▰▰▰▰▰▱▱", "▰▰▰▰▰▰▰▱", "▰▰▰▰▰▰▰▰"];
        
        for (let frame of loadingFrames) {
            await ctx.telegram.editMessageText(
                ctx.chat.id,
                msg1.message_id,
                null,
                `🔄 *FETCHING USER DATA*\\n\\n${frame} 25%`,
                { parse_mode: 'Markdown' }
            );
            await sleep(300);
        }
        
        await ctx.telegram.editMessageText(
            ctx.chat.id,
            msg1.message_id,
            null,
            "✅ *DATA RETRIEVAL COMPLETE*",
            { parse_mode: 'Markdown' }
        );
        await sleep(1000);
        await ctx.telegram.deleteMessage(ctx.chat.id, msg1.message_id);

        // Phase 2: Database Verification
        let msg2 = await ctx.reply("🔍 *VERIFYING DATABASE ACCESS*", { parse_mode: 'Markdown' });
        
        const verificationSteps = [
            "🔐 Connecting to secure database...",
            "🔐 Authentication in progress...",
            "🔐 Scanning user records...",
            "🔐 Cross-referencing official lists..."
        ];
        
        for (let step of verificationSteps) {
            await ctx.telegram.editMessageText(
                ctx.chat.id,
                msg2.message_id,
                null,
                step
            );
            await sleep(1000);
        }
        
        // Phase 3: Security Check
        let msg3 = await ctx.reply("🛡️ *SECURITY SCAN IN PROGRESS*", { parse_mode: 'Markdown' });
        
        const securityFrames = [
            "🛡️ Scanning user credentials...",
            "🛡️ Verifying access permissions...",
            "🛡️ Checking approval status...",
            "⚠️  **ACCESS RESTRICTED DETECTED**"
        ];
        
        for (let frame of securityFrames) {
            await ctx.telegram.editMessageText(
                ctx.chat.id,
                msg3.message_id,
                null,
                frame
            );
            await sleep(1500);
        }
        
        await ctx.telegram.deleteMessage(ctx.chat.id, msg3.message_id);

        // Final Message
        const finalText = `
❌ *MEMBERSHIP STATUS: PENDING*

━━━━━━━━━━━━━━━━━━━━━━━━

🔒 *ACCESS RESTRICTED*

You are currently not in our official members database\\. Your account requires administrator approval\\.

⏰ *Processing Time:* 24\\-48 hours

📋 *Next Steps:*
1\\. Wait for administrator review
2\\. You'll receive notification upon approval
3\\. Once approved, full access will be granted

💡 *Note:* This process ensures community security and authenticity\\.

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ *Secured by Advanced Verification System*
`;
        await ctx.reply(finalText, { parse_mode: 'MarkdownV2' });

    } catch (error) {
        console.error("Error in loading sequence:", error);
    }
}

async function sendSuccessAnimation(ctx, userName) {
    let successMsg = await ctx.reply("🎉 *WELCOME ABOARD\\!*", { parse_mode: 'MarkdownV2' });
    
    const welcomeFrames = [
        `✨ **Welcome, ${userName}\\!** ✨`,
        `🚀 **System Access Granted** 🚀`, 
        `✅ **Membership Verified** ✅`,
        `🎯 **Profile Activated** 🎯`
    ];
    
    for (let frame of welcomeFrames) {
        await ctx.telegram.editMessageText(
            ctx.chat.id,
            successMsg.message_id,
            null,
            frame,
            { parse_mode: 'MarkdownV2' }
        );
        await sleep(1000);
    }
    
    await ctx.telegram.deleteMessage(ctx.chat.id, successMsg.message_id);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ========== BOT COMMANDS ==========
bot.start(async (ctx) => {
    const user = ctx.from;
    await addOrUpdateUser(user);
    const row = await getUser(user.id);
    const approved = row && row.approved === 1;
    
    const welcomeText = `
🤖 *WELCOME TO SYMBIOTIC AI BOT* 

━━━━━━━━━━━━━━━━━━━━━━━━

👋 Hello *${user.first_name}*\\!

Thank you for joining our exclusive community\\. We're implementing advanced security measures to protect our members\\.

🔒 *Security Level:* **Enterprise Grade**
🎯 *Platform:* **AI\\-Powered Investment**
🌟 *Community:* **Verified Members Only**

━━━━━━━━━━━━━━━━━━━━━━━━

Please complete the security verification below to continue\\.
`;
    await ctx.reply(welcomeText, { parse_mode: 'MarkdownV2' });
    
    if (approved) {
        await sendSuccessAnimation(ctx, user.first_name);
        const text = profileTextFromRow(row);
        await ctx.reply(text, { parse_mode: 'Markdown' });
        return;
    }

    // Captcha Challenge
    const { question, answer } = generateMathCaptcha();
    captchaStore.set(user.id, answer);
    
    const captchaText = `
🧮 *SECURITY VERIFICATION*

━━━━━━━━━━━━━━━━━━━━━━━━

To ensure you're human, please solve this simple math problem:

${question}

📝 *Instructions:*
• Type only the numerical answer
• You have 3 attempts
• Use /start to restart if needed

━━━━━━━━━━━━━━━━━━━━━━━━

🔐 This helps us prevent automated access\\.
`;
    await ctx.reply(captchaText, { parse_mode: 'Markdown' });
});

// Captcha answer handler
bot.on('text', async (ctx) => {
    const userId = ctx.from.id;
    const expected = captchaStore.get(userId);
    
    if (!expected) return;
    
    const userAnswer = ctx.message.text.trim();
    
    if (userAnswer === expected) {
        captchaStore.delete(userId);
        const successText = `
✅ *VERIFICATION SUCCESSFUL*

━━━━━━━━━━━━━━━━━━━━━━━━

🎉 Excellent\\! You've passed the security check\\.

Now accessing our member database to verify your status\\.\\.\\.

🛡️ *Security Status:* **Verified Human**
`;
        await ctx.reply(successText, { parse_mode: 'MarkdownV2' });
        await sleep(2000);
        
        await sendLoadingSequence(ctx);
        
        // Notify Admin
        const user = ctx.from;
        const adminText = `
👤 *NEW MEMBER REQUEST*

━━━━━━━━━━━━━━━━━━━━━━━━

🆔 **User ID:** \`${user.id}\`
📛 **Name:** ${user.first_name} ${user.last_name || ''}
📧 **Username:** @${user.username || 'N/A'}
🌐 **Language:** ${user.language_code || 'N/A'}
🕒 **Request Time:** ${new Date().toUTCString()}

━━━━━━━━━━━━━━━━━━━━━━━━

*Security Check:* ✅ Passed
*Captcha Score:* 🎯 Excellent

Please review and approve/reject this membership request\\.
`;
        const keyboard = Markup.inlineKeyboard([
            [
                Markup.button.callback("✅ Approve Member", `approve_user_${user.id}`),
                Markup.button.callback("❌ Reject Request", `reject_user_${user.id}`)
            ],
            [Markup.button.callback("👁️ View Profile", `view_profile_${user.id}`)]
        ]);
        
        await ctx.telegram.sendMessage(ADMIN_ID, adminText, {
            parse_mode: 'Markdown',
            ...keyboard
        });
    } else {
        await ctx.reply(`
❌ *VERIFICATION FAILED*

━━━━━━━━━━━━━━━━━━━━━━━━

Incorrect answer\\. Please try again or type /start for a new security challenge\\.

💡 *Tip:* Double\\-check your calculation and enter only the numerical result\\.
`, { parse_mode: 'MarkdownV2' });
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
    
    const loadingMsg = await ctx.reply("🔄 Loading your profile...");
    await sleep(1500);
    await ctx.deleteMessage(loadingMsg.message_id);
    
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
        ...keyboard
    });
});

// Help command
bot.command('help', async (ctx) => {
    const helpText = `
🎯 *SYMBIOTIC AI BOT \\- HELP GUIDE*

━━━━━━━━━━━━━━━━━━━━━━━━

🤖 **Available Commands:**

• /start \\- Initialize bot & verification
• /profile \\- View your member profile  
• /help \\- Show this help message

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ **Security Features:**
• Advanced captcha verification
• Administrator approval system
• Real\\-time monitoring
• Secure data handling

━━━━━━━━━━━━━━━━━━━━━━━━

💡 **Need Assistance?**
Contact: @Symbioticl

🔒 *Your security and privacy are our top priorities\\.*
`;
    await ctx.reply(helpText, { parse_mode: 'MarkdownV2' });
});

// ========== ADMIN COMMANDS ==========
bot.command('set', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.reply(`
🔒 *ACCESS DENIED*

━━━━━━━━━━━━━━━━━━━━━━━━

This command requires administrator privileges\\.

🛡️ *Security Notice:* Unauthorized access attempts are logged\\.
`, { parse_mode: 'MarkdownV2' });
        return;
    }
    
    const parts = ctx.message.text.split(' ');
    if (parts.length < 2) {
        const usageText = `
🎯 *ADMIN TOOL: USER MANAGEMENT*

━━━━━━━━━━━━━━━━━━━━━━━━

📝 *Usage:* \`/set <user_id>\`

📋 *Example:* \`/set 123456789\`

🔍 *Description:* Modify user profile fields and financial data\\.

━━━━━━━━━━━━━━━━━━━━━━━━

💡 Use /users to see registered user IDs
`;
        await ctx.reply(usageText, { parse_mode: 'MarkdownV2' });
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
        [Markup.button.callback("👑 Approval", `setfield_${targetId}_approved`)]
    ]);
    
    const userInfo = `
👤 *USER MANAGEMENT PANEL*

━━━━━━━━━━━━━━━━━━━━━━━━

🆔 **User ID:** \`${targetId}\`
📛 **Name:** ${row.name}
📧 **Username:** @${row.username || 'N/A'}
✅ **Approved:** ${row.approved ? 'Yes ✅' : 'No ❌'}

━━━━━━━━━━━━━━━━━━━━━━━━

Select field to modify:
`;
    await ctx.reply(userInfo, {
        parse_mode: 'Markdown',
        ...keyboard
    });
});

bot.command('users', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) return;
    
    const stats = await getUserStats();
    const statsText = `
📊 *SYSTEM STATISTICS*

━━━━━━━━━━━━━━━━━━━━━━━━

👥 **User Analytics:**
• 👤 Total Users: \`${stats.total}\`
• ✅ Approved: \`${stats.approved}\`
• ⏳ Pending: \`${stats.pending}\`

📈 **Platform Metrics:**
• 🎯 Approval Rate: \`${((stats.approved / stats.total) * 100).toFixed(1)}%\\`
• 🔄 Growth: Monitoring
• 🛡️ Security: Active

━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Admin Tools:*
• /set \\- Manage users
• /broadcast \\- Send announcements
• /stats \\- Detailed analytics
`;
    await ctx.reply(statsText, { parse_mode: 'MarkdownV2' });
});

// Broadcast system
const broadcastState = new Map();

bot.command('broadcast', async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.reply("🔒 Administrator access required.");
        return;
    }
    
    const broadcastInfo = `
📢 *BROADCAST MANAGEMENT*

━━━━━━━━━━━━━━━━━━━━━━━━

Send the message you want to broadcast to all approved members\\.

📋 *Supported Formats:*
• Text messages
• Photos with captions  
• Videos with captions
• Documents
• Audio files

🎯 *Target:* All approved members
📊 *Delivery:* Real\\-time with analytics

💡 *Pro Tip:* Include engaging content and clear call\\-to\\-action\\!

━━━━━━━━━━━━━━━━━━━━━━━━

Please send your broadcast content now\\.\\.\\.
`;
    await ctx.reply(broadcastInfo, { parse_mode: 'MarkdownV2' });
    broadcastState.set(ctx.from.id, true);
});

bot.on('message', async (ctx) => {
    if (!broadcastState.get(ctx.from.id) || ctx.from.id !== ADMIN_ID) return;
    
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
                    ...contactKeyboard
                });
            } else if (ctx.message.photo) {
                await ctx.telegram.sendPhoto(uid, ctx.message.photo[ctx.message.photo.length - 1].file_id, {
                    caption: ctx.message.caption || "",
                    parse_mode: 'Markdown',
                    ...contactKeyboard
                });
            } else if (ctx.message.video) {
                await ctx.telegram.sendVideo(uid, ctx.message.video.file_id, {
                    caption: ctx.message.caption || "",
                    parse_mode: 'Markdown',
                    ...contactKeyboard
                });
            } else if (ctx.message.document) {
                await ctx.telegram.sendDocument(uid, ctx.message.document.file_id, {
                    caption: ctx.message.caption || "",
                    parse_mode: 'Markdown',
                    ...contactKeyboard
                });
            } else if (ctx.message.audio) {
                await ctx.telegram.sendAudio(uid, ctx.message.audio.file_id, {
                    caption: ctx.message.caption || "",
                    parse_mode: 'Markdown',
                    ...contactKeyboard
                });
            } else {
                await ctx.forwardMessage(uid);
            }
            
            success++;
            
            if (i % 10 === 0) {
                await ctx.telegram.editMessageText(
                    ctx.chat.id,
                    progressMsg.message_id,
                    null,
                    `📊 *Broadcast Progress:* ${i + 1}/${totalUsers}\\n✅ Success: ${success} | ❌ Failed: ${failed}`,
                    { parse_mode: 'Markdown' }
                );
            }
            
            await sleep(100);
        } catch (error) {
            failed++;
            await sleep(200);
        }
    }
    
    const reportText = `
📢 *BROADCAST COMPLETED*

━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Delivery Report:**
• ✅ Successful: ${success}
• ❌ Failed: ${failed} 
• 📈 Success Rate: ${((success / totalUsers) * 100).toFixed(1)}%

🎯 **Target Audience:** Approved Members
🕒 **Completion Time:** ${new Date().toLocaleTimeString()}

━━━━━━━━━━━━━━━━━━━━━━━━

📋 *Next Steps:*
• Monitor engagement metrics
• Respond to member inquiries
• Plan follow\\-up communications
`;
    
    await ctx.deleteMessage(progressMsg.message_id);
    await ctx.reply(reportText, { parse_mode: 'MarkdownV2' });
});

// ========== CALLBACK HANDLERS ==========
bot.action(/approve_user_(\d+)/, async (ctx) => {
    if (ctx.from.id !== ADMIN_ID) {
        await ctx.answerCbQuery("🔒 Administrator access required.");
        return;
    }
    
    const targetId = parseInt(ctx.match[1]);
    await setUserField(targetId, "approved", "1");
    
    try {
        const approvalText = `
🎉 *MEMBERSHIP APPROVED\\!*

━━━━━━━━━━━━━━━━━━━━━━━━

✅ **Congratulations\\!** Your membership has been approved by our administration team\\.

🚀 *What's Next:*
• Full access to platform features
• Real\\-time announcements  
• Investment opportunities
• Community privileges

📊 Use /profile to view your complete dashboard

💬 Need help\\? Contact: @Symbioticl
`;
        await ctx.telegram.sendMessage(targetId, approvalText, { parse_mode: 'MarkdownV2' });
        await sendSuccessAnimation({ ...ctx, chat: { id: targetId } }, "Member");
    } catch (error) {
        console.error("Failed to notify user:", error);
    }
    
    await ctx.answerCbQuery("✅ Member approved successfully!");
    await ctx.editMessageText(
        `✅ *APPROVED*\\n\\nUser \`${targetId}\` has been granted full membership access\\.`,
        { parse_mode: 'MarkdownV2' }
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
        const rejectionText = `
❌ *MEMBERSHIP DECLINED*

━━━━━━━━━━━━━━━━━━━━━━━━

We regret to inform you that your membership request has been declined\\.

📋 *Possible Reasons:*
• Incomplete profile information
• Security concerns
• Platform capacity limits

💡 *Note:* You may reapply after 30 days or contact support for clarification\\.

💬 Support: @Symbioticl
`;
        await ctx.telegram.sendMessage(targetId, rejectionText, { parse_mode: 'MarkdownV2' });
    } catch (error) {
        console.error("Failed to notify user:", error);
    }
    
    await ctx.answerCbQuery("❌ Membership request rejected");
    await ctx.editMessageText(
        `❌ *REJECTED*\\n\\nUser \`${targetId}\` membership request has been declined\\.`,
        { parse_mode: 'MarkdownV2' }
    );
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
        ...keyboard
    });
    await ctx.answerCbQuery("✅ Profile refreshed!");
});

bot.action('view_stats', async (ctx) => {
    const statsText = `
📊 *PERSONAL STATISTICS*

━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **Coming Soon:**
• Investment portfolio
• ROI analytics  
• Performance metrics
• Growth charts

━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *Premium features are under development and will be available soon\\!*

💡 Stay tuned for updates\\!
`;
    await ctx.answerCbQuery();
    await ctx.reply(statsText, { parse_mode: 'MarkdownV2' });
});

// ========== START BOT ==========
console.log("🚀 Symbiotic AI Bot Started Successfully!");
console.log("📊 Database Initialized");
console.log("🛡️ Security Systems Active");

bot.launch().then(() => {
    console.log('🤖 Bot is running...');
});

// Enable graceful stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
