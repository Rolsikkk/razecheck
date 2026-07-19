import datetime
import os
import shutil
import struct
import subprocess

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QCursor, QFont
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

# ── Константы ─────────────────────────────────────────────────────────────────

_FILETIME_EPOCH = 116_444_736_000_000_000   # 100-нс от 1601 до 1970

C_BG     = "#0c0c0c"
C_PANEL  = "#111111"
C_BORDER = "#2a2a2a"
C_HEADER = "#3a9fff"
C_USB    = "#f1fa8c"
C_FILE   = "#8be9fd"
C_DIM    = "#555566"
C_GREEN  = "#50fa7b"
C_RED    = "#ff5555"
C_TEXT   = "#c8ccd4"

ITEM_HEADER = 0
ITEM_USB    = 1
ITEM_FILE   = 2
ITEM_INFO   = 3

# ── База имён читов ───────────────────────────────────────────────────────────

_CHEAT_KEYWORDS = {
    # Общие
    "eulen", "stand", "kiddion", "midnight", "cherax", "lynx", "luna",
    "scarlet", "flare", "rage", "ozark", "bigbase", "yimmenu", "phantom",
    "modest", "skuller", "gta-hack", "gtahack", "menyoo", "simple-trainer",
    "vanish", "nightclub", "leet", "1337", "aimbot", "wallhack", "triggerbot",
    "cheat", "hack", "inject", "injector", "bypass", "spoofer", "hwid",
    "loader", "trainer", "menu", "external", "internal", "overlay",
    "altv-cheat", "fivem-cheat", "ragemp", "unknowncheats",
    "wearedevs", "neverlose", "fatality", "gamesense", "aimware",
    "skeet", "primordial", "onetap", "interium", "nixware",
    "bespoiled", "projectx", "pandora", "narcotic",
    # Majestic RP / AltV специфичные
    "euphoria", "amidone", "mason", "hydrogen", "ret9", "skript",
    "menace", "omni", "woodvanish", "wood", "phoenix", "elite",
    "procheat", "procheck",
}


# ── Утилиты ───────────────────────────────────────────────────────────────────

def _ft_to_dt(ft: int) -> datetime.datetime:
    try:
        return datetime.datetime.fromtimestamp((ft - _FILETIME_EPOCH) / 10_000_000)
    except Exception:
        return datetime.datetime.now()


def get_recent_usb(hours: int = 10) -> list[tuple[str, datetime.datetime]]:
    """Флешки (только Disk), подключённые за последние N часов — из реестра USBSTOR."""
    if not _HAS_WINREG:
        return []
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
    found: list[tuple[str, datetime.datetime]] = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                              r"SYSTEM\CurrentControlSet\Enum\USBSTOR")
        i = 0
        while True:
            try:
                sub_name = winreg.EnumKey(root, i); i += 1
                if not sub_name.startswith("Disk&"):
                    continue
                parts  = sub_name.split("&")
                vendor = next((p[4:] for p in parts if p.startswith("Ven_")), "").strip("_").strip()
                prod   = next((p[5:] for p in parts if p.startswith("Prod_")), "").strip("_").strip()
                label  = f"{vendor} {prod}".strip() or sub_name

                dev_key = winreg.OpenKey(root, sub_name)
                j = 0
                while True:
                    try:
                        inst = winreg.EnumKey(dev_key, j); j += 1
                        ik   = winreg.OpenKey(dev_key, inst)
                        _, _, lw = winreg.QueryInfoKey(ik)
                        winreg.CloseKey(ik)
                        dt = _ft_to_dt(lw)
                        if dt >= cutoff:
                            found.append((label, dt))
                    except OSError:
                        break
                winreg.CloseKey(dev_key)
            except OSError:
                break
        winreg.CloseKey(root)
    except Exception:
        pass
    return sorted(found, key=lambda x: x[1], reverse=True)


def _get_sid() -> str:
    try:
        r = subprocess.run(["whoami", "/user"], capture_output=True, text=True)
        for tok in r.stdout.split():
            if tok.startswith("S-1-5-"):
                return tok
    except Exception:
        pass
    return ""


