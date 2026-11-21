"""Оновлює довгострокові токени Instagram і Threads (діють 60 днів)
і записує нові значення назад у GitHub Secrets через gh CLI.

Потрібні секрети: IG_TOKEN, THREADS_TOKEN, GH_PAT (токен GitHub з правом
змінювати secrets цього репозиторію). Запускається workflow раз на 2 тижні.
"""

import os
import subprocess
import sys

import requests

REPO = os.environ["GITHUB_REPOSITORY"]


def refresh(url, grant, token):
    r = requests.get(url, params={"grant_type": grant, "access_token": token}, timeout=60)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"{url}: {data}")
    return data["access_token"], data.get("expires_in")


def set_secret(name, value):
    subprocess.run(["gh", "secret", "set", name, "--repo", REPO, "--body", value],
                   check=True, env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]})


def main():
    failed = False
    jobs = [
        ("IG_TOKEN", "https://graph.instagram.com/refresh_access_token", "ig_refresh_token"),
        ("THREADS_TOKEN", "https://graph.threads.net/refresh_access_token", "th_refresh_token"),
    ]
    for name, url, grant in jobs:
        old = os.environ.get(name, "").strip()
        if not old:
            print(f"{name}: не задано, пропускаю")
            continue
        try:
            new, expires = refresh(url, grant, old)
            set_secret(name, new)
            print(f"{name}: оновлено, діє ще {expires} с")
        except Exception as e:  # noqa: BLE001
            failed = True
            print(f"{name}: помилка {e}", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
