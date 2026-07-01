"""
testar.py — exploração da estrutura dos DataFrames produzidos pelo extrair.py.

Objetivo: ver o que saiu em cada tabela (events, lineups, match, freeze)
antes de partir para as métricas. Corre com:  python testar.py
"""

import pandas as pd
from src.data import carregar_jogo
from src.viz import plotar_freeze, plotar_quebra_linhas, plotar_mapa_pressao
from src.metrics import passes_quebra_linhas, resumo_por_jogador
from src.metrics import (acoes_sob_pressao, resumo_pressao_por_jogador,
                         pressao_aplicada_por_jogador)

# --- mostrar tudo, sem cortes com "..." ---
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", 40)


def cols(df, *nomes):
    """Devolve só as colunas que existem (evita erros se faltar alguma)."""
    return [c for c in nomes if c in df.columns]


jogo = carregar_jogo("data_dir", match_id=3943043, competition_id=55, season_id=282)

# definir as cores reais das equipas (para o plotar_freeze e plotar_quebra_linhas)
cores = {
    "Spain": "#C8102E",     # vermelho
    "England": "#FFFFFF",   # branco
}
#print("=" * 70)
#print(jogo.resumo())
# um evento qualquer com 360
event_id = jogo.eventos_com_360().iloc[20]["id"]
fig, ax = plotar_freeze(jogo, event_id, cores=cores)
fig.savefig("outputs/frame.png", dpi=130, bbox_inches="tight")


# ======================================================================
# 1. EVENTS
# ======================================================================
ev = jogo.events
print("\n" + "=" * 70)
print(f"EVENTS — {ev.shape[0]} linhas x {ev.shape[1]} colunas")
print("=" * 70)

# Todas as colunas disponíveis (são muitas; convém ver a lista completa)
#print("\n-- todas as colunas --")
#print(list(ev.columns))

# Tipos de dados de cada coluna
#print("\n-- dtypes --")
#print(ev.dtypes)

# Núcleo dos eventos por ordem temporal
print("\n-- primeiros eventos (núcleo) --")
nucleo = cols(ev, "index", "minute", "second", "type_name", "team_name",
              "player_name", "x", "y", "possession", "play_pattern_name")
print(ev[nucleo].head(12).to_string(index=False))

# Que tipos de evento existem e com que frequência
print("\n-- contagem por tipo de evento --")
print(ev["type_name"].value_counts())

# Como começaram as fases de jogo
print("\n-- contagem por play_pattern --")
print(ev["play_pattern_name"].value_counts())

# Ver TODOS os campos preenchidos de UM passe (truque: esconder colunas vazias)
print("\n-- um Pass com todas as colunas não-vazias --")
um_passe = ev[ev["type_name"] == "Pass"].iloc[0]
print(um_passe.dropna().to_string())


# ======================================================================
# 2. LINEUPS
# ======================================================================
lu = jogo.lineups
print("\n" + "=" * 70)
print(f"LINEUPS — {lu.shape[0]} linhas x {lu.shape[1]} colunas")
print("=" * 70)
print("\n-- colunas --")
print(list(lu.columns))
print("\n-- titulares por equipa --")
titulares = lu[lu["titular"]]
print(titulares[cols(lu, "team_name", "jersey_number", "player_name", "posicao_inicial")]
      .to_string(index=False))


# ======================================================================
# 3. MATCH (metadados — 1 linha, muitas colunas: ver transposto)
# ======================================================================
#print("\n" + "=" * 70)
#print("MATCH — metadados do jogo (transposto para leitura)")
#print("=" * 70)
#print(jogo.match.iloc[0].to_string())


# ======================================================================
# 4. FREEZE (360 em forma longa)
# ======================================================================
fz = jogo.freeze
print("\n" + "=" * 70)
print(f"FREEZE (360) — {fz.shape[0]} linhas x {fz.shape[1]} colunas")
print("=" * 70)
print(f"eventos distintos com 360: {fz['event_uuid'].nunique()}")
print("\n-- colunas --")
print(list(fz.columns))
print("\n-- primeiras linhas --")
print(fz.head(10).to_string(index=False))

# Um freeze frame completo (todos os jogadores de um evento)
print("\n-- freeze frame de um evento --")
ev_id = jogo.eventos_com_360().iloc[20]["id"]
frame = jogo.freeze_de(ev_id)
print(f"evento {ev_id} — {len(frame)} jogadores "
      f"({int(frame['teammate'].sum())} colegas, "
      f"{int((~frame['teammate']).sum())} adversários)")
print(frame.to_string(index=False))


# ======================================================================
# 5. MÉTRICAS
# ======================================================================

# Passes que quebram linhas
# 1) calcular -> isto dá-te a TABELA (vês no terminal ao imprimir)
df = passes_quebra_linhas(jogo)
print(f"\nPasses que quebram linhas: {len(df)}")
print(df[["minute", "team_name", "player_name", "recipient", "n_quebrados"]].head(10).to_string(index=False))

print("\nRanking por jogador:")
print(resumo_por_jogador(df).head(8).to_string(index=False))

# 2) desenhar UM passe concreto -> isto gera a IMAGEM
melhor = df.iloc[0]            # o que mais linhas quebra
fig, ax = plotar_quebra_linhas(jogo, melhor["id"], cores=cores)
fig.savefig("outputs/quebra_linhas.png", dpi=130, bbox_inches="tight")
print(f"\nimagem do melhor passe guardada em outputs/quebra_linhas.png")


# Pressão
df = acoes_sob_pressao(jogo)                          # todas as ações sob pressão
compostura = resumo_pressao_por_jogador(acoes_sob_pressao(jogo, tipos=["Pass"]))  # compostura no passe
pressao = pressao_aplicada_por_jogador(jogo)                    # quem mais pressiona

# imprimir
print(f"\nAções sob pressão no total: {len(df)}")

print("\nCompostura no passe (retenção sob pressão):")
print(compostura.head(10).to_string(index=False))

print("\nQuem mais pressiona:")
print(pressao.head(10).to_string(index=False))

# mapa pressão no campo
fig, axs = plotar_mapa_pressao(jogo)
fig.savefig("outputs/mapa_pressao.png", dpi=130, bbox_inches="tight")