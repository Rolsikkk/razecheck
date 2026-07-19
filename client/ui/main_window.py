"""
main_window.py — Razecheck UI
Signal red + near-black. Animated perimeter scanner, glitch title, sweep button.
"""
import math
import os
import random
import subprocess
import sys
import webbrowser

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QPoint, QRectF, QRect,
)
from PyQt6.QtGui import (
    QBrush, QColor, QCursor, QFont,
    QLinearGradient, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import (
    QAbstractButton, QApplication,
    QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow,
    QVBoxLayout, QWidget,
)

# ── Design tokens ─────────────────────────────────────────────────────────────

C_BG     = "#080808"    # near-black
C_BORDER = "#1A1A1A"    # structural lines
C_ACCENT = "#E8331A"    # signal red
C_GREEN  = "#1AE86F"    # completion green
C_TEXT   = "#C8C8C8"    # primary text
C_MUTED  = "#404040"    # secondary
C_DIM    = "#111111"    # panels
RADIUS   = 0
TB_H     = 28
GLYPHS   = "!@#$%^&*<>[]{}|\\?~─═■□▪▫●○◆◇▶◀"


# ── Border scanner ────────────────────────────────────────────────────────────

class _BorderScan:
    """Bright segment that travels around the window perimeter, leaving a fading trail."""
    TRAIL = 240

    def __init__(self, period_ms: int = 4000):
        self._pos   = 0.0
        self._perim = 0.0
        self._spd   = 0.0
        self._W = self._H = 0
        self.set_size(738, 372, period_ms)

    def set_size(self, w: int, h: int, period_ms: int = 4000):
        self._W     = w
        self._H     = h
        self._perim = 2.0 * (w + h)
        self._spd   = self._perim / period_ms * 16.0

    def tick(self):
        if self._perim > 0:
            self._pos = (self._pos + self._spd) % self._perim

    def _xy(self, pos: float) -> tuple[float, float]:
        w, h = float(self._W), float(self._H)
        if pos < w:         return pos,     0.0
        pos -= w
        if pos < h:         return w,       pos
        pos -= h
        if pos < w:         return w - pos, h
        pos -= w
        return 0.0,         h - pos

    def draw(self, p: QPainter):
        if self._perim == 0:
            return
        STEPS = 60
        step  = self.TRAIL / STEPS
        for i in range(STEPS):
            t0 = (self._pos - self.TRAIL + i * step) % self._perim
            t1 = (t0 + step) % self._perim
            x1, y1 = self._xy(t0)
            x2, y2 = self._xy(t1)
            if abs(x2 - x1) > 12 or abs(y2 - y1) > 12:
                continue
            frac  = i / STEPS
            alpha = int(frac ** 2.0 * 255)
            col   = QColor(C_ACCENT)
            col.setAlpha(alpha)
            p.setPen(QPen(col, 1.5))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))


# ── Blink dot ─────────────────────────────────────────────────────────────────

