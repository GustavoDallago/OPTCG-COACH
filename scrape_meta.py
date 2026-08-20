import os
import re
import sys
import json
import time
import argparse
from urllib.parse import urlparse, parse_qs, quote
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

DATA_DIR = "optcg_data"

def parse_args():
    parser = argparse.ArgumentParser(description="Scraper de Meta Game do OPTCG")
    parser.add_argument("--set", type=str, default="OP09", help="Coleção a ser buscada (ex: OP09, OP10, OP16)")
    return parser.parse_args()

def setup_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Suprime logs excessivos do ChromeDriver
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def parse_card_title(title_text):
    """
    Tratamento robusto para separar Nome da Carta, Porcentagem e Cópias a partir do atributo title.
    Exemplo de entrada: 'Trafalgar Law · 100.0% · usually 4x' ou 'Trafalgar Law • 100.0% • usually 4x'
    """
    if not title_text:
        return None, 0.0, ""
    
    # Divide por qualquer separador comum (middle dot \u00b7 / ·, bullet \u2022 / •, traço, seta ou pipe)
    parts = [p.strip() for p in re.split(r"[·•\-\u00b7\u2022\u2192|]", title_text)]
    
    # Caso ideal com 3 partes: [Nome, Percentual, Cópias]
    if len(parts) >= 3:
        name = parts[0]
        pct_match = re.search(r"([\d.]+)", parts[1])
        percentage = float(pct_match.group(1)) if pct_match else 0.0
        copies = parts[2]
        return name, percentage, copies
    elif len(parts) == 2:
        name = parts[0]
        pct_match = re.search(r"([\d.]+)%", parts[1])
        percentage = float(pct_match.group(1)) if pct_match else 0.0
        copies_match = re.search(r"(usually\s*\d+\s*x|\d+\s*copies)", parts[1], re.I)
        copies = copies_match.group(1) if copies_match else ""
        return name, percentage, copies
        
    return title_text, 0.0, ""

