#!/usr/bin/env python3
"""
metricas.py — métricas de desempenho a partir dos dados do jogo.

Recebe um objeto Jogo (do extrair.py) e devolve
DataFrames / números. (Não desenha nada, isso é o viz.py).

Primeira métrica: passes que quebram linhas, usando os dados 360.
"""

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Geometria reutilizável (também usada pela visualização)
# --------------------------------------------------------------------------- #

def adversarios_quebrados(opp_xy, x0, y0, x1, y1, buffer=5.0):
    """
    Devolve uma Lista de booleans (True/False) dos adversários "quebrados" (ultrapassados) por um passe.
    O nº de elementos na lista depende do nº de adversários presentes no frame. Cada elemento indica se o adversário correspondente foi quebrado.

    Um adversário é quebrado se ficar DENTRO do corredor do passe:
      - projetado sobre a linha do passe entre o início e o fim (0 < t < 1), e
      - a uma distância perpendicular <= buffer dessa linha.
    O buffer é quão longe da linha reta do passe um adversário ainda conta como "quebrado".

    Parâmetros
    ----------
    opp_xy : array (n, 2) com as posições (ff_x, ff_y) dos adversários no frame.
    x0, y0 : início do passe (localização do evento).
    x1, y1 : fim do passe (pass_end_x, pass_end_y).
    buffer : meia-largura do corredor, em unidades de campo (campo é 120 x 80). isto é, — quão longe da linha reta do passe um adversário ainda conta como "quebrado".
    """
    opp_xy = np.asarray(opp_xy, dtype=float)
    if opp_xy.size == 0:
        return np.array([], dtype=bool)

    p0 = np.array([x0, y0], dtype=float)
    p1 = np.array([x1, y1], dtype=float)
    d = p1 - p0
    L2 = float(d.dot(d))
    if L2 == 0.0:                      # passe sem comprimento
        return np.zeros(len(opp_xy), dtype=bool)

    t = (opp_xy - p0) @ d / L2         # projecao normalizada de cada adversario
    proj = p0 + np.outer(t, d)         # ponto projetado na linha do passe
    perp = np.linalg.norm(opp_xy - proj, axis=1)   # distancia perpendicular

    return (t > 0) & (t < 1) & (perp <= buffer)


# --------------------------------------------------------------------------- #
# Metrica: passes que quebram linhas
# --------------------------------------------------------------------------- #

def passes_quebra_linhas(jogo, buffer=5.0, min_progressao=5.0,
                         apenas_completos=True, minimo=1):
    """
    Deteta passes que quebram linhas, usando os freeze frames 360.

    Considera apenas passes que:
      - tem freeze frame 360 associado;
      - sao progressivos (avancam pelo menos `min_progressao` rumo a x=120);
      - (opcional) foram completados com sucesso.

    Para cada um, conta quantos adversarios foram quebrados (ver
    adversarios_quebrados). Devolve um DataFrame ordenado do passe que mais
    linhas quebra para o que quebrou menos, com os passes que quebram >= `minimo`.

    Nota metodologica: o freeze frame corresponde ao INSTANTE do passe; os adversarios
    podem mover-se ate a bola chegar. A contagem corresponde, portanto, sobre o cenário
    no momento em que o passe e dado - é o padrao para esta analise.
    """
    passes = jogo.por_tipo("Pass").copy()

    com360 = set(jogo.freeze["event_uuid"].unique())
    passes = passes[passes["id"].isin(com360) & passes["pass_end_x"].notna()]

    # progressivo: a bola avanca rumo a baliza adversaria (x cresce)
    passes = passes[(passes["pass_end_x"] - passes["x"]) >= min_progressao]

    # passe completo = sem pass_outcome_name (so os falhados trazem outcome)
    if apenas_completos and "pass_outcome_name" in passes.columns:
        passes = passes[passes["pass_outcome_name"].isna()]

    registos = []
    for _, p in passes.iterrows():
        frame = jogo.freeze_de(p["id"])
        opp = frame[~frame["teammate"]]
        mask = adversarios_quebrados(
            opp[["ff_x", "ff_y"]].values,
            p["x"], p["y"], p["pass_end_x"], p["pass_end_y"],
            buffer=buffer,
        )
        registos.append({
            "id": p["id"],
            "minute": int(p["minute"]),
            "second": int(p["second"]),
            "team_name": p["team_name"],
            "player_name": p["player_name"],
            "recipient": p.get("pass_recipient_name"),
            "x": p["x"], "y": p["y"],
            "end_x": p["pass_end_x"], "end_y": p["pass_end_y"],
            "play_pattern": p.get("play_pattern_name"),
            "n_quebrados": int(mask.sum()),
        })

    df = pd.DataFrame(registos)
    if df.empty:
        return df
    return (df[df["n_quebrados"] >= minimo]
            .sort_values(["n_quebrados", "minute", "second"],
                         ascending=[False, True, True])
            .reset_index(drop=True))


