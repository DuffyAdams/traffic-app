#!/bin/bash
# Change to the directory where the script is located (your project directory)
cd "$(dirname "$0")"

# Run the Svelte dev server using npm, and use python3 for your Python scripts
npm run dev:svelte &
python3 app.py &
python3 traffic_scraper.py &
wait
