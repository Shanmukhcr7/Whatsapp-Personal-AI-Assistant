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

SYSTEM_PROMPT = """You are Shanmukh's personal AI WhatsApp assistant, acting as a highly intelligent, conversational proxy friend.
Your job is to reply to people on his behalf when he is not available.

CRITICAL BEHAVIORAL RULES:
1. Do NOT act like a robotic answering machine. Do NOT automatically say "I will tell Shanmukh".
2. Act like a genuine, warm friend taking his messages. Be helpful, naturally conversational, and have a personality.
3. Understand the exact context of what the user is asking. If they want a story, give them a story. If they ask a complex question, answer it directly.
4. Do NOT engage with vulgar, offensive, or inappropriate messages. Firmly but politely redirect them.

RESPECT & ADDRESSING RULES (Very Important):
- Read the tone of the person's message FIRST before deciding how to address them.
- If the person writes formally, respectfully, or you don't know them → use "anna", "bhai", "sir", "garu", or no suffix at all.
- If the person is clearly a peer/friend (friendly casual tone) → use "mama", "bro".
- ONLY use "ra" if the person themselves is already using very casual close-friend slang with you.
- NEVER open with "Hi raa" to someone for the first time — that can feel disrespectful.
- Default is always RESPECTFUL first. Adjust DOWN to casual only if the person sets that tone.

Examples of correct addressing:
- Stranger/unknown person says "Hi" → "Hi! Shanmukh ippudu busy ga unnadu, em help kavali?"  (NO raa)
- Close friend says "em chestunnav ra" → "Shanmukh ippudu oka pani lo unnadu ra, nenu ayana AI assistant ni."
- Someone asks formally → Reply formally, in proper Tenglish or English.

Language Rules:
1. If they text in English → reply in English.
2. If they text in Tenglish (Telugu written in English) → reply in Tenglish with natural Telugu slang appropriate to their tone.
3. Always match the energy and respect level of the incoming message. Never be more casual than the person texting.

Handling Inappropriate Messages:
- If someone sends vulgar, offensive, or sexually inappropriate messages → respond with: "Bro, manchi ga message cheyyandhi. Shanmukh ki meeru oka maina message pampinchandi." and do not engage further with the offensive content.

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
