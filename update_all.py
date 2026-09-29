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
from typing import List, Dict, Any, Union, Optional

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LOG_FILE = "update_log.txt"
BR_TZ = datetime.timezone(datetime.timedelta(hours=-3), name="BRT")

def log(msg: str) -> None:
    timestamp = datetime.datetime.now(BR_TZ).strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    try:
        print(formatted)
    except Exception:
        try:
            print(formatted.encode("ascii", errors="backslashreplace").decode("ascii"))
        except Exception:
            pass
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

def atomic_save_json(data: Any, filepath: str, indent: Optional[int] = None) -> bool:
    """Saves JSON data atomically using a temporary file and atomic replace in compact format."""
    dirname = os.path.dirname(filepath)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    tmp_file = f"{filepath}.tmp_{os.getpid()}_{int(time.time()*1000)}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            if indent is not None:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            else:
                json.dump(data, f, separators=(',', ':'), ensure_ascii=False)
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
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env
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

def get_season_plan(target_date: Optional[Union[str, datetime.date]] = None) -> Dict[str, Any]:
    """
    Determina dinamicamente o set ativo da temporada e quais sets anteriores precisam
    ser consolidados (rodados com --days 0 sem filtro de dias).
    Lê a data de lançamento dos próximos sets em optcg_data/spoiler_config.json.
    """
    import re
    if target_date is not None:
        if isinstance(target_date, str):
            today = datetime.datetime.strptime(target_date[:10], "%Y-%m-%d").date()
        else:
            today = target_date
    else:
        now_dt = datetime.datetime.now(BR_TZ)
        today = now_dt.date()

    # Lê configuração de spoilers/lançamentos
    spoiler_cfg = {}
    cfg_path = os.path.join("optcg_data", "spoiler_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                spoiler_cfg = json.load(f)
        except Exception as e:
            log(f"Erro ao ler spoiler_config.json: {e}")

    # Coleta todos os números de coleções OP disponíveis
    all_op_nums = set()
    for fp in glob.glob("optcg_data/meta_OP*.json"):
        base = os.path.splitext(os.path.basename(fp))[0]
        m = re.match(r"meta_OP(\d+)", base, re.IGNORECASE)
        if m:
            all_op_nums.add(int(m.group(1)))

    for k in spoiler_cfg.keys():
        m = re.match(r"^OP(\d+)$", k, re.IGNORECASE)
        if m:
            all_op_nums.add(int(m.group(1)))

    sorted_ops = [f"OP{n:02d}" for n in sorted(all_op_nums)]
    if not sorted_ops:
        sorted_ops = ["OP17"]

    # Identifica o set ativo: começa em OP17 (base atual). Se houver set com release_date <= today, avança.
    active_set = "OP17"
    for s_code in sorted_ops:
        cfg = spoiler_cfg.get(s_code, {})
        r_date_str = cfg.get("release_date")
        if r_date_str:
            try:
                r_date = datetime.datetime.strptime(r_date_str[:10], "%Y-%m-%d").date()
                if today >= r_date:
                    active_set = s_code
            except Exception:
                pass

    active_num = int(re.sub(r"\D", "", active_set) or 0)
    past_to_consolidate: List[str] = []

    # Verifica coleções passadas que ainda não foram consolidadas
    for s_code in sorted_ops:
        num = int(re.sub(r"\D", "", s_code) or 0)
        if num < active_num:
            meta_path = os.path.join("optcg_data", f"meta_{s_code}.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        m_data = json.load(f)
                    # Se não estiver marcado como consolidado, precisa rodar consolidado retroativo
                    if not m_data.get("is_consolidated"):
                        past_to_consolidate.append(s_code)
                except Exception:
                    past_to_consolidate.append(s_code)

    return {
        "active_set": active_set,
        "past_to_consolidate": past_to_consolidate,
        "today": today.strftime("%Y-%m-%d")
    }

def fix_meta_decks_tracked() -> None:
    """Recalculates and updates decks_tracked totals for all meta_*.json files,
    and flags past archival collections as consolidated."""
    log("Recalculating decks_tracked and checking consolidation status for all meta JSON files...")
    updated_count = 0
    plan = get_season_plan()
    active_set = plan["active_set"]

    for filepath in glob.glob("optcg_data/meta_*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            code = (data.get("set_code") or "").upper()
            modified = False

            leaders = data.get("leaders", [])
            if leaders:
                total = sum(l.get("deck_count", 0) for l in leaders if l.get("is_active", True) is not False)
                if data.get("decks_tracked") != total:
                    data["decks_tracked"] = total
                    modified = True

            # Marca coleções passadas existentes como consolidadas caso ainda não estejam
            if code and code != active_set:
                if not data.get("is_consolidated"):
                    data["is_consolidated"] = True
                    data["season_status"] = "consolidated"
                    if "Past" in str(data.get("source", "")):
                        data["source"] = "Limitless TCG (Consolidado da Temporada Completa - Western Meta)"
                    modified = True

            if modified:
                if atomic_save_json(data, filepath):
                    updated_count += 1
        except Exception as e:
            log(f"Error processing {filepath}: {e}")
    log(f"Updated metadata / decks_tracked in {updated_count} files.")

def generate_manifest() -> None:
    """Generates optcg_data/manifest.json with the list of available meta sets and consolidation status."""
    import re
    log("Generating optcg_data/manifest.json...")
    available: List[Dict[str, Any]] = []
    pattern = re.compile(r'meta_([A-Z0-9]+)\.json$', re.IGNORECASE)
    plan = get_season_plan()
    active_set = plan["active_set"]

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
                is_cons = data.get("is_consolidated", code != active_set)
                available.append({
                    "code": code,
                    "deck_count": data.get("decks_tracked", 0),
                    "scraped_at": data.get("scraped_at", ""),
                    "is_consolidated": is_cons,
                    "season_status": data.get("season_status", "consolidated" if is_cons else "active")
                })
        except Exception as e:
            log(f"[manifest] Error reading {filepath}: {e}")

    manifest = {
        "generated_at": datetime.datetime.now(BR_TZ).strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "active_season_set": active_set,
        "available_meta_sets": available,
        "total_sets": len(available)
    }
    if atomic_save_json(manifest, "optcg_data/manifest.json"):
        log(f"manifest.json generated: {len(available)} sets available (Active Season: {active_set}).")
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

    # 2. Season Transition Management & Metagame Scrape
    plan = get_season_plan()
    log(f"Season Plan: Active Season = {plan['active_set']} (15d), Past to Consolidate = {plan['past_to_consolidate']}")

    # 2a. Consolidate full season for finished sets (e.g. OP17 when OP18 starts)
    for past_set in plan["past_to_consolidate"]:
        log(f"--> Transição de temporada detectada! Rodando consolidado completo da temporada para {past_set} (--days 0)...")
        s_cons = run_cmd([sys.executable, "scrape_limitless.py", "--set", past_set, "--days", "0", "--min-players", "8"])
        if s_cons:
            log(f"✅ Temporada {past_set} consolidada com sucesso!")
        else:
            log(f"⚠️ Erro ao consolidar temporada {past_set}.")

    # 2b. Scrape active set (Past 15 Days)
    log(f"--> Atualizando meta da temporada ativa ({plan['active_set']}) com janela de 15 dias...")
    s2 = run_cmd([sys.executable, "scrape_limitless.py", "--set", plan["active_set"], "--days", "15", "--min-players", "8"])
    if not s2:
        log(f"WARNING: Limitless scraper encountered an issue for {plan['active_set']}. Existing meta JSON preserved.")

    # 3. Recalculate decks_tracked and ensure consolidation metadata
    fix_meta_decks_tracked()

    # 4. Generate manifest.json
    generate_manifest()

    # 5. Fetch YouTube Video Meta Insights for Coach IA
    s_yt = run_cmd([sys.executable, "fetch_video_insights.py"])

    # 6. Run automated test suite
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
