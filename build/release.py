"""
release.py — сборка + публикация релиза Razecheck с VirusTotal ссылкой.

Использование:
    python build/release.py [--vt-key YOUR_VIRUSTOTAL_API_KEY] [--version v1.0.2]

Без --vt-key создаётся релиз с SHA256 хэшем (ссылка на VT поиск).
С --vt-key файл загружается на VirusTotal, ждём скан и добавляем прямую ссылку.

Бесплатный ключ: https://www.virustotal.com/gui/join-us
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EXE_PATH   = Path(__file__).parent.parent / "dist" / "Razecheck.exe"
REPO       = "Rolsikkk/razecheck"
VT_UPLOAD  = "https://www.virustotal.com/api/v3/files"
VT_ANALYSE = "https://www.virustotal.com/api/v3/analyses/{id}"
VT_FILE    = "https://www.virustotal.com/gui/file/{sha256}/detection"
VT_SEARCH  = "https://www.virustotal.com/gui/search/{sha256}"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def vt_upload(api_key: str, path: Path) -> str | None:
    """Загружает файл на VT, возвращает analysis id."""
    boundary = "----RazecheckBoundary"
    body  = f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode()
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        VT_UPLOAD,
        data=body,
        headers={
            "x-apikey":    api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            return data["data"]["id"]
    except Exception as e:
        print(f"[VT] Upload error: {e}")
        return None


def vt_wait_analysis(api_key: str, analysis_id: str, timeout: int = 120) -> dict | None:
    """Ждём завершения анализа, возвращаем stats."""
    url = VT_ANALYSE.format(id=analysis_id)
    req = urllib.request.Request(url, headers={"x-apikey": api_key})
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            status = data["data"]["attributes"]["status"]
            if status == "completed":
                return data["data"]["attributes"]["stats"]
        except Exception:
            pass
        print("  Waiting for VT scan...", end="\r")
        time.sleep(10)
    return None


def build_exe():
    print("[Build] Running PyInstaller...")
    root = Path(__file__).parent.parent
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--noconsole",
        "--name", "Razecheck",
        f"--icon={root / 'client' / 'assets' / 'icon.ico'}",
        "--add-data", f"{root / 'client' / 'config.json'};.",
        "--add-data", f"{root / 'client' / 'assets' / 'icon.ico'};assets",
        "--paths", str(root / "client"),
        str(root / "client" / "main.py"),
    ]
    result = subprocess.run(cmd, cwd=root)
    if result.returncode != 0:
        print("[Build] FAILED")
        sys.exit(1)
    print("[Build] OK")


def create_release(version: str, notes: str):
    print(f"[Release] Creating {version} ...")
    subprocess.run(["gh", "release", "delete", version, "--yes"],
                   capture_output=True)
    cmd = ["gh", "release", "create", version,
           str(EXE_PATH),
           "--title", f"Razecheck {version}",
           "--notes", notes,
           "--repo", REPO]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[Release] Error: {result.stderr}")
        sys.exit(1)
    print(f"[Release] Published: {result.stdout.strip()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vt-key",   default=os.environ.get("VT_API_KEY", ""))
    parser.add_argument("--version",  default="v1.0.2")
    parser.add_argument("--no-build", action="store_true",
                        help="Пропустить сборку (использовать существующий exe)")
    args = parser.parse_args()

    if not args.no_build:
        # Остановить запущенный exe
        subprocess.run(["taskkill", "/f", "/im", "Razecheck.exe"],
                       capture_output=True)
        time.sleep(0.5)
        build_exe()

    if not EXE_PATH.exists():
        print(f"[Error] Exe not found: {EXE_PATH}")
        sys.exit(1)

    sha = sha256_of(EXE_PATH)
    size_mb = EXE_PATH.stat().st_size / 1024 / 1024
    print(f"[SHA256] {sha}")

    vt_line = ""
    if args.vt_key:
        print("[VT] Uploading to VirusTotal...")
        aid = vt_upload(args.vt_key, EXE_PATH)
        if aid:
            stats = vt_wait_analysis(args.vt_key, aid)
            if stats:
                mal   = stats.get("malicious", 0)
                total = sum(stats.values())
                vt_line = (
                    f"\n### VirusTotal\n"
                    f"**Результат:** {mal}/{total} детектов  \n"
                    f"**Ссылка:** {VT_FILE.format(sha256=sha)}"
                )
            else:
                vt_line = (
                    f"\n### VirusTotal\n"
                    f"Скан в процессе: {VT_FILE.format(sha256=sha)}"
                )
    else:
        vt_line = (
            f"\n### VirusTotal\n"
            f"SHA256: `{sha}`  \n"
            f"Проверить: {VT_SEARCH.format(sha256=sha)}"
        )

    notes = f"""## Что нового
- Discord сканер показывает серверы из которых вышел (Cache + IndexedDB)
- Typewriter-эффект в панели результатов
- Scanline overlay анимация
- Открывается папка Discord Cache при проверке

**Размер:** {size_mb:.1f} MB
**SHA256:** `{sha}`
{vt_line}

## Использование
Запусти `Razecheck.exe` — нажми **CHECK** — жди результатов.
"""

    create_release(args.version, notes)


if __name__ == "__main__":
    main()
