#!/usr/bin/env python3
"""
extrair.py — camada de extração e estruturação dos dados de um jogo StatsBomb.

Lê os ficheiros de um jogo descarregados pelo filtrar_repositorio.py
(events, lineups, three-sixty, e a linha correspondente em matches) e
devolve DataFrames organizados e prontos para a camada de métricas.

Estrutura de pastas esperada (a que o filtrar_repositorio.py cria):

    data_dir/
        matches/{competition_id}/{season_id}.json
        events/{match_id}.json
        lineups/{match_id}.json
        three-sixty/{match_id}.json

Uso rápido:

    from extrair import carregar_jogo
    jogo = carregar_jogo("statsbomb_data", match_id=3895292)

    jogo.events        # eventos ordenados por index, com x/y já extraídos
    jogo.lineups       # jogadores das duas equipas (forma longa)
    jogo.match         # 1 linha de metadados do jogo
    jogo.freeze        # 360 em forma longa: 1 linha por (evento, jogador)

    jogo.freeze_de(event_id)   # freeze frame de um evento, pronto a plotar
    jogo.juntar_360()          # eventos x jogadores do freeze (só quando precisas)

Depende apenas de pandas.
"""

import json
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Dimensões do campo em coordenadas StatsBomb (usadas nas visualizações).
PITCH_X = 120.0
PITCH_Y = 80.0


# --------------------------------------------------------------------------- #
# Leitura de baixo nível
# --------------------------------------------------------------------------- #

def _ler_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _split_xy(serie):
    """
    Série de listas [x, y] (ou None) -> duas séries numéricas (x, y).

    Usa NaN (não pd.NA) para os valores em falta, para que as colunas fiquem
    com dtype float64 e permitam contas vetorizadas (distâncias, ângulos...).
    """
    xs = pd.to_numeric(
        serie.apply(lambda v: v[0] if isinstance(v, list) and len(v) >= 2 else np.nan),
        errors="coerce",
    )
    ys = pd.to_numeric(
        serie.apply(lambda v: v[1] if isinstance(v, list) and len(v) >= 2 else np.nan),
        errors="coerce",
    )
    return xs, ys


# --------------------------------------------------------------------------- #
# Carregadores por tipo de ficheiro
# --------------------------------------------------------------------------- #

def carregar_events(events_path):
    """Eventos achatados, ordenados por index, com localizações extraídas."""
    ev = pd.json_normalize(_ler_json(events_path), sep="_")
    ev = ev.sort_values("index").reset_index(drop=True)

    # Localização inicial do evento -> x, y
    if "location" in ev.columns:
        ev["x"], ev["y"] = _split_xy(ev["location"])

    # Localizações finais mais usadas (passes e conduções) -> end_x, end_y
    finais = {
        "pass_end_location": ("pass_end_x", "pass_end_y"),
        "carry_end_location": ("carry_end_x", "carry_end_y"),
    }
    for col, (cx, cy) in finais.items():
        if col in ev.columns:
            ev[cx], ev[cy] = _split_xy(ev[col])

    return ev


def carregar_lineups(lineups_path):
    """Jogadores das duas equipas em forma longa (1 linha por jogador)."""
    dados = _ler_json(lineups_path)
    linhas = []
    for equipa in dados:
        for jog in equipa["lineup"]:
            posicoes = jog.get("positions") or []
            linhas.append({
                "team_id": equipa["team_id"],
                "team_name": equipa["team_name"],
                "player_id": jog["player_id"],
                "player_name": jog["player_name"],
                "player_nickname": jog.get("player_nickname"),
                "jersey_number": jog.get("jersey_number"),
                "country": (jog.get("country") or {}).get("name"),
                "posicao_inicial": posicoes[0]["position"] if posicoes else None,
                "titular": bool(posicoes) and posicoes[0].get("start_reason") == "Starting XI",
                "positions": posicoes,   # lista completa (entradas/saídas), caso precises
                "cards": jog.get("cards") or [],
            })
    return pd.DataFrame(linhas)


