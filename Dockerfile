# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install wget, gnupg, Xvfb (Virtual Display), and necessary dependencies for Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    xvfb \
    libnss3 \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container
COPY . .

# Make the entrypoint script executable
RUN chmod +x entrypoint.sh

# Run the entrypoint script to start Xvfb and then Python
ENTRYPOINT ["./entrypoint.sh"]
