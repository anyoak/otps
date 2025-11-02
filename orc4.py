# config.py
LOGIN_URL = "https://www.orangecarrier.com/login"
CALL_URL = "https://www.orangecarrier.com/live/calls" 
BASE_URL = "https://www.orangecarrier.com"
BOT_TOKEN = "your_bot_token"
CHAT_ID = "your_chat_id"
DOWNLOAD_FOLDER = "recordings"
CHECK_INTERVAL = 5
MAX_ERRORS = 10
RECORDING_RETRY_DELAY = 10
MAX_RECORDING_WAIT = 300  # 5 minutes maximum wait for recording

# Additional settings for better performance
ACTIVITY_CHECK_URL = "https://www.orangecarrier.com/live/calls/activity"