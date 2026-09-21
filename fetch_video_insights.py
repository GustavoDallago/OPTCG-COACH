"""
fetch_video_insights.py - OPTCG Coach
Coleta os videos mais recentes dos canais do YouTube cadastrados em optcg_data/youtube_channels.json,
identifica lideres, formatos (OP15, OP16, OP17), matchups abordados e gera resumos taticos em optcg_data/ai_meta_insights.json.
"""
from __future__ import annotations

import os
import re
import json
import time
import datetime
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

CHANNELS_FILE = "optcg_data/youtube_channels.json"
OUTPUT_FILE = "optcg_data/ai_meta_insights.json"

def atomic_save_json(data: Any, filepath: str, indent: Optional[int] = 2) -> bool:
    dirname = os.path.dirname(filepath)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    tmp_file = f"{filepath}.tmp_{os.getpid()}_{int(time.time()*1000)}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            if indent is not None:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            else:
                json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
        os.replace(tmp_file, filepath)
        return True
    except Exception as e:
        print(f"[Error] Falha ao salvar {filepath}: {e}")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False

def extract_channel_id(url: str) -> Optional[str]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r'channel_id=(UC[a-zA-Z0-9_-]{22})', html)
        if not m:
            m = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', html)
        if m:
            return m.group(1)
    except Exception as e:
        print(f"[Aviso] Nao foi possivel obter channel_id para {url}: {e}")
    return None

def fetch_channel_feed(channel_id: str) -> List[Dict[str, str]]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    
    entries_data = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)
        ns = {
            "a": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/"
        }
        for entry in root.findall("a:entry", ns):
            title_node = entry.find("a:title", ns)
            pub_node = entry.find("a:published", ns)
            vid_node = entry.find("yt:videoId", ns)
            desc_node = entry.find(".//media:description", ns)
            
            title = title_node.text.strip() if title_node is not None and title_node.text else ""
            pub_date = pub_node.text.strip() if pub_node is not None and pub_node.text else ""
            vid_id = vid_node.text.strip() if vid_node is not None and vid_node.text else ""
            desc = desc_node.text.strip() if desc_node is not None and desc_node.text else ""
            
            if vid_id and title:
                entries_data.append({
                    "video_id": vid_id,
                    "title": title,
                    "published_at": pub_date,
                    "description": desc,
                    "url": f"https://www.youtube.com/watch?v={vid_id}"
                })
    except Exception as e:
        print(f"[Aviso] Erro ao carregar feed para {channel_id}: {e}")
        
    return entries_data

NON_OPTCG_KEYWORDS = ["yugioh", "yu-gi-oh", "pokemon", "magic the gathering", "riftbound", "lorcana"]
OPTCG_KEYWORDS = [
    "one piece", "optcg", "op-0", "op0", "op1", "st-", "st0", "st1", "st2",
    "meta", "deck", "matchup", "gameplay", "tournament", "locals", "regional",
    "combo", "mulligan", "leader", "don!!", "tcg"
]

def is_optcg_content(title: str, desc: str) -> bool:
    full_text = f"{title} {desc}".lower()
    if any(k in full_text for k in NON_OPTCG_KEYWORDS):
        if "one piece" not in full_text and "optcg" not in full_text:
            return False
    return any(k in full_text for k in OPTCG_KEYWORDS)

DESC_OPPS_REGEX = r'(?:vs\.?|against)\s+["\']?([A-Za-z0-9&/\s-]{3,25})["\']?'

def extract_matchups_from_desc(desc: str) -> List[str]:
    matchups = []
    for line in desc.split("\n"):
        m = re.findall(DESC_OPPS_REGEX, line, re.IGNORECASE)
        for opp in m:
            clean_opp = opp.strip().split("-")[0].strip()
            if len(clean_opp) > 2 and clean_opp.lower() not in ["intro", "outro", "deck", "timestamps"]:
                if clean_opp not in matchups:
                    matchups.append(clean_opp)
    return matchups[:5]

LEADERS_REF = [
    "Yamato", "Bonney", "Luffy", "Zoro", "Nami", "Law", "Katakuri",
    "Doflamingo", "Lucci", "Enel", "Ace", "Sabo", "Pluton", "Kaido",
    "Reiju", "Uta", "Smoker", "Moria", "Perona", "Kuro", "Caesar Clown",
    "Shanks", "Buggy", "Teach", "Blackbeard", "Belo Betty", "Chopper",
    "Marco", "Kid", "Whitebeard", "Robin", "Pudding", "Hody Jones",
    "Sanji", "Kouzuki Oden", "Kuzan", "Sakazuki", "Issho", "Fujitora", "Garp",
    # OP18 leaders
    "Karoo", "Franky", "Ms. All Sunday", "Spandam", "Saint Gunko", "Nico Robin",
]

def identify_leader_and_set(title: str, desc: str) -> Dict[str, Any]:
    text = f"{title} {desc}"
    fmt = ""
    m_fmt = re.search(r'\b(EB-?0[1-9]|OP-?1[0-9]|OP-?0[1-9])\b', text, re.IGNORECASE)
    if m_fmt:
        fmt = m_fmt.group(1).upper().replace("-", "")
    matched_leaders = []
    for ldr in LEADERS_REF:
        pattern = r'\b' + re.escape(ldr) + r'\b'
        if re.search(pattern, title, re.IGNORECASE):
            matched_leaders.append(ldr)
    return {"format": fmt, "leaders": matched_leaders}

MAX_META_VIDEO_AGE_DAYS = 90

