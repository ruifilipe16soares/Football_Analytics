# Football_Analytics

Análise tática de jogos de futebol a partir dos dados abertos da StatsBomb,
com foco nos dados de tracking 360. Exemplo principal: final do Euro 2024.

## Estrutura
- `src/extract.py` — download seletivo de jogos do repositório StatsBomb
- `src/data.py` — carregamento e estruturação em DataFrames
- `src/metrics.py` — métricas (passes que quebram linhas com 360; ações sob pressão)
- `src/viz.py` — visualizações espaciais (freeze frames, mapa de pressão)
- `app.py` — aplicação Streamlit
- `testar.py` — script de exploração

## Como correr
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
streamlit run app.py