def carregar_freeze(threesixty_path):
    """
    Dados 360 em forma longa: 1 linha por (evento, jogador).

    Devolve (freeze_df, visible_area_dict), onde visible_area_dict mapeia
    event_uuid -> polígono visível pelo tracking.
    """
    dados = _ler_json(threesixty_path)
    linhas = []
    visiveis = {}
    for frame in dados:
        uuid = frame["event_uuid"]
        visiveis[uuid] = frame.get("visible_area")
        for p in frame["freeze_frame"]:
            x, y = p["location"]
            linhas.append({
                "event_uuid": uuid,
                "ff_x": x,
                "ff_y": y,
                "teammate": p["teammate"],   # True = mesma equipa do executante do evento
                "actor": p["actor"],         # True = jogador que executa o evento
                "keeper": p["keeper"],       # True = guarda-redes
            })
    freeze = pd.DataFrame(
        linhas,
        columns=["event_uuid", "ff_x", "ff_y", "teammate", "actor", "keeper"],
    )
    return freeze, visiveis


def _extrair_manager(df, col, prefixo):
    """
    'managers' é uma LISTA de dicts (o json_normalize não achata listas),
    por isso extraímos à mão o nome/id do primeiro treinador para colunas
    próprias, à semelhança do que fazemos com o location -> x/y.
    """
    if col not in df.columns:
        return

    def primeiro(v, campo):
        return v[0].get(campo) if isinstance(v, list) and v else None

    df[f"{prefixo}_manager_name"] = df[col].apply(lambda v: primeiro(v, "name"))
    df[f"{prefixo}_manager_id"] = df[col].apply(lambda v: primeiro(v, "id"))


def carregar_match(matches_path, match_id):
    """Extrai a linha de metadados de um jogo do ficheiro de matches da época."""
    dados = _ler_json(matches_path)
    if isinstance(dados, dict):
        dados = [dados]
    df = pd.json_normalize(dados, sep="_")

    # managers vem como lista -> separar nome/id em colunas próprias
    _extrair_manager(df, "home_team_managers", "home_team")
    _extrair_manager(df, "away_team_managers", "away_team")

    linha = df[df["match_id"] == match_id]
    if linha.empty:
        raise ValueError(f"match_id {match_id} não está em {matches_path}")
    return linha.reset_index(drop=True)


def _encontrar_match(data_dir, match_id, competition_id, season_id):
    """Localiza a linha do jogo, com ou sem competition/season conhecidos."""
    matches_dir = os.path.join(data_dir, "matches")
    if competition_id is not None and season_id is not None:
        caminhos = [os.path.join(matches_dir, str(competition_id), f"{season_id}.json")]
    else:
        caminhos = [
            os.path.join(raiz, f)
            for raiz, _, fichs in os.walk(matches_dir)
            for f in fichs if f.endswith(".json")
        ]
    for c in caminhos:
        if not os.path.exists(c):
            continue
        try:
            return carregar_match(c, match_id)
        except ValueError:
            continue
    raise ValueError(
        f"match_id {match_id} não encontrado nos ficheiros de matches em {matches_dir}. "
        f"Indica competition_id e season_id se a procura automática falhar."
    )


# --------------------------------------------------------------------------- #
# Objeto que agrega o jogo + utilitários
# --------------------------------------------------------------------------- #