def is_video_within_meta_window(published_at_str: str, max_days: int = MAX_META_VIDEO_AGE_DAYS) -> bool:
    """Verifica se o video foi publicado dentro da janela de relevancia do meta (padrao: 90 dias / ~3 meses)."""
    if not published_at_str:
        return True
    try:
        clean_str = published_at_str.replace("Z", "+00:00")
        pub_dt = datetime.datetime.fromisoformat(clean_str)
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=datetime.timezone.utc)
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        age_days = (now_dt - pub_dt).total_seconds() / 86400.0
        return age_days <= max_days
    except Exception:
        return True

def process_channel_videos() -> Dict[str, Any]:
    if not os.path.exists(CHANNELS_FILE):
        print(f"[Erro] Arquivo {CHANNELS_FILE} nao encontrado.")
        return {}
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    channels = config.get("channels", [])
    br_tz = datetime.timezone(datetime.timedelta(hours=-3), name="BRT")
    insights = {
        "last_updated": datetime.datetime.now(br_tz).strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "total_channels": len(channels),
        "total_insights": 0,
        "videos_by_leader": {},
        "latest_videos": []
    }
    for ch in channels:
        ch_name = ch.get("name", "Canal")
        ch_url = ch.get("url", "")
        ch_id = ch.get("channel_id", "")
        print(f"\n-> Canal: {ch_name} ({ch_url})")
        if not ch_id:
            ch_id = extract_channel_id(ch_url)
            if ch_id:
                ch["channel_id"] = ch_id
        if not ch_id:
            print("   Pular canal: channel_id nao encontrado.")
            continue
        videos = fetch_channel_feed(ch_id)
        print(f"   {len(videos)} videos recebidos do feed.")
        optcg_count = 0
        for v in videos:
            if not is_optcg_content(v["title"], v["description"]):
                continue
            # Filtro 1: Descartar videos com mais de 90 dias (fora do meta ativo)
            if not is_video_within_meta_window(v.get("published_at", "")):
                continue
            optcg_count += 1
            meta = identify_leader_and_set(v["title"], v["description"])
            matchups = extract_matchups_from_desc(v["description"])
            desc_lines = [l.strip() for l in v["description"].split("\n") if l.strip()]
            summary = desc_lines[0] if desc_lines else "Analise de deck e gameplay."
            if len(summary) > 200:
                summary = summary[:197] + "..."
            entry = {
                "video_id": v["video_id"],
                "title": v["title"],
                "channel_name": ch_name,
                "published_at": v["published_at"],
                "video_url": v["url"],
                "format": meta["format"],
                "identified_leaders": meta["leaders"],
                "matchups_covered": matchups,
                "summary": summary
            }
            insights["latest_videos"].append(entry)
            for ldr in meta["leaders"]:
                ldr_key = ldr.lower()
                if ldr_key not in insights["videos_by_leader"]:
                    insights["videos_by_leader"][ldr_key] = []
                insights["videos_by_leader"][ldr_key].append({
                    "title": entry["title"],
                    "channel_name": ch_name,
                    "published_at": entry["published_at"],
                    "video_url": entry["video_url"],
                    "format": entry["format"],
                    "matchups_covered": matchups
                })
        print(f"   {optcg_count} videos de OPTCG recentes (ultimos {MAX_META_VIDEO_AGE_DAYS} dias) identificados.")

    # Filtro 2: Deduplicacao por canal + lider
    # Se o mesmo canal tiver multiplos videos para o mesmo lider, mantem apenas o mais recente.
    # Entre canais diferentes, mantem ambos e ordena por published_at decrescente.
    deduped_videos_by_leader: Dict[str, List[Dict[str, Any]]] = {}
    for ldr_key, vlist in insights["videos_by_leader"].items():
        channel_latest: Dict[str, Dict[str, Any]] = {}
        for v in vlist:
            ch_key = v.get("channel_name", "").strip().lower()
            if ch_key not in channel_latest:
                channel_latest[ch_key] = v
            else:
                if v.get("published_at", "") > channel_latest[ch_key].get("published_at", ""):
                    channel_latest[ch_key] = v
        sorted_leader_videos = sorted(channel_latest.values(), key=lambda x: x.get("published_at", ""), reverse=True)
        deduped_videos_by_leader[ldr_key] = sorted_leader_videos

    insights["videos_by_leader"] = deduped_videos_by_leader
    insights["total_insights"] = len(insights["latest_videos"])
    insights["latest_videos"].sort(key=lambda x: x.get("published_at", ""), reverse=True)
    atomic_save_json(insights, OUTPUT_FILE)
    print(f"\n[Sucesso] {OUTPUT_FILE} gerado com {insights['total_insights']} videos de meta.")
    return insights

EVERGREEN_FILE = "optcg_data/evergreen_strategy_guides.json"

def process_evergreen_guides() -> None:
    if not os.path.exists(EVERGREEN_FILE):
        return
    try:
        with open(EVERGREEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        guides = data.get("guides", [])
        print(f"\n[Evergreen Guides] Validando {len(guides)} guias fundamentais cadastrados...")
        valid = [g for g in guides if g.get("title") and g.get("category")]
        print(f"[Evergreen Guides] {len(valid)} guias estrategicos atemporais prontos para alimentar o Coach IA.")
    except Exception as e:
        print(f"[Aviso] Erro ao ler {EVERGREEN_FILE}: {e}")

if __name__ == "__main__":
    process_channel_videos()
    process_evergreen_guides()