def scrape_meta(set_code):
    print(f"=== Iniciando Scraper de Meta Game para o Set: {set_code} ===")
    
    driver = setup_webdriver()
    meta_data = {
        "set_code": set_code,
        "decks_tracked": 0,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "leaders": []
    }
    
    try:
        # 1. Carrega a página principal do Meta
        main_url = f"https://deckbuilder.egmanevents.com/optcg/meta?set={set_code}"
        print(f"Carregando a página principal: {main_url}")
        driver.get(main_url)
        time.sleep(5)  # Espera renderização do React
        
        # Tenta extrair a quantidade de decks rastreados
        try:
            decks_tracked_text = driver.find_element(By.XPATH, "//*[contains(text(), 'DECKS TRACKED')]").text
            # Ex: "212 DECKS TRACKED"
            decks_count = int(re.search(r"(\d+)", decks_tracked_text).group(1))
            meta_data["decks_tracked"] = decks_count
            print(f"Total de decks rastreados no meta: {decks_count}")
        except Exception:
            print("Não foi possível identificar o número total de decks rastreados.")
            
        # Localiza os tiles de líderes
        tiles = driver.find_elements(By.CLASS_NAME, "archetype-tile")
        print(f"Líderes encontrados no Meta: {len(tiles)}")
        
        leaders_list = []
        for idx, tile in enumerate(tiles):
            try:
                name_el = tile.find_element(By.CLASS_NAME, "archetype-tile-name")
                name = name_el.text.strip()
                
                # Porcentagem de uso
                share_el = tile.find_element(By.CLASS_NAME, "archetype-tile-share")
                share_pct = float(share_el.text.replace("%", "").strip())
                
                # Contagem de Decks e Link de Archetype
                count_link = tile.find_element(By.CLASS_NAME, "archetype-tile-count")
                deck_count_text = count_link.text
                deck_count = int(re.search(r"(\d+)", deck_count_text).group(1))
                
                href = count_link.get_attribute("href")
                parsed_url = urlparse(href)
                q_val = parse_qs(parsed_url.query).get("q", [None])[0]
                
                # ID do Card do Líder
                img_el = tile.find_element(By.TAG_NAME, "img")
                img_src = img_el.get_attribute("src")
                
                leader_card_id = "UNKNOWN"
                if q_val and "||" in q_val:
                    leader_card_id = q_val.split("||")[0].strip().upper()
                else:
                    card_id_match = re.search(r"\/([A-Z0-9\-]+)\.(png|jpg|jpeg|webp)", img_src, re.I)
                    if card_id_match:
                        leader_card_id = card_id_match.group(1).split('-r17')[0].upper()
                
                # Fallback caso o parâmetro q_val não esteja no link
                if not q_val:
                    # Tenta deduzir a cor pelo texto do nome, ex: "Monkey.D.Luffy (Purple)" -> "Purple"
                    color_match = re.search(r"\(([^)]+)\)", name)
                    color = color_match.group(1) if color_match else "Multi"
                    q_val = f"{leader_card_id}||{color}"
                    
                leaders_list.append({
                    "name": name,
                    "leader_card_id": leader_card_id,
                    "deck_count": deck_count,
                    "share_percentage": share_pct,
                    "archetype_code": q_val,
                    "image": img_src
                })
                print(f"Líder {idx+1}: {name} | Decks: {deck_count} ({share_pct}%) | ID: {leader_card_id} | Archetype: {q_val}")
            except Exception as tile_err:
                print(f"Erro ao extrair líder no índice {idx}: {tile_err}")
                
        # 2. Visita a página de Card Ratios para cada líder e extrai os detalhes
        for leader in leaders_list:
            arch_code = leader["archetype_code"]
            # Monta a URL de Card Ratios (exemplo: set=OP09&archetype=OP05-060%7C%7CPurple)
            encoded_arch = quote(arch_code)
            ratio_url = f"https://deckbuilder.egmanevents.com/optcg/meta?set={set_code}&archetype={encoded_arch}"
            print(f"\nColetando cartas mais usadas para: {leader['name']}...")
            print(f"URL: {ratio_url}")
            
            try:
                driver.get(ratio_url)
                time.sleep(5)  # Tempo para renderizar os cards e suas propriedades
                
                cards_scraped = []
                card_nodes = driver.find_elements(By.CLASS_NAME, "modern-deck-card")
                print(f"Encontradas {len(card_nodes)} cartas associadas ao líder.")
                
                for card_node in card_nodes:
                    try:
                        title_attr = card_node.get_attribute("title")
                        card_name, inclusion_pct, copies = parse_card_title(title_attr)
                        
                        img_node = card_node.find_element(By.TAG_NAME, "img")
                        img_src = img_node.get_attribute("src")
                        
                        # Extrai ID do card da imagem (ex: OP09-069)
                        card_id = "UNKNOWN"
                        card_id_match = re.search(r"\/([A-Z0-9\-]+)\.(png|jpg|jpeg|webp)", img_src, re.I)
                        if card_id_match:
                            card_id = card_id_match.group(1).split('-r17')[0].upper()
                            
                        # Extrai número de decks a partir do texto renderizado embaixo do card
                        decks_text = ""
                        try:
                            # O texto de decks fica na mesma estrutura do card (ex: "57/57 decks")
                            decks_el = card_node.find_element(By.XPATH, "..//*[contains(text(), 'decks')]")
                            decks_text = decks_el.text.strip()
                        except Exception:
                            pass
                            
                        cards_scraped.append({
                            "card_name": card_name,
                            "card_id": card_id,
                            "inclusion_percentage": inclusion_pct,
                            "copies_recommendation": copies,
                            "decks_count_text": decks_text,
                            "image": img_src
                        })
                    except Exception as card_err:
                        print(f"Erro ao parsear card individual: {card_err}")
                
                leader["cards"] = cards_scraped
                print(f"Sucesso: {len(cards_scraped)} cartas salvas para {leader['name']}.")
                
            except Exception as ratio_err:
                print(f"Erro ao carregar card ratios de {leader['name']}: {ratio_err}")
                leader["cards"] = []
            
            # Pequeno intervalo antes do próximo request
            time.sleep(1)
            
        meta_data["leaders"] = leaders_list
        if meta_data.get("decks_tracked", 0) == 0 and leaders_list:
            meta_data["decks_tracked"] = sum(l.get("deck_count", 0) for l in leaders_list)
        
        # 3. Salva os dados consolidados no arquivo JSON local
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            
        filepath = os.path.join(DATA_DIR, f"meta_{set_code}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=4, ensure_ascii=False)
            
        print(f"\n==================================================")
        print(f" Sucesso! Meta Game do Set {set_code} baixado.")
        print(f" Salvo em: {filepath}")
        print(f"==================================================")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    args = parse_args()
    scrape_meta(args.set)
