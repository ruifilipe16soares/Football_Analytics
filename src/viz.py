#!/usr/bin/env python3
"""
viz.py — visualizacoes espaciais a partir dos dados 360.

Camada de desenho: recebe um objeto Jogo (do data.py) e produz figuras
matplotlib. Nao calcula metricas nem le ficheiros - so desenha.

A figura devolvida (fig) entra diretamente:
    - num script:    fig.savefig("outputs/frame.png")
    - no Streamlit:   st.pyplot(fig)

Depende de mplsoccer (que traz o matplotlib).
"""

import matplotlib.pyplot as plt
import numpy as np
from mplsoccer import Pitch

# Cores por omissao (usadas quando nao se passa um dict `cores`)
COR_COLEGAS = "#3b82f6"      # azul
COR_ADVERSARIOS = "#ef4444"  # vermelho
COR_ACTOR = "#fbbf24"        # dourado  que destaca quem executa
COR_BOLA = "#111111"
COR_VISIVEL = "#22c55e"      # area visivel pelo tracking
COR_QUEBRADOS = "#16a34a"    # anel dos adversarios quebrados
EDGE = "#222222"             # contorno escuro: mantem visivel qualquer cor (ate branco)


def _info_evento(jogo, event_id):
    """Texto descritivo de um evento para o titulo."""
    linha = jogo.evento(event_id)
    if linha.empty:
        return f"evento {event_id}"
    e = linha.iloc[0]
    minuto = f"{int(e.get('minute', 0)):02d}:{int(e.get('second', 0)):02d}"
    return (f"{minuto}  |  {e.get('player_name', '?')}  "
            f"({e.get('team_name', '?')})  -  {e.get('type_name', '?')}")


def _resolver_cores(jogo, event_id, cores):
    """
    Resolve as cores e etiquetas pela EQUIPA REAL (nao por colega/adversario).

    Devolve (cor_actor, cor_adversaria, label_actor, label_adversaria).
    Se `cores` (dict {equipa: cor}) for dado, usa as cores reais; caso
    contrario cai nas cores por omissao (azul / vermelho).
    """
    ev = jogo.evento(event_id)
    actor_team = ev.iloc[0]["team_name"] if not ev.empty else None
    casa, fora = jogo.equipas
    if actor_team == casa:
        opp_team = fora
    elif actor_team == fora:
        opp_team = casa
    else:                                  
        opp_team = fora if actor_team != fora else casa

    if cores:
        return (cores.get(actor_team, COR_COLEGAS),
                cores.get(opp_team, COR_ADVERSARIOS),
                actor_team or "Colegas", opp_team or "Adversarios")
    return COR_COLEGAS, COR_ADVERSARIOS, "Colegas", "Adversarios"


def plotar_freeze(jogo, event_id, ax=None, mostrar_visivel=True,
                  mostrar_seta=True, titulo=None, cores=None):
    """
    Desenha o freeze frame 360 de um evento.

    - jogadores coloridos pela equipa real (ver `cores`)
    - o executante (actor) com a cor da sua equipa e um anel dourado a destacar
    - guarda-redes com contorno preto reforcado
    - area visivel pelo tracking sombreada 
    - seta da acao para passes/conducoes 

    Devolve (fig, ax). Se ax for dado, desenha nesse eixo, permitindo composição em grelhas.
    """
    frame = jogo.freeze_de(event_id)
    if frame.empty:
        raise ValueError(
            f"O evento {event_id} nao tem freeze frame 360. "
            f"Usa jogo.eventos_com_360() para escolher um que tenha."
        )

    cor_act, cor_adv, lbl_act, lbl_adv = _resolver_cores(jogo, event_id, cores)

    pitch = Pitch(pitch_type="statsbomb", line_color="#cfcfcf",
                  pitch_color="#d2f8a6")
    if ax is None:
        fig, ax = pitch.draw(figsize=(11, 7.5))
    else:
        fig = ax.figure
        pitch.draw(ax=ax)

    # 1) area visivel pelo tracking
    if mostrar_visivel:
        va = jogo.visible_area.get(event_id)
        if va:
            pontos = np.array(va).reshape(-1, 2)
            pitch.polygon([pontos], ax=ax, color=COR_VISIVEL, alpha=0.10, zorder=0)

    # 2) jogadores, por categoria
    colegas = frame[(frame["teammate"]) & (~frame["actor"])]
    adversarios = frame[~frame["teammate"]]
    actor = frame[frame["actor"]]
    guarda_redes = frame[frame["keeper"]]

    pitch.scatter(adversarios["ff_x"], adversarios["ff_y"], ax=ax, s=320,
                  color=cor_adv, edgecolors=EDGE, linewidth=1.0,
                  zorder=3, label=lbl_adv)
    pitch.scatter(colegas["ff_x"], colegas["ff_y"], ax=ax, s=320,
                  color=cor_act, edgecolors=EDGE, linewidth=1.0,
                  zorder=3, label=lbl_act)
    if not guarda_redes.empty:
        pitch.scatter(guarda_redes["ff_x"], guarda_redes["ff_y"], ax=ax, s=360,
                      facecolors="none", edgecolors="black", linewidth=2.4,
                      zorder=4, label="Guarda-redes")
    if not actor.empty:
        pitch.scatter(actor["ff_x"], actor["ff_y"], ax=ax, s=520,
                      color=cor_act, edgecolors=COR_ACTOR, linewidth=2.8,
                      zorder=5, label="Executante")

    # 3) bola + seta da acao
    ev = jogo.evento(event_id).iloc[0]
    x, y = ev.get("x"), ev.get("y")
    if x is not None and not _eh_na(x):
        pitch.scatter([x], [y], ax=ax, s=90, marker="o", color=COR_BOLA, zorder=6)
        if mostrar_seta:
            ex = ev.get("pass_end_x") if not _eh_na(ev.get("pass_end_x")) else ev.get("carry_end_x")
            ey = ev.get("pass_end_y") if not _eh_na(ev.get("pass_end_y")) else ev.get("carry_end_y")
            if ex is not None and not _eh_na(ex):
                pitch.arrows(x, y, ex, ey, ax=ax, width=2, headwidth=6,
                             color=COR_BOLA, zorder=6)

    ax.set_title(titulo or _info_evento(jogo, event_id), fontsize=12, pad=10)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9, bbox_to_anchor=(0, 0))
    return fig, ax


