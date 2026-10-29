"""Alertas de escanteios HT/FT. Nunca publica apostas nem simula dados ausentes."""
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests

BASE = "https://m4.sokkerpro.com/"
STATE = Path(os.getenv("STATE_FILE", "state.json"))
TZ = ZoneInfo("America/Sao_Paulo")
LOG = logging.getLogger(__name__)


def auth_headers():
    """A API M4 não publicou esquema de autenticação verificado: requer configuração."""
    value = os.getenv("M4_AUTH_VALUE", "")
    name = os.getenv("M4_AUTH_HEADER", "")
    if not value or not name or not re.fullmatch(r"[A-Za-z0-9-]+", name):
        raise RuntimeError("Configure M4_AUTH_HEADER e M4_AUTH_VALUE; autenticação M4 ainda não verificada")
    return {name: value, "Accept": "application/json"}


def get_json(session, path):
    url = urljoin(BASE, path)
    if not url.startswith(BASE):
        raise ValueError("URL fora da API M4")
    response = session.get(url, headers=auth_headers(), timeout=20)
    response.raise_for_status()
    return response.json()


def fixtures_from_live(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("fixtures", "matches", "data", "results", "livescores"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                try:
                    return fixtures_from_live(value)
                except ValueError:
                    pass
    raise ValueError("Formato de /livescores desconhecido; nenhum alerta enviado")


def match_id(item):
    if not isinstance(item, dict):
        return None
    value = item.get("id") or item.get("fixture_id") or item.get("fixtureId")
    if isinstance(value, (int, str)) and re.fullmatch(r"[0-9]+", str(value)):
        return str(value)
    fixture = item.get("fixture")
    if isinstance(fixture, dict):
        return match_id(fixture)
    return None


def parse_corners(detail):
    """Aceita só campos explicitamente rotulados home/away corners; não adivinha estatísticas."""
    if not isinstance(detail, dict):
        return None
    candidates = [detail, detail.get("statistics"), detail.get("stats"), detail.get("data")]
    for stats in candidates:
        if not isinstance(stats, dict):
            continue
        if "corners" in stats and isinstance(stats["corners"], dict):
            stats = stats["corners"]
        home = stats.get("home_corners", stats.get("homeCorners", stats.get("home")))
        away = stats.get("away_corners", stats.get("awayCorners", stats.get("away")))
        if isinstance(home, dict):
            home = home.get("corners")
        if isinstance(away, dict):
            away = away.get("corners")
        if all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in (home, away)):
            return home, away
    return None


def minute_and_teams(detail):
    if not isinstance(detail, dict):
        return None
    minute = detail.get("minute", detail.get("elapsed"))
    try:
        minute = int(minute)
    except (ValueError, TypeError):
        return None
    home = detail.get("home_name") or detail.get("homeName")
    away = detail.get("away_name") or detail.get("awayName")
    teams = detail.get("teams")
    if isinstance(teams, dict):
        for side, current in (("home", home), ("away", away)):
            item = teams.get(side)
            if not current and isinstance(item, dict):
                if side == "home":
                    home = item.get("name")
                else:
                    away = item.get("name")
    if not home or not away or minute < 0 or minute > 130:
        return None
    return minute, str(home), str(away)


def thresholds():
    # Mínimo de escanteios acumulados até a janela. Ajustável; não é odd de aposta.
    return {"HT": (int(os.getenv("HT_MIN_CORNERS", "4")), 25, 44),
            "FT": (int(os.getenv("FT_MIN_CORNERS", "8")), 65, 89)}


def collect(session, seen):
    out = []
    live = fixtures_from_live(get_json(session, "livescores"))
    ids = list(dict.fromkeys(filter(None, (match_id(item) for item in live))))
    for fixture_id in ids[:int(os.getenv("MAX_FIXTURES", "100"))]:
        try:
            detail = get_json(session, f"fixture/{fixture_id}")
            if isinstance(detail, dict) and isinstance(detail.get("data"), dict):
                detail = detail["data"]
            info, corners = minute_and_teams(detail), parse_corners(detail)
            if info is None or corners is None:
                LOG.info("Partida %s sem campos suficientes; ignorada", fixture_id)
                continue
            minute, home, away = info
            total = sum(corners)
            for phase, (minimum, start, end) in thresholds().items():
                key = f"{fixture_id}:{phase}"
                if start <= minute <= end and total >= minimum and key not in seen:
                    text = (f"⚽ Escanteios {phase} | {home} x {away}\n"
                            f"Minuto: {minute}' | Escanteios: {corners[0]}–{corners[1]} (total {total})\n"
                            f"Critério: ≥{minimum} até {phase} | Partida: {fixture_id}\n"
                            "Alerta estatístico; não é recomendação de aposta.")
                    out.append((key, text))
        except (requests.RequestException, ValueError, TypeError) as exc:
            LOG.warning("Partida %s ignorada: %s", fixture_id, exc)
    return out


def telegram_send(session, text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    response = session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=20)
    response.raise_for_status()
    if response.json().get("ok") is not True:
        raise RuntimeError("Telegram não confirmou envio")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if not os.getenv(name):
            raise RuntimeError(f"Falta {name}")
    auth_headers()  # falha antes de enviar se M4 não configurada
    seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()
    session = requests.Session()
    alerts = collect(session, seen)
    for key, text in alerts:
        telegram_send(session, text)
        seen.add(key)
        STATE.write_text(json.dumps(sorted(seen)))
    LOG.info("Processadas %s partidas com alerta; enviados %s", len(seen), len(alerts))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        LOG.error("Falha: %s", exc)
        sys.exit(1)
