"""
app.py — aplicacao Streamlit: analise da final do Euro 2024 (Espanha-Inglaterra).

Camada de apresentacao. Nao implementa logica: importa data.py, metrics.py e
viz.py, e limita-se a orquestrar e mostrar.

Correr a partir da raiz do projeto:  streamlit run app.py
"""

import matplotlib.pyplot as plt
import streamlit as st

from src.data import carregar_jogo
from src.metrics import (passes_quebra_linhas, resumo_por_jogador,
                         acoes_sob_pressao, resumo_pressao_por_jogador,
                         pressao_aplicada_por_jogador)
from src.viz import plotar_quebra_linhas, plotar_mapa_pressao, plotar_freeze

# --------------------------------------------------------------------------- #
# Configuracao do jogo
# --------------------------------------------------------------------------- #
DATA_DIR = "data_dir"
MATCH_ID = 3943043
COMPETITION_ID = 55
SEASON_ID = 282
CORES = {"Spain": "#C8102E", "England": "#EDEDED"}   # vermelho / branco
MIN_ACOES = 8   # amostra minima para a leitura de compostura

st.set_page_config(page_title="Final Euro 2024 - Analise", layout="wide")


# --------------------------------------------------------------------------- #
# Carregamento e metricas (em cache: correm uma vez, nao a cada clique)
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="A carregar o jogo...")
def carregar():
    return carregar_jogo(DATA_DIR, MATCH_ID, COMPETITION_ID, SEASON_ID)


@st.cache_data(show_spinner=False)
def get_quebra(buffer=5.0, min_progressao=5.0):
    return passes_quebra_linhas(carregar(), buffer=buffer,
                                min_progressao=min_progressao)


@st.cache_data(show_spinner=False)
def get_compostura():
    return resumo_pressao_por_jogador(acoes_sob_pressao(carregar(), tipos=["Pass"]))


@st.cache_data(show_spinner=False)
def get_pressao():
    return pressao_aplicada_por_jogador(carregar())


def mostrar_fig(fig):
    st.pyplot(fig)
    plt.close(fig)


jogo = carregar()
m = jogo.match.iloc[0]
casa, fora = jogo.equipas

# --------------------------------------------------------------------------- #
# Cabecalho
# --------------------------------------------------------------------------- #
st.title("Final do Euro 2024 — análise tática")
st.markdown(
    f"### {casa} {int(m['home_score'])}–{int(m['away_score'])} {fora}  "
    f"<span style='color:gray;font-size:0.7em'>{m['match_date']} · "
    f"{m.get('competition_stage_name','')} · {m.get('stadium_name','')}</span>",
    unsafe_allow_html=True,
)
st.caption("Análise de um só jogo; as amostras são naturalmente reduzidas. "
           "Métricas espaciais calculadas sobre os eventos com dados 360.")

# =========================================================================== #
# INSIGHTS
# =========================================================================== #
st.header("Principais conclusões")

ql = get_quebra()
rank_ql = resumo_por_jogador(ql)
esp_top10 = int((rank_ql.head(10)["team_name"] == "Spain").sum())
top_jog = rank_ql.iloc[0]

# ---- Insight 1 ----
st.subheader("1 · A Espanha progrediu por dentro — e sempre para os extremos")
st.markdown(
    f"No ranking de **passes que quebram linhas**, a Espanha ocupa "
    f"**{esp_top10} dos 10** lugares cimeiros. **{top_jog['player_name']}** lidera, "
    f"com **{int(top_jog['total_adversarios_quebrados'])} adversários quebrados** "
    f"em {int(top_jog['passes_quebra_linha'])} passes. Os passes mais incisivos "
    f"procuram repetidamente os extremos (Nico Williams e Lamine Yamal), o que "
    f"traduz o plano espanhol: sair a jogar por dentro e libertar a velocidade nas alas."
)
c1, c2 = st.columns([1, 1])
with c1:
    st.markdown("**Ranking de progressão (passes que quebram linhas)**")
    st.dataframe(rank_ql, width="stretch", hide_index=True)
