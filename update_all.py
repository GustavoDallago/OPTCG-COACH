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

def main():
    log("==========================================")
    log("Starting Full Automatic Update Pipeline...")
    log("==========================================")
    
    # 1. Fetch latest card and set data
    s1 = run_cmd(f"{sys.executable} fetch_optcg_data.py")
    
    # 2. Scrape OP17 Meta Game data
    s2 = run_cmd(f"{sys.executable} scrape_meta.py --set OP17")
    
    # 3. Recalculate decks_tracked for all meta files
    fix_meta_decks_tracked()
    
    # 4. Run automated test suite
    s3 = run_cmd(f"{sys.executable} -m unittest test_deck_analyzer.py")
    
    if s1 and s2 and s3:
        log("==========================================")
        log("SUCCESS: All update tasks completed flawlessly!")
        log("==========================================")
    else:
        log("==========================================")
        log("WARNING: Pipeline finished with warnings or non-zero return codes.")
        log("==========================================")

if __name__ == "__main__":
    main()
