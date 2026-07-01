"""
app.py — aplicacao Streamlit: analise tatica de um jogo StatsBomb (com 360).

Camada de apresentacao. Orquestra extract/data/metrics/viz e organiza a
informacao em separadores. Selecao de jogo com botao "Analisar jogo".

Correr a partir da raiz do projeto:  streamlit run app.py
"""

import os

import matplotlib.pyplot as plt
import streamlit as st

from src.extract import listar_competicoes, listar_jogos, descarregar_jogo
from src.data import carregar_jogo
from src.metrics import (passes_quebra_linhas, resumo_por_jogador,
                         acoes_sob_pressao, resumo_pressao_por_jogador,
                         pressao_aplicada_por_jogador)
from src.viz import (plotar_quebra_linhas, plotar_mapa_pressao, plotar_freeze,
                     plotar_onze_inicial)

ALVO = {"match_id": 3943043, "competition_id": 55, "season_id": 282}
DATA_DIR = "data_dir"
MIN_ACOES = 8
CORES_DEFEITO = ["#C8102E", "#1D4ED8"]
CORES_CONHECIDAS = {"Spain": "#C8102E", "England": "#EDEDED"}
LOGO = "assets/statsbomb.png"

st.set_page_config(page_title="Football Analytics — StatsBomb 360",
                   page_icon="⚽", layout="wide")

# logótipo discreto no canto superior (se o ficheiro existir)
if os.path.exists(LOGO):
    try:
        st.logo(LOGO)
    except Exception:
        pass

# leve toque de fundo futebolístico (o tema principal vem do config.toml)
st.markdown(
    "<style>.stApp{background:linear-gradient(180deg,#f3f8f3 0%,#eef4ee 100%);}</style>",
    unsafe_allow_html=True,
)


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


RENOMEAR = {
    "team_name": "Equipa", "player_name": "Jogador", "recipient": "Recetor",
    "minute": "Minuto", "n_quebrados": "Adversários quebrados",
    "passes_quebra_linha": "Passes que quebram linhas",
    "total_adversarios_quebrados": "Adversários quebrados (total)",
    "max_num_quebrados": "Máx. num só passe",
    "acoes_sob_pressao": "Ações sob pressão", "perdas": "Perdas de posse",
    "retencao_pct": "Retenção (%)", "pressoes_aplicadas": "Pressões aplicadas",
}


def bonito(df):
    """Renomeia colunas técnicas para nomes naturais (apenas para exibição)."""
    return df.rename(columns=RENOMEAR)


# --------------------------------------------------------------------------- #
# BARRA LATERAL — selecao (só analisa ao clicar no botao)
# --------------------------------------------------------------------------- #
st.sidebar.header("1 · Escolher jogo")
try:
    comps = competicoes()
except Exception:
    st.error("Não foi possível contactar o repositório StatsBomb. Verifica a Internet.")
    st.stop()

st.sidebar.checkbox(
    "Só competições com dados 360", value=True, disabled=True,
    help="A análise assenta nos dados 360, por isso esta opção está sempre ativa.")
if "match_available_360" in comps.columns:
    comps = comps[comps["match_available_360"].notna()]
comps = comps.sort_values(["competition_name", "season_name"]).reset_index(drop=True)
comp_labels = (comps["competition_name"] + " · " + comps["season_name"]).tolist()

cmask = ((comps["competition_id"] == ALVO["competition_id"]) &
         (comps["season_id"] == ALVO["season_id"]))
cidx = int(comps.index[cmask][0]) if cmask.any() else 0
ci = st.sidebar.selectbox("Competição / época", range(len(comps)),
                          index=cidx, format_func=lambda i: comp_labels[i])
comp_id = int(comps.iloc[ci]["competition_id"])
season_id = int(comps.iloc[ci]["season_id"])

js = jogos(comp_id, season_id).reset_index(drop=True)
if js.empty:
    st.warning("Sem jogos para esta competição/época.")
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

