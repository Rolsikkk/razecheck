import math
import os
import random
import subprocess
import sys
import time
import webbrowser

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QVariantAnimation, QEasingCurve,
    QParallelAnimationGroup,
    QPoint, QRectF,
)
from PyQt6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetrics,
    QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QAbstractButton, QApplication,
    QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow,
    QVBoxLayout, QWidget,
)

# ── Palette ───────────────────────────────────────────────────────────────────

C_BG_TOP   = "#0d1526"
C_BG_BOT   = "#131c33"
C_ACCENT   = "#3a6df0"
C_ACCENT_B = "#5b8cff"
C_TEXT     = "#e8ecf7"
C_SUBTITLE = "#6b7fa3"
RADIUS     = 15
TB_H       = 36


# ── Particle factory ──────────────────────────────────────────────────────────

def _spawn_particle(W: int, H: int, fresh: bool = True) -> dict:
    max_life = random.uniform(5.0, 14.0)
    return {
        'x':        random.uniform(0, W),
        'y':        random.uniform(0, H),
        'vx':       random.uniform(-25, 25),   # px / sec
        'vy':       random.uniform(-25, 25),
        'r':        random.uniform(1.0, 2.5),
        'base_a':   random.randint(45, 105),
        'life':     0.0 if fresh else random.uniform(0, max_life),
        'max_life': max_life,
    }


# ── Custom check button ───────────────────────────────────────────────────────