with c2:
    hero = ql[ql["team_name"] == "Spain"].iloc[0]
    st.markdown(f"**Passe-assinatura:** {hero['player_name']} → {hero['recipient']} "
                f"(quebra {int(hero['n_quebrados'])}), aos {int(hero['minute'])}'")
    fig, _ = plotar_quebra_linhas(jogo, hero["id"], cores=CORES)
    mostrar_fig(fig)

st.divider()

# ---- Insight 2 ----
st.subheader("2 · Pressão semelhante, compostura muito diferente")
comp = get_compostura()
alto_vol = comp[comp["acoes_sob_pressao"] >= MIN_ACOES]
media_ret = alto_vol.groupby("team_name")["retencao_pct"].mean().round(0)
ret_esp = media_ret.get("Spain", float("nan"))
ret_eng = media_ret.get("England", float("nan"))
st.markdown(
    f"O volume de pressão foi equilibrado, mas a resposta a essa pressão não. "
    f"Entre os jogadores mais solicitados sob pressão (≥{MIN_ACOES} passes), a Espanha "
    f"reteve a posse em média **{ret_esp:.0f}%** contra **{ret_eng:.0f}%** da Inglaterra. "
    f"Os homens-chave ingleses cederam sob pressão, enquanto os espanhóis se mantiveram serenos."
)
st.markdown("**Onde cada equipa pressiona**")
fig, _ = plotar_mapa_pressao(jogo)
mostrar_fig(fig)
c1, c2 = st.columns([1, 1])
with c1:
    st.markdown("**Compostura no passe sob pressão** (retenção %)")
    st.dataframe(comp, width="stretch", hide_index=True)
with c2:
    st.markdown("**Pressões aplicadas por jogador**")
    st.dataframe(get_pressao(), width="stretch", hide_index=True)

# =========================================================================== #
# EXPLORACAO
# =========================================================================== #
st.header("Exploração")
tab1, tab2, tab3 = st.tabs(["Passes que quebram linhas", "Pressão", "Remates (360)"])

with tab1:
    st.markdown("Ajusta os parâmetros da métrica e inspeciona qualquer passe.")
    cc1, cc2 = st.columns(2)
    buffer = cc1.slider("Largura do corredor (buffer)", 2.0, 10.0, 5.0, 0.5)
    min_prog = cc2.slider("Progressão mínima", 0.0, 20.0, 5.0, 1.0)
    ql2 = get_quebra(buffer, min_prog)
    st.caption(f"{len(ql2)} passes que quebram pelo menos 1 linha.")
    st.dataframe(ql2[["minute", "team_name", "player_name", "recipient", "n_quebrados"]],
                 width="stretch", hide_index=True)
    if not ql2.empty:
        rotulos = {
            f"{int(r.minute)}' · {r.player_name} → {r.recipient} (quebra {int(r.n_quebrados)})": r.id
            for r in ql2.itertuples()
        }
        escolha = st.selectbox("Escolhe um passe para ver o freeze frame", list(rotulos))
        fig, _ = plotar_quebra_linhas(jogo, rotulos[escolha], buffer=buffer, cores=CORES)
        mostrar_fig(fig)

with tab2:
    fig, _ = plotar_mapa_pressao(jogo)
    mostrar_fig(fig)
    st.dataframe(comp, width="stretch", hide_index=True)

with tab3:
    st.markdown("Freeze frames dos remates — inclui os golos.")
    remates = jogo.por_tipo("Shot")
    remates = remates[remates["id"].isin(set(jogo.freeze["event_uuid"]))]
    rotulos = {
        f"{int(r.minute)}' · {r.player_name} ({r.team_name})"
        + (f" — {r.shot_outcome_name}" if "shot_outcome_name" in remates.columns else ""): r.id
        for r in remates.itertuples()
    }
    if rotulos:
        escolha = st.selectbox("Escolhe um remate", list(rotulos))
        fig, _ = plotar_freeze(jogo, rotulos[escolha], cores=CORES)
        mostrar_fig(fig)
    else:
        st.info("Nenhum remate com dados 360 neste jogo.")