def get_recycle_files() -> list[dict]:
    """Файлы в Корзине текущего пользователя."""
    rb_root = "C:\\$Recycle.Bin"
    sid = _get_sid()
    dirs: list[str] = []
    if sid:
        sd = os.path.join(rb_root, sid)
        if os.path.isdir(sd):
            dirs.append(sd)
    if not dirs:
        try:
            dirs = [os.path.join(rb_root, d)
                    for d in os.listdir(rb_root)
                    if os.path.isdir(os.path.join(rb_root, d))]
        except Exception:
            pass

    result: list[dict] = []
    for rb_dir in dirs:
        try:
            for fname in os.listdir(rb_dir):
                if not fname.upper().startswith("$I"):
                    continue
                i_file = os.path.join(rb_dir, fname)
                r_file = os.path.join(rb_dir, "$R" + fname[2:])
                if not os.path.exists(r_file):
                    continue
                try:
                    with open(i_file, "rb") as f:
                        data = f.read()
                    version = struct.unpack_from("<q", data, 0)[0]
                    del_ft  = struct.unpack_from("<q", data, 16)[0]
                    del_dt  = _ft_to_dt(del_ft)
                    if version == 2 and len(data) >= 28:
                        path_len  = struct.unpack_from("<i", data, 24)[0]
                        orig_path = data[28:28 + path_len * 2].decode(
                            "utf-16-le", errors="replace").rstrip("\x00")
                    else:
                        orig_path = data[24:].decode(
                            "utf-16-le", errors="replace").rstrip("\x00")
                    if orig_path:
                        result.append({
                            "orig_path": orig_path,
                            "del_time":  del_dt,
                            "r_file":    r_file,
                            "i_file":    i_file,
                        })
                except Exception:
                    continue
        except Exception:
            continue
    return sorted(result, key=lambda x: x["del_time"], reverse=True)


def restore_file(entry: dict) -> bool:
    """Восстанавливает файл из Корзины или Shadow Copy."""
    try:
        orig = entry["orig_path"]
        os.makedirs(os.path.dirname(orig) or ".", exist_ok=True)

        if entry.get("type") == "shadow":
            shutil.copy2(entry["shadow_path"], orig)
        else:
            shutil.move(entry["r_file"], orig)
            try:
                os.remove(entry["i_file"])
            except Exception:
                pass

        if os.path.isdir(orig):
            subprocess.Popen(["explorer", orig])
        else:
            try:
                os.startfile(orig)
            except Exception:
                subprocess.Popen(["explorer", os.path.dirname(orig)])
        return True
    except Exception:
        return False


def _ensure_vss() -> bool:
    """Запускает службу VSS если остановлена (снимки не создаёт)."""
    try:
        subprocess.run(["net", "start", "vss"],
                       capture_output=True, timeout=15)
    except Exception:
        pass
    return True


def get_shadow_deleted_files(max_files: int = 120) -> list[dict]:
    """Ищет удалённые файлы через Shadow Copy (снимки Windows)."""
    import re

    _ensure_vss()

    # Получаем список теневых копий для диска C:
    try:
        r = subprocess.run(
            ["vssadmin", "list", "shadows", "/for=C:"],
            capture_output=True, text=True, errors="replace", timeout=10
        )
        shadows = re.findall(r"Shadow Copy Volume:\s*(\S+)", r.stdout)
    except Exception:
        return []

    if not shadows:
        return []

    # Берём самую свежую копию (последняя в списке)
    shadow_root = shadows[-1].rstrip("\\") + "\\"

    username = os.environ.get("USERNAME", "")
    scan_dirs = [
        f"Users\\{username}\\Desktop",
        f"Users\\{username}\\Documents",
        f"Users\\{username}\\Downloads",
        f"Users\\{username}\\Pictures",
        f"Users\\{username}\\Videos",
        f"Users\\{username}\\Music",
        f"Users\\{username}\\AppData\\Roaming",
    ]

    deleted: list[dict] = []
    for rel in scan_dirs:
        shadow_dir  = shadow_root + rel
        current_dir = "C:\\" + rel
        try:
            for name in os.listdir(shadow_dir):
                s_item = os.path.join(shadow_dir, name)
                c_item = os.path.join(current_dir, name)
                if not os.path.exists(c_item):
                    try:
                        mtime = os.stat(s_item).st_mtime
                        deleted.append({
                            "orig_path":   c_item,
                            "shadow_path": s_item,
                            "del_time":    datetime.datetime.fromtimestamp(mtime),
                            "type":        "shadow",
                        })
                        if len(deleted) >= max_files:
                            return deleted
                    except Exception:
                        pass
        except Exception:
            continue

    return sorted(deleted, key=lambda x: x["del_time"], reverse=True)


