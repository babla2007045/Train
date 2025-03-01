FROM python:3.11-slim

   # Install dependencies
   RUN apt-get update && apt-get install -y \
       git \
       libglib2.0-0 \
       libnss3 \
       libnspr4 \
       libatk1.0-0 \
       libatk-bridge2.0-0 \
       libcups2 \
       libdrm2 \
       libdbus-1-3 \
       libxcb1 \
       libxkbcommon0 \
       libx11-6 \
       libx11-xcb1 \
       libxcomposite1 \
       libxdamage1 \
       libxext6 \
       libxfixes3 \
       libxrandr2 \
       libgbm1 \
       libpango-1.0-0 \
       libcairo2 \
       libasound2 \
       libatspi2.0-0 \
       libwayland-client0

   # Install Playwright and Chromium
   RUN pip install playwright && playwright install chromium

   # Copy files
   COPY . /app
   WORKDIR /app

   # Run the script
   CMD ["python", "main.py"]