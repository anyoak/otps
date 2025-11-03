# Telegram Bot Configuration
BOT_TOKEN = "8522542742:AAHr7nwP7BBTfOLFBLemRhn4bDe5bySoaIc"  # Your Telegram Bot Token from @BotFather
CHAT_ID = "-1002631004312"     # Your Telegram Group/Chat ID

# Orange Carrier URLs
BASE_URL = "https://www.orangecarrier.com"
LOGIN_URL = "https://www.orangecarrier.com/login"
CALL_URL = "https://www.orangecarrier.com/live/calls"

# Download Settings
DOWNLOAD_FOLDER = "downloads"  # Folder to store temporary recordings

# Monitoring Settings
CHECK_INTERVAL = 3  # Seconds between checks for new calls (reduced for faster response)
MAX_ERRORS = 10     # Maximum consecutive errors before stopping

# Recording Settings
RECORDING_DURATION = 30000  # Duration to record audio in milliseconds (30 seconds)
RECORDING_TIMEOUT = 35      # Seconds to wait for recording to complete

# Audio Settings
AUDIO_FORMAT = "audio/mp3"  # Format for recorded audio

# Browser Settings (for SeleniumBase)
BROWSER_HEADLESS = False  # Set to True if you want to run without browser window
BROWSER_INCOGNITO = True  # Use incognito mode for better isolation

# Retry Settings
MAX_RETRY_ATTEMPTS = 3    # Maximum number of retry attempts for downloads
RETRY_DELAY = 2           # Seconds to wait between retries

# Telegram API Settings
TELEGRAM_TIMEOUT = 60     # Timeout for Telegram API requests
