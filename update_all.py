import os
import sys
import json
import glob
import subprocess
import datetime

LOG_FILE = "update_log.txt"

def log(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def rotate_log(max_lines: int = 1000):
    """Mantém apenas as últimas max_lines linhas do log para evitar crescimento ilimitado."""
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-max_lines:])
            print(f"[Log] Rotacionado: mantidas as últimas {max_lines} linhas ({len(lines)} -> {max_lines}).")
    except Exception as e:
        print(f"[Log] Erro ao rotacionar log: {e}")

def run_cmd(cmd: str) -> bool:
    log(f"Executing: {cmd}")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            log(f"SUCCESS: {cmd}")
            return True
        else:
            log(f"ERROR (code {res.returncode}): {cmd}\n--- Stdout ---\n{res.stdout}\n--- Stderr ---\n{res.stderr}")
            return False
    except Exception as e:
        log(f"EXCEPTIONAL ERROR running {cmd}: {e}")
        return False

def fix_meta_decks_tracked():
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
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                updated_count += 1
        except Exception as e:
            log(f"Error processing {filepath}: {e}")
    log(f"Updated decks_tracked in {updated_count} files.")

def generate_manifest():
    """Generates optcg_data/manifest.json with the list of available meta sets."""
    import re
    log("Generating optcg_data/manifest.json...")
    available = []
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
            if leaders:  # Only include sets that actually have leader data
                available.append({
                    "code": code,
                    "deck_count": data.get("decks_tracked", 0),
                    "scraped_at": data.get("scraped_at", "")
                })
        except Exception as e:
            log(f"[manifest] Error reading {filepath}: {e}")
    
    manifest = {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "available_meta_sets": available,
        "total_sets": len(available)
    }
    try:
        with open("optcg_data/manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        log(f"manifest.json generated: {len(available)} sets available.")
    except Exception as e:
        log(f"Error writing manifest.json: {e}")

def main():
    rotate_log()
    log("==========================================")
    log("Starting Full Automatic Update Pipeline...")
    log("==========================================")
    
    # 1. Fetch latest card, set, and banlist data
    s1 = run_cmd(f"{sys.executable} fetch_optcg_data.py")
    s_ban = run_cmd(f"{sys.executable} scrape_banlist.py")
    
    # 2. Scrape OP17 Meta Game data from Limitless TCG (Past 7 Days tournaments, pairings, and 50-card lists)
    s2 = run_cmd(f"{sys.executable} scrape_limitless.py --set OP17 --min-players 8")
    if not s2:
        log("WARNING: Limitless scraper failed or found no data. The existing meta JSON was preserved.")

    
    # 3. Recalculate decks_tracked for all meta files
    fix_meta_decks_tracked()
    
    # 4. Generate manifest.json
    generate_manifest()
    
    # 5. Run automated test suite
    s3 = run_cmd(f"{sys.executable} -m unittest test_deck_analyzer.py")
    
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
