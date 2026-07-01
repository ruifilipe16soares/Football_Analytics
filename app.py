"""
app.py — aplicacao Streamlit: analise tatica de um jogo StatsBomb (com 360).

Camada de apresentacao. Nao implementa logica: orquestra extract/data/metrics/viz.
Camada inicial de SELECAO de jogo (competicao -> epoca -> jogo), com download a
pedido via extract.py e cores das equipas dinamicas.

Correr a partir da raiz do projeto:  streamlit run app.py
"""

import matplotlib.pyplot as plt
import streamlit as st

from src.extract import listar_competicoes, listar_jogos, descarregar_jogo
from src.data import carregar_jogo
from src.metrics import (passes_quebra_linhas, resumo_por_jogador,
                         acoes_sob_pressao, resumo_pressao_por_jogador,
                         pressao_aplicada_por_jogador)
from src.viz import plotar_quebra_linhas, plotar_mapa_pressao, plotar_freeze

# jogo pre-selecionado por omissao (a final do Euro 2024)
ALVO = {"match_id": 3943043, "competition_id": 55, "season_id": 282}
DATA_DIR = "data_dir"
MIN_ACOES = 8                       # amostra minima para a leitura de compostura
CORES_DEFEITO = ["#C8102E", "#1D4ED8"]
CORES_CONHECIDAS = {"Spain": "#C8102E", "England": "#EDEDED"}

st.set_page_config(page_title="StatsBomb 360 — Análise de jogo", layout="wide")


# --------------------------------------------------------------------------- #
# Loaders em cache
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def competicoes():
    return listar_competicoes()


@st.cache_data(show_spinner=False)
def jogos(comp, season):
    return listar_jogos(comp, season)


@st.cache_resource(show_spinner="A descarregar e carregar o jogo...")
def carregar(match_id, comp, season):
    descarregar_jogo(match_id, comp, season, DATA_DIR)
    return carregar_jogo(DATA_DIR, match_id, comp, season)


@st.cache_data(show_spinner=False)
def quebra(match_id, comp, season, buffer=5.0, min_prog=5.0):
    return passes_quebra_linhas(carregar(match_id, comp, season),
                                buffer=buffer, min_progressao=min_prog)


@st.cache_data(show_spinner=False)
def compostura(match_id, comp, season):
    return resumo_pressao_por_jogador(
        acoes_sob_pressao(carregar(match_id, comp, season), tipos=["Pass"]))


@st.cache_data(show_spinner=False)
def pressao(match_id, comp, season):
    return pressao_aplicada_por_jogador(carregar(match_id, comp, season))


def mostrar_fig(fig):
    st.pyplot(fig)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# BARRA LATERAL — selecao de jogo + cores
# --------------------------------------------------------------------------- #
st.sidebar.header("1 · Escolher jogo")
try:
    comps = competicoes()
except Exception:
    st.error("Não foi possível contactar o repositório StatsBomb. Verifica a ligação à Internet.")
    st.stop()

if st.sidebar.checkbox("Só competições com dados 360", value=True) \
        and "match_available_360" in comps.columns:
    comps = comps[comps["match_available_360"].notna()]

comps = comps.sort_values(["competition_name", "season_name"]).reset_index(drop=True)
comp_labels = (comps["competition_name"] + " · " + comps["season_name"]).tolist()

# indice por omissao -> competicao do ALVO
cmask = ((comps["competition_id"] == ALVO["competition_id"]) &
         (comps["season_id"] == ALVO["season_id"]))
cidx = int(comps.index[cmask][0]) if cmask.any() else 0
ci = st.sidebar.selectbox("Competição / época", range(len(comps)),
                          index=cidx, format_func=lambda i: comp_labels[i])
comp_id = int(comps.iloc[ci]["competition_id"])
season_id = int(comps.iloc[ci]["season_id"])

js = jogos(comp_id, season_id).reset_index(drop=True)
if js.empty:
    st.error("Sem jogos para esta competição/época.")
    st.stop()


def _rotulo_jogo(i):
    r = js.iloc[i]
    base = (f"{r['home_team_home_team_name']} {int(r['home_score'])}"
            f"–{int(r['away_score'])} {r['away_team_away_team_name']}")
    if "competition_stage_name" in js.columns:
        base += f"  ({r['competition_stage_name']})"
    return base


mmask = js["match_id"] == ALVO["match_id"]
midx = int(js.index[mmask][0]) if mmask.any() else 0
mi = st.sidebar.selectbox("Jogo", range(len(js)), index=midx,
                          format_func=_rotulo_jogo)
match_id = int(js.iloc[mi]["match_id"])

jogo = carregar(match_id, comp_id, season_id)
casa, fora = jogo.equipas

st.sidebar.header("2 · Cores das equipas")
c_casa = st.sidebar.color_picker(casa, CORES_CONHECIDAS.get(casa, CORES_DEFEITO[0]))
c_fora = st.sidebar.color_picker(fora, CORES_CONHECIDAS.get(fora, CORES_DEFEITO[1]))
CORES = {casa: c_casa, fora: c_fora}

# --------------------------------------------------------------------------- #
# CABECALHO
# --------------------------------------------------------------------------- #
m = jogo.match.iloc[0]
st.title("Análise tática — StatsBomb 360")
st.markdown(
    f"### {casa} {int(m['home_score'])}–{int(m['away_score'])} {fora}  "
    f"<span style='color:gray;font-size:0.7em'>{m['match_date']} · "
    f"{m.get('competition_stage_name','')} · {m.get('stadium_name','')}</span>",
    unsafe_allow_html=True,
)
st.caption("Análise de um só jogo; amostras naturalmente reduzidas. "
           "Métricas espaciais calculadas sobre os eventos com dados 360.")

