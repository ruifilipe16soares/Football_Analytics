#!/usr/bin/env python3
"""
extract.py — acesso seletivo ao repositorio StatsBomb open-data.

Duas utilizacoes:
  1. Como biblioteca (usada pela app): listar competicoes/jogos e descarregar
     os ficheiros de UM jogo a pedido.
  2. Como script: descarga em lote por filtro (ver __main__).

So depende da biblioteca-padrao (urllib) + pandas para as listagens.
"""

import json
import os
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

import pandas as pd

RAW_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
TIPOS_JOGO = ("events", "lineups", "three-sixty")


# --------------------------------------------------------------------------- #
# Baixo nivel
# --------------------------------------------------------------------------- #

def fetch_json(url):
    """Descarrega e faz parse de um JSON. None se 404."""
    req = Request(url, headers={"User-Agent": "statsbomb-app"})
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            return None
        raise


def _download(url, dest):
    """Descarrega url -> dest (cria pastas; salta se existir). True se ok."""
    if os.path.exists(dest):
        return True
    req = Request(url, headers={"User-Agent": "statsbomb-app"})
    try:
        with urlopen(req, timeout=60) as r:
            data = r.read()
    except (HTTPError, URLError):
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    return True


# --------------------------------------------------------------------------- #
# Biblioteca (usada pela app)
# --------------------------------------------------------------------------- #

def listar_competicoes():
    """DataFrame de todas as competicoes/epocas disponiveis."""
    dados = fetch_json(f"{RAW_BASE}/competitions.json")
    return pd.DataFrame(dados or [])


def listar_jogos(competition_id, season_id):
    """DataFrame dos jogos de uma competicao/epoca (achatado)."""
    dados = fetch_json(f"{RAW_BASE}/matches/{competition_id}/{season_id}.json")
    return pd.json_normalize(dados or [], sep="_")


def descarregar_jogo(match_id, competition_id, season_id, data_dir="data_dir",
                     tipos=TIPOS_JOGO):
    """
    Descarrega os ficheiros de UM jogo para data_dir, espelhando a estrutura
    do repositorio, e tambem o ficheiro de matches da epoca (metadados).
    Salta os que ja existem. Devolve dict {tipo: ok?}.
    """
    resultado = {}
    for t in tipos:
        dest = os.path.join(data_dir, t, f"{match_id}.json")
        resultado[t] = _download(f"{RAW_BASE}/{t}/{match_id}.json", dest)
    # ficheiro de matches da epoca (para os metadados do jogo)
    dest_m = os.path.join(data_dir, "matches", str(competition_id), f"{season_id}.json")
    resultado["matches"] = _download(
        f"{RAW_BASE}/matches/{competition_id}/{season_id}.json", dest_m)
    return resultado


# --------------------------------------------------------------------------- #
# Script: descarga em lote por filtro
# --------------------------------------------------------------------------- #

def descarregar_filtrado(competition_filter=None, match_filter=None,
                         data_dir="data_dir", tipos=TIPOS_JOGO):
    """
    Descarrega em lote todos os jogos que passam os filtros dados (funcoes que
    recebem um registo e devolvem True/False). Sem filtros, aceita tudo.
    """
    comps = listar_competicoes()
    if competition_filter:
        comps = comps[comps.apply(competition_filter, axis=1)]
    total = 0
    for _, c in comps.iterrows():
        jogos = listar_jogos(c["competition_id"], c["season_id"])
        if match_filter is not None and not jogos.empty:
            jogos = jogos[jogos.apply(match_filter, axis=1)]
        for _, j in jogos.iterrows():
            descarregar_jogo(j["match_id"], c["competition_id"], c["season_id"],
                             data_dir, tipos)
            total += 1
            print(f"  ok match {j['match_id']}")
    print(f"total de jogos descarregados: {total}")


if __name__ == "__main__":
    # Exemplo: descarregar so a final do Euro 2024
    descarregar_filtrado(
        competition_filter=lambda c: c["competition_name"] == "UEFA Euro"
                                     and c["season_name"] == "2024",
        match_filter=lambda m: m.get("competition_stage_name") == "Final",
    )