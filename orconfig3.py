# Telegram Bot Configuration
BOT_TOKEN = "8354581009:AAH28Cn3VQAdmQYb8a9q7WNEIly7x7s8moM"  # Get from @BotFather
CHAT_ID = "-1002631004312"  # Your Telegram group/channel ID

# Orange Carrier Website URLs
LOGIN_URL = "https://www.orangecarrier.com/login"
CALL_URL = "https://www.orangecarrier.com/live/calls"
BASE_URL = "https://www.orangecarrier.com"

# File Storage Configuration
DOWNLOAD_FOLDER = "recordings"  # Folder to temporarily store recordings

# Monitoring Settings
CHECK_INTERVAL = 10  # Seconds between checks for new calls
MAX_ERRORS = 10  # Maximum consecutive errors before stopping

# Recording Download Settings
RECORDING_RETRY_DELAY = 30  # Seconds between recording download attempts
MAX_RECORDING_WAIT = 600  # Maximum seconds to wait for recording (10 minutes)

# Optional: Advanced Settings
MAX_RECORDING_CHECKS = 20  # Maximum number of recording download attempts
