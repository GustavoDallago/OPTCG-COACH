# One Piece Card Game (OPTCG) - Database, Limitless Meta & Deck Builder

This project is a complete, lightweight, and modern tool for One Piece Card Game (OPTCG) players. It provides a full official card database, automated scrapers for international tournament results (Limitless TCG & Egman Events), dynamic set integration (OP01-OP17, EB, ST01-ST36), interactive deck building, TXT import/export, and in-depth combat analytics with matchup strategy guides.

---

## 🚀 Key Features

1. **Full Database Viewer & Dynamic Set Discovery**:
   * Filter official cards by Sets (OP01 to OP17+), Starter Decks (ST01 to ST36+), Promos, and Don!! cards.
   * Search by card name, card ID, or effect text.
   * Filter by color (including multi-color), card type (Leader, Character, Event, Stage), cost, and rarity.
   * High-resolution official Western English artwork CDN (`_EN.webp`).
   * Direct search links to **Liga One Piece** for Brazilian market pricing and card stock.

2. **Meta Game Mapper (Limitless TCG & Egman Events)**:
   * 100% calibrated for the **Western English Meta (EN Meta)**.
   * Real tournament data from international championships and online leagues (Past 7 Days).
   * **Customized Ranking System**: Automatically sorted by **1. Total Deck Count (Presence)** ➔ **2. Win Rate (% WR)** ➔ **3. Meta Share (% Usage)**.
   * Visual indicator badges with dynamic color coding for win rates and usage rates.
   * Card categorization for every archetype: **Core / Staples** (>70%), **Suggested Build** (30%-70%), and **Tech Choices** (<30%).

3. **Interactive Deck Builder & Validator**:
   * Pick any Leader to dynamically unlock allowed deck colors and eligible card pool.
   * Real-time validation (strictly 50 cards + 1 Leader, max 4 copies per ID).
   * Live defensive statistics (`+2000` Counter count and `Blocker` count).
   * Interactive **Cost Curve (Mana Curve)** histogram from cost 0 to 10.
   * Smart card swap recommendations based on real meta percentage data.

4. **Text Import & Export Utility (TXT)**:
   * **Import**: Paste standard simulator format lists (e.g. `1xOP14-020`, `4xOP12-034`) to automatically set up the leader and populate the deck.
   * **Export**: Copy formatted decklists to the clipboard or download as `.txt` for use in simulators or tournament registration.

5. **Combat Simulator & Step-by-Step Matchup Guide**:
   * Heuristically calculates your estimated win rate (%) against every meta leader based on card meta-alignment, defense counts (against Aggro), and removal counts (against Big Character decks).
   * **Turn Preference**: Whether to choose going first (Odd/First) or second (Even/Second).
   * **Starting Hand & Mulligan**: Key cards to look for and when to redraw.
   * **Don Curve Strategy**: Recommended plays for Early, Mid, and Late game phases.
   * **General Matchup Strategy**: Detailed tactical explanations of game dynamics.

6. **100% Mobile Responsive UI**:
   * Optimized for smartphones and tablets with smooth scrolling and responsive card modal inspectors.

---

## 🛠️ Tech Stack

* **Backend / Pipeline**: Python 3.10+ (Limitless / Egman web scrapers, data normalizer, and local HTTP server).
* **Frontend**: HTML5, Vue.js 3, and Tailwind CSS (Served purely via CDN — **zero Node.js, npm, or build steps required**).
* **Automated CI/CD**: GitHub Actions daily cron pipeline (`update.yml`).
* **Automated Testing**: Python's native `unittest` module.

---

## 📦 Prerequisites

1. **Python 3.10+** ([Download Python](https://www.python.org/downloads/))
2. **Google Chrome** (Optional: only needed if running Selenium Egman scraper).

### Installing Dependencies

```bash
pip install requests selenium
```

---

## ⚙️ How to Run

### Step 1: Start the Local Application
Run the built-in server script:
```bash
python server.py
```
This starts the local web server at `http://localhost:8000` and **automatically opens your default web browser**.

---

## 🔄 Automated Updates & Pipeline

The project includes an automatic update pipeline that fetches new cards, meta data, and runs unit tests:

```bash
python update_all.py
```

### GitHub Actions (Daily Cloud Updates)
A GitHub Actions workflow is pre-configured in `.github/workflows/update.yml`. It runs automatically every day at 03:00 AM UTC (00:00 BRT), executes `python update_all.py`, commits the newly scraped meta files directly to the repository, and deploys without needing any local computer running.

---

## ➕ Adding New Sets / Collections

You can add new sets (e.g., `OP18`, `ST36`) in two ways:

### Method A: Via Scraper (Recommended & Automatic)
Run the Limitless scraper for the new set code:
```bash
python scrape_limitless.py --set OP18
```
This generates `optcg_data/meta_OP18.json`. The frontend will automatically detect the new file on load, inject `OP18` into the collection dropdown, and make all new cards searchable in the **Collections** and **Deck Builder** tabs!

### Method B: Manual JSON Entry
1. Add the set object to `optcg_data/sets.json`:
   ```json
   { "set_id": "OP-18", "set_name": "Two Legends (OP18)", "set_image": "URL" }
   ```
2. Add cards to `optcg_data/set_cards.json`:
   ```json
   {
     "card_name": "Monkey.D.Luffy",
     "card_set_id": "OP18-001",
     "card_type": "Leader",
     "card_color": "Red",
     "card_cost": "5",
     "card_power": "5000",
     "card_image": "https://limitlesstcg.nyc3.digitaloceanspaces.com/one-piece/OP18/OP18-001_EN.webp",
     "set_id": "OP-18",
     "rarity": "L"
   }
   ```

---

## 📂 Project Directory Structure

* `index.html`: Main single-page application (Vue.js 3 + Tailwind CSS).
* `update_all.py`: Master pipeline script for automated card fetching, scraping, and testing.
* `scrape_limitless.py`: High-speed scraper for Limitless TCG tournament meta data and Western English card lists.
* `scrape_meta.py`: Headless Selenium scraper for Egman Events tournament meta.
* `fetch_optcg_data.py`: API downloader for official base card databases.
* `server.py`: Local Python HTTP server with anti-caching headers and auto-browser opening.
* `test_deck_analyzer.py`: Unit test suite verifying simulator rules and math logic.
* `optcg_data/`: Folder containing all `.json` databases and meta files (`meta_OP01.json` to `meta_OP17.json`).
* `.github/workflows/update.yml`: GitHub Actions daily cron auto-updater.