@dataclass
class Jogo:
    match_id: int
    match: pd.DataFrame      # 1 linha de metadados (equipas, data, fase, jornada...)
    events: pd.DataFrame     # eventos ordenados por index, com x/y
    lineups: pd.DataFrame    # jogadores das duas equipas
    freeze: pd.DataFrame     # 360 em forma longa (1 linha por evento x jogador)
    visible_area: dict = field(default_factory=dict)

    # ---------------------- acesso a eventos ----------------------
    def evento(self, event_id):
        """A linha de um evento pelo seu id."""
        return self.events[self.events["id"] == event_id]

    def sequencia(self, possession):
        """Todos os eventos de uma sequência de posse, já ordenados."""
        return self.events[self.events["possession"] == possession]

    def por_tipo(self, *tipos):
        """Eventos de um ou mais tipos (ex.: por_tipo('Pass', 'Shot'))."""
        return self.events[self.events["type_name"].isin(tipos)]

    def relacionados(self, event_id):
        """Eventos ligados a este via related_events (passe<->receção, etc.)."""
        linha = self.evento(event_id)
        if linha.empty:
            return self.events.iloc[0:0]
        ids = linha.iloc[0].get("related_events")
        if not isinstance(ids, list):
            return self.events.iloc[0:0]
        return self.events[self.events["id"].isin(ids)]

    # ---------------------- acesso ao 360 ----------------------
    def freeze_de(self, event_id):
        """Freeze frame (long) de um evento, pronto a plotar."""
        return self.freeze[self.freeze["event_uuid"] == event_id]

    def tem_360(self, event_id):
        return (self.freeze["event_uuid"] == event_id).any()

    def eventos_com_360(self):
        """Subconjunto de eventos que têm freeze frame associado."""
        ids = set(self.freeze["event_uuid"].unique())
        return self.events[self.events["id"].isin(ids)]

    def juntar_360(self, eventos=None):
        """
        Junta eventos x jogadores do freeze frame (forma longa, pesada).
        Passa um DataFrame de eventos já filtrado para limitar o tamanho.
        """
        base = self.events if eventos is None else eventos
        return base.merge(
            self.freeze, left_on="id", right_on="event_uuid", how="inner"
        )

    # ---------------------- conveniências ----------------------
    @property
    def equipas(self):
        m = self.match.iloc[0]
        return m["home_team_home_team_name"], m["away_team_away_team_name"]

    def resumo(self):
        casa, fora = self.equipas
        m = self.match.iloc[0]
        return (
            f"{casa} {m['home_score']}-{m['away_score']} {fora}  "
            f"({m.get('match_date')}, {m.get('competition_stage_name')})\n"
            f"  eventos: {len(self.events)}  |  "
            f"com 360: {self.eventos_com_360().shape[0]}  |  "
            f"jogadores: {len(self.lineups)}"
        )


def carregar_jogo(data_dir, match_id, competition_id=None, season_id=None):
    """
    Carrega um jogo completo a partir da estrutura criada pelo filtrar_repositorio.py.

    Se competition_id/season_id forem dados, vai direto ao ficheiro de matches certo;
    caso contrário procura o match_id em todos os ficheiros de matches existentes.
    """
    events = carregar_events(os.path.join(data_dir, "events", f"{match_id}.json"))
    lineups = carregar_lineups(os.path.join(data_dir, "lineups", f"{match_id}.json"))

    ts_path = os.path.join(data_dir, "three-sixty", f"{match_id}.json")
    if os.path.exists(ts_path):
        freeze, visible = carregar_freeze(ts_path)
    else:
        # jogo sem dados 360 disponíveis
        freeze = pd.DataFrame(
            columns=["event_uuid", "ff_x", "ff_y", "teammate", "actor", "keeper"]
        )
        visible = {}

    match = _encontrar_match(data_dir, match_id, competition_id, season_id)

    return Jogo(
        match_id=match_id,
        match=match,
        events=events,
        lineups=lineups,
        freeze=freeze,
        visible_area=visible,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extrair dados de um jogo StatsBomb.")
    parser.add_argument("match_id", type=int, help="ID do jogo")
    parser.add_argument("--data-dir", default="statsbomb_data", help="Pasta dos dados")
    parser.add_argument("--competition-id", type=int, default=None)
    parser.add_argument("--season-id", type=int, default=None)
    args = parser.parse_args()

    jogo = carregar_jogo(
        args.data_dir, args.match_id, args.competition_id, args.season_id
    )
    print(jogo.resumo())