def _is_suspicious(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in _CHEAT_KEYWORDS)


def get_bam_entries() -> list[dict]:
    """
    BAM (Background Activity Monitor) — реестр всех запускавшихся .exe
    с временными метками. Возвращает подозрительные записи.
    """
    if not _HAS_WINREG:
        return []
    sid = _get_sid()
    results = []
    bam_paths = [
        rf"SYSTEM\CurrentControlSet\Services\bam\State\UserSettings\{sid}",
        rf"SYSTEM\CurrentControlSet\Services\bam\UserSettings\{sid}",  # старый путь
    ]
    for bam_path in bam_paths:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bam_path)
            i = 0
            while True:
                try:
                    name, data, _ = winreg.EnumValue(key, i); i += 1
                    if not isinstance(data, bytes) or len(data) < 8:
                        continue
                    exe_name = os.path.basename(name.replace("\\", "/"))
                    if not exe_name.lower().endswith(".exe"):
                        continue
                    ft = struct.unpack_from("<Q", data, 0)[0]
                    dt = _ft_to_dt(ft)
                    if _is_suspicious(exe_name):
                        results.append({
                            "name": exe_name,
                            "full_path": name,
                            "time": dt,
                            "source": "BAM",
                        })
                except OSError:
                    break
            winreg.CloseKey(key)
            if results:
                break
        except Exception:
            continue
    return sorted(results, key=lambda x: x["time"], reverse=True)


def get_prefetch_entries() -> list[dict]:
    """
    Prefetch-файлы (C:\\Windows\\Prefetch\\) — история запусков программ.
    Возвращает подозрительные записи по имени файла.
    """
    pf_dir = r"C:\Windows\Prefetch"
    results = []
    try:
        for fname in os.listdir(pf_dir):
            if not fname.upper().endswith(".PF"):
                continue
            # Формат: NAME.EXE-XXXXXXXX.pf
            exe_name = fname.rsplit("-", 1)[0]
            if not _is_suspicious(exe_name):
                continue
            fpath = os.path.join(pf_dir, fname)
            try:
                mtime = os.path.getmtime(fpath)
                dt    = datetime.datetime.fromtimestamp(mtime)
                results.append({
                    "name":   exe_name,
                    "pf_file": fpath,
                    "time":   dt,
                    "source": "Prefetch",
                })
            except Exception:
                pass
    except Exception:
        pass
    return sorted(results, key=lambda x: x["time"], reverse=True)


