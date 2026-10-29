"""Painel local de configuração; não hospeda segredos e não envia mensagens."""
import json
import shutil
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).parent
FILE = ROOT / "config.json"
EXAMPLE = ROOT / "config.example.json"

st.set_page_config(page_title="Escanteios HT/FT", page_icon="⚽")
st.title("Painel de escanteios HT/FT")
st.caption("Configura regras não secretas localmente. Não publique este painel sem autenticação.")
if not FILE.exists():
    shutil.copy(EXAMPLE, FILE)
cfg = json.loads(FILE.read_text(encoding="utf-8"))

st.warning("Modo seguro: o bot fica desativado e em simulação até você validar a API e os logs.")
cfg["enabled"] = st.toggle("Habilitar consultas", value=cfg.get("enabled", False))
cfg["dry_run"] = st.toggle("Simulação: não enviar ao Telegram", value=cfg.get("dry_run", True))
for phase, title in (("ht", "Primeiro tempo (HT)"), ("ft", "Jogo inteiro (FT)")):
    with st.expander(title, expanded=True):
        item = cfg[phase]
        item["enabled"] = st.toggle("Monitorar", value=item["enabled"], key=f"{phase}_enabled")
        item["min_corners"] = st.number_input("Escanteios mínimos", min_value=0, max_value=40, value=item["min_corners"], key=f"{phase}_corners")
        item["minute_from"] = st.number_input("Minuto inicial", min_value=0, max_value=120, value=item["minute_from"], key=f"{phase}_start")
        item["minute_to"] = st.number_input("Minuto final", min_value=0, max_value=120, value=item["minute_to"], key=f"{phase}_end")
cfg["max_matches"] = st.slider("Máximo de partidas por consulta", 0, 20, cfg.get("max_matches", 6))
league_text = st.text_input("IDs de ligas (separados por vírgula; vazio = todas)", value=", ".join(map(str, cfg.get("league_ids", []))))
if st.button("Salvar configuração"):
    try:
        cfg["league_ids"] = [int(x.strip()) for x in league_text.split(",") if x.strip()]
        for phase in ("ht", "ft"):
            item = cfg[phase]
            if item["minute_from"] > item["minute_to"]:
                raise ValueError(f"Minutos inválidos em {phase}")
        FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        st.success("Salvo em config.json (sem senhas/tokens).")
    except ValueError as exc:
        st.error(str(exc))
st.info("Credenciais ficam SOMENTE nos Secrets do GitHub Actions. O painel não exibe nem armazena tokens.")
