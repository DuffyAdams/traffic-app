# Traffic Alerts App (San Diego)

A real-time dashboard and backend service that monitors, aggregates, and visualizes traffic and emergency incidents across the San Diego region.

## Overview

The Traffic Alerts App automatically scrapes and structures incident data from multiple local agencies, utilizing large language models to generate tweet-friendly summaries and displaying the results on a modern, responsive map interface. 

It provides an efficient way to track accidents, road hazards, maintenance activities, and emergency dispatch events in near real-time.

### Key Features
* **Multi-Agency Aggregation**: Consolidates live data from:
  * California Highway Patrol (CHP)
  * San Diego Police Department (SDPD)
  * San Diego Fire-Rescue Department (SDFD)
* **Automated Geocoding & Mapping**: Automatically reverse-geocodes street descriptions and generates static map imagery for incidents.
* **AI-Generated Summaries**: Uses LLMs (via OpenRouter/Google Gemini) to transform dense dispatcher codes into easily readable, concise alerts.
* **Modern Frontend**: A fully responsive web interface built with Svelte that includes interactive maps, real-time updates, and filtering capabilities.
* **Interactive Community**: Users can "like" and comment on specific traffic incidents directly through the web UI.

---

## Architecture

* **Backend / API**: Python & Flask
* **Database**: SQLite (Optimized with WAL mode for high concurrency)
* **Frontend**: Svelte (Vite build system)
* **Data Processing**: `BeautifulSoup4` for web scraping, `ThreadPoolExecutor` for concurrent operations.
* **AI Integration**: OpenAI Python SDK interfaced with OpenRouter (Google Gemini).

---

## Installation

### Prerequisites
* **Python 3.9+**
* **Node.js (v18+)** and `npm`

### 1. Backend Setup

Clone the repository and set up a Python virtual environment:

```bash
cd traffic-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the root directory and populate it with the necessary API keys, relying on `.env.example` (or `cred.env`) as a template:

```ini
GPT_KEY=your_openrouter_or_openai_key
MAP_ACCESS_TOKEN=your_mapbox_access_token
# (Optional) Add your Twitter/X Developer credentials for the RoadAlerts auto-poster
```

### 3. Frontend Setup

Install the Node dependencies for the Svelte interface:

```bash
cd traffic-app/src
npm install
```

---

## Running the Application

### Option 1: Standard Execution (Local Development)

First, build the frontend:
```bash
cd traffic-app
npm run build
```

Then, run the main Python script from the root project directory. This single script (`traffic_scraper.py`) will start the continuous background scraping threads AND initialize the Flask server to serve both the API and the compiled Svelte static files.

```bash
python traffic_scraper.py
```

*The frontend will be accessible at: `http://localhost:5002`*

### Option 2: Live Development Mode

If you are actively developing the Svelte frontend, you can run the Vite development server independent of Flask (note you will still need to run the Python backend separately).

```bash
# In terminal 1 (Backend)
python traffic_scraper.py

# In terminal 2 (Frontend)
cd traffic-app
npm run dev
```

---

## Project Structure

```text
traffic-app/
├── traffic_scraper.py       # Main entry point: runs the Flask API and background scrapers
├── geocoding.py             # Custom geocoding and caching logic
├── generate_map.py          # Script for generating map static imagery
├── requirements.txt         # Python dependencies
├── traffic_data.db          # SQLite Database containing incidents, likes, comments (Generated at runtime)
├── .env                     # Contains critical API Keys (OpenRouter, MapBox)
└── traffic-app/             # Svelte Frontend Root Directory
    ├── src/                 # Svelte Components and Assets (App.svelte, MapTab.svelte, etc.)
    ├── public/              # Static assets and icons
    └── package.json         # Node.js dependencies
```

## License

This project is open-source. Please see the `LICENSE` file for more details. 