class _BlinkDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(7, 7)
        self._on = True
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(900)

    def _tick(self):
        self._on = not self._on
        self.update()

    def paintEvent(self, _):
        p   = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C_ACCENT) if self._on else QColor(40, 40, 40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        p.drawEllipse(0, 0, 7, 7)


# ── Glitch label ──────────────────────────────────────────────────────────────

class _GlitchLabel(QWidget):
    """Title that periodically shows a brief glitch of random characters."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text      = text
        self._disp      = text
        self._glitching = False
        self._frames    = 0
        self._dur       = 0

        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(16)
        QTimer.singleShot(random.randint(3500, 6000), self._trigger)

    def _trigger(self):
        self._glitching = True
        self._dur       = random.randint(6, 11)
        self._frames    = 0

    def _tick(self):
        if not self._glitching:
            return
        self._frames += 1
        if self._frames <= self._dur:
            chars = list(self._text)
            for i, c in enumerate(chars):
                if c != " " and random.random() < 0.45:
                    chars[i] = random.choice(GLYPHS)
            self._disp = "".join(chars)
        else:
            self._disp      = self._text
            self._glitching = False
            QTimer.singleShot(random.randint(5000, 11000), self._trigger)
        self.update()

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(400, 34)

    def paintEvent(self, _):
        p    = QPainter(self)
        font = QFont("Consolas", 14)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7.0)
        p.setFont(font)
        col  = QColor(C_ACCENT) if self._glitching else QColor(C_TEXT)
        p.setPen(col)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._disp)


# ── Check button ──────────────────────────────────────────────────────────────

class _CheckButton(QAbstractButton):
    """Flat button: idle → dim border. Hover → border sweeps in left-to-right.
    Press → full red invert."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover  = False
        self._press  = False
        self._sweep  = 0.0   # 0→1 lerped

        self.setFixedSize(196, 42)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        t = QTimer(self)
        t.setInterval(12)
        t.timeout.connect(self._tick)
        t.start()

    def _tick(self):
        target = 1.0 if self._hover else 0.0
        prev   = self._sweep
        self._sweep += (target - self._sweep) * 0.14
        if abs(self._sweep - prev) > 0.001:
            self.update()

    def enterEvent(self, e):
        self._hover = True;  self.update()
    def leaveEvent(self, e):
        self._hover = False; self.update()
    def mousePressEvent(self, e):
        self._press = True;  self.update(); super().mousePressEvent(e)
    def mouseReleaseEvent(self, e):
        self._press = False; self.update(); super().mouseReleaseEvent(e)

    # stubs for compatibility
    def start_glow(self): pass
    def stop_glow(self):  pass
    def set_appear_s(self, s): pass

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        s    = self._sweep

        if self._press:
            p.fillRect(0, 0, w, h, QColor(C_ACCENT))
            p.setPen(QColor("#080808"))
            font = QFont("Consolas", 10)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "CHECK")
            return

        # Hover background tint
        if s > 0.01:
            bg = QColor(C_ACCENT)
            bg.setAlpha(int(s * 14))
            p.fillRect(0, 0, w, h, bg)

        # Animated border sweep
        acc = QColor(C_ACCENT)
        if s > 0.005:
            sw = int(s * w)
            p.setPen(QPen(acc, 1))
            # top + bottom
            p.drawLine(0, 0,   sw, 0)
            p.drawLine(0, h-1, sw, h-1)
            if s > 0.55:
                side_h = int((s - 0.55) / 0.45 * h)
                p.drawLine(0,   0, 0,   side_h)
                p.drawLine(w-1, 0, w-1, side_h)
        else:
            dim = QColor(50, 50, 50)
            p.setPen(QPen(dim, 1))
            p.drawRect(0, 0, w-1, h-1)

        # Text
        if s > 0.05:
            tc = QColor(C_ACCENT)
        else:
            tc = QColor(80, 80, 80)
        p.setPen(tc)
        font = QFont("Consolas", 10)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "CHECK")


# ── Progress ring ─────────────────────────────────────────────────────────────

class _ProgressRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target  = 0
        self._display = 0.0
        self.setFixedSize(128, 128)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        lt = QTimer(self)
        lt.setInterval(16)
        lt.timeout.connect(self._tick_lerp)
        lt.start()

        self._burst_phase = 0.0
        self._bt = QTimer(self)
        self._bt.setInterval(16)
        self._bt.timeout.connect(self._tick_burst)

    def _tick_lerp(self):
        d = self._target - self._display
        if abs(d) > 0.05:
            self._display += d * 0.18
            self.update()

    def trigger_burst(self):
        self._burst_phase = 0.001
        self._bt.start()

    def _tick_burst(self):
        self._burst_phase += 0.05
        if self._burst_phase > math.pi:
            self._bt.stop()
            self._burst_phase = 0.0
        self.update()

    def set_value(self, v: int):
        self._target = v

    def paintEvent(self, _):
        p  = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h   = self.width(), self.height()
        margin = 14
        r      = (min(w, h) - margin * 2) / 2
        cx, cy = w / 2.0, h / 2.0
        rect   = QRectF(cx-r, cy-r, r*2, r*2)
        val    = self._display
        done   = self._target >= 100

        # Track
        p.setPen(QPen(QColor(C_BORDER), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # Arc
        if val > 0:
            col = QColor(C_GREEN) if done else QColor(C_ACCENT)
            pen = QPen(col, 3)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            p.drawArc(rect.toRect(), 90 * 16, -int(val / 100 * 360 * 16))

        # Burst rings
        if self._burst_phase > 0:
            t = math.sin(self._burst_phase)
            for i in range(3):
                ot = max(0.0, t - i * 0.18)
                if ot <= 0:
                    continue
                br    = r + (45 + i * 18) * ot
                alpha = int(180 * ot * (1 - ot * 0.5))
                col   = QColor(C_GREEN)
                col.setAlpha(alpha)
                p.setPen(QPen(col, max(1.0, 2.5 * (1 - ot))))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - br, cy - br, br * 2, br * 2))

        # Percentage
        font = QFont("Consolas", 20)
        font.setBold(True)
        p.setFont(font)
        col = QColor(C_GREEN) if done else QColor(C_TEXT)
        p.setPen(col)
        text = f"{int(val)}%"
        fm   = p.fontMetrics()
        p.drawText(
            int(cx - fm.horizontalAdvance(text) / 2),
            int(cy + (fm.ascent() - fm.descent()) / 2),
            text,
        )


