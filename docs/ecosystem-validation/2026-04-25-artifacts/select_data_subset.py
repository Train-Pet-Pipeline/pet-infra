"""按 spec §1.5 确定性选 50 样本（cat 25 / dog 25），写 manifest。

选样规则：
- 图片 / 音频：字典序前 N
- 视频：duration 升序，duration 相同则字典序升序，取前 N

PET_DATA_ROOT env var 可覆盖 DATA_ROOT 默认（rental 上指向 /workspace/raw_data）。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

DATA_ROOT = Path(os.environ.get("PET_DATA_ROOT", "/Users/bamboo/Githubs/Purr-Sight/data"))
OUTPUT = Path(__file__).parent / "data-subset-manifest.json"

PLAN = [
    ("cat_images", 15, "lex"),
    ("dog_images", 15, "lex"),
    ("cat_audio", 8, "lex"),
    ("dog_audio", 8, "lex"),
    ("cat_video", 2, "duration"),
    ("dog_video", 2, "duration"),
]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def video_duration(path: Path) -> float:
    """ffprobe 读时长；失败返回 inf 让该文件排到最后。"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return float(result.stdout.strip())
    except (
        subprocess.CalledProcessError,
        ValueError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return float("inf")


def select(category: str, n: int, sort_mode: str) -> list[Path]:
    folder = DATA_ROOT / category
    files = sorted(p for p in folder.iterdir() if p.is_file())
    if sort_mode == "lex":
        return files[:n]
    if sort_mode == "duration":
        return sorted(files, key=lambda p: (video_duration(p), p.name))[:n]
    raise ValueError(f"unknown sort_mode: {sort_mode}")


def main() -> None:
    if not DATA_ROOT.exists():
        raise SystemExit(f"DATA_ROOT not found: {DATA_ROOT}")
    manifest: dict = {
        "spec": "2026-04-25-design.md §1.5",
        "data_root": str(DATA_ROOT),
        "samples": [],
    }
    for category, n, mode in PLAN:
        for p in select(category, n, mode):
            manifest["samples"].append({
                "category": category,
                "filename": p.name,
                "size_bytes": p.stat().st_size,
                "sha256": sha256_of(p),
                "rel_path": f"{category}/{p.name}",
            })
    OUTPUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"wrote {len(manifest['samples'])} entries → {OUTPUT}")


if __name__ == "__main__":
    main()