# --------------------------------------------------------------------------- #
# INSIGHTS
# --------------------------------------------------------------------------- #
st.header("Principais conclusões")

ql = quebra(match_id, comp_id, season_id)
rank_ql = resumo_por_jogador(ql)

st.subheader("1 · Progressão por passe (quebra de linhas)")
if not ql.empty:
    tot = ql.groupby("team_name")["n_quebrados"].sum()
    top_team = tot.idxmax()
    top_share = int((rank_ql.head(10)["team_name"] == top_team).sum())
    top_jog = rank_ql.iloc[0]
    st.markdown(
        f"**{top_team}** liderou a progressão: ocupa **{top_share} dos 10** lugares "
        f"cimeiros do ranking de passes que quebram linhas, e **{top_jog['player_name']}** "
        f"destaca-se com **{int(top_jog['total_adversarios_quebrados'])} adversários "
        f"quebrados** em {int(top_jog['passes_quebra_linha'])} passes."
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Ranking de progressão**")
        st.dataframe(rank_ql, width="stretch", hide_index=True)
    with c2:
        hero = ql[ql["team_name"] == top_team].iloc[0]
        st.markdown(f"**Passe-assinatura:** {hero['player_name']} → {hero['recipient']} "
                    f"(quebra {int(hero['n_quebrados'])}), aos {int(hero['minute'])}'")
        fig, _ = plotar_quebra_linhas(jogo, hero["id"], cores=CORES)
        mostrar_fig(fig)
else:
    st.info("Nenhum passe que quebra linhas detetado neste jogo.")

st.divider()

st.subheader("2 · Compostura sob pressão")
comp = compostura(match_id, comp_id, season_id)
alto = comp[comp["acoes_sob_pressao"] >= MIN_ACOES]
media = alto.groupby("team_name")["retencao_pct"].mean().round(0)
if len(media) >= 2:
    melhor, pior = media.idxmax(), media.idxmin()
    st.markdown(
        f"Entre os jogadores mais solicitados sob pressão (≥{MIN_ACOES} passes), "
        f"**{melhor}** reteve a posse em média **{media[melhor]:.0f}%**, contra "
        f"**{media[pior]:.0f}%** de **{pior}** — uma diferença clara de serenidade com bola."
    )
else:
    st.markdown("Retenção de posse por jogador quando pressionado (ver tabela).")
st.markdown("**Onde cada equipa pressiona**")
fig, _ = plotar_mapa_pressao(jogo)
mostrar_fig(fig)
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Compostura no passe sob pressão** (retenção %)")
    st.dataframe(comp, width="stretch", hide_index=True)
with c2:
    st.markdown("**Pressões aplicadas por jogador**")
    st.dataframe(pressao(match_id, comp_id, season_id), width="stretch", hide_index=True)

# comentario tatico curado, so para o jogo alvo
if match_id == ALVO["match_id"]:
    with st.expander("Leitura tática — final do Euro 2024"):
        st.markdown(
            "A Espanha construiu por dentro e libertou repetidamente os extremos "
            "**Nico Williams** e **Lamine Yamal** entre linhas — o padrão de quebra de "
            "linhas confirma-o, com os defesas e laterais espanhóis (Laporte, Le Normand, "
            "Carvajal, Cucurella) como origem da progressão. Já a diferença de compostura "
            "sob pressão ajuda a explicar o desfecho: os homens-chave ingleses cederam a "
            "posse com muito mais frequência do que os espanhóis quando pressionados."
        )

# --------------------------------------------------------------------------- #
# EXPLORACAO
# --------------------------------------------------------------------------- #
st.header("Exploração")
tab1, tab2, tab3 = st.tabs(["Passes que quebram linhas", "Pressão", "Remates (360)"])

with tab1:
    cc1, cc2 = st.columns(2)
    buffer = cc1.slider("Largura do corredor (buffer)", 2.0, 10.0, 5.0, 0.5)
    min_prog = cc2.slider("Progressão mínima", 0.0, 20.0, 5.0, 1.0)
    ql2 = quebra(match_id, comp_id, season_id, buffer, min_prog)
    st.caption(f"{len(ql2)} passes que quebram pelo menos 1 linha.")
    st.dataframe(ql2[["minute", "team_name", "player_name", "recipient", "n_quebrados"]],
                 width="stretch", hide_index=True)
    if not ql2.empty:
        rotulos = {
            f"{int(r.minute)}' · {r.player_name} → {r.recipient} (quebra {int(r.n_quebrados)})": r.id
            for r in ql2.itertuples()
        }
        escolha = st.selectbox("Ver o freeze frame de um passe", list(rotulos))
        fig, _ = plotar_quebra_linhas(jogo, rotulos[escolha], buffer=buffer, cores=CORES)
        mostrar_fig(fig)

with tab2:
    fig, _ = plotar_mapa_pressao(jogo)
    mostrar_fig(fig)
    st.dataframe(comp, width="stretch", hide_index=True)

with tab3:
    remates = jogo.por_tipo("Shot")
    remates = remates[remates["id"].isin(set(jogo.freeze["event_uuid"]))]
    rotulos = {}
    for r in remates.itertuples():
        rot = f"{int(r.minute)}' · {r.player_name} ({r.team_name})"
        if "shot_outcome_name" in remates.columns:
            rot += f" — {getattr(r, 'shot_outcome_name', '')}"
        rotulos[rot] = r.id
    if rotulos:
        escolha = st.selectbox("Escolhe um remate", list(rotulos))
        fig, _ = plotar_freeze(jogo, rotulos[escolha], cores=CORES)
        mostrar_fig(fig)
    else:
        st.info("Nenhum remate com dados 360 neste jogo.")