if st.sidebar.button("⚽  Analisar jogo", type="primary", width="stretch"):
    st.session_state["jogo_sel"] = (match_id, comp_id, season_id)

# --------------------------------------------------------------------------- #
# ECRA INICIAL (enquanto nao se clica em Analisar)
# --------------------------------------------------------------------------- #
if "jogo_sel" not in st.session_state:
    st.title("⚽ Football Analytics")
    st.markdown(
        "Análise tática de jogos de futebol a partir dos dados abertos da "
        "**StatsBomb**, com foco no *tracking* 360.\n\n"
        "**Como usar:** escolhe uma competição e um jogo na barra lateral e "
        "clica em **«Analisar jogo»**."
    )
    st.info("Nenhum jogo analisado ainda. A seleção não descarrega nada até clicares no botão.")
    st.sidebar.caption("Dados: StatsBomb")
    st.stop()

match_id, comp_id, season_id = st.session_state["jogo_sel"]
jogo = carregar(match_id, comp_id, season_id)
casa, fora = jogo.equipas
m = jogo.match.iloc[0]

# cores (só aparecem depois de haver jogo carregado)
st.sidebar.header("2 · Cores das equipas")
c_casa = st.sidebar.color_picker(casa, CORES_CONHECIDAS.get(casa, CORES_DEFEITO[0]))
c_fora = st.sidebar.color_picker(fora, CORES_CONHECIDAS.get(fora, CORES_DEFEITO[1]))
CORES = {casa: c_casa, fora: c_fora}
st.sidebar.caption("Altere as cores clicando na cor atual.")
st.sidebar.caption("Dados: StatsBomb")

# --------------------------------------------------------------------------- #
# CABECALHO + SEPARADORES
# --------------------------------------------------------------------------- #
comp_nome = f"{m.get('competition_competition_name','')} "\
            f"{m.get('season_season_name','')}".strip()
st.markdown(
    f"## {casa} {int(m['home_score'])}–{int(m['away_score'])} {fora}  "
    f"<span style='color:gray;font-size:0.6em'>{m['match_date']} · "
    f"{comp_nome} · {m.get('competition_stage_name','')}</span>",
    unsafe_allow_html=True,
)

tab_geral, tab_concl, tab_prog, tab_press, tab_jog = st.tabs(
    ["Visão geral", "Métricas desenvolvidas", "Progressão", "Pressão", "Métricas por jogador"])

# ---- Visão geral ----
with tab_geral:
    st.caption(f"{m['match_date']} · {m.get('competition_stage_name','')} · "
               f"{m.get('stadium_name','')} · árbitro {m.get('referee_name','?')}")
    fig, _ = plotar_onze_inicial(jogo, cores=CORES)
    mostrar_fig(fig)

    subs = jogo.substituicoes()
    REN = {"jersey_number": "Nº Camisola", "player_name": "Nome Completo",
           "posicao_inicial": "Posição Inicial"}

    def _tabelas_equipa(team):
        lu = jogo.lineups[jogo.lineups["team_name"] == team].copy()
        lu["jersey_number"] = lu["jersey_number"].astype("Int64")
        st_eq = subs[subs["team_name"] == team]
        saiu_map = dict(zip(st_eq["saiu"], st_eq["minute"]))
        entrou_map = dict(zip(st_eq["entrou"], st_eq["minute"]))

        xi = lu[lu["titular"]].sort_values("posicao_id").copy()
        xi["Saiu"] = xi["player_name"].map(
            lambda n: f"{int(saiu_map[n])}'" if n in saiu_map else "—")
        xi_show = xi.rename(columns=REN)[
            ["Nº Camisola", "Nome Completo", "Posição Inicial", "Saiu"]]

        banco = lu[~lu["titular"]].copy()
        banco["_ord"] = banco["player_name"].map(lambda n: entrou_map.get(n, 999))
        banco = banco.sort_values(["_ord", "jersey_number"])
        banco["Entrou"] = banco["player_name"].map(
            lambda n: f"{int(entrou_map[n])}'" if n in entrou_map else "—")
        banco_show = banco.rename(columns=REN)[
            ["Nº Camisola", "Nome Completo", "Entrou"]]
        return xi_show, banco_show

    col1, col2 = st.columns(2)
    for col, team in zip((col1, col2), (casa, fora)):
        with col:
            st.markdown(f"**{team}**")
            xi_show, banco_show = _tabelas_equipa(team)
            st.markdown("Onze inicial")
            st.dataframe(xi_show, width="stretch", hide_index=True)
            st.markdown("Banco")
            st.dataframe(banco_show, width="stretch", hide_index=True)

