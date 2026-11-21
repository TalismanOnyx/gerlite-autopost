"""Автопостинг GERLITE в Instagram і Threads через офіційні API Meta.

Запускається з GitHub Actions щогодини. Публікує всі пости з schedule.json,
час яких уже настав і які ще не опубліковані (стан зберігається в posted.json).

Змінні середовища (GitHub Secrets):
  IG_USER_ID, IG_TOKEN            — Instagram API with Instagram Login
  THREADS_USER_ID, THREADS_TOKEN  — Threads API
  MEDIA_BASE_URL                  — публічна адреса папки media,
                                    напр. https://raw.githubusercontent.com/<user>/<repo>/main/media
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).parent
SCHEDULE = ROOT / "schedule.json"
POSTED = ROOT / "posted.json"
TZ = ZoneInfo("Europe/Kyiv")

IG_API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v25.0")
TH_API = "https://graph.threads.net/v1.0"

# Пости, що запізнилися більше ніж на стільки годин, не публікуються автоматично
MAX_DELAY_HOURS = 12


class PublishError(Exception):
    pass


def env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise PublishError(f"Не задано секрет {name}")
    return value


def call(method, url, **params):
    for attempt in range(3):
        r = requests.request(method, url, params=params, timeout=60)
        if r.status_code < 500:
            break
        time.sleep(5 * (attempt + 1))
    data = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in data:
        raise PublishError(f"{method} {url.split('?')[0]} -> {r.status_code}: {data}")
    return data


def media_url(rel_path):
    return env("MEDIA_BASE_URL").rstrip("/") + "/" + rel_path.lstrip("/")


# ---------------- Instagram ----------------

def ig_wait(container_id, token, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        data = call("GET", f"{IG_API}/{container_id}", fields="status_code,status", access_token=token)
        code = data.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise PublishError(f"Контейнер {container_id}: {data}")
        time.sleep(5)
    raise PublishError(f"Контейнер {container_id} не готовий за {timeout} с")


def ig_publish(post):
    user, token = env("IG_USER_ID"), env("IG_TOKEN")
    images = post["images"]
    caption = post.get("caption", "")
    if len(images) == 1:
        c = call("POST", f"{IG_API}/{user}/media",
                 image_url=media_url(images[0]), caption=caption, access_token=token)
        container = c["id"]
    else:
        children = []
        for img in images:
            c = call("POST", f"{IG_API}/{user}/media",
                     image_url=media_url(img), is_carousel_item="true", access_token=token)
            children.append(c["id"])
        for child in children:
            ig_wait(child, token)
        c = call("POST", f"{IG_API}/{user}/media", media_type="CAROUSEL",
                 children=",".join(children), caption=caption, access_token=token)
        container = c["id"]
    ig_wait(container, token)
    res = call("POST", f"{IG_API}/{user}/media_publish", creation_id=container, access_token=token)
    return res["id"]


# ---------------- Threads ----------------

def th_publish(post):
    user, token = env("THREADS_USER_ID"), env("THREADS_TOKEN")
    c = call("POST", f"{TH_API}/{user}/threads", media_type="TEXT",
             text=post["text"], access_token=token)
    time.sleep(30)  # Meta радить почекати перед публікацією контейнера
    res = call("POST", f"{TH_API}/{user}/threads_publish", creation_id=c["id"], access_token=token)
    return res["id"]


# ---------------- Основний цикл ----------------

def main():
    schedule = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    posted = json.loads(POSTED.read_text(encoding="utf-8")) if POSTED.exists() else {}
    now = datetime.now(TZ)
    errors = []

    for post in sorted(schedule, key=lambda p: p["at"]):
        pid = post["id"]
        if pid in posted:
            continue
        due = datetime.fromisoformat(post["at"]).replace(tzinfo=TZ)
        if due > now:
            continue
        if post.get("manual"):
            posted[pid] = {"status": "manual", "note": "Опублікуй вручну (позначка партнерства)"}
            errors.append(f"{pid}: потрібна ручна публікація")
            continue
        if now - due > timedelta(hours=MAX_DELAY_HOURS):
            posted[pid] = {"status": "skipped_late", "due": post["at"]}
            errors.append(f"{pid}: пропущено, запізнення понад {MAX_DELAY_HOURS} год")
            continue
        try:
            media_id = ig_publish(post) if post["platform"] == "instagram" else th_publish(post)
            posted[pid] = {"status": "ok", "media_id": media_id, "at": now.isoformat()}
            print(f"OK {pid} -> {media_id}")
        except PublishError as e:
            errors.append(f"{pid}: {e}")
            print(f"FAIL {pid}: {e}", file=sys.stderr)

    POSTED.write_text(json.dumps(posted, ensure_ascii=False, indent=2), encoding="utf-8")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)  # падіння workflow -> GitHub надішле лист


if __name__ == "__main__":
    main()
