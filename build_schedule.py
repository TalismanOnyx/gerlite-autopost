"""Збирає schedule.json і media/*.jpg з тижневої папки контенту.

Використання:
  python build_schedule.py <папка_тижня> <файл_підписів.txt> <дата_понеділка YYYY-MM-DD> [--manual-every N]

Папка тижня містить підпапки по днях (сортуються за назвою), у кожній —
файли post1_*.png, post2_*.png, post3_*.png (слайди каруселі з _slideNN).
Файл підписів — формат «Підписи_тижденьN.txt» з розділами ДЕНЬ і THREADS.
"""

import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
MEDIA = ROOT / "media"
SCHEDULE = ROOT / "schedule.json"

IG_TIMES = ["09:00", "13:00", "19:00"]
THREADS_TIME = "11:00"


def parse_captions(text):
    days, threads = [], []
    mode, current = None, None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r"^=+ ДЕНЬ", line):
            mode = "day"
            days.append([])
        elif re.match(r"^=+ THREADS", line):
            mode = "threads"
        elif mode == "day" and line.startswith("--- Пост"):
            current = []
            days[-1].append(current)
        elif mode == "day" and current is not None and line and not line.startswith("="):
            current.append(line)
        elif mode == "threads" and re.match(r"^\S+ \d{2}\.\d{2}:$", line):
            threads.append(lines[i + 1].strip())
            i += 1
        if not line:
            current = None
        i += 1
    return [["\n".join(c) for c in d] for d in days], threads


def to_jpeg(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGB").save(dst, "JPEG", quality=90, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("week_dir")
    ap.add_argument("captions")
    ap.add_argument("monday")
    args = ap.parse_args()

    week_dir = Path(args.week_dir)
    monday = date.fromisoformat(args.monday)
    captions, threads = parse_captions(Path(args.captions).read_text(encoding="utf-8"))
    day_dirs = sorted(p for p in week_dir.iterdir() if p.is_dir())
    if len(day_dirs) != len(captions):
        raise SystemExit(f"Днів у папці {len(day_dirs)}, а в підписах {len(captions)}")

    schedule = json.loads(SCHEDULE.read_text(encoding="utf-8")) if SCHEDULE.exists() else []
    known = {p["id"] for p in schedule}

    for d, day_dir in enumerate(day_dirs):
        day = monday + timedelta(days=d)
        for k in range(1, 4):
            files = sorted(day_dir.glob(f"post{k}_*.png"))
            if not files:
                raise SystemExit(f"Немає post{k} у {day_dir}")
            rel = []
            for f in files:
                out = MEDIA / day.isoformat() / (f.stem + ".jpg")
                to_jpeg(f, out)
                rel.append(out.relative_to(MEDIA).as_posix())
            pid = f"ig-{day.isoformat()}-{k}"
            caption = captions[d][k - 1]
            entry = {
                "id": pid,
                "platform": "instagram",
                "at": datetime.fromisoformat(f"{day.isoformat()}T{IG_TIMES[k - 1]}").isoformat(),
                "images": rel,
                "caption": caption,
            }
            if "#партнерство" in caption or "#ad" in caption:
                entry["manual"] = True
            if pid not in known:
                schedule.append(entry)
        if d < len(threads):
            pid = f"th-{day.isoformat()}"
            if pid not in known:
                schedule.append({
                    "id": pid,
                    "platform": "threads",
                    "at": datetime.fromisoformat(f"{day.isoformat()}T{THREADS_TIME}").isoformat(),
                    "text": threads[d],
                })

    schedule.sort(key=lambda p: p["at"])
    SCHEDULE.write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"У розкладі {len(schedule)} постів")


if __name__ == "__main__":
    main()