def resumo_por_jogador(df_quebras):
    """Agrega o resultado de passes_quebra_linhas por jogador."""
    if df_quebras.empty:
        return df_quebras
    return (df_quebras
            .groupby(["team_name", "player_name"])
            .agg(passes_quebra_linha=("id", "count"),
                 total_adversarios_quebrados=("n_quebrados", "sum"),
                 max_num_quebrados=("n_quebrados", "max"))
            .sort_values("total_adversarios_quebrados", ascending=False)
            .reset_index())


# --------------------------------------------------------------------------- #
# Metrica: acoes sob pressao (lado ofensivo) + pressao aplicada (lado defensivo)
# --------------------------------------------------------------------------- #

def _mapa_pressure(jogo):
    """
    {id_da_acao_pressionada: [nomes de quem pressionou]}.

    Construido a partir dos eventos Pressure e do seu related_events - e a
    peça que usa related_events para ligar a acao pressionadora à acao pressionada. 
    """
    mapa = {}
    for _, p in jogo.por_tipo("Pressure").iterrows():
        rel = p.get("related_events")
        if isinstance(rel, list):
            for rid in rel:
                mapa.setdefault(rid, []).append(p["player_name"])
    return mapa


def _perdeu_posse(ev):
    """Responde à questao: esta acao resultou em perda de posse?"""
    t = ev["type_name"]
    if t in ("Miscontrol", "Dispossessed"):
        return True
    if t == "Pass":
        return isinstance(ev.get("pass_outcome_name"), str)   # falhados tem outcome
    if t == "Dribble":
        return ev.get("dribble_outcome_name") == "Incomplete"
    return False


def acoes_sob_pressao(jogo, tipos=None):
    """
    Todas as acoes realizadas sob pressao (under_pressure=True), enriquecidas
    com o resultado (perdeu ou nao a posse) e quem aplicou a pressao (através do _mapa_pressure).

    tipos : lista opcional de tipos a manter (ex.: ["Pass"] para passes sob
            pressao). Por omissao inclui todas as acoes do portador.
    """
    ev = jogo.events
    if "under_pressure" not in ev.columns:
        return pd.DataFrame()

    sob = ev[ev["under_pressure"].fillna(False).astype(bool)].copy()
    sob = sob[sob["type_name"] != "Pressure"]     # Pressure e a acao defensiva
    if tipos:
        sob = sob[sob["type_name"].isin(tipos)]

    mapa = _mapa_pressure(jogo)
    registos = []
    for _, e in sob.iterrows():
        registos.append({
            "id": e["id"],
            "minute": int(e["minute"]), "second": int(e["second"]),
            "team_name": e["team_name"], "player_name": e.get("player_name"),
            "type_name": e["type_name"],
            "x": e.get("x"), "y": e.get("y"),
            "perdeu_posse": _perdeu_posse(e),
            "pressores": mapa.get(e["id"], []),
        })
    return pd.DataFrame(registos)


def resumo_pressao_por_jogador(df_acoes):
    """
    Lado ofensivo: por jogador, quantas acoes sob pressao fez e
    que % delas manteve a posse. So conta acoes cujo resultado e mensuravel
    (as que nunca "perdem" por natureza inflacionariam a retencao).
    """
    if df_acoes.empty:
        return df_acoes
    g = (df_acoes.groupby(["team_name", "player_name"])
         .agg(acoes_sob_pressao=("id", "count"),
              perdas=("perdeu_posse", "sum"))
         .reset_index())
    g["retencao_pct"] = (100 * (1 - g["perdas"] / g["acoes_sob_pressao"])).round(1)
    return (g.sort_values("acoes_sob_pressao", ascending=False)
            .reset_index(drop=True))


def pressao_aplicada_por_jogador(jogo):
    """Lado defensivo: pressoes aplicadas por jogador (eventos Pressure)."""
    press = jogo.por_tipo("Pressure")
    if press.empty:
        return press
    return (press.groupby(["team_name", "player_name"])
            .size().reset_index(name="pressoes_aplicadas")
            .sort_values("pressoes_aplicadas", ascending=False)
            .reset_index(drop=True))