class _GlowButton(QAbstractButton):
    """
    Изменения:
    • Spring-hover: velocity-based (лёгкий overshoot при наведении)
    • Press scale: -5% при нажатии с плавным возвратом
    • Appear scale: set_appear_s() управляет масштабом при появлении
    • Compound-sine pulse: два синуса → органичный, не механический ритм
    • Усиленное ambient-свечение в центре при idle-pulse
    """

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._label = text

        self._hover     = False
        self._hover_raw = 0.0    # unclipped spring value (может слегка >1.0)
        self._hover_vel = 0.0
        self._hover_t   = 0.0    # clamped 0..1 для отрисовки

        self._pressed   = False
        self._press_t   = 0.0   # 0..1, lerp к press

        self._appear_s  = 0.75  # начальный масштаб при появлении
        self._glow_phase = 0.0

        self._mx = 140.0; self._my = 40.0
        self._tx = 140.0; self._ty = 40.0

        self.setFixedSize(280, 80)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(16)   # 60 fps
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

    # ── Spring hover + press + glow tick ────────────────────────────────────

    def _tick(self):
        # Spring: k=0.14 жёсткость, d=0.72 демпфирование — живее, больше overshoot
        target = 1.0 if self._hover else 0.0
        self._hover_vel = (self._hover_vel + (target - self._hover_raw) * 0.14) * 0.72
        self._hover_raw += self._hover_vel
        self._hover_t = max(0.0, min(1.0, self._hover_raw))

        # Press lerp
        press_target = 1.0 if self._pressed else 0.0
        self._press_t += (press_target - self._press_t) * 0.28

        # Spotlight follows mouse — быстрее отклик
        self._mx += (self._tx - self._mx) * 0.26
        self._my += (self._ty - self._my) * 0.26

        # Glow phase
        if self._glow_phase > 0:
            self._glow_phase += 0.035   # немного медленнее для изящества

        self.update()

    def start_glow(self):
        self._glow_phase = 0.001

    def stop_glow(self):
        self._glow_phase = 0.0
        self.update()

    def set_appear_s(self, s: float):
        """Вызывается из MainWindow._intro_btn() через QVariantAnimation."""
        self._appear_s = s
        self.update()

    # ── Mouse events ─────────────────────────────────────────────────────────

    def mouseMoveEvent(self, e):
        self._tx = e.position().x()
        self._ty = e.position().y()
        super().mouseMoveEvent(e)

    def enterEvent(self, e):
        self._hover = True
        pos = self.mapFromGlobal(e.globalPosition().toPoint())
        self._mx = self._tx = float(pos.x())
        self._my = self._ty = float(pos.y())
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._pressed = True
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._pressed = False
        super().mouseReleaseEvent(e)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        t = self._hover_t

        # Compound-sine pulse: два синуса → органичный ритм
        if self._glow_phase > 0:
            s1 = math.sin(self._glow_phase * 1.0)
            s2 = math.sin(self._glow_phase * 2.3 + 0.7) * 0.35
            pulse = max(0.0, min(1.0, (s1 + s2) / 1.35 * 0.5 + 0.5))
        else:
            pulse = 0.0

        # Scale transform: appear (OutBack overshoot) + press shrink
        scale = self._appear_s * (1.0 - 0.05 * self._press_t)
        if abs(scale - 1.0) > 0.001:
            p.translate(w / 2, h / 2)
            p.scale(scale, scale)
            p.translate(-w / 2, -h / 2)

        shape = QPainterPath()
        shape.addRoundedRect(0, 0, w, h, 16, 16)

        def lerp_color(c1, c2, v):
            return QColor(
                int(c1.red()   + (c2.red()   - c1.red())   * v),
                int(c1.green() + (c2.green() - c1.green()) * v),
                int(c1.blue()  + (c2.blue()  - c1.blue())  * v),
            )

        # Layer 1: background
        bg_alpha = int(255 * t)
        if bg_alpha > 0:
            bg_top = lerp_color(QColor("#141e38"), QColor("#1d2f56"), t)
            bg_bot = lerp_color(QColor("#0d1526"), QColor("#131e40"), t)
            bg_top.setAlpha(bg_alpha)
            bg_bot.setAlpha(bg_alpha)
            bg = QLinearGradient(0, 0, 0, h)
            bg.setColorAt(0.0, bg_top)
            bg.setColorAt(1.0, bg_bot)
            p.fillPath(shape, QBrush(bg))

        # Layer 2: spotlight / idle ambient pulse
        hover_glow = t * 0.92
        idle_glow  = pulse * 0.70 * (1.0 - t)
        glow_strength = max(hover_glow, idle_glow)
        if glow_strength > 0.005:
            cx = self._mx if t > 0.01 else w * 0.5
            cy = self._my if t > 0.01 else h * 0.5

            # Широкий мягкий ореол (фон вокруг курсора)
            rg_wide = QRadialGradient(cx, cy, w * 0.85)
            c_wide = QColor(C_ACCENT)
            c_wide.setAlpha(int(55 * glow_strength))
            rg_wide.setColorAt(0.0, c_wide)
            rg_wide.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.fillPath(shape, QBrush(rg_wide))

            # Яркий узкий spotlight
            radius = w * (0.42 + idle_glow * 0.20)
            rg = QRadialGradient(cx, cy, radius)
            c_center = QColor(C_ACCENT_B)
            c_center.setAlpha(int(190 * glow_strength))
            c_mid = QColor(C_ACCENT)
            c_mid.setAlpha(int(80 * glow_strength))
            c_edge = QColor(C_ACCENT)
            c_edge.setAlpha(0)
            rg.setColorAt(0.0, c_center)
            rg.setColorAt(0.45, c_mid)
            rg.setColorAt(1.0, c_edge)
            p.fillPath(shape, QBrush(rg))

        # Layer 3: top shimmer glint
        if t > 0.01:
            glint = QLinearGradient(0, 0, 0, h * 0.5)
            glint.setColorAt(0.0, QColor(255, 255, 255, int(55 * t)))
            glint.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillPath(shape, QBrush(glint))

        # Text
        font = QFont("Consolas")
        font.setPixelSize(18)
        font.setBold(True)
        p.setFont(font)

        text = self._label.upper()
        fm   = QFontMetrics(font)
        gap  = 9
        total_w = sum(fm.horizontalAdvance(c) for c in text) + gap * (len(text) - 1)
        x0 = (w - total_w) / 2.0
        y0 = (h + fm.ascent() - fm.descent()) / 2.0

        if t > 0.05:
            p.setPen(QColor(0, 0, 0, int(80 * t)))
            x = x0
            for ch in text:
                p.drawText(int(x) + 1, int(y0) + 1, ch)
                x += fm.horizontalAdvance(ch) + gap

        txt_col = lerp_color(QColor("#5a6f9a"), QColor(C_TEXT), t)
        p.setPen(txt_col)
        x = x0
        for ch in text:
            p.drawText(int(x), int(y0), ch)
            x += fm.horizontalAdvance(ch) + gap


