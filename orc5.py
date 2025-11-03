# Telegram Bot Configuration
BOT_TOKEN = "8522542742:AAHr7nwP7BBTfOLFBLemRhn4bDe5bySoaIc"
CHAT_ID = "-1002631004312"

# Orange Carrier URLs
BASE_URL = "https://www.orangecarrier.com"
LOGIN_URL = "https://www.orangecarrier.com/login"
CALL_URL = "https://www.orangecarrier.com/live/calls"

# Download Settings
DOWNLOAD_FOLDER = "downloads"

# Monitoring Settings
CHECK_INTERVAL = 3
MAX_ERRORS = 10

# Recording Settings
RECORDING_DURATION = 30000
RECORDING_TIMEOUT = 35

# Audio Settings
AUDIO_FORMAT = "audio/mp3"

# Browser Settings (for SeleniumBase)
BROWSER_HEADLESS = False
BROWSER_INCOGNITO = True

# Retry Settings
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

# Telegram API Settings
TELEGRAM_TIMEOUT = 60

# Additional Requirements for new features
REQUIREMENTS = [
    "seleniumbase==4.25.0",
    "requests==2.31.0", 
    "phonenumbers==8.13.27",
    "pycountry==23.12.11",
    "schedule==1.2.0"
]