def plotar_quebra_linhas(jogo, event_id, buffer=5.0, ax=None, titulo=None,
                         cores=None):
    """
    Desenha um passe que quebra linhas: o freeze frame, mais o corredor do
    passe sombreado e um anel a volta dos adversarios quebrados.

    Reaproveita o plotar_freeze e a geometria do metrics.py, para que o
    desenho mostre exatamente o que a metrica contou. Aceita `cores`.
    """
    from .metrics import adversarios_quebrados

    ev = jogo.evento(event_id).iloc[0]
    x0, y0 = float(ev["x"]), float(ev["y"])
    x1 = ev.get("pass_end_x")
    y1 = ev.get("pass_end_y")
    if _eh_na(x1):
        raise ValueError("Este evento nao tem localizacao final de passe.")
    x1, y1 = float(x1), float(y1)

    fig, ax = plotar_freeze(jogo, event_id, ax=ax, mostrar_seta=True,
                            titulo=titulo, cores=cores)
    pitch = Pitch(pitch_type="statsbomb")  # so para transformar coordenadas

    # corredor do passe (retangulo de meia-largura `buffer` em torno da linha)
    d = np.array([x1 - x0, y1 - y0], dtype=float)
    norma = np.linalg.norm(d)
    if norma > 0:
        n = np.array([-d[1], d[0]]) / norma
        cantos = np.array([
            [x0, y0] + n * buffer, [x1, y1] + n * buffer,
            [x1, y1] - n * buffer, [x0, y0] - n * buffer,
        ])
        pitch.polygon([cantos], ax=ax, color="#fbbf24", alpha=0.15, zorder=1)

    # anel a volta dos adversarios quebrados
    frame = jogo.freeze_de(event_id)
    opp = frame[~frame["teammate"]]
    mask = adversarios_quebrados(opp[["ff_x", "ff_y"]].values, x0, y0, x1, y1, buffer)
    quebrados = opp[mask]
    if not quebrados.empty:
        pitch.scatter(quebrados["ff_x"], quebrados["ff_y"], ax=ax, s=620,
                      facecolors="none", edgecolors=COR_QUEBRADOS, linewidth=2.8,
                      zorder=7)

    n_q = int(mask.sum())
    base = titulo or _info_evento(jogo, event_id)
    ax.set_title(f"{base}   |   quebra {n_q} adversario(s)", fontsize=12, pad=10)
    return fig, ax


def _eh_na(v):
    """True se v for None ou NaN (pd.NA incluido). Usada antes de desenhar, para saltar
    valores em falta (ex.: um passe sem coordenada de destino)."""
    if v is None:
        return True
    try:
        return bool(np.isnan(v))
    except (TypeError, ValueError):
        return v != v


if __name__ == "__main__":
    import argparse
    from .data import carregar_jogo

    parser = argparse.ArgumentParser(description="Plotar um freeze frame 360.")
    parser.add_argument("match_id", type=int)
    parser.add_argument("--data-dir", default="data_dir")
    parser.add_argument("--competition-id", type=int, default=None)
    parser.add_argument("--season-id", type=int, default=None)
    parser.add_argument("--event-id", default=None)
    parser.add_argument("--out", default="outputs/freeze.png")
    args = parser.parse_args()

    jogo = carregar_jogo(args.data_dir, args.match_id,
                         args.competition_id, args.season_id)
    event_id = args.event_id or jogo.eventos_com_360().iloc[20]["id"]
    fig, _ = plotar_freeze(jogo, event_id)
    fig.savefig(args.out, dpi=130, bbox_inches="tight")
    print(f"guardado em {args.out}  (evento {event_id})")


