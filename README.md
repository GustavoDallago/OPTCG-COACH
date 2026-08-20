# One Piece Card Game (OPTCG) - Database, Scraper & Deck Builder

This project is a complete and lightweight tool for One Piece Card Game (OPTCG) players. It allows you to view all official cards, scrape real tournament data from international championships to map the current meta game, build interactive decks, import official simulator lists (TXT format), and obtain a detailed deck analysis (estimated win rate and step-by-step combat guide) against the game's top meta opponents.

---

## 🚀 Key Features

1. **Full Database Viewer**:
   * Filter official cards by Set, Starter Decks, Promotional cards, and Don!! cards.
   * Search by card name, card set ID, or effect text.
   * Filter by color, card type (Leader, Character, Event, Stage), and rarity.
   * Direct search links to **Liga One Piece** for Brazilian market prices and availability.

2. **Meta Game Mapper (Egman Events Scraper)**:
   * Collects the latest statistics from top international tournament winning decklists.
   * Categorizes cards into three segments: **Staples / Core** (usage > 70%), **Suggested / Start Building** (inclusion from 30% to 70%), and **Tech Choices / Alternatives** (usage < 30%).

3. **Interactive Deck Builder & Validator**:
   * Choose any leader to dynamically build your eligible card pool based on allowed deck colors.
   * Automatically enforces official deck limits (exactly 50 cards and a maximum of 4 copies of any card set ID).
   * Displays live counter statistics for `+2000` counter counts and `Blocker` counts.
   * Renders a reactive **Cost Curve (Mana Curve)** chart from cost 0 to 10.
   * Suggests replacement cards to cut from your deck when recommending card improvements for a full 50-card deck.

4. **Text Import Utility (TXT)**:
   * Import complete decklists by copying and pasting simulator format lists (e.g. `1xOP14-020`, `4xOP12-034`).
   * Automatically identifies the Leader card and filters out invalid card colors.

5. **Combat Simulator & Step-by-Step Matchup Guide**:
   * Heuristically calculates your estimated win rate (%) against every meta leader based on card meta-alignment, defense counts (against Aggro), and removal counts (against Big Character decks).
   * Provides an interactive **Step-by-Step Guide** for each matchup:
     * **Turn Preference**: Whether to choose going first (Odd/First) or second (Even/Second).
     * **Starting Hand & Mulligan**: Tips on key cards to look for and when to redraw.
     * **Don Curve Strategy**: Recommended plays for the *Early*, *Mid*, and *Late Game*.
     * **General Matchup Strategy**: Detailed tactical explanations of game dynamics.

---

## 🛠️ Tech Stack

The project is designed to be **extremely lightweight and simple to run**:
* **Backend / Scripts**: Python 3.10+ (API data downloading, metadata scraping, and local HTTP server).
* **Frontend**: HTML5, Vue.js 3, and Tailwind CSS (Served purely via CDN. **No Node.js, npm, or complex build processes required**).
* **Automated Testing**: Python's native `unittest` module.
* **Scraping**: Headless Selenium Web Driver.

---

## 📦 Prerequisites

Ensure you have the following installed on your machine:
1. **Python 3.10+** ([Download Python](https://www.python.org/downloads/))
2. **Google Chrome** (Required for headless meta game scraping via Selenium).

### Installing Python Dependencies

Open your terminal in the project directory and install the required dependencies:

```bash
pip install selenium requests
```

*(Standard libraries like `http.server`, `urllib`, `json`, `re`, and `unittest` are shipped with Python).*

---

## ⚙️ Step-by-Step Execution Guide

Run the scripts in the following order to load the data and start the web application:

### Step 1: Download the Card Database
Run the downloader script to download all sets, starter decks, official images, and prices from the public OPTCG API:
```bash
python fetch_optcg_data.py
```
This will create an `optcg_data/` folder with `.json` database files containing card details and prices.

### Step 2: Scrape Meta Game Data (Egman Events)
Run the Selenium scraper script to visit Egman Events, map winning archetypes, and download card inclusion rates for your chosen set (e.g. `OP09`, `OP10`, or custom sets):
```bash
python scrape_meta.py --set OP09
```
*Tip: Change the `--set OP10` argument to scrape data for different sets. It generates files like `meta_OP09.json` inside the `optcg_data/` folder.*

### Step 3: Run Automated Tests (Optional)
To verify that the deckbuilding rules, deck heuristics, and matchups are calculated correctly, run the unit test suite:
```bash
python -m unittest test_deck_analyzer.py
```

### Step 4: Start the Web Server & Play!
Since the application loads local `.json` files via HTTP requests, browsers block local file loading under CORS rules if you open the HTML file directly. To avoid this, run our lightweight Python HTTP server:
```bash
python server.py
```
This will start a local server at `http://localhost:8000` and **automatically open your default web browser** to the application homepage!

---

## 📂 Project Directory Structure

* `fetch_optcg_data.py`: API downloader for cards, images, and pricing.
* `scrape_meta.py`: Headless Selenium scraper for the Egman Events meta database.
* `server.py`: Local Python HTTP server with anti-caching headers and auto-browser opening.
* `test_deck_analyzer.py`: Unit test suite verifying simulator rules and math logic.
* `index.html`: Main single-page application frontend (Vue.js 3 + Tailwind CSS).
* `optcg_data/`: Automatically generated folder containing card databases and meta files.

---

## ♻️ Simulator Text Import Format Example (TXT)

In the **"Builder"** tab, click **"Import from Text (TXT)"** and paste a decklist formatted for the official One Piece simulator.

**Example of valid text input:**
```text
1xOP14-020
4xOP12-034
4xOP14-023
2xOP15-035
4xST32-001
3xST32-005
4xOP14-033
4xST32-002
```
* The importer will automatically detect `OP14-020` as the green Leader Dracule Mihawk, configure the builder, and populate the main deck with 4 copies of the other color-compatible cards.