# ── Circular progress ring ────────────────────────────────────────────────────

class _ProgressRing(QWidget):
    """
    Изменения:
    • _display: float лерпит к _target → плавное движение дуги и счётчика
    • Burst: 3 концентрических кольца с поочерёдным появлением
    • Antialias включён
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target  = 0      # целевое значение (int, от MainWindow)
        self._display = 0.0    # плавное отображаемое значение
        sz = 140
        self.setFixedSize(sz, sz)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Lerp timer — независимо от prog_timer
        self._lerp_timer = QTimer(self)
        self._lerp_timer.setInterval(16)
        self._lerp_timer.timeout.connect(self._tick_lerp)
        self._lerp_timer.start()

        self._burst_phase = 0.0
        self._burst_timer = QTimer(self)
        self._burst_timer.setInterval(16)
        self._burst_timer.timeout.connect(self._tick_burst)

    def _tick_lerp(self):
        diff = self._target - self._display
        if abs(diff) > 0.05:
            self._display += diff * 0.18
            self.update()

    def trigger_burst(self):
        self._burst_phase = 0.001
        self._burst_timer.start()

    def _tick_burst(self):
        self._burst_phase += 0.05
        if self._burst_phase > math.pi:
            self._burst_timer.stop()
            self._burst_phase = 0.0
        self.update()

    def set_value(self, v: int):
        self._target = v
        # lerp timer подхватит сам

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        margin = 14
        r = (min(w, h) - margin * 2) / 2
        cx, cy = w / 2.0, h / 2.0
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        val  = self._display
        done = self._target >= 100

        # Track ring
        p.setPen(QPen(QColor("#1e2c4e"), 5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # Progress arc — плавный через _display
        if val > 0:
            color = QColor("#5bffb0") if done else QColor(C_ACCENT_B)
            pen = QPen(color, 5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            span = int(val / 100.0 * 360 * 16)
            p.drawArc(rect.toRect(), 90 * 16, -span)

        # Burst rings
        if self._burst_phase > 0:
            t = math.sin(self._burst_phase)
            for i in range(3):
                offset_t = max(0.0, t - i * 0.18)
                if offset_t <= 0:
                    continue
                br = r + (55 + i * 22) * offset_t
                alpha = int(200 * offset_t * (1 - offset_t * 0.5))
                col = QColor("#5bffb0")
                col.setAlpha(alpha)
                pen2 = QPen(col, max(1.0, 3.0 * (1 - offset_t)))
                p.setPen(pen2)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - br, cy - br, br * 2, br * 2))

        # Percentage text — счётчик считает плавно
        font = QFont("Consolas")
        font.setPixelSize(30)
        font.setBold(True)
        p.setFont(font)
        color = QColor("#5bffb0") if done else QColor(C_TEXT)
        p.setPen(color)
        text = f"{int(val)}%"
        fm = QFontMetrics(font)
        p.drawText(
            int(cx - fm.horizontalAdvance(text) / 2),
            int(cy + (fm.ascent() - fm.descent()) / 2),
            text,
        )


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    W, H = 738, 372

    def __init__(self):
        super().__init__()
        self._drag_pos   = None
        self._progress   = 0
        self._prog_timer = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self.setWindowTitle("Razecheck")

        # Particles — delta-time, life/fade
        self._particles: list[dict] = [
            _spawn_particle(self.W, self.H, fresh=False) for _ in range(45)
        ]
        self._last_part_t = time.perf_counter()
        self._part_timer = QTimer(self)
        self._part_timer.setInterval(16)   # 60 fps (было 33ms / 30fps)
        self._part_timer.timeout.connect(self._tick_particles)
        self._part_timer.start()

        self._build_ui()
        QTimer.singleShot(50, self._intro_start)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget(self)
        root.setStyleSheet("background: transparent;")
        self.setCentralWidget(root)

        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Title bar
        tb = QWidget()
        tb.setFixedHeight(TB_H)
        tb.setStyleSheet("background: transparent;")
        tb_h = QHBoxLayout(tb)
        tb_h.setContentsMargins(14, 6, 10, 0)
        tb_h.addStretch()
        self._close_btn = _make_close_btn()
        self._close_btn.clicked.connect(lambda: sys.exit(0))
        tb_h.addWidget(self._close_btn)
        vbox.addWidget(tb)

        # Content
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content)
        cv.setContentsMargins(36, 0, 36, 30)
        cv.setSpacing(0)

        # Title block
        self._title_w = QWidget()
        self._title_w.setStyleSheet("background: transparent;")
        tv = QVBoxLayout(self._title_w)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(4)

        lbl_name = QLabel("Razecheck")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        fn = QFont(); fn.setPixelSize(33); fn.setBold(True)
        lbl_name.setFont(fn)
        lbl_name.setStyleSheet(f"color:{C_TEXT};")

        lbl_by = QLabel("by .rolsik")
        lbl_by.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        fb = QFont("Consolas"); fb.setPixelSize(12)
        lbl_by.setFont(fb)
        lbl_by.setStyleSheet(f"color:{C_SUBTITLE};letter-spacing:1px;")

        tv.addWidget(lbl_name)
        tv.addWidget(lbl_by)

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

        self._check_btn = _GlowButton("check")
        self._check_btn.clicked.connect(self._on_check)

        self._ring = _ProgressRing()
        self._ring.setVisible(False)

        bv.addWidget(self._check_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        bv.addWidget(self._ring,      alignment=Qt.AlignmentFlag.AlignHCenter)

        self._btn_eff = QGraphicsOpacityEffect()
        self._btn_eff.setOpacity(0.0)
        self._btn_w.setGraphicsEffect(self._btn_eff)

        cv.addStretch(2)
        cv.addWidget(self._title_w, alignment=Qt.AlignmentFlag.AlignHCenter)
        cv.addSpacing(36)
        cv.addWidget(self._btn_w,   alignment=Qt.AlignmentFlag.AlignHCenter)
        cv.addStretch(3)

        self._main_content = content
        vbox.addWidget(content)

        # ── Результаты (скрыты до конца проверки) ─────────────────────────────
        self._result_panel = self._build_result_panel()
        self._result_panel.setVisible(False)
        vbox.addWidget(self._result_panel)

    # ── Result panel ──────────────────────────────────────────────────────────

    def _build_result_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14, 6, 14, 14)
        pl.setSpacing(0)

        lw = QListWidget()
        lw.setFont(QFont("Consolas", 9))
        lw.setStyleSheet("""
            QListWidget {
                background: rgba(10,12,22,210);
                color: #c8ccd4;
                border: 1px solid #1e2a3a;
                border-radius: 8px;
                outline: none;
                padding: 8px 10px;
            }
            QListWidget::item { padding: 1px 0; border: none; }
            QListWidget::item:hover { background: #141e30; }
            QListWidget::item:selected { background: #1a2a40; color: #e8ecf7; }
            QScrollBar:vertical {
                background: transparent; width: 4px; border: none;
            }
            QScrollBar::handle:vertical {
                background: #2a3a55; border-radius: 2px;
            }
        """)
        lw.itemClicked.connect(self._on_result_click)
        self._result_lw = lw

        eff = QGraphicsOpacityEffect()
        eff.setOpacity(0.0)
        lw.setGraphicsEffect(eff)
        self._result_eff = eff

        pl.addWidget(lw)
        return panel

    def _fill_results(self, usb_devices: list, recycle_files: list,
                      shadow_files: list, bam: list, prefetch: list):
        from ui.cmd_window import ITEM_HEADER, ITEM_USB, ITEM_FILE, ITEM_INFO
        lw = self._result_lw

        def row(text, kind, data=None, color="#c8ccd4"):
            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            item.setData(Qt.ItemDataRole.UserRole, (kind, data))
            if kind in (ITEM_HEADER, ITEM_INFO, ITEM_USB):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            lw.addItem(item)

        ln = "─" * 90

        # ── USB ───────────────────────────────────────────────────────────────
        row("", ITEM_INFO)
        row(f"  ┌─ USB FLASH DRIVES — LAST 10H  {ln[:38]}", ITEM_HEADER, color="#3a9fff")
        if usb_devices:
            for name, dt in usb_devices:
                row(f"  │   {dt.strftime('%H:%M:%S')}   {name}", ITEM_USB, color="#f1fa8c")
        else:
            row("  │   no flash drives found in last 10 hours", ITEM_USB, color="#3a4a66")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#3a9fff")
        row("", ITEM_INFO)

        # ── Корзина ───────────────────────────────────────────────────────────
        row(f"  ┌─ RECYCLE BIN  {ln[:55]}", ITEM_HEADER, color="#3a9fff")
        if recycle_files:
            for entry in recycle_files[:60]:
                path = entry["orig_path"]
                disp = path if len(path) <= 62 else "…" + path[-61:]
                ts   = entry["del_time"].strftime("%d.%m %H:%M")
                row(f"  │   [{ts}]   {disp}", ITEM_FILE, data=entry, color="#8be9fd")
        else:
            row("  │   recycle bin is empty", ITEM_INFO, color="#3a4a66")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#3a9fff")
        row("", ITEM_INFO)

        # ── Shadow Copy (навсегда удалённые) ──────────────────────────────────
        row(f"  ┌─ DELETED FILES (SHADOW COPY)  {ln[:39]}", ITEM_HEADER, color="#bd93f9")
        if shadow_files:
            for entry in shadow_files[:60]:
                path = entry["orig_path"]
                disp = path if len(path) <= 62 else "…" + path[-61:]
                ts   = entry["del_time"].strftime("%d.%m %H:%M")
                row(f"  │   [{ts}]   {disp}", ITEM_FILE, data=entry, color="#ff79c6")
        else:
            row("  │   no shadow copies found or no deleted files detected",
                ITEM_INFO, color="#3a4a66")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#bd93f9")
        row("", ITEM_INFO)
        row("  >  click any file to restore it to its original location",
            ITEM_INFO, color="#3a4a66")
        row("", ITEM_INFO)

        # ── BAM — история запусков ────────────────────────────────────────────
        row(f"  ┌─ BAM — RECENTLY EXECUTED (suspicious)  {ln[:30]}", ITEM_HEADER, color="#ffb86c")
        if bam:
            for e in bam:
                ts = e["time"].strftime("%d.%m %H:%M")
                fp = e["full_path"]
                disp = fp if len(fp) <= 55 else "…" + fp[-54:]
                row(f"  │   [{ts}]   {disp}", ITEM_INFO, color="#ffb86c")
        else:
            row("  │   nothing suspicious found in BAM", ITEM_INFO, color="#3a4a66")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#ffb86c")
        row("", ITEM_INFO)

        # ── Prefetch ─────────────────────────────────────────────────────────
        row(f"  ┌─ PREFETCH — LAST RUN (suspicious)  {ln[:34]}", ITEM_HEADER, color="#ff79c6")
        if prefetch:
            for e in prefetch:
                ts = e["time"].strftime("%d.%m %H:%M")
                row(f"  │   [{ts}]   {e['name']}", ITEM_INFO, color="#ff79c6")
        else:
            row("  │   nothing suspicious found in Prefetch", ITEM_INFO, color="#3a4a66")
        row(f"  └{ln[:70]}", ITEM_INFO, color="#ff79c6")

    def _on_result_click(self, item):
        from ui.cmd_window import restore_file, ITEM_FILE
        kind, data = item.data(Qt.ItemDataRole.UserRole)
        if kind != ITEM_FILE or data is None:
            return
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        if restore_file(data):
            item.setText(item.text() + "   ✓")
            item.setForeground(QColor("#50fa7b"))
        else:
            item.setText(item.text() + "   ✗")
            item.setForeground(QColor("#ff5555"))

    # ── Particles ─────────────────────────────────────────────────────────────

    def _tick_particles(self):
        now = time.perf_counter()
        dt  = min(now - self._last_part_t, 0.05)   # cap при просадке FPS
        self._last_part_t = now
        W, H = self.W, self.H

        for i, pt in enumerate(self._particles):
            # Jitter: gaussian nudge масштабируется по dt
            pt['vx'] += random.gauss(0, 4) * dt
            pt['vy'] += random.gauss(0, 4) * dt
            # Soft speed cap
            spd = math.sqrt(pt['vx'] ** 2 + pt['vy'] ** 2)
            if spd > 35:
                pt['vx'] = pt['vx'] / spd * 35
                pt['vy'] = pt['vy'] / spd * 35
            # Move
            pt['x'] = (pt['x'] + pt['vx'] * dt) % W
            pt['y'] = (pt['y'] + pt['vy'] * dt) % H
            # Age — respawn when life ends
            pt['life'] += dt
            if pt['life'] >= pt['max_life']:
                self._particles[i] = _spawn_particle(W, H, fresh=True)

        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.H)
        grad.setColorAt(0.0, QColor(C_BG_TOP))
        grad.setColorAt(1.0, QColor(C_BG_BOT))
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.W, self.H, RADIUS, RADIUS)
        p.fillPath(path, QBrush(grad))

        shimmer = QLinearGradient(0, 0, 0, 60)
        shimmer.setColorAt(0.0, QColor(255, 255, 255, 8))
        shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, QBrush(shimmer))

        # Particles: clip to rounded rect, fade by lifetime
        p.setClipPath(path)
        CONNECT = 95
        CONNECT_SQ = CONNECT * CONNECT
        pts = self._particles
        accent   = QColor(C_ACCENT)
        accent_b = QColor(C_ACCENT_B)

        # Connections — используем d² до sqrt только при совпадении
        for i in range(len(pts)):
            ax, ay   = pts[i]['x'], pts[i]['y']
            fade_a   = math.sin(pts[i]['life'] / pts[i]['max_life'] * math.pi)
            for j in range(i + 1, len(pts)):
                dx = ax - pts[j]['x']
                dy = ay - pts[j]['y']
                d_sq = dx * dx + dy * dy
                if d_sq < CONNECT_SQ:
                    d      = math.sqrt(d_sq)
                    fade_b = math.sin(pts[j]['life'] / pts[j]['max_life'] * math.pi)
                    alpha  = int(28 * (1 - d / CONNECT) * min(fade_a, fade_b))
                    if alpha < 2:
                        continue
                    col = QColor(accent)
                    col.setAlpha(alpha)
                    p.setPen(QPen(col, 0.8))
                    p.drawLine(int(ax), int(ay), int(pts[j]['x']), int(pts[j]['y']))

        # Dots — fade in/out по синусу жизни
        p.setPen(Qt.PenStyle.NoPen)
        for pt in pts:
            fade  = math.sin(pt['life'] / pt['max_life'] * math.pi)
            alpha = int(pt['base_a'] * fade)
            if alpha < 2:
                continue
            col = QColor(accent_b)
            col.setAlpha(alpha)
            p.setBrush(QBrush(col))
            r = pt['r']
            p.drawEllipse(QRectF(pt['x'] - r, pt['y'] - r, r * 2, r * 2))

        p.setClipping(False)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _e):
        self._drag_pos = None

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
        up = orig + QPoint(0, -28)
        self.move(up)
        self.setWindowOpacity(0.0)

        a_pos = QPropertyAnimation(self, b"pos", self)
        a_pos.setDuration(650)
        a_pos.setStartValue(up)
        a_pos.setEndValue(orig)
        a_pos.setEasingCurve(QEasingCurve.Type.OutCubic)

        a_opa = self._prop(self, b"windowOpacity", 0.0, 1.0, 550)

        g = QParallelAnimationGroup(self)
        g.addAnimation(a_pos)
        g.addAnimation(a_opa)
        g.start()
        self._refs = [g]
        QTimer.singleShot(380, self._intro_title)

    def _intro_title(self):
        a = self._prop(self._title_eff, b"opacity", 0.0, 1.0, 480,
                       QEasingCurve.Type.OutCubic)
        a.start()
        self._refs.append(a)
        QTimer.singleShot(320, self._intro_btn)

    def _intro_btn(self):
        # Opacity: OutCubic 0→1
        a_opa = self._prop(self._btn_eff, b"opacity", 0.0, 1.0, 440,
                           QEasingCurve.Type.OutCubic)
        a_opa.finished.connect(self._check_btn.start_glow)

        # Scale: OutBack 0.75→1.0 → лёгкий bounce при появлении
        # QVariantAnimation анимирует float и передаёт в set_appear_s()
        a_scl = QVariantAnimation(self)
        a_scl.setStartValue(0.75)
        a_scl.setEndValue(1.0)
        a_scl.setDuration(560)
        a_scl.setEasingCurve(QEasingCurve.Type.OutBack)
        a_scl.valueChanged.connect(self._check_btn.set_appear_s)

        g = QParallelAnimationGroup(self)
        g.addAnimation(a_opa)
        g.addAnimation(a_scl)
        g.start()
        self._refs.append(g)

    def _fade_close(self):
        a = self._prop(self, b"windowOpacity", 1.0, 0.0, 420,
                       QEasingCurve.Type.InCubic)
        a.finished.connect(lambda: sys.exit(0))
        a.start()
        self._close_anim = a

    # ── Logic ─────────────────────────────────────────────────────────────────

    # ── Browser detection ─────────────────────────────────────────────────────

    @staticmethod
    def _find_browsers() -> dict[str, str]:
        """Возвращает {name: exe_path} для установленных браузеров."""
        local = os.environ.get("LOCALAPPDATA", "")
        prog  = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        prog86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        user  = os.environ.get("USERPROFILE", "")

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

    @staticmethod
    def _browser_urls(name: str) -> tuple[str, str]:
        """Возвращает (history_url, passwords_url) для браузера."""
        schemes = {
            "chrome":  ("chrome://history",       "chrome://settings/passwords"),
            "edge":    ("edge://history",          "edge://settings/passwords"),
            "brave":   ("brave://history",         "brave://settings/passwords"),
            "opera":   ("opera://history",         "opera://settings/passwords"),
            "firefox": ("about:history",           "about:logins"),
            "yandex":  ("browser://history",       "browser://passwords"),
        }
        return schemes.get(name, ("about:blank", "about:blank"))

    @staticmethod
    def _usb_history() -> list[str]:
        """Читает из реестра список USB-накопителей, подключавшихся к ПК."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Enum\USBSTOR"
            )
            devices = []
            i = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(key, i)
                    i += 1
                    # Имя вида "Disk&Ven_SanDisk&Prod_Ultra&Rev_1.00"
                    parts = sub_name.split("&")
                    vendor  = next((p[4:] for p in parts if p.startswith("Ven_")),  "")
                    product = next((p[5:] for p in parts if p.startswith("Prod_")), "")
                    if vendor or product:
                        devices.append(f"{vendor} {product}".strip())
                except OSError:
                    break
            winreg.CloseKey(key)
            return devices
        except Exception:
            return []

    # ── Check logic ───────────────────────────────────────────────────────────

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
            # Папки
            (55, f"__folder__{local}"),
            (65, f"__folder__{os.path.join(appdata, 'Microsoft', 'Windows', 'Recent')}"),
            (72, "__folder__C:\\"),
        ]

        # Браузеры: сохранить список путей в txt и открыть блокнотом
        browsers = self._find_browsers()
        if browsers:
            tmp_br = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "razecheck_browsers.txt")
            try:
                with open(tmp_br, "w", encoding="utf-8") as f:
                    f.write("Браузеры, установленные на ПК:\n\n")
                    for name, exe in browsers.items():
                        f.write(f"  {name.capitalize():<12} {exe}\n")
                self._actions.append((35, f"__shell__notepad \"{tmp_br}\""))
            except Exception:
                pass


        self._actions.sort(key=lambda x: x[0])
        self._action_idx = 0

        self._prog_timer = QTimer(self)
        self._prog_timer.setInterval(18)
        self._prog_timer.timeout.connect(self._tick_progress)
        self._prog_timer.start()

    def _tick_progress(self):
        self._progress = min(self._progress + 2, 100)
        self._ring.set_value(self._progress)

        # Запускаем все действия чей порог пройден
        while (self._action_idx < len(self._actions) and
               self._actions[self._action_idx][0] <= self._progress):
            _, target = self._actions[self._action_idx]
            self._action_idx += 1
            try:
                if target.startswith("__folder__"):
                    subprocess.Popen(["explorer", target[len("__folder__"):]])
                elif target.startswith("__uri__"):
                    os.startfile(target[len("__uri__"):])
                elif target.startswith("__browser__"):
                    # __browser__<exe>||<url>
                    parts = target[len("__browser__"):].split("||", 1)
                    if len(parts) == 2:
                        subprocess.Popen([parts[0], parts[1]])
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
                                   get_bam_entries, get_prefetch_entries)
        usb      = get_recent_usb(hours=10)
        files    = get_recycle_files()
        shadow   = get_shadow_deleted_files()
        bam      = get_bam_entries()
        prefetch = get_prefetch_entries()
        self._fill_results(usb, files, shadow, bam, prefetch)

        # Плавно скрыть центральный контент
        a_hide = QPropertyAnimation(self._btn_eff,   b"opacity", self)
        a_hide.setDuration(220); a_hide.setStartValue(1.0); a_hide.setEndValue(0.0)
        a_hide2 = QPropertyAnimation(self._title_eff, b"opacity", self)
        a_hide2.setDuration(220); a_hide2.setStartValue(1.0); a_hide2.setEndValue(0.0)
        grp = QParallelAnimationGroup(self)
        grp.addAnimation(a_hide); grp.addAnimation(a_hide2)

        def _swap():
            self._main_content.setVisible(False)
            self._result_panel.setVisible(True)
            # Растянуть окно чтобы вместить список
            self.resize(self.W, 480)
            a_show = QPropertyAnimation(self._result_eff, b"opacity", self)
            a_show.setDuration(280); a_show.setStartValue(0.0); a_show.setEndValue(1.0)
            a_show.start(); self._res_anim = a_show

        grp.finished.connect(_swap)
        grp.start(); self._hide_grp = grp


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_close_btn():
    from PyQt6.QtWidgets import QPushButton
    btn = QPushButton("✕")
    btn.setFixedSize(26, 26)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(
        "QPushButton{background:transparent;color:#3d4f70;"
        "border:none;font-size:13px;border-radius:13px;}"
        "QPushButton:hover{background:rgba(255,77,77,.15);color:#ff5555;}"
    )
    return btn