# ---- Conclusões ----
with tab_concl:
    ql = quebra(match_id, comp_id, season_id)
    rank_ql = resumo_por_jogador(ql)
    st.subheader("1 · Passes que quebram linhas")
    if not ql.empty:
        tot = ql.groupby("team_name")["n_quebrados"].sum()
        top_team = tot.idxmax()
        top_share = int((rank_ql.head(10)["team_name"] == top_team).sum())
        tj = rank_ql.iloc[0]
        st.markdown(
            f"**{top_team}** liderou a progressão: ocupa **{top_share} dos 10** lugares "
            f"cimeiros do ranking, e **{tj['player_name']}** destaca-se com "
            f"**{int(tj['total_adversarios_quebrados'])} adversários ultrapassados** "
            f"em {int(tj['passes_quebra_linha'])} passes executados."
        )
        cc1, cc2 = st.columns([1, 1])
        cc1.dataframe(bonito(rank_ql), width="stretch", hide_index=True)
        with cc2:
            hero = ql[ql["team_name"] == top_team].iloc[0]
            fig, _ = plotar_quebra_linhas(jogo, hero["id"], cores=CORES)
            mostrar_fig(fig)

    st.subheader("2 · Ações sob pressão")
    comp = compostura(match_id, comp_id, season_id)
    alto = comp[comp["acoes_sob_pressao"] >= MIN_ACOES]
    media = alto.groupby("team_name")["retencao_pct"].mean().round(0)
    if len(media) >= 2:
        melhor, pior = media.idxmax(), media.idxmin()
        st.markdown(
            f"Entre os mais solicitados sob pressão (≥{MIN_ACOES} passes), **{melhor}** "
            f"reteve **{media[melhor]:.0f}%** da posse, contra **{media[pior]:.0f}%** "
            f"de **{pior}** — diferença clara de serenidade com bola."
        )
    fig, _ = plotar_mapa_pressao(jogo)
    mostrar_fig(fig)

    # ------------------------------------------------------------------ #
    # LEITURA TÁTICA (texto curado, escrito à mão; só para o jogo alvo).
    # Edita livremente o texto abaixo para escrever a tua própria análise.
    # ------------------------------------------------------------------ #
    if match_id == ALVO["match_id"]:
        st.markdown("#### Insights Principais")
        st.markdown(
            "A Espanha foi claramente superior na progressão ofensiva, liderando as estatísticas de passes que quebram linhas, confirmando assim ser uma equipa muito forte a descobrir soluções em posse. É de destacar os jogadores Nico Williams e Dani Olmo, cujos passes foram os que mais quebraram linhas adversários em relação ao número de passes efetuados por eles. De destacar os dois defesas centrais estarem no topo da lista, confirmando que a Espanha é auma equipa que priveligia a saída em posse desde a 1ª fase de construção, com defesas muito confortáveis com bola no pé. "
        )
        st.markdown(
            "As métricas das Ações sob pressão confirmam a principal valência desta equipa: o momento com bola. Os 89% de retenção da posse sob pressão confirmam a dificuldade do adversário em retirar a bola à Espanha, sendo a diferença de 16% para a Inglaterra um indicador claro da qualidade da Espanha com bola."
        )