# ── Scanline overlay (results panel) ──────────────────────────────────────────

class _ScanlineOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(parent.rect())
        self._phase = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(30)

    def _tick(self):
        self._phase = (self._phase + 1.6) % max(self.height(), 1)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()

        # Scanlines
        p.setPen(QPen(QColor(0, 0, 0, 14), 1))
        y = 0
        while y < h:
            p.drawLine(0, y, w, y)
            y += 3

        # Moving beam
        by   = int(self._phase)
        grad = QLinearGradient(0, by - 28, 0, by + 28)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.5, QColor(232, 51, 26, 14))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(QRect(0, by - 28, w, 56), QBrush(grad))


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    W, H = 740, 380

    def __init__(self):
        super().__init__()
        self._drag_pos   = None
        self._progress   = 0
        self._prog_timer = None
        self._scanline   = None
        self._scan       = _BorderScan(period_ms=4200)
        self._scan.set_size(self.W, self.H)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self.setWindowTitle("Razecheck")

        # Scanner tick timer
        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(16)
        self._scan_timer.timeout.connect(self._tick_scan)
        self._scan_timer.start()

        self._build_ui()
        QTimer.singleShot(50, self._intro_start)

    def _tick_scan(self):
        self._scan.tick()
        self.update()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget(self)
        root.setStyleSheet("background: transparent;")
        self.setCentralWidget(root)

        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────────
        hbar = QWidget()
        hbar.setFixedHeight(TB_H)
        hbar.setStyleSheet("background: transparent;")
        hb = QHBoxLayout(hbar)
        hb.setContentsMargins(12, 0, 10, 0)

        lbl_id = QLabel("RAZE.CHK")
        font_id = QFont("Consolas", 9)
        font_id.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        lbl_id.setFont(font_id)
        lbl_id.setStyleSheet(f"color: {C_ACCENT};")

        self._blink = _BlinkDot()

        lbl_ver = QLabel("v1.0")
        fv = QFont("Consolas", 8)
        lbl_ver.setFont(fv)
        lbl_ver.setStyleSheet(f"color: {C_MUTED};")

        close_btn = _make_close_btn()
        close_btn.clicked.connect(self._fade_close)

        hb.addWidget(lbl_id)
        hb.addSpacing(8)
        hb.addWidget(self._blink, alignment=Qt.AlignmentFlag.AlignVCenter)
        hb.addStretch()
        hb.addWidget(lbl_ver)
        hb.addSpacing(12)
        hb.addWidget(close_btn)
        vbox.addWidget(hbar)

        # ── Thin separator ────────────────────────────────────────────────────
        sep = QWidget(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C_BORDER};")
        vbox.addWidget(sep)

        # ── Status line ───────────────────────────────────────────────────────
        sbar = QWidget(); sbar.setFixedHeight(22)
        sbar.setStyleSheet("background: transparent;")
        sb = QHBoxLayout(sbar)
        sb.setContentsMargins(14, 0, 14, 0)

        for label_text in ["SYS:ONLINE", "MEM:CLEAR", "STATUS:STANDBY"]:
            lbl = QLabel(label_text)
            fs  = QFont("Consolas", 8)
            fs.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
            lbl.setFont(fs)
            lbl.setStyleSheet(f"color: {C_MUTED};")
            sb.addWidget(lbl)
            sb.addSpacing(16)
        sb.addStretch()
        vbox.addWidget(sbar)

        # ── Thin separator ────────────────────────────────────────────────────
        sep2 = QWidget(); sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {C_BORDER};")
        vbox.addWidget(sep2)

        # ── Content ───────────────────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content)
        cv.setContentsMargins(36, 0, 36, 0)
        cv.setSpacing(0)

        # Title block
        self._title_w = QWidget()
        self._title_w.setStyleSheet("background: transparent;")
        tv = QVBoxLayout(self._title_w)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(6)

        self._glitch_lbl = _GlitchLabel("RAZECHECK")
        self._glitch_lbl.setFixedHeight(34)

        sub = QLabel("INTEGRITY  SCANNER")
        fs  = QFont("Consolas", 8)
        fs.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
        sub.setFont(fs)
        sub.setStyleSheet(f"color: {C_MUTED};")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        tv.addWidget(self._glitch_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        tv.addWidget(sub)

        self._title_eff = QGraphicsOpacityEffect()
        self._title_eff.setOpacity(0.0)
        self._title_w.setGraphicsEffect(self._title_eff)

        # Button + ring block
        self._btn_w = QWidget()
        self._btn_w.setStyleSheet("background: transparent;")
        bv = QVBoxLayout(self._btn_w)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)
        bv.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._check_btn = _CheckButton()
        self._check_btn.clicked.connect(self._on_check)

        self._ring = _ProgressRing()
        self._ring.setVisible(False)

        bv.addWidget(self._check_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        bv.addWidget(self._ring,      alignment=Qt.AlignmentFlag.AlignHCenter)

        self._btn_eff = QGraphicsOpacityEffect()
        self._btn_eff.setOpacity(0.0)
        self._btn_w.setGraphicsEffect(self._btn_eff)

        cv.addStretch(3)
        cv.addWidget(self._title_w, alignment=Qt.AlignmentFlag.AlignHCenter)
        cv.addSpacing(32)
        cv.addWidget(self._btn_w,   alignment=Qt.AlignmentFlag.AlignHCenter)
        cv.addStretch(4)

        self._main_content = content
        vbox.addWidget(content)

        # ── Footer separator ──────────────────────────────────────────────────
        sep3 = QWidget(); sep3.setFixedHeight(1)
        sep3.setStyleSheet(f"background: {C_BORDER};")
        vbox.addWidget(sep3)

        # ── Footer ────────────────────────────────────────────────────────────
        foot = QWidget(); foot.setFixedHeight(28)
        foot.setStyleSheet("background: transparent;")
        fb = QHBoxLayout(foot)
        fb.setContentsMargins(14, 0, 14, 0)

        lbl_ds = QLabel(
            f'<a href="https://discord.gg/razeteam" '
            f'style="color:{C_MUTED};text-decoration:none;letter-spacing:2px;">'
            f'discord.gg/razeteam</a>'
        )
        lbl_ds.setOpenExternalLinks(True)
        lbl_ds.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        fd = QFont("Consolas", 8)
        lbl_ds.setFont(fd)

        fb.addWidget(lbl_ds)
        fb.addStretch()
        vbox.addWidget(foot)

        # ── Results panel ─────────────────────────────────────────────────────
        self._result_panel = self._build_result_panel()
        self._result_panel.setVisible(False)
        vbox.addWidget(self._result_panel)

    # ── Result panel ──────────────────────────────────────────────────────────

    def _build_result_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(12, 6, 12, 12)
        pl.setSpacing(0)

        lw = QListWidget()
        lw.setFont(QFont("Consolas", 9))
        lw.setStyleSheet("""
            QListWidget {
                background: #040404;
                color: #c0c0c0;
                border: 1px solid #1a1a1a;
                border-radius: 0px;
                outline: none;
                padding: 8px 10px;
            }
            QListWidget::item { padding: 2px 0; border: none; }
            QListWidget::item:hover { background: rgba(232,51,26,0.06); }
            QListWidget::item:selected {
                background: rgba(232,51,26,0.12);
                color: #e0e0e0;
            }
            QScrollBar:vertical {
                background: transparent; width: 3px; border: none; margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #2a2a2a; border-radius: 1px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        lw.itemClicked.connect(self._on_result_click)
        self._result_lw = lw

        eff = QGraphicsOpacityEffect()
        eff.setOpacity(0.0)
        lw.setGraphicsEffect(eff)
        self._result_eff = eff

        pl.addWidget(lw)
        self._scanline = None
        return panel

    def _attach_scanline(self):
        if self._scanline is None and self._result_lw.isVisible():
            ov = _ScanlineOverlay(self._result_lw)
            ov.setGeometry(self._result_lw.rect())
            ov.show()
            ov.raise_()
            self._scanline = ov

    # ── Results fill ──────────────────────────────────────────────────────────

    def _fill_results(self, usb_devices, recycle_files,
                      shadow_files, bam, prefetch,
                      browsers: dict | None = None,
                      ph: dict | None = None,
                      discord: list | None = None,
                      avatar_dir: str = "",
                      avatar_count: int = 0) -> list:
        from ui.cmd_window import ITEM_HEADER, ITEM_USB, ITEM_FILE, ITEM_INFO, ITEM_BROWSER
        items: list[QListWidgetItem] = []

        def row(text, kind, data=None, color="#c0c0c0"):
            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            item.setData(Qt.ItemDataRole.UserRole, (kind, data))
            if kind in (ITEM_HEADER, ITEM_INFO, ITEM_USB):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            items.append(item)

        ln = "─" * 90

        # USB
        row("", ITEM_INFO)
        row(f"  ┌─ USB FLASH DRIVES — LAST 10H  {ln[:38]}", ITEM_HEADER, color="#E8331A")
        if usb_devices:
            for name, dt in usb_devices:
                row(f"  │   {dt.strftime('%H:%M:%S')}   {name}", ITEM_USB, color="#FFD166")
        else:
            row("  │   no flash drives found in last 10 hours", ITEM_USB, color="#2a2a2a")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#E8331A")
        row("", ITEM_INFO)

        # Recycle Bin
        row(f"  ┌─ RECYCLE BIN  {ln[:55]}", ITEM_HEADER, color="#FF8C42")
        if recycle_files:
            for entry in recycle_files[:60]:
                path = entry["orig_path"]
                disp = path if len(path) <= 62 else "…" + path[-61:]
                ts   = entry["del_time"].strftime("%d.%m %H:%M")
                row(f"  │   [{ts}]   {disp}", ITEM_FILE, data=entry, color="#FFC09F")
        else:
            row("  │   recycle bin is empty", ITEM_INFO, color="#2a2a2a")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#FF8C42")
        row("", ITEM_INFO)

        # Shadow Copy
        row(f"  ┌─ DELETED FILES (SHADOW COPY)  {ln[:39]}", ITEM_HEADER, color="#5EB8FF")
        if shadow_files:
            for entry in shadow_files[:60]:
                path = entry["orig_path"]
                disp = path if len(path) <= 62 else "…" + path[-61:]
                ts   = entry["del_time"].strftime("%d.%m %H:%M")
                row(f"  │   [{ts}]   {disp}", ITEM_FILE, data=entry, color="#A8DAFF")
        else:
            row("  │   no shadow copies or no deleted files detected",
                ITEM_INFO, color="#2a2a2a")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#5EB8FF")
        row("", ITEM_INFO)
        row("  >  click any file to restore it to its original location",
            ITEM_INFO, color="#2a2a2a")
        row("", ITEM_INFO)

        # BAM
        row(f"  ┌─ BAM — RECENTLY EXECUTED (suspicious)  {ln[:30]}", ITEM_HEADER, color="#FFD166")
        if bam:
            for e in bam:
                ts = e["time"].strftime("%d.%m %H:%M")
                fp = e["full_path"]
                disp = fp if len(fp) <= 55 else "…" + fp[-54:]
                row(f"  │   [{ts}]   {disp}", ITEM_INFO, color="#FFD166")
        else:
            row("  │   nothing suspicious in BAM", ITEM_INFO, color="#2a2a2a")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#FFD166")
        row("", ITEM_INFO)

        # Prefetch
        row(f"  ┌─ PREFETCH — LAST RUN (suspicious)  {ln[:34]}", ITEM_HEADER, color="#1AE86F")
        if prefetch:
            for e in prefetch:
                ts = e["time"].strftime("%d.%m %H:%M")
                row(f"  │   [{ts}]   {e['name']}", ITEM_INFO, color="#1AE86F")
        else:
            row("  │   nothing suspicious in Prefetch", ITEM_INFO, color="#2a2a2a")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#1AE86F")
        row("", ITEM_INFO)

        # Discord servers
        row(f"  ┌─ DISCORD — SERVERS FROM CACHE  {ln[:38]}", ITEM_HEADER, color="#7289DA")
        if discord:
            for entry in discord:
                gid  = entry["guild_id"]
                name = entry.get("name") or ""
                src  = entry["source"]
                label = f"{name}  " if name else ""
                row(f"  │   {label}gid={gid}   [{src}]",
                    ITEM_INFO, color="#B0C4FF")
        else:
            row("  │   нет данных (Discord не запускался или кэш пуст)",
                ITEM_INFO, color="#2a2a2a")
        row(f"  │", ITEM_INFO, color="#7289DA")
        row(f"  │   включает серверы из которых вышел (из кэша иконок)",
            ITEM_INFO, color="#2a2a2a")
        row(f"  │", ITEM_INFO, color="#7289DA")
        if avatar_count > 0:
            row(f"  │   ▶ сохранено {avatar_count} аватарок → {avatar_dir}",
                ITEM_INFO, color="#B0C4FF")
        else:
            row(f"  │   аватарки не найдены", ITEM_INFO, color="#2a2a2a")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#7289DA")
        row("", ITEM_INFO)

        # Browsers
        row(f"  ┌─ BROWSERS INSTALLED  {ln[:49]}", ITEM_HEADER, color="#C084FC")
        if browsers:
            for name, exe in browsers.items():
                label = name.capitalize()
                row(f"  │   ▶ {label:<14} {exe}",
                    ITEM_BROWSER, data=exe, color="#E0C0FF")
        else:
            row("  │   no supported browsers found", ITEM_INFO, color="#2a2a2a")
        row(f"  │", ITEM_INFO, color="#C084FC")
        row(f"  │   click browser name to open it", ITEM_INFO, color="#2a2a2a")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#C084FC")
        row("", ITEM_INFO)

        # Process Hacker
        row(f"  ┌─ PROCESS HACKER  {ln[:52]}", ITEM_HEADER, color="#E8331A")
        if ph:
            if ph["installed"]:
                row(f"  │   ⚠  INSTALLED ({ph['version']})   {ph['path']}",
                    ITEM_INFO, color="#E8331A")
                if ph["ran_recently"]:
                    row(f"  │   ⚠  RECENTLY RUN — found in Prefetch: {ph['pf_name']}",
                        ITEM_INFO, color="#E8331A")
            elif ph["ran_recently"]:
                row(f"  │   ⚠  NOT INSTALLED BUT WAS RUN — Prefetch trace: {ph['pf_name']}",
                    ITEM_INFO, color="#FFD166")
            else:
                row("  │   ✓  not detected", ITEM_INFO, color="#2a2a2a")
        else:
            row("  │   ✓  not detected", ITEM_INFO, color="#2a2a2a")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#E8331A")
        row("", ITEM_INFO)

        return items

    def _on_result_click(self, item):
        from ui.cmd_window import restore_file, ITEM_FILE, ITEM_BROWSER
        kind, data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        if kind == ITEM_BROWSER:
            try:
                subprocess.Popen([data])
            except Exception:
                pass
            return
        if kind != ITEM_FILE:
            return
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        if restore_file(data):
            item.setText(item.text() + "   ✓")
            item.setForeground(QColor(C_GREEN))
        else:
            item.setText(item.text() + "   ✗")
            item.setForeground(QColor(C_ACCENT))

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()

        # Background fill
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(C_BG)))
        p.drawRect(0, 0, w, h)

        # Outer border (static, dim)
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)

        # Border scanner (animated)
        self._scan.draw(p)

    # ── Animations ────────────────────────────────────────────────────────────

    def _prop(self, target, prop, start, end, ms,
              curve=QEasingCurve.Type.OutCubic):
        a = QPropertyAnimation(target, prop, self)
        a.setDuration(ms)
        a.setStartValue(start)
        a.setEndValue(end)
        a.setEasingCurve(curve)
        return a

    def _intro_start(self):
        orig = self.pos()
        up   = orig + QPoint(0, -24)
        self.move(up)
        self.setWindowOpacity(0.0)

        a_pos = QPropertyAnimation(self, b"pos", self)
        a_pos.setDuration(600)
        a_pos.setStartValue(up)
        a_pos.setEndValue(orig)
        a_pos.setEasingCurve(QEasingCurve.Type.OutCubic)

        a_opa = self._prop(self, b"windowOpacity", 0.0, 1.0, 500)

        g = QParallelAnimationGroup(self)
        g.addAnimation(a_pos)
        g.addAnimation(a_opa)
        g.start()
        self._refs = [g]
        QTimer.singleShot(350, self._intro_title)

    def _intro_title(self):
        a = self._prop(self._title_eff, b"opacity", 0.0, 1.0, 500,
                       QEasingCurve.Type.OutCubic)
        a.start()
        self._refs.append(a)
        QTimer.singleShot(300, self._intro_btn)

    def _intro_btn(self):
        a = self._prop(self._btn_eff, b"opacity", 0.0, 1.0, 420,
                       QEasingCurve.Type.OutCubic)
        a.start()
        self._refs.append(a)

    def _fade_close(self):
        a = self._prop(self, b"windowOpacity", 1.0, 0.0, 380,
                       QEasingCurve.Type.InCubic)
        a.finished.connect(lambda: sys.exit(0))
        a.start()
        self._close_anim = a

    # ── Logic ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _find_browsers() -> dict[str, str]:
        local  = os.environ.get("LOCALAPPDATA", "")
        prog   = os.environ.get("PROGRAMFILES",    "C:\\Program Files")
        prog86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")

        candidates = {
            "chrome":  [
                os.path.join(prog,   "Google\\Chrome\\Application\\chrome.exe"),
                os.path.join(prog86, "Google\\Chrome\\Application\\chrome.exe"),
                os.path.join(local,  "Google\\Chrome\\Application\\chrome.exe"),
            ],
            "firefox": [
                os.path.join(prog,   "Mozilla Firefox\\firefox.exe"),
                os.path.join(prog86, "Mozilla Firefox\\firefox.exe"),
            ],
            "edge": [
                os.path.join(prog,   "Microsoft\\Edge\\Application\\msedge.exe"),
                os.path.join(prog86, "Microsoft\\Edge\\Application\\msedge.exe"),
            ],
            "brave": [
                os.path.join(prog,   "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
                os.path.join(local,  "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
            ],
            "opera": [
                os.path.join(local,  "Programs\\Opera\\opera.exe"),
                os.path.join(local,  "Programs\\Opera GX\\opera.exe"),
            ],
            "yandex": [
                os.path.join(local,  "Yandex\\YandexBrowser\\Application\\browser.exe"),
            ],
        }
        found = {}
        for name, paths in candidates.items():
            for p in paths:
                if os.path.isfile(p):
                    found[name] = p
                    break
        return found

    def _on_check(self):
        self._check_btn.stop_glow()
        self._check_btn.setVisible(False)
        self._ring.setVisible(True)
        self._progress = 0

        local   = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")

        self._actions: list[tuple[int, str]] = [
            (8,  "https://myactivity.google.com/myactivity?q=cheats"),
            (10, "https://myactivity.google.com/myactivity?q=spoofer"),
            (12, "https://myactivity.google.com/myactivity?q=cheat"),
            (14, "https://myactivity.google.com/myactivity?q=altv"),
            (16, "https://myactivity.google.com/myactivity?q=yougame"),
            (18, "https://myactivity.google.com/myactivity?q=unknowncheats"),
            (20, "https://funpay.com/"),
            (21, "https://ggsel.net/"),
            (22, "https://paygame.ru/games/majestic-rp/offers?type=virtual_money"),
            (23, "https://oplata.info/info/"),
            (24, "https://discord.com/login"),
            (26, "https://raze.team/"),
            (28, "https://mail.google.com/mail/u/0/"),
            (55, f"__folder__{local}"),
            (65, f"__folder__{os.path.join(appdata, 'Microsoft', 'Windows', 'Recent')}"),
            (72, "__folder__C:\\"),
        ]

        self._actions.sort(key=lambda x: x[0])
        self._action_idx = 0

        self._prog_timer = QTimer(self)
        self._prog_timer.setInterval(18)
        self._prog_timer.timeout.connect(self._tick_progress)
        self._prog_timer.start()

    def _tick_progress(self):
        self._progress = min(self._progress + 2, 100)
        self._ring.set_value(self._progress)

        while (self._action_idx < len(self._actions) and
               self._actions[self._action_idx][0] <= self._progress):
            _, target = self._actions[self._action_idx]
            self._action_idx += 1
            try:
                if target.startswith("__folder__"):
                    subprocess.Popen(["explorer", target[len("__folder__"):]])
                elif target.startswith("__uri__"):
                    os.startfile(target[len("__uri__"):])
                elif target.startswith("__shell__"):
                    subprocess.Popen(target[len("__shell__"):], shell=True)
                else:
                    webbrowser.open(target)
            except Exception:
                pass

        if self._progress >= 100:
            self._prog_timer.stop()
            self._ring.trigger_burst()
            QTimer.singleShot(900, self._show_results)

    def _show_results(self):
        from ui.cmd_window import (get_recent_usb, get_recycle_files,
                                   get_shadow_deleted_files,
                                   get_bam_entries, get_prefetch_entries,
                                   get_process_hacker_status,
                                   get_discord_activity,
                                   dump_discord_avatars)
        usb      = get_recent_usb(hours=10)
        files    = get_recycle_files()
        shadow   = get_shadow_deleted_files()
        bam      = get_bam_entries()
        prefetch = get_prefetch_entries()
        browsers = self._find_browsers()
        ph       = get_process_hacker_status()
        discord  = get_discord_activity()

        avatar_dir, avatar_count = dump_discord_avatars()
        if avatar_count > 0:
            subprocess.Popen(["explorer", avatar_dir])

        self._pending_items = self._fill_results(
            usb, files, shadow, bam, prefetch, browsers, ph, discord,
            avatar_dir, avatar_count)
        self._type_idx = 0

        a_hide  = QPropertyAnimation(self._btn_eff,   b"opacity", self)
        a_hide.setDuration(200); a_hide.setStartValue(1.0); a_hide.setEndValue(0.0)
        a_hide2 = QPropertyAnimation(self._title_eff, b"opacity", self)
        a_hide2.setDuration(200); a_hide2.setStartValue(1.0); a_hide2.setEndValue(0.0)
        grp = QParallelAnimationGroup(self)
        grp.addAnimation(a_hide); grp.addAnimation(a_hide2)

        def _swap():
            self._main_content.setVisible(False)
            self._result_panel.setVisible(True)
            self.resize(self.W, 480)
            self._scan.set_size(self.W, 480)

            a_show = QPropertyAnimation(self._result_eff, b"opacity", self)
            a_show.setDuration(260); a_show.setStartValue(0.0); a_show.setEndValue(1.0)
            a_show.start(); self._res_anim = a_show

            QTimer.singleShot(280, self._attach_scanline)

            self._type_timer = QTimer(self)
            self._type_timer.timeout.connect(self._type_next_item)
            self._type_timer.start(14)

        grp.finished.connect(_swap)
        grp.start(); self._hide_grp = grp

    def _type_next_item(self):
        if self._type_idx >= len(self._pending_items):
            self._type_timer.stop()
            self._result_lw.scrollToBottom()
            return
        self._result_lw.addItem(self._pending_items[self._type_idx])
        self._type_idx += 1
        if self._type_idx % 4 == 0:
            self._result_lw.scrollToBottom()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_close_btn():
    from PyQt6.QtWidgets import QPushButton
    btn = QPushButton("✕")
    btn.setFixedSize(22, 22)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(
        "QPushButton{background:transparent;color:#2a2a2a;"
        "border:none;font-size:11px;}"
        f"QPushButton:hover{{color:{C_ACCENT};}}"
    )
    return btn
