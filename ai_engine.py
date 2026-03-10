import requests
from config import NVIDIA_API_KEY
from utils import get_logger

logger = get_logger(__name__)

if not NVIDIA_API_KEY or NVIDIA_API_KEY == "your_nvidia_api_key_here":
    logger.warning("NVIDIA_API_KEY is not set correctly in the .env file. The AI might not work.")

# We will maintain conversation history manually since we are using a REST API directly
# active_chats will map contact_name -> list of message dicts: [{"role": "user"/"assistant", "content": "..."}]
active_chats = {}

# We enforce a maximum history length to prevent token explosion
MAX_HISTORY_LEN = 20

# We use the Qwen 3.5 122B model as requested by user
NVIDIA_MODEL = "qwen/qwen3.5-122b-a10b"
NVIDIA_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

SYSTEM_PROMPT = """You are Shanmukh's personal AI WhatsApp assistant.
Your job is to reply to people on his behalf when he is not available.

TONE & RESPECT (This is the MOST important rule):
- ALWAYS be respectful and polite. No exceptions.
- NEVER use casual terms like "ra", "mama", "da" unless the person first uses those exact terms with you.
- Default address for EVERY person = neutral and polite. Use "bhai", "anna", "sir", or just no suffix at all.
- Only mirror the person's casualness if they are explicitly casual first.
- Think of yourself as Shanmukh's polite, well-mannered personal assistant — not a casual friend.

Examples of CORRECT respectful replies:
- Someone says "Hi" → "Hi! Shanmukh garu ippudu busy ga unnaru. Meeru oka message vadili vellandi, nenu theesukuntanu."
- Someone says "em chestunnav ra" (casual) → only THEN you can reply "Shanmukh ippudu busy ga unnadu, nenu ayana assistant ni."
- Someone says "Hello sir" → "Hello! Shanmukh sir ippudu available kadu, meeru oka message vadili pothe, ayana tarvata connect avutadu."

BEHAVIORAL RULES:
1. Do NOT act like a robotic answering machine. Be warm and helpful.
2. Do NOT just say "I will tell Shanmukh" — keep the conversation going naturally.
3. If someone asks a question, try to answer it helpfully. If you can't, acknowledge it and say Shanmukh will reply.
4. Do NOT engage with vulgar or offensive messages. Respond with: "Meeru manchi ga message cheyyandi. Shanmukh ki meeru oka proper message pampinchand." and do not continue with the offensive topic.

Handling Non-Text Messages (images, stickers, voice notes, videos):
- If the incoming message is "[sent a photo/sticker/voice note/video]", acknowledge it politely.
- Example: "Meeru oka media message pampincharu. Shanmukh ippudu busy ga unnaru, ayana tarvata chusatadu."
- Or in English: "I see you've sent a media message. Shanmukh will check it as soon as he's free!"

Language Rules:
1. If they text in English → reply in English, politely.
2. If they text in Tenglish (Telugu written in English) → reply in Tenglish, respectfully.
3. ALWAYS match or exceed the politeness level of the incoming message. Never be MORE casual than them.

Ending Signature Rule (MANDATORY ON EVERY MESSAGE AT THE VERY END):
Always end every single message with one of these short lines:
- "This is Shanmukh's personal AI assistant." (if speaking in English)
- "Idi Shanmukh personal AI assistant." (if speaking in Tenglish)"""


def get_or_create_chat(contact_name):
    """Retrieves an existing chat session history for a contact, or creates a new one."""
    if contact_name not in active_chats:
        logger.info(f"Starting new AI chat session for '{contact_name}'")
        # Initialize with the system prompt
        active_chats[contact_name] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return active_chats[contact_name]

def trim_history(history):
    """Keeps the system prompt but trims the oldest messages to avoid token limit overflow."""
    if len(history) > MAX_HISTORY_LEN:
        # Keep the system prompt at index 0, but slice the oldest user/assistant messages
        return [history[0]] + history[-(MAX_HISTORY_LEN - 1):]
    return history

def generate_reply(incoming_message, contact_name="Unknown"):
    """
    Generates an AI reply using Nvidia's REST API.
    Maintains conversation history manually.
    """
    if not NVIDIA_API_KEY:
        logger.error("NVIDIA API key is not initialized. Cannot generate reply.")
        return "Sorry, Shanmukh's assistant is currently offline."
    
    try:
        logger.info(f"Sending message from '{contact_name}' to AI: '{incoming_message}'")
        
        history = get_or_create_chat(contact_name)
        
        # Append the new user message
        history.append({"role": "user", "content": incoming_message})
        
        # Prevent context from growing infinitely
        history = trim_history(history)
        active_chats[contact_name] = history
        
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json"
        }

        payload = {
            "model": NVIDIA_MODEL,
            "messages": history,
            "max_tokens": 1024,
            "temperature": 0.60,
            "top_p": 0.95,
            "stream": False,
        }
        
        response = requests.post(NVIDIA_INVOKE_URL, headers=headers, json=payload, timeout=45)
        
        if response.status_code == 200:
            data = response.json()
            reply = data["choices"][0]["message"]["content"].strip()
            
            # Save assistant response to history
            history.append({"role": "assistant", "content": reply})
            
            # Enforce suffix if the model forgot it
            suffix_en = "This is Shanmukh's personal AI assistant."
            suffix_te = "Idi Shanmukh personal AI assistant."
            if suffix_en not in reply and suffix_te not in reply:
                reply += f"\n\n{suffix_en}"
                
            logger.info(f"Generated AI reply: '{reply}'")
            return reply
        else:
            logger.error(f"NVIDIA API Error: {response.status_code} - {response.text}")
            return "Shanmukh is currently unavailable. This is an automated message."
        
    except Exception as e:
        logger.error(f"Error generating AI reply: {e}")
        return "Shanmukh is currently unavailable. This is an automated message."
