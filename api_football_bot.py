"""Alertas de escanteios via API-Football; fail-closed, teste manual primeiro."""
import json
import os
import sys
from pathlib import Path
import requests

BASE = "https://v3.football.api-sports.io"
CONFIG_PATH = Path(os.getenv("CONFIG_FILE", "config.json"))
if not CONFIG_PATH.exists() and not os.getenv("CONFIG_FILE"):
    CONFIG_PATH = Path("config.example.json")
STATE_PATH = Path(os.getenv("STATE_FILE", "state.json"))


def config():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for phase in ("ht", "ft"):
        item = cfg[phase]
        if not (0 <= int(item["minute_from"]) <= int(item["minute_to"]) <= 120 and int(item["min_corners"]) >= 0):
            raise ValueError(f"Configuração inválida: {phase}")
    if not 0 <= int(cfg["max_matches"]) <= 20:
        raise ValueError("max_matches deve ser entre 0 e 20")
    return cfg


def api(session, endpoint, params):
    key = os.environ["API_FOOTBALL_KEY"]
    response = session.get(BASE + endpoint, params=params, headers={"x-apisports-key": key}, timeout=25)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("errors") or not isinstance(data.get("response"), list):
        error = data.get("errors") if isinstance(data, dict) else "formato inválido"
        raise RuntimeError(f"API-Football falhou em {endpoint}: {str(error)[:160]}")
    return data["response"], response.headers.get("x-ratelimit-requests-remaining", "?")


def corners_by_team(rows, home_id, away_id, half):
    values = {}
    for row in rows:
        team = row.get("team", {})
        if not isinstance(team, dict):
            continue
        team_id = team.get("id")
        if team_id not in (home_id, away_id):
            continue
        stats = row.get("statistics", [])
        if not isinstance(stats, list):
            continue
        for stat in stats:
            if not isinstance(stat, dict) or stat.get("type") != "Corner Kicks":
                continue
            # API-Football half=true pode retornar um campo half; usar apenas a fase exigida.
            if half is not None and stat.get("half") not in (half, str(half)):
                continue
            value = stat.get("value")
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                values[team_id] = value
    if home_id not in values or away_id not in values:
        return None
    return values[home_id], values[away_id]


def alert(session, chat_id, token, text):
    r = session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": text}, timeout=20)
    r.raise_for_status()
    if r.json().get("ok") is not True:
        raise RuntimeError("Telegram não confirmou envio")


def main():
    cfg = config()
    if not cfg.get("enabled", False):
        print("Painel desativado; nenhum envio ou consulta")
        return
    session = requests.Session()
    fixtures, remaining = api(session, "/fixtures", {"live": "all"})
    print(f"API /fixtures: HTTP 200, jogos ao vivo={len(fixtures)}, cota restante={remaining}")
    if not fixtures and not cfg.get("allow_empty_live", False):
        raise RuntimeError("Zero jogos ao vivo: verifique cobertura/temporada antes de declarar sucesso")
    seen = set(json.loads(STATE_PATH.read_text())) if STATE_PATH.exists() else set()
    allowed = set(int(x) for x in cfg.get("league_ids", []))
    candidates = [x for x in fixtures if not allowed or x.get("league", {}).get("id") in allowed]
    candidates = candidates[:int(cfg["max_matches"])]
    if len(candidates) != len(fixtures):
        print(f"Filtrados/limitados a {len(candidates)} jogos para respeitar cota")
    for fixture in candidates:
        info = fixture.get("fixture", {})
        teams = fixture.get("teams", {})
        fid = info.get("id")
        minute = info.get("status", {}).get("elapsed")
        home, away = teams.get("home", {}), teams.get("away", {})
        if not isinstance(fid, int) or not isinstance(minute, int):
            continue
        active = [(phase, rules) for phase, rules in (("ht", cfg["ht"]), ("ft", cfg["ft"]))
                  if rules.get("enabled") and int(rules["minute_from"]) <= minute <= int(rules["minute_to"])
                  and f"{fid}:{phase}" not in seen]
        if not active:
            continue
        rows, remaining = api(session, "/fixtures/statistics", {"fixture": fid})
        if not rows:
            print(f"Jogo {fid}: estatísticas indisponíveis; ignorado (não são zero escanteios)")
            continue
        # Sem confirmação do formato de estatísticas HT em dados reais, FT usa o acumulado,
        # HT também usa o acumulado mas APENAS durante o primeiro tempo.
        corners = corners_by_team(rows, home.get("id"), away.get("id"), None)
        if corners is None:
            print(f"Jogo {fid}: Corner Kicks ausente; nenhum alerta")
            continue
        print(f"Jogo {fid}: minuto={minute}, escanteios={corners[0]}+{corners[1]}, cota restante={remaining}")
        for phase, rules in active:
            if sum(corners) < int(rules["min_corners"]):
                continue
            key = f"{fid}:{phase}"
            text = (f"⚽ Escanteios {phase.upper()} | {home.get('name')} x {away.get('name')}\n"
                    f"{minute}' | {corners[0]}–{corners[1]} (total {sum(corners)})\n"
                    "Alerta estatístico; não é recomendação de aposta.")
            if cfg.get("dry_run", True):
                print(f"DRY RUN: {text}")
                continue
            alert(session, os.environ["TG_GROUP_ID"], os.environ["TG_SOKKERPRO_TOKEN"], text)
            seen.add(key)
            STATE_PATH.write_text(json.dumps(sorted(seen)))
    print("Consulta encerrada; logs não incluem segredos")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