def plotar_mapa_pressao(jogo, bins=(6, 4), cmap="Reds", titulo=None):
    """
    Mapa de pressao: heatmap de ONDE cada equipa aplica pressao.

    Dois paineis lado a lado (um por equipa), ambos a atacar para a direita
    (x=120), com escala de cor PARTILHADA para a comparacao ser honesta.
    x alto = pressao alta (no meio-campo adversario).

    Usa os eventos Pressure do Data Events. Devolve (fig, axs).
    """
    press = jogo.por_tipo("Pressure")
    press = press[press["x"].notna()]
    casa, fora = jogo.equipas
    equipas = [casa, fora]

    pitch = Pitch(pitch_type="statsbomb", line_color="#8a8a8a",
                  pitch_color="#f7f7f7", linewidth=1)

    # 1) calcular os bins de ambas as equipas e o maximo global (escala partilhada)
    dados = {}
    vmax = 1
    for team in equipas:
        sub = press[press["team_name"] == team]
        st = pitch.bin_statistic(sub["x"].values, sub["y"].values,
                                 statistic="count", bins=bins)
        dados[team] = (st, len(sub), sub["x"].mean())
        vmax = max(vmax, float(st["statistic"].max()))

    # 2) desenhar
    fig, axs = plt.subplots(1, 2, figsize=(16, 6))
    ultimo_pcm = None
    for ax, team in zip(axs, equipas):
        pitch.draw(ax=ax)
        st, n, mx = dados[team]
        ultimo_pcm = pitch.heatmap(st, ax=ax, cmap=cmap, vmin=0, vmax=vmax,
                                   edgecolors="#f7f7f7")
        pitch.label_heatmap(st, ax=ax, str_format="{:.0f}", color="#111",
                            fontsize=10, ha="center", va="center",
                            exclude_zeros=True)
        # seta do sentido de ataque
        ax.annotate("", xy=(0.72, -0.05), xytext=(0.28, -0.05),
                    xycoords="axes fraction",
                    arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.5))
        ax.text(0.5, -0.10, "sentido do ataque", transform=ax.transAxes,
                ha="center", fontsize=8, color="#555")
        ax.set_title(f"{team}\n{n} pressões  ·  x médio {mx:.0f}", fontsize=12)

    fig.suptitle(titulo or "Mapa de pressão — onde cada equipa pressiona",
                 fontsize=14, y=1.02)
    cbar = fig.colorbar(ultimo_pcm, ax=axs, shrink=0.6, pad=0.02)
    cbar.set_label("nº de pressões na zona", fontsize=9)
    return fig, axs


def _texto_contraste(hex_cor):
    """Preto ou branco, conforme a luminancia da cor de fundo (para legibilidade)."""
    h = str(hex_cor).lstrip("#")
    if len(h) != 6:
        return "#111111"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return "#111111" if lum > 150 else "#ffffff"


def plotar_onze_inicial(jogo, cores=None):
    """
    Onze inicial de cada equipa, posicionado pela POSICAO MEDIA real (media das
    localizacoes dos seus eventos no jogo). Dois paineis, um por equipa, ambos
    a atacar para a direita. Marcadores com o numero da camisola.

    Devolve (fig, axs).
    """
    ev = jogo.events.dropna(subset=["x", "y"])
    pos = ev.groupby("player_id")[["x", "y"]].mean()
    titulares = jogo.lineups[jogo.lineups["titular"]]
    casa, fora = jogo.equipas

    pitch = Pitch(pitch_type="statsbomb", line_color="#8a8a8a",
                  pitch_color="#f7f7f7", linewidth=1)
    fig, axs = plt.subplots(1, 2, figsize=(16, 6))
    for ax, team in zip(axs, [casa, fora]):
        pitch.draw(ax=ax)
        cor = (cores or {}).get(team, COR_COLEGAS)
        txt = _texto_contraste(cor)
        sub = titulares[titulares["team_name"] == team]
        for _, jog in sub.iterrows():
            pid = jog["player_id"]
            if pid not in pos.index:
                continue
            x, y = float(pos.loc[pid, "x"]), float(pos.loc[pid, "y"])
            pitch.scatter([x], [y], ax=ax, s=680, color=cor,
                          edgecolors=EDGE, linewidth=1.2, zorder=3)
            num = jog.get("jersey_number")
            if num is not None and num == num:   # nao NaN
                ax.text(x, y, str(int(num)), color=txt, ha="center", va="center",
                        fontsize=9, weight="bold", zorder=4)
        ax.annotate("", xy=(0.70, -0.05), xytext=(0.30, -0.05),
                    xycoords="axes fraction",
                    arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.4))
        ax.set_title(team, fontsize=13)
    fig.suptitle("Onze inicial — posição média no jogo", fontsize=14, y=1.01)
    return fig, axs