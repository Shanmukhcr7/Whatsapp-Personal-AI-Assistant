import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# WhatsApp Automation Config
WEB_WHATSAPP_URL = "https://web.whatsapp.com"

# How often to check for new messages (in seconds)
MESSAGE_SCAN_INTERVAL = 3  

# Minimum and Maximum delay before replying (Anti-spam safety)
REPLY_DELAY_MIN = 10  # seconds
REPLY_DELAY_MAX = 25  # seconds
