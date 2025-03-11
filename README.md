
# 🚦 San Diego Traffic Watch

**Welcome to San Diego Traffic Watch!**  
A real-time traffic monitoring system that scrapes incident data from the **California Highway Patrol (CHP)**, generates maps, and serves it through an interactive web app built with **Flask** and **Svelte**. Stay informed about traffic incidents in San Diego with a sleek, user-friendly interface!

---

## ✨ Features

- **Real-Time Scraping**: Fetches live traffic incidents from CHP's website.
- **Map Generation**: Creates visual maps for each incident using coordinates.
- **Database Storage**: Stores incidents in **SQLite** with **likes** and **comments**.
- **Interactive Frontend**: A **Svelte-powered UI** with **dark mode**, **infinite scroll**, and **responsive design**.
- **Social Features**: Like incidents, add comments, and share updates.
- **UUID Tracking**: Tracks users via cookies for a personalized experience without using IP addresses.

---

## 🛠 Tech Stack

**Backend**: Python, Flask, SQLite, OpenAI, BeautifulSoup, Geopy  
**Frontend**: Svelte, HTML/CSS  
**Tools**: Requests, Subprocess, Threading, dotenv  

---

## 📁 Project Structure

```
traffic-watch/
├── traffic-app/         # Frontend static files (Svelte dist)
│   ├── dist/            # Compiled Svelte app
│   └── maps/            # Generated map images
├── generate_map.py      # Script to create map images
├── traffic_data.db      # SQLite database
├── main.py              # Main Flask app and scraper
└── README.md            # You're here! 👋
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js (for Svelte frontend)
- OpenAI API key (optional, for descriptions)

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/traffic-watch.git
cd traffic-watch
```

#### 2. Set Up Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\ScriptsActivate
pip install -r requirements.txt
```

#### 3. Install Frontend Dependencies

```bash
cd traffic-app
npm install
npm run build
cd ..
```

#### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```
GPT_KEY=your-openai-api-key
```

#### 5. Run the App

```bash
python main.py
```

Visit: [http://localhost:5000](http://localhost:5000)

---

## ⚙️ How It Works

### Scraper
- Fetches data from [cad.chp.ca.gov](https://cad.chp.ca.gov/traffic.aspx) every **60 seconds**.
- Extracts incident details, coordinates, and generates descriptions using OpenAI.

### Database
- Stores incidents with unique `incident_no` and `date` key.
- Tracks **likes** and **comments** per user via **UUID**.

### Map Generator
- Runs `generate_map.py` to create PNG maps for each incident.

### Web App
- **Flask** serves API endpoints (`/api/incidents`, `/maps/*`).
- **Svelte** frontend displays incidents with **infinite scroll** and **real-time updates**.

---

## 📡 API Endpoints

| Endpoint                      | Method | Description                     |
| ----------------------------  | ------ | ------------------------------ |
| `/api/incidents`              | GET    | Fetch all incidents             |
| `/maps/<filename>`            | GET    | Serve map images                |
| `/api/incidents/<id>/like`    | POST   | Like an incident                |
| `/api/incidents/<id>/comment` | POST   | Comment on an incident          |
| `/api/user/check`             | GET    | Check user UUID                 |

---

## 🎨 Frontend Highlights

- **Dark Mode**: Toggle via header.
- **Infinite Scroll**: Loads more posts as you scroll.
- **Animations**: Smooth transitions using Svelte's `fade`, `slide`, and `flip`.
- **Responsive**: Mobile, tablet, and desktop-friendly.

---

## 🔧 Configuration

| Setting             | Value                          |
| ------------------ | ------------------------------ |
| Scrape URL         | `https://cad.chp.ca.gov/traffic.aspx` |
| Cookie             | UUID stored for 1 year         |
| Refresh Rate       | Frontend refreshes every 20s   |
| Posts per Page     | 20 incidents per load          |

---

## 📊 Example Incident (JSON)

```json
{
  "incident_no": "12345",
  "date": "2025-03-10",
  "timestamp": "2025-03-10 14:30:00",
  "city": "San Diego",
  "location": "I-5 Northbound",
  "type": "Accident",
  "description": "Car crash on I-5 NB near downtown 🚗💥",
  "latitude": 32.7157,
  "longitude": -117.1611,
  "map_filename": "map_20250310_1430.png",
  "likes": 5,
  "comments": [{"username": "CoolPanda42", "comment": "Stay safe!"}]
}
```

---

## 🤝 Contributing

1. **Fork** the repo  
2. Create a branch:  
   ```bash
   git checkout -b feature/awesome-idea
   ```
3. Commit changes:  
   ```bash
   git commit -m "Add awesome idea"
   ```
4. Push your branch:  
   ```bash
   git push origin feature/awesome-idea
   ```
5. **Open a Pull Request**

---

## 📝 Notes

- Ensure `generate_map.py` exists for map generation.
- OpenAI API key is **optional**; fallback descriptions are used if absent.
- Use `Ctrl+C` to stop the scraper in the terminal.

---

## 📜 License

MIT License © 2025 — Free to use, modify, and share!  
**Happy monitoring!** Feel free to reach out with questions or ideas to improve the project.

---
