import time
import sys
from whatsapp_listener import WhatsAppBot
from config import MESSAGE_SCAN_INTERVAL
from utils import get_logger

logger = get_logger("shanmukh_assistant")

def main():
    logger.info("=" * 50)
    logger.info("Starting Shanmukh's WhatsApp AI Assistant...")
    logger.info("=" * 50)
    
    bot = None
    try:
        # Initialize and login to WhatsApp via Selenium
        bot = WhatsAppBot()
        bot.start()
        
        logger.info(f"Bot is ready. Scanning for incoming messages every {MESSAGE_SCAN_INTERVAL} seconds.")
        logger.info("Press Ctrl+C to stop the bot at any time.")
        
        # Continuous monitoring loop
        while True:
            try:
                bot.check_for_unread_messages()
            except Exception as e:
                logger.error(f"Error in main loop while checking messages: {e}")
            
            # Loop delay
            time.sleep(MESSAGE_SCAN_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Bot manually stopped right now by the operator (KeyboardInterrupt).")
        
    except Exception as e:
        logger.critical(f"Critical error occurred causing system failure: {e}")
        
    finally:
        # Clean up session
        if bot:
            logger.info("Closing WebDriver session safely...")
            bot.quit()
        logger.info("WhatsApp AI Assistant terminated.")
        sys.exit(0)

if __name__ == "__main__":
    main()
