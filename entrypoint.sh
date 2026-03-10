#!/bin/bash
# Start Xvfb in the background so Chrome has a "virtual screen" to render on
Xvfb :99 -ac &
export DISPLAY=:99

# Start the WhatsApp bot
python main.py