def get_discord_activity() -> list[dict]:
    """
    Ищет все Guild ID которые когда-либо были в Discord:
    1. LevelDB — last_channel_GUILDID (текущие серверы)
    2. Cache\Cache_Data — cdn.discordapp.com/icons/GUILD_ID/ (включая покинутые)
    3. IndexedDB, Session Storage — дополнительные источники
    Возвращает {guild_id, name, client, source, mtime}.
    """
    import re

    appdata = os.environ.get("APPDATA", "")
    variants = {
        "Discord":        "discord",
        "Discord PTB":    "discordptb",
        "Discord Canary": "discordcanary",
    }

    # guild_id → {name, client, source, mtime}
    found: dict[str, dict] = {}

    def _add(gid: str, client: str, source: str,
             mtime: datetime.datetime, name: str | None = None):
        if gid not in found:
            found[gid] = {"guild_id": gid, "name": name,
                          "client": client, "source": source, "mtime": mtime}
        else:
            # Обновляем имя если нашли
            if name and not found[gid]["name"]:
                found[gid]["name"] = name
            # Берём самую свежую дату
            if mtime > found[gid]["mtime"]:
                found[gid]["mtime"] = mtime

    for display, folder in variants.items():
        base = os.path.join(appdata, folder)
        if not os.path.isdir(base):
            continue

        # ── 1. LevelDB (Local Storage) ────────────────────────────────────────
        for ldb_sub in [
            os.path.join(base, "Local Storage", "leveldb"),
            os.path.join(base, "Session Storage"),
        ]:
            if not os.path.isdir(ldb_sub):
                continue
            try:
                files = [f for f in os.listdir(ldb_sub)
                         if f.endswith(".ldb") or f.endswith(".log")]
            except Exception:
                continue
            for fname in files:
                fpath = os.path.join(ldb_sub, fname)
                try:
                    with open(fpath, "rb") as f:
                        raw = f.read()
                    mtime = datetime.datetime.fromtimestamp(
                        os.path.getmtime(fpath))

                    # last_channel_GUILDID
                    for m in re.finditer(
                            rb"last[_\x00]channel[_\x00](\d{17,19})", raw):
                        gid = m.group(1).decode()
                        # Имя рядом
                        chunk = raw[max(0, m.start()-256): m.start()+512]
                        nm = re.search(rb'"name"\s*:\s*"([^"]{1,80})"', chunk)
                        name = None
                        if nm:
                            try:
                                name = nm.group(1).decode("utf-8", errors="replace")
                            except Exception:
                                pass
                        _add(gid, display, "LevelDB", mtime, name)

                    # /channels/GUILD_ID/
                    for m in re.finditer(
                            rb"/channels/(\d{17,19})/", raw):
                        _add(m.group(1).decode(), display, "LevelDB", mtime)

                except Exception:
                    continue

        # ── 2. Cache (cdn.discordapp.com/icons/GUILD_ID/) — покинутые серверы
        cache_dir = os.path.join(base, "Cache", "Cache_Data")
        if not os.path.isdir(cache_dir):
            # Старые версии Discord
            cache_dir = os.path.join(base, "Cache")
        if os.path.isdir(cache_dir):
            try:
                cache_files = os.listdir(cache_dir)
            except Exception:
                cache_files = []
            for fname in cache_files:
                fpath = os.path.join(cache_dir, fname)
                if os.path.isdir(fpath):
                    continue
                try:
                    with open(fpath, "rb") as f:
                        raw = f.read(65536)   # первые 64KB достаточно
                    mtime = datetime.datetime.fromtimestamp(
                        os.path.getmtime(fpath))
                    # cdn.discordapp.com/icons/GUILD_ID/
                    for m in re.finditer(
                            rb"cdn\.discordapp\.com/icons/(\d{17,19})/", raw):
                        _add(m.group(1).decode(), display,
                             "Cache (left server)", mtime)
                    # /channels/GUILD_ID/
                    for m in re.finditer(
                            rb"/channels/(\d{17,19})/\d{17,19}", raw):
                        _add(m.group(1).decode(), display, "Cache", mtime)
                except Exception:
                    continue

        # ── 3. IndexedDB ──────────────────────────────────────────────────────
        idb_dir = os.path.join(base, "IndexedDB")
        if os.path.isdir(idb_dir):
            try:
                for sub in os.listdir(idb_dir):
                    ldb2 = os.path.join(idb_dir, sub)
                    if not os.path.isdir(ldb2):
                        continue
                    for fname in os.listdir(ldb2):
                        if not (fname.endswith(".ldb") or
                                fname.endswith(".log")):
                            continue
                        fpath = os.path.join(ldb2, fname)
                        try:
                            with open(fpath, "rb") as f:
                                raw = f.read()
                            mtime = datetime.datetime.fromtimestamp(
                                os.path.getmtime(fpath))
                            for m in re.finditer(
                                    rb'"guild_id"\s*:\s*"(\d{17,19})"', raw):
                                _add(m.group(1).decode(), display,
                                     "IndexedDB", mtime)
                        except Exception:
                            continue
            except Exception:
                pass

    return sorted(found.values(), key=lambda x: x["mtime"], reverse=True)


# ── CMD-окно ─────────────────────────────────────────────────────────────────

