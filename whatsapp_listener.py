import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

from config import WEB_WHATSAPP_URL, IGNORED_GROUPS
from ai_engine import generate_reply
from utils import get_logger, random_delay

logger = get_logger(__name__)

class WhatsAppBot:
    def __init__(self):
        """Initializes the bot and the Chrome driver."""
        self.driver = self._init_driver()
        # Set to track already replied messages (text-based, for within a session)
        self.replied_messages = set()
        # Dict to track the message count per contact for the open-chat passive monitor.
        # Key: contact_name, Value: number of incoming messages when we last replied.
        self.last_message_count = {}
        
    def _init_driver(self):
        """Sets up Chrome WebDriver with user profile saved."""
        logger.info("Initializing Chrome WebDriver...")
        chrome_options = Options()
        import os
        # Saving user data avoids scanning the QR code every single run
        profile_path = os.path.abspath("./chrome_profile")
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-allow-origins=*")
        
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def start(self):
        """Opens WhatsApp Web and waits for QR login."""
        logger.info(f"Navigating to {WEB_WHATSAPP_URL}")
        self.driver.get(WEB_WHATSAPP_URL)
        
        logger.info("Waiting for WhatsApp to load (and for QR code scan if needed)...")
        try:
            # Wait for the main app UI to indicate successful login
            # 'side' div is the main left sidebar of WhatsApp Web.
            WebDriverWait(self.driver, 120).until(
                EC.presence_of_element_located((By.XPATH, '//div[@id="side"]'))
            )
            logger.info("Successfully loaded WhatsApp Web.")
        except TimeoutException:
            logger.error("Timeout waiting for WhatsApp Web to load. Make sure you scanned the QR code.")
            self.driver.quit()
            raise

    def get_incoming_message_count(self):
        """Returns the current number of incoming (received) messages visible in the open chat."""
        try:
            incoming = self.driver.find_elements(By.XPATH, '//div[contains(@class, "message-in")]')
            return len(incoming)
        except Exception:
            return 0

    def check_current_open_chat_passive(self):
        """
        Passively checks the currently open chat window (if any) for new messages
        using a MESSAGE COUNT approach.

        If message count in current open chat increased since we last replied,
        there is a new unread message that needs a reply.
        """
        try:
            # Get the CHAT panel header (inside #main), NOT the sidebar header.
            # Using //header[0] is wrong — that's the sidebar/search bar.
            header = None
            for selector in ['//div[@id="main"]//header', '//div[@data-testid="conversation-header"]']:
                elems = self.driver.find_elements(By.XPATH, selector)
                if elems:
                    header = elems[0]
                    break

            if not header:
                # No chat is open right now
                return False

            # Extract the contact name from the chat header
            contact_name = None
            for xpath in ['.//span[@dir="auto"]', './/span[@title]']:
                try:
                    spans = header.find_elements(By.XPATH, xpath)
                    for span in spans:
                        name = (span.get_attribute("title") or span.text or "").strip()
                        if name:
                            contact_name = name
                            break
                except Exception:
                    pass
                if contact_name:
                    break

            if not contact_name:
                return False

            # Count incoming messages currently visible in the open chat
            current_count = self.get_incoming_message_count()
            last_count = self.last_message_count.get(contact_name, -1)

            # -1 means this chat was never processed by us in this session.
            # We initialize the count WITHOUT triggering a reply so we don't
            # send duplicate replies to old messages on startup.
            if last_count == -1:
                self.last_message_count[contact_name] = current_count
                return False

            if current_count > last_count:
                logger.info(
                    f"Passive check: {current_count - last_count} new message(s) detected in "
                    f"open chat with '{contact_name}' (was {last_count}, now {current_count})."
                )
                # Re-enter the active monitor loop — it will handle group filtering internally
                self.process_chat(None, already_open=True)
                return True

        except Exception as e:
            logger.warning(f"Passive open chat check failed: {e}")
        return False


    def check_for_unread_messages(self):
        """Checks the chat list for unread messages."""
        try:
            # 1. First, always check if the chat that is currently open on the screen
            # has any new messages. (WhatsApp removes the badge if the chat is open).
            if self.check_current_open_chat_passive():
                return True
                
            # 2. WhatsApp unread badges usually have 'unread message' in the aria-label
            unread_badges = self.driver.find_elements(
                By.XPATH, 
                '//span[@aria-label and contains(@aria-label, "unread message")]'
            )
            
            if not unread_badges:
                return False
                
            for badge in unread_badges:
                # Find the parent wrapper to click on the chat
                try:
                    chat = badge.find_element(By.XPATH, './ancestor::div[@role="row"] | ./ancestor::div[@role="listitem"]')
                except NoSuchElementException:
                    # Fallback to clicking the badge or its immediate container
                    logger.warning("Could not find role='row' or 'listitem'. Falling back to badge itself.")
                    chat = badge
                
                self.process_chat(chat)
                
            return True
            
        except StaleElementReferenceException:
            # List might update while we are checking, skip and check again later
            return False
        except Exception as e:
            logger.error(f"Error checking for unread messages: {e}")
            return False

    def should_ignore_chat(self):
        """
        Detects if the active chat is a group, channel, or community.
        Returns True if the chat should be IGNORED.
        """
        try:
            # 1. ── Check against predefined IGNORED_GROUPS list first ──
            header = None
            for selector in ['//div[@id="main"]//header', '//div[@data-testid="conversation-header"]']:
                elems = self.driver.find_elements(By.XPATH, selector)
                if elems:
                    header = elems[0]
                    break
            
            if header:
                contact_name = ""
                try:
                    name_elem = header.find_element(By.XPATH, './/span[@dir="auto"]')
                    contact_name = name_elem.text.strip()
                except:
                    pass
                
                if contact_name and any(group.lower() in contact_name.lower() for group in IGNORED_GROUPS):
                    logger.info(f"Chat '{contact_name}' matched IGNORED_GROUPS list. Skipping.")
                    return True

            # 2. ── PRIMARY: The 3-Dot Menu "Info" Check (100% Reliable) ──
            # The most foolproof way to know if a chat is 1-on-1 or a Group:
            # Click the 3-dot menu in the header.
            # - Group/Channel: First option is "Group info" or "Channel info".
            # - 1-on-1 chat: First option is ALWAYS "Contact info".
            try:
                # Find the 3-dot menu button in the chat header (it has data-icon="menu")
                menu_btn = header.find_element(By.XPATH, './/span[@data-icon="menu"]/ancestor::div[@role="button"]')
                menu_btn.click()
                
                # Wait briefly for the dropdown to open
                time.sleep(0.3)
                
                # The dropdown menu is appended to the body, usually in an ul/li structure
                # We look for the first menu item (it's always the info button)
                menu_items = self.driver.find_elements(By.XPATH, '//ul/li/div[@role="button"]')
                
                is_group = False
                if menu_items:
                    first_item_text = menu_items[0].text.lower().strip()
                    logger.info(f"Group check — 3-dot menu first item is: '{first_item_text}'")
                    
                    if "contact info" in first_item_text:
                        is_group = False  # Definitely a 1-on-1 chat
                    else:
                        is_group = True   # "Group info", "Channel info", etc.
                
                # Close the menu by clicking the body or the menu button again
                try:
                    # Press escape to close the menu cleanly
                    webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                except:
                    pass
                
                if is_group:
                    logger.info("Group detected via 3-dot menu ('Contact info' not found). Skipping.")
                    return True
                else:
                    logger.info("1-on-1 chat confirmed via 3-dot menu ('Contact info').")
                    return False
                    
            except Exception as e:
                logger.warning(f"Failed to use 3-dot menu, error: {e}")
                pass

            logger.info("Group check passed (fell through) — treating as 1-on-1 chat by default.")
            return False

        except Exception as e:
            logger.warning(f"Group check failed, defaulting to SKIP for safety. Error: {e}")
            return True


    def get_last_message_text(self):
        """Helper to get the text of the last incoming message in the active chat."""
        try:
            incoming_messages = self.driver.find_elements(By.XPATH, '//div[contains(@class, "message-in")]')
            if not incoming_messages:
                return None
                
            last_message_element = incoming_messages[-1]
            # Extract text using reliable span classes/directions used by WhatsApp Web
            text_spans = last_message_element.find_elements(By.XPATH, './/span[@dir="ltr"] | .//span[contains(@class, "copyable-text")]')
            
            if not text_spans:
                return None
                
            # Assemble text parts
            return " ".join([span.text for span in text_spans if span.text.strip() != ""]).strip()
            
        except StaleElementReferenceException:
            return None
        except Exception as e:
            logger.debug(f"Failed to extract last message text: {e}")
            return None

    def check_active_chat_for_new_messages(self, contact_name):
        """Checks the currently open chat for new messages and replies if found."""
        last_message_text = self.get_last_message_text()
        
        # If no text could be extracted, the person may have sent an image, sticker,
        # voice note, or video. We still want to reply to acknowledge it.
        if not last_message_text:
            # Check if there is at least one incoming message in the DOM
            incoming_count = self.get_incoming_message_count()
            if incoming_count == 0:
                return False
            # Use a placeholder so the AI knows to reply generically
            last_message_text = "[sent a photo/sticker/voice note/video]"
            
        # We also need to keep track of the absolute last message processed during this active loop 
        # to prevent double-replying to the exact same message text if the DOM reloads.
        msg_id = f"{contact_name}::{last_message_text}"
        
        # Check for duplicates or already handled messages
        if msg_id in self.replied_messages:
            return False
            
        # Check against an instance variable tracking the last actively processed message
        if getattr(self, "last_active_message", None) == msg_id:
             return False

        logger.info(f"Processing new message from '{contact_name}': {last_message_text}")
        
        # Lock in this message as the currently processing one
        self.last_active_message = msg_id
        
        # Simulate human delay before sending response
        random_delay()
        
        # Ask AI for a reply
        reply_text = generate_reply(last_message_text, contact_name=contact_name)
        
        # Type and send
        self.send_message(reply_text)
        
        # Mark it as replied to avoid ghost replays within the same active session
        self.replied_messages.add(msg_id)
        
        # CRITICAL: Update the message count tracker so the passive checker knows
        # the current message count has been handled. Any future increase means
        # a brand new message arrived.
        self.last_message_count[contact_name] = self.get_incoming_message_count()
        
        logger.info(f"Successfully sent AI reply to '{contact_name}'.")
        return True

    def process_chat(self, chat_element=None, already_open=False):
        """Opens a chat (if not already open) and continuously monitors it for new messages."""
        contact_name = "Unknown"
        try:
            if not already_open and chat_element:
                # Use Javascript click as fallback if normal click is intercepted
                try:
                    chat_element.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", chat_element)
                    
            # Wait dynamically instead of fixed sleep
            header = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//header'))
            )
            time.sleep(1) # Small buffer for DOM to settle
            
            try:
                contact_name = header.find_element(By.XPATH, './/span[@dir="auto"]').text
            except NoSuchElementException:
                # Fallback to the text of the header or a general span
                try:
                    contact_name = header.find_element(By.XPATH, './/span[contains(@class, "ggj6brxn")]').text
                except:
                    contact_name = header.text.split('\n')[0] if header.text else "Unknown"
            
            # Check if it's a group, channel, or community
            if self.should_ignore_chat():
                logger.info(f"Chat '{contact_name}' detected as a GROUP/CHANNEL/COMMUNITY. Skipping AI reply.")
                return

            logger.info(f"Actively monitoring chat with '{contact_name}'...")
            
            # Check immediately upon opening
            self.check_active_chat_for_new_messages(contact_name)
            
            # Monitor the active chat for a short duration to reply to follow-ups
            # We don't want to get stuck here forever if other chats have unread messages
            monitor_duration = 30 # seconds to monitor active chat
            start_time = time.time()
            
            while time.time() - start_time < monitor_duration:
                # Small delay to prevent CPU spinning
                time.sleep(2)
                
                # Check for new messages in the currently open chat
                if self.check_active_chat_for_new_messages(contact_name):
                    # If we found and replied to a new message, reset the monitor timer
                    start_time = time.time()
                    
                # Break early if we see an unread badge from someone else in the chat list
                try:
                    unread_badges = self.driver.find_elements(
                        By.XPATH, 
                        '//span[@aria-label and contains(@aria-label, "unread message")]'
                    )
                    if unread_badges:
                        logger.info("Found new unread messages in other chats. Exiting active monitor.")
                        break
                except StaleElementReferenceException:
                    pass
            
            logger.info(f"Finished active monitoring for '{contact_name}'. Returning to main scan.")
            # Reset the text-based dedup so the passive count-checker
            # remains the sole authority on new messages in open chats.
            self.last_active_message = None
            
        except StaleElementReferenceException:
            logger.warning(f"DOM updated unexpectedly while processing chat. Will check again on next scan.")
        except Exception as e:
            logger.error(f"Error processing chat '{contact_name}': {e}")

    def send_message(self, text):
        """Finds the chat composer box and inputs the multi-line text message to send."""
        try:
            import pyperclip
            
            # We locate the text input box footer
            message_box_xpath = '//footer//div[@contenteditable="true"]'
            
            message_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, message_box_xpath))
            )
            
            # WhatsApp Web sometimes treats a pasted block with newlines as an immediate Send trigger
            # or truncates it. Natively, we want to type out newlines using SHIFT+ENTER.
            # However, ChromeDriver cannot type emojis (BMP only).
            # Solution: Copy-paste each line one by one, adding SHIFT+ENTER between them.
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line:
                    # Windows clipboard is asynchronous and slow. We must verify it copied
                    # before telling Chrome to paste, otherwise it pastes the old buffer.
                    pyperclip.copy(line)
                    
                    # Wait up to 1 second for clipboard to actually grab the text
                    attempts = 0
                    while pyperclip.paste() != line and attempts < 10:
                        time.sleep(0.1)
                        attempts += 1
                        
                    # Use keyboard shortcuts to paste the text based on the OS.
                    message_box.send_keys(Keys.CONTROL, 'v')
                    time.sleep(0.3) # Wait longer for React to process paste
                    
                # Add newline if it's not the last line
                if i < len(lines) - 1:
                    message_box.send_keys(Keys.SHIFT, Keys.ENTER)
            
            time.sleep(1) # Allow React to process the full message box
            
            # Hard enter sends the message
            message_box.send_keys(Keys.ENTER)
            time.sleep(1) # Extra buffer for WhatsApp to register sent msg
            
        except Exception as e:
            logger.error(f"Failed to send the final message back: {e}")

    def quit(self):
        """Cleanup and close the browser session explicitly."""
        if self.driver:
            self.driver.quit()
            logger.info("Chrome WebDriver closed.")