# ---- Progressão ----
with tab_prog:
    cc1, cc2 = st.columns(2)
    buffer = cc1.slider("Largura do corredor (buffer)", 2.0, 10.0, 5.0, 0.5)
    min_prog = cc2.slider("Progressão mínima", 0.0, 20.0, 5.0, 1.0)
    ql2 = quebra(match_id, comp_id, season_id, buffer, min_prog)
    st.markdown("#### Todos os passes que quebram linhas registados")
    st.caption(f"{len(ql2)} passes que quebram pelo menos 1 linha.")
    st.dataframe(bonito(ql2[["minute", "team_name", "player_name", "recipient", "n_quebrados"]]),
                 width="stretch", hide_index=True)
    if not ql2.empty:
        st.markdown("#### Selecionar Freeze Frames de cada passe progressivo")
        rot = {f"{int(r.minute)}' · {r.player_name} → {r.recipient} "
               f"(quebra {int(r.n_quebrados)})": r.id for r in ql2.itertuples()}
        esc = st.selectbox("Ver o freeze frame de um passe", list(rot))
        fig, _ = plotar_quebra_linhas(jogo, rot[esc], buffer=buffer, cores=CORES)
        mostrar_fig(fig)

# ---- Pressão ----
with tab_press:
    fig, _ = plotar_mapa_pressao(jogo)
    mostrar_fig(fig)
    cc1, cc2 = st.columns(2)
    cc1.markdown("**Compostura no passe sob pressão** (retenção %)")
    cc1.dataframe(bonito(compostura(match_id, comp_id, season_id)), width="stretch", hide_index=True)
    cc2.markdown("**Pressões aplicadas por jogador**")
    cc2.dataframe(bonito(pressao(match_id, comp_id, season_id)), width="stretch", hide_index=True)

# ---- Por jogador ----
with tab_jog:
    nomes = sorted(jogo.lineups["player_name"].dropna().unique())
    jsel = st.selectbox("Jogador", nomes)
    ql_all = quebra(match_id, comp_id, season_id)
    mine = ql_all[ql_all["player_name"] == jsel]
    m1, m2 = st.columns(2)
    m1.metric("Passes que quebram linhas", len(mine))
    m2.metric("Adversários quebrados", int(mine["n_quebrados"].sum()) if not mine.empty else 0)
    if not mine.empty:
        st.dataframe(bonito(mine[["minute", "recipient", "n_quebrados"]]),
                     width="stretch", hide_index=True)
        rot = {f"{int(r.minute)}' → {r.recipient} (quebra {int(r.n_quebrados)})": r.id
               for r in mine.itertuples()}
        esc = st.selectbox("Ver passe", list(rot))
        fig, _ = plotar_quebra_linhas(jogo, rot[esc], cores=CORES)
        mostrar_fig(fig)
    else:
        st.info("Este jogador não tem passes que quebram linhas registados.")

    st.divider()
    st.markdown("**Explorar ações com dados 360**")
    com360 = set(jogo.freeze["event_uuid"])
    acoes = jogo.events[
        (jogo.events["player_name"] == jsel)
        & (jogo.events["id"].isin(com360))
        & (jogo.events["x"].notna())
    ].copy()
    if acoes.empty:
        st.info("Este jogador não tem ações com dados 360.")
    else:
        tipos = sorted(acoes["type_name"].unique())
        tsel = st.selectbox("Tipo de ação", tipos, key="tipo_acao_jog")
        subset = acoes[acoes["type_name"] == tsel]

        def _rot_acao(r):
            base = f"{int(r.minute)}' · {r.type_name}"
            rec = getattr(r, "pass_recipient_name", None)
            if r.type_name == "Pass" and isinstance(rec, str):
                base += f" → {rec}"
            out = getattr(r, "shot_outcome_name", None)
            if r.type_name == "Shot" and isinstance(out, str):
                base += f" ({out})"
            return base

        rots = {_rot_acao(r): r.id for r in subset.itertuples()}
        asel = st.selectbox("Ação", list(rots), key="acao_jog")
        fig, _ = plotar_freeze(jogo, rots[asel], cores=CORES)
        mostrar_fig(fig)