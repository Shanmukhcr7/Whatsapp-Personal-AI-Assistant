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

# ─────────────────────────────────────────────────────────────────
# IGNORED GROUPS — add exact or partial WhatsApp group names here.
# The bot will NEVER reply in any chat whose name CONTAINS one of
# these strings (case-insensitive). Add as many as you like.
# ─────────────────────────────────────────────────────────────────
IGNORED_GROUPS = [
    # Full Names
    "AI & AIML 2027 placements group",
    "AI-2027",
    "AI-B students(2023-27)",
    "cryptography III-II,AI-B",
    "IgniteXT X GITHUB",
    "AI & AIML Men Annual Sports",
    "TBCS(AI-A&B) 3rd yr",
    
    # Catch-all partials based on the user's groups
    "AI & AIML",
    "AI-B",
    "AI-A",
    "placements group",
]
