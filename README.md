# Shanmukh's WhatsApp AI Assistant

## Overview
This project is a fully automated, intelligent WhatsApp AI assistant designed to act as a proxy when Shanmukh is unavailable. It intercepts incoming WhatsApp messages, understands the context and language (English or Tenglish), and responds naturally using NVIDIA's powerful `qwen/qwen3.5-122b-a10b` Large Language Model.

Unlike standard auto-responders, this bot:
1. Maintains full conversational memory (history) for each contact individually.
2. Handles real-time rapid texting by "sitting" inside active chats to provide instant replies.
3. Automatically detects and ignores group chats, communities, and channels.
4. Simulates human typing and reading delays to avoid spam detection.
5. Employs advanced clipboard-pacing logic to prevent half-sent messages or missing emojis.

---

## Project Structure
* `main.py`: The entry point. Handles the main execution loop and gracefully shuts down the browser upon exit.
* `whatsapp_listener.py`: The core Selenium web-scraper. It interacts with the WhatsApp Web DOM, clicks on chats, reads messages, checks chat states, and safely sends replies via OS clipboard shortcuts.
* `ai_engine.py`: The "brain" of the bot. Manages the REST API connection to NVIDIA, retains memory of previous messages per user, executes the System Prompt instructions, and generates the contextual text reply.
* `config.py`: Centralized configuration variables (timeouts, intervals) and API key exports.
* `utils.py`: Helper functions—specifically the logging setup and the `random_delay()` generator to mimic human interaction times.
* `.env`: A hidden secrets file containing your authentications (e.g. `NVIDIA_API_KEY`).

---

## How It Works: The Full Lifecycle

### 1. Initialization (`main.py` -> `whatsapp_listener.py`)
When you start the bot by running `python main.py`, it launches a Google Chrome browser instance running headless under the hood using Selenium. It navigates to WhatsApp Web. Notably, it uses a persistent Chrome profile (`/chrome_profile` directory) so that you do not have to scan the QR code with your phone every time you restart the script.

### 2. The Main Scanning Loop (`check_for_unread_messages`)
Once WhatsApp loads successfully, the script enters an infinite loop, parsing the screen every 3 seconds:
* **Passive Open Chat Check:** First, it checks the large chat panel actively open on the right side of the screen. Because WhatsApp *removes* the "green unread badge" if a chat window is already selected, the bot parses the open chat history to verify if the contact sent a brand-new message while the bot was idling.
* **Sidebar Badge Scanning:** Next, it scans the left-side contacts list for the classic green "unread message" badges (by looking into the raw HTML for `aria-label` elements containing the phrase "unread message"). 

### 3. Processing a Chat (`process_chat`)
If a new message is detected, the bot clicks the contact in the sidebar to open their chat panel.
* **Group Check:** It verifies the chat header. If it detects group SVGs, community icons, or words like "group/channel" in the title, it immediately aborts. (This prevents the bot from spamming massive group chats).
* **Message Extraction:** It scrapes the very last text bubble from the screen under the `message-in` CSS class. 
* **Deduplication Validation:** It stores this exact message text paired with the contact's name in a tracking variable (`self.replied_messages` and `self.last_active_message`) to guarantee it never answers the same exact text bubble twice if the screen refreshes.

### 4. AI Generation (`ai_engine.py`)
The text is passed to the AI Engine pipeline.
* The engine checks its dictionary to retrieve the user's specific array of chat history (so it remembers what it said 10 minutes ago).
* It appends the newly scraped text and sends the bundle via a REST POST request to NVIDIA's API endpoint. 
* The AI is directed by a powerful **System Prompt** to act as a friendly, highly intelligent proxy assistant (using Tenglish slang if needed) and to actively answer questions naturally rather than repeating robotic "Shanmukh is busy" phrases. 

### 5. Sending the Message (`whatsapp_listener.send_message`)
Once the AI generates a paragraph reply, it executes a highly supervised mechanism to type it out:
* ChromeDriver normally cannot natively type Emojis (it crashes on characters outside the Basic Multilingual Plane). To bypass this gracefully, the bot copies the AI text directly to your Windows OS clipboard using the `pyperclip` library.
* **Race Condition Verification:** Windows clipboards are notoriously slow. The bot loops `pyperclip.paste() == line` to actively verify the OS clipboard was successfully populated *before* commanding Chrome to press `CONTROL + V`. This is what prevents the AI messages from being cut off mid-word (truncated).
* **Multi-line Formatting:** It splits multi-paragraph AI responses up and uses `SHIFT + ENTER` to type out line-breaks natively into one big chat bubble, then executes a final hard `ENTER` to physically send it.

### 6. Active Monitoring (The 30-Second Loop)
After a message successfully sends, the bot doesn't immediately leave. It *stays* inside that contact's chat panel for 30 seconds.
* It loops every 2 seconds watching the screen for an immediate text back (i.e. rapid texting).
* If the user replies instantly within the 30-second window, the bot catches it, replies naturally again without needing to click the sidebar, and resets its 30-second timer to keep talking. 
* If 30 full seconds pass in silence, OR if another green badge pops up in the left sidebar from someone else waiting, the bot actively exits the chat loop and returns to Phase 2 (Scanning) to handle other people.

---

## Technical Setup & Execution

1. Build dependencies: `pip install -r requirements.txt` (Installs Selenium, WebDriver Manager, Requests, Dotenv)
2. Create the `.env` file in the root directory and map your key:
   `NVIDIA_API_KEY=nvapi-your-key-here`
3. Start the process: `python main.py`
4. Scan the QR code (first run only). Leave the terminal window operating securely in the background. Press `Ctrl+C` in the terminal to invoke a safe exit that shuts down the driver cleanly.
