# Telegram Bot Configuration
BOT_TOKEN = "8522542742:AAHr7nwP7BBTfOLFBLemRhn4bDe5bySoaIc"  # Your Telegram Bot Token
CHAT_ID = "-1002631004312"     # Your Telegram Group/Chat ID

# Orange Carrier URLs
BASE_URL = "https://www.orangecarrier.com"
LOGIN_URL = "https://www.orangecarrier.com/login"
CALL_URL = "https://www.orangecarrier.com/live/calls"

# Download Settings
DOWNLOAD_FOLDER = "downloads"  # Folder to store temporary recordings

# Monitoring Settings
CHECK_INTERVAL = 5  # Seconds between checks for new calls
MAX_ERRORS = 10     # Maximum consecutive errors before stopping

# Recording Settings
RECORDING_RETRY_DELAY = 10  # Seconds between recording availability checks
MAX_RECORDING_WAIT = 300    # Maximum seconds to wait for recording (5 minutes)

# Download Settings
DOWNLOAD_TIMEOUT = 60
MAX_DOWNLOAD_ATTEMPTS = 5
RETRY_DELAY = 10

# Optional: Proxy Settings (if needed)
# PROXY = {
#     "http": "http://username:password@proxy_ip:port",
#     "https": "https://username:password@proxy_ip:port"
# }
