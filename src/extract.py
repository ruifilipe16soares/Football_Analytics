#!/usr/bin/env python3
# VER O QUE É ISTO

# O QUE FALTA A ESTE SCRIPT:

# DAR A POSSIBILIDADE DE ESCOLHER SÓ UM JOGO.
"""
Download seletivo do repositório StatsBomb open-data.

Em vez de clonar o repositório inteiro (lento e enorme, sobretudo por causa
dos dados 360), este script usa os metadados leves (competitions + matches)
para decidir, em cascata, exatamente que ficheiros descarregar.

Fluxo:
    1. Lê competitions.json  -> aplica COMPETITION_FILTER
    2. Lê matches/{comp}/{season}.json para as competições escolhidas
       -> aplica MATCH_FILTER
    3. Descarrega events / lineups / three-sixty só para os jogos filtrados

Os ficheiros são guardados a espelhar a estrutura do repositório, por isso
podes usá-los tal como usarias um clone normal.
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #

RAW_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
OUTPUT_DIR = "data_dir"   # pasta local onde tudo é guardado

# Que tipos de dados queres para cada jogo selecionado.
# Tira "three-sixty" daqui se não precisares dos frames (são os mais pesados).
DATA_TYPES = ["events", "lineups", "three-sixty"]

# Quantos downloads em paralelo. 8-16 é razoável; baixa se tiveres timeouts.
MAX_WORKERS = 12

# --------------------------------------------------------------------------- #
# FILTROS  ->  é AQUI que defines as tuas condições
# Devolve True para manter, False para ignorar. Edita à vontade.
# --------------------------------------------------------------------------- #

def COMPETITION_FILTER(comp: dict) -> bool:
    """Recebe um registo do competitions.json."""
    # Exemplos (descomenta/ajusta o que quiseres):
    #
    return comp["competition_name"] == "Champions League"
    return comp["country_name"] == "Europe"
    return comp["competition_gender"] == "male"
    return comp["match_available_360"] is not None      # só competições com dados 360
    #
    # Por omissão: aceita tudo (filtras só ao nível dos jogos).
    return True


def MATCH_FILTER(match: dict) -> bool:
    """Recebe um registo de um ficheiro matches/{comp}/{season}.json."""
    # Campos disponíveis incluem: match_id, match_date, home_team, away_team,
    # home_score, away_score, competition_stage, match_week, stadium, referee...
    #
    # Exemplos:
    #
    # return match["competition_stage"]["name"] == "Final"
    # return "Barcelona" in (match["home_team"]["home_team_name"],
    #                        match["away_team"]["away_team_name"])
    # return match["match_week"] <= 5
    # return (match["home_score"] + match["away_score"]) >= 5   # jogos com muitos golos
    # return match["match_date"] >= "2024-01-01"
    #
    # Por omissão: aceita todos os jogos das competições selecionadas.
    return True


# --------------------------------------------------------------------------- #
# Mecânica (normalmente não precisas de mexer abaixo desta linha)
# --------------------------------------------------------------------------- #

def fetch_json(url: str):
    """Descarrega e faz parse de um JSON. Devolve None se não existir (404)."""
    req = Request(url, headers={"User-Agent": "statsbomb-seletivo"})
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            return None
        raise


def download_to(url: str, dest_path: str) -> str:
    """Descarrega url para dest_path (cria pastas, salta se já existir)."""
    if os.path.exists(dest_path):
        return f"existe   {dest_path}"
    req = Request(url, headers={"User-Agent": "statsbomb-seletivo"})
    try:
        with urlopen(req, timeout=60) as r:
            data = r.read()
    except HTTPError as e:
        if e.code == 404:
            return f"sem dados {url} (404)"
        return f"ERRO {e.code} {url}"
    except URLError as e:
        return f"ERRO {e} {url}"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(data)
    kb = len(data) / 1024
    return f"ok {kb:8.1f} KB  {dest_path}"


def main():
    print("A descarregar competitions.json...")
    competitions = fetch_json(f"{RAW_BASE}/competitions.json")
    if competitions is None:
        sys.exit("Não foi possível obter competitions.json")

    selected_comps = [c for c in competitions if COMPETITION_FILTER(c)]
    print(f"Competições/épocas selecionadas: {len(selected_comps)} de {len(competitions)}")

    # Recolher os match_id que passam os filtros
    match_ids: set[int] = set()
    for c in selected_comps:
        cid, sid = c["competition_id"], c["season_id"]
        matches = fetch_json(f"{RAW_BASE}/matches/{cid}/{sid}.json")
        if not matches:
            continue
        kept = [m for m in matches if MATCH_FILTER(m)]
        for m in kept:
            match_ids.add(m["match_id"])
        print(f"  [{cid}/{sid}] {c['competition_name']} {c['season_name']}: "
              f"{len(kept)}/{len(matches)} jogos")

        # Guardar também o próprio ficheiro de matches (útil de ter localmente)
        dest = os.path.join(OUTPUT_DIR, "matches", str(cid), f"{sid}.json")
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(matches, f, ensure_ascii=False)

    print(f"\nTotal de jogos a descarregar: {len(match_ids)}")
    if not match_ids:
        print("Nenhum jogo passou os filtros. Ajusta COMPETITION_FILTER / MATCH_FILTER.")
        return

    # Construir a lista de downloads (events/lineups/three-sixty por jogo)
    jobs = []
    for mid in sorted(match_ids):
        for dt in DATA_TYPES:
            url = f"{RAW_BASE}/{dt}/{mid}.json"
            dest = os.path.join(OUTPUT_DIR, dt, f"{mid}.json")
            jobs.append((url, dest))

    print(f"A descarregar {len(jobs)} ficheiros com {MAX_WORKERS} workers...\n")
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(download_to, u, d): (u, d) for u, d in jobs}
        for fut in as_completed(futures):
            done += 1
            print(f"[{done}/{len(jobs)}] {fut.result()}")

    print(f"\nConcluído. Dados em ./{OUTPUT_DIR}/")


if __name__ == "__main__":
    main()