import time
import random
import logging

# Configure basic logging system
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

def get_logger(name):
    """
    Returns a configured logger instance with the given name.
    """
    return logging.getLogger(name)

def random_delay(min_seconds=1, max_seconds=2):
    """
    Introduces a random delay to simulate human typing and behavior.
    This helps in avoiding spam detection blocks on WhatsApp.
    Reduced to 1-2 seconds for much faster real-time response.
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger = get_logger(__name__)
    logger.info(f"Simulating human delay. Waiting for {delay:.2f} seconds before replying...")
    time.sleep(delay)