class CmdWindow(QWidget):
    def __init__(self, usb_devices: list, recycle_files: list, parent=None):
        super().__init__(parent, Qt.WindowType.Window |
                                 Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._files = recycle_files
        self._drag  = None
        self._build(usb_devices, recycle_files)
        self.resize(860, 500)
        self._center()
        self.setWindowOpacity(0.0)
        QTimer.singleShot(60, self._fade_in)

    def _center(self):
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.center().x() - self.width() // 2,
                  geo.center().y() - self.height() // 2)

    def _fade_in(self):
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(320)
        a.setStartValue(0.0); a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start(); self._anim = a

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self, usb_devices, recycle_files):
        self.setStyleSheet(
            f"background:{C_BG}; border:1px solid {C_BORDER};"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Заголовок
        tb = QWidget()
        tb.setFixedHeight(34)
        tb.setStyleSheet(f"background:{C_PANEL}; border-bottom:1px solid {C_BORDER};")
        th = QHBoxLayout(tb)
        th.setContentsMargins(14, 0, 8, 0)

        lbl = QLabel("C:\\RAZECHECK\\scan_results.exe")
        lbl.setFont(QFont("Consolas", 9))
        lbl.setStyleSheet(f"color:{C_DIM}; background:transparent; border:none;")
        th.addWidget(lbl)
        th.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.setStyleSheet(
            "QPushButton{background:transparent;color:#444;border:none;font-size:13px;}"
            "QPushButton:hover{color:#ff5555;}"
        )
        btn_close.clicked.connect(self.close)
        th.addWidget(btn_close)
        root.addWidget(tb)

        # Список
        self._lw = QListWidget()
        self._lw.setFont(QFont("Consolas", 10))
        self._lw.setStyleSheet(f"""
            QListWidget {{
                background:{C_BG}; color:{C_TEXT};
                border:none; outline:none; padding:10px 16px;
            }}
            QListWidget::item {{ padding:2px 0; border:none; }}
            QListWidget::item:hover {{ background:#141414; }}
            QListWidget::item:selected {{ background:#1a2233; color:{C_TEXT}; }}
            QScrollBar:vertical {{
                background:#111; width:5px; border:none;
            }}
            QScrollBar::handle:vertical {{
                background:#2a2a2a; border-radius:2px;
            }}
        """)
        self._lw.itemClicked.connect(self._on_click)
        self._fill(usb_devices, recycle_files)
        root.addWidget(self._lw)

    def _row(self, text: str, kind: int, data=None, color: str = C_TEXT):
        item = QListWidgetItem(text)
        item.setForeground(QColor(color))
        item.setData(Qt.ItemDataRole.UserRole, (kind, data))
        if kind in (ITEM_HEADER, ITEM_INFO, ITEM_USB):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self._lw.addItem(item)
        return item

    def _fill(self, usb_devices, recycle_files):
        ln = "─" * 80

        # USB секция
        self._row("", ITEM_INFO)
        self._row(f"  ┌─ USB FLASH DRIVES — LAST 10H  {ln[:36]}", ITEM_HEADER, color=C_HEADER)
        if usb_devices:
            for name, dt in usb_devices:
                self._row(
                    f"  │   {dt.strftime('%H:%M:%S')}   {name}",
                    ITEM_USB, color=C_USB
                )
        else:
            self._row("  │   no flash drives found in last 10 hours",
                      ITEM_USB, color=C_DIM)
        self._row(f"  └{ln[:68]}", ITEM_INFO, color=C_HEADER)
        self._row("", ITEM_INFO)

        # Корзина секция
        self._row(f"  ┌─ RECOVERABLE FILES (RECYCLE BIN)  {ln[:33]}", ITEM_HEADER, color=C_HEADER)
        if recycle_files:
            for entry in recycle_files[:80]:
                path = entry["orig_path"]
                disp = path if len(path) <= 65 else "…" + path[-64:]
                ts   = entry["del_time"].strftime("%d.%m  %H:%M")
                self._row(
                    f"  │   [{ts}]   {disp}",
                    ITEM_FILE, data=entry, color=C_FILE
                )
        else:
            self._row("  │   recycle bin is empty", ITEM_INFO, color=C_DIM)
        self._row(f"  └{ln[:68]}", ITEM_INFO, color=C_HEADER)
        self._row("", ITEM_INFO)
        self._row(
            "  >  click any file to restore it to its original location",
            ITEM_INFO, color=C_DIM
        )
        self._row("", ITEM_INFO)

    def _on_click(self, item: QListWidgetItem):
        kind, data = item.data(Qt.ItemDataRole.UserRole)
        if kind != ITEM_FILE or data is None:
            return
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        if restore_file(data):
            item.setText(item.text() + "   ✓ restored")
            item.setForeground(QColor(C_GREEN))
        else:
            item.setText(item.text() + "   ✗ error")
            item.setForeground(QColor(C_RED))

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _e):
        self._drag = None
