"""
OPTCG COACH - Master Pipeline Automation Orchestrator
Executes data downloaders, banlist scrapers, metagame scrapers, manifest generators,
and unit tests with explicit timeouts and atomic file updates.
"""
from __future__ import annotations

import os
import sys
import json
import glob
import time
import subprocess
import datetime
from typing import List, Dict, Any, Union

LOG_FILE = "update_log.txt"

def log(msg: str) -> None:
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def rotate_log(max_lines: int = 1000) -> None:
    """Retains only the latest max_lines of the log file to prevent unbounded growth."""
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-max_lines:])
            print(f"[Log] Rotated log file: kept last {max_lines} lines ({len(lines)} -> {max_lines}).")
    except Exception as e:
        print(f"[Log] Error rotating log: {e}")

def atomic_save_json(data: Any, filepath: str, indent: int = 2) -> bool:
    """Saves JSON data atomically using a temporary file and atomic replace."""
    dirname = os.path.dirname(filepath)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    tmp_file = f"{filepath}.tmp_{os.getpid()}_{int(time.time()*1000)}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        os.replace(tmp_file, filepath)
        return True
    except Exception as e:
        log(f"Error during atomic save to {filepath}: {e}")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False

def run_cmd(cmd: Union[str, List[str]], timeout: int = 600) -> bool:
    """Executes a command safely with timeout and detailed output logging."""
    display_cmd = cmd if isinstance(cmd, str) else " ".join(cmd)
    log(f"Executing: {display_cmd}")
    try:
        res = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )
        if res.returncode == 0:
            log(f"SUCCESS: {display_cmd}")
            return True
        else:
            log(f"ERROR (code {res.returncode}): {display_cmd}\n--- Stdout ---\n{res.stdout}\n--- Stderr ---\n{res.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT ERROR: Command timed out after {timeout} seconds: {display_cmd}")
        return False
    except Exception as e:
        log(f"EXCEPTIONAL ERROR running {display_cmd}: {e}")
        return False

def fix_meta_decks_tracked() -> None:
    """Recalculates and updates decks_tracked totals for all meta_*.json files."""
    log("Recalculating decks_tracked for all meta JSON files...")
    updated_count = 0
    for filepath in glob.glob("optcg_data/meta_*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            leaders = data.get("leaders", [])
            if leaders:
                total = sum(l.get("deck_count", 0) for l in leaders)
                data["decks_tracked"] = total
                if atomic_save_json(data, filepath, indent=4):
                    updated_count += 1
        except Exception as e:
            log(f"Error processing {filepath}: {e}")
    log(f"Updated decks_tracked in {updated_count} files.")

def generate_manifest() -> None:
    """Generates optcg_data/manifest.json with the list of available meta sets."""
    import re
    log("Generating optcg_data/manifest.json...")
    available: List[Dict[str, Any]] = []
    pattern = re.compile(r'meta_([A-Z0-9]+)\.json$', re.IGNORECASE)
    for filepath in sorted(glob.glob("optcg_data/meta_*.json")):
        m = pattern.search(filepath)
        if not m:
            continue
        code = m.group(1).upper()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            leaders = data.get("leaders", [])
            if leaders:
                available.append({
                    "code": code,
                    "deck_count": data.get("decks_tracked", 0),
                    "scraped_at": data.get("scraped_at", "")
                })
        except Exception as e:
            log(f"[manifest] Error reading {filepath}: {e}")

    manifest = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "available_meta_sets": available,
        "total_sets": len(available)
    }
    if atomic_save_json(manifest, "optcg_data/manifest.json", indent=2):
        log(f"manifest.json generated: {len(available)} sets available.")
    else:
        log("Failed to write manifest.json")

def main() -> None:
    rotate_log()
    log("==========================================")
    log("Starting Full Automatic Update Pipeline...")
    log("==========================================")

    # 1. Fetch latest card, set, and banlist data
    s1 = run_cmd([sys.executable, "fetch_optcg_data.py"])
    s_ban = run_cmd([sys.executable, "scrape_banlist.py"])

    # 2. Scrape OP17 Meta Game data from Limitless TCG (Past 7 Days tournaments)
    s2 = run_cmd([sys.executable, "scrape_limitless.py", "--set", "OP17", "--min-players", "8"])
    if not s2:
        log("WARNING: Limitless scraper encountered an issue or found no new tournaments. Existing meta JSON preserved.")

    # 3. Recalculate decks_tracked for all meta files
    fix_meta_decks_tracked()

    # 4. Generate manifest.json
    generate_manifest()

    # 5. Run automated test suite
    s3 = run_cmd([sys.executable, "-m", "unittest", "test_deck_analyzer.py"])

    if s1 and s_ban and s3:
        log("==========================================")
        log("SUCCESS: All update tasks completed flawlessly!")
        log("==========================================")
    else:
        log("==========================================")
        log("WARNING: Pipeline finished with warnings or non-zero return codes.")
        log("==========================================")

if __name__ == "__main__":
    main()
