import math
import os
import subprocess
import sys
import webbrowser

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup,
    QPoint, QRectF, QRect,
)
from PyQt6.QtGui import (
    QBrush, QColor, QCursor, QFont,
    QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QAbstractButton, QApplication,
    QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow,
    QVBoxLayout, QWidget,
)

# ── Palette ───────────────────────────────────────────────────────────────────

C_BG      = "#09090E"   # near-black
C_BORDER  = "#16192B"   # subtle dark border
C_ACCENT  = "#4C6EF5"   # indigo
C_TEXT    = "#D4D8E8"   # cool off-white
C_MUTED   = "#353A52"   # muted labels
RADIUS    = 12
TB_H      = 32


# ── Check button (minimal) ────────────────────────────────────────────────────

class _CheckButton(QAbstractButton):
    """Минималистичная плоская кнопка — без свечения, spring-анимации и частиц."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = False
        self._press = False
        self.setFixedSize(188, 46)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def enterEvent(self, e):
        self._hover = True;  self.update()
    def leaveEvent(self, e):
        self._hover = False; self.update()
    def mousePressEvent(self, e):
        self._press = True;  self.update(); super().mousePressEvent(e)
    def mouseReleaseEvent(self, e):
        self._press = False; self.update(); super().mouseReleaseEvent(e)

    # stub-ы для совместимости с местами где вызывается start/stop_glow
    def start_glow(self): pass
    def stop_glow(self):  pass
    def set_appear_s(self, s): pass

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._press:
            border = QColor(76, 110, 245, 210)
            bg     = QColor(76, 110, 245, 25)
            tc     = QColor("#8AAAFA")
        elif self._hover:
            border = QColor(76, 110, 245, 150)
            bg     = QColor(76, 110, 245, 10)
            tc     = QColor("#4C6EF5")
        else:
            border = QColor(255, 255, 255, 18)
            bg     = QColor(0, 0, 0, 0)
            tc     = QColor(212, 216, 232, 120)

        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, w - 1, h - 1, 6, 6)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg))
        p.drawPath(path)

        p.setPen(QPen(border, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        font = QFont("Segoe UI", 10)
        font.setWeight(QFont.Weight.Medium)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
        p.setFont(font)
        p.setPen(tc)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "CHECK")


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
        p.setPen(QPen(QColor("#141620"), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # Progress arc — плавный через _display
        if val > 0:
            color = QColor("#34C759") if done else QColor(C_ACCENT)
            pen = QPen(color, 4)
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
                col = QColor("#34C759")
                col.setAlpha(alpha)
                pen2 = QPen(col, max(1.0, 3.0 * (1 - offset_t)))
                p.setPen(pen2)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - br, cy - br, br * 2, br * 2))

        # Percentage text — счётчик считает плавно
        font = QFont("Segoe UI", 18)
        font.setWeight(QFont.Weight.Light)
        p.setFont(font)
        color = QColor("#34C759") if done else QColor(C_TEXT)
        p.setPen(color)
        text = f"{int(val)}%"
        fm = QFontMetrics(font)
        p.drawText(
            int(cx - fm.horizontalAdvance(text) / 2),
            int(cy + (fm.ascent() - fm.descent()) / 2),
            text,
        )


# ── Scanline overlay ──────────────────────────────────────────────────────────

class _ScanlineOverlay(QWidget):
    """Прозрачный виджет поверх results panel: CRT-линии + скользящая подсветка."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(parent.rect())
        self._phase = 0.0
        self._dir   = 1.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(30)
        self._timer = t

    def _tick(self):
        h = max(self.height(), 1)
        self._phase += self._dir * 1.8
        if self._phase >= h + 40:
            self._phase = -40.0
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()

        # CRT horizontal scanlines (1px на каждые 3px)
        sc = QColor(0, 0, 0, 18)
        p.setPen(QPen(sc, 1))
        y = 0
        while y < h:
            p.drawLine(0, y, w, y)
            y += 3

        # Moving highlight beam
        beam_y = int(self._phase)
        grad = QLinearGradient(0, beam_y - 30, 0, beam_y + 30)
        grad.setColorAt(0.0, QColor(58, 111, 240, 0))
        grad.setColorAt(0.5, QColor(91, 140, 255, 18))
        grad.setColorAt(1.0, QColor(58, 111, 240, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(QRect(0, beam_y - 30, w, 60), QBrush(grad))

        # Corner glow (top-left)
        cg = QRadialGradient(0, 0, 120)
        cg.setColorAt(0, QColor(58, 111, 240, 22))
        cg.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(QRect(0, 0, 120, 90), QBrush(cg))


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

        lbl_name = QLabel("RAZECHECK")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        fn = QFont("Segoe UI"); fn.setPixelSize(17); fn.setWeight(QFont.Weight.Light)
        lbl_name.setFont(fn)
        lbl_name.setStyleSheet(
            f"color:{C_TEXT}; letter-spacing: 8px;"
        )

        lbl_by = QLabel("system integrity check")
        lbl_by.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        fb = QFont("Segoe UI"); fb.setPixelSize(11)
        lbl_by.setFont(fb)
        lbl_by.setStyleSheet(f"color:{C_MUTED}; letter-spacing: 2px;")

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

        self._check_btn = _CheckButton()
        self._check_btn.clicked.connect(self._on_check)

        self._ring = _ProgressRing()
        self._ring.setVisible(False)

        bv.addWidget(self._check_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        bv.addWidget(self._ring,      alignment=Qt.AlignmentFlag.AlignHCenter)

        self._btn_eff = QGraphicsOpacityEffect()
        self._btn_eff.setOpacity(0.0)
        self._btn_w.setGraphicsEffect(self._btn_eff)

        # Discord ссылка внизу
        lbl_ds = QLabel('<a href="https://discord.gg/razeteam" style="color:#4C6EF5;text-decoration:none;letter-spacing:2px;">discord.gg/razeteam</a>')
        lbl_ds.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lbl_ds.setOpenExternalLinks(True)
        lbl_ds.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        fd = QFont("Segoe UI"); fd.setPixelSize(10)
        lbl_ds.setFont(fd)
        lbl_ds.setStyleSheet("background: transparent;")

        cv.addStretch(2)
        cv.addWidget(self._title_w, alignment=Qt.AlignmentFlag.AlignHCenter)
        cv.addSpacing(36)
        cv.addWidget(self._btn_w,   alignment=Qt.AlignmentFlag.AlignHCenter)
        cv.addStretch(3)
        cv.addWidget(lbl_ds, alignment=Qt.AlignmentFlag.AlignHCenter)
        cv.addSpacing(10)

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
                background: rgba(8,10,20,220);
                color: #c8ccd4;
                border: 1px solid #1e3050;
                border-radius: 8px;
                outline: none;
                padding: 8px 10px;
            }
            QListWidget::item { padding: 2px 0; border: none; }
            QListWidget::item:hover { background: rgba(58,111,240,0.08); }
            QListWidget::item:selected {
                background: rgba(58,111,240,0.15);
                color: #e8ecf7;
            }
            QScrollBar:vertical {
                background: transparent; width: 4px; border: none; margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #2a3a55; border-radius: 2px; min-height: 20px;
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

        # Scanline overlay поверх lw — создаётся после layout
        self._scanline: _ScanlineOverlay | None = None

        return panel

    def _attach_scanline(self):
        """Overlay крепится после того как lw получил реальные размеры."""
        if self._scanline is None and self._result_lw.isVisible():
            ov = _ScanlineOverlay(self._result_lw)
            ov.setGeometry(self._result_lw.rect())
            ov.show()
            ov.raise_()
            self._scanline = ov

    def _fill_results(self, usb_devices: list, recycle_files: list,
                      shadow_files: list, bam: list, prefetch: list) -> list:
        """Собирает список QListWidgetItem для typewriter-анимации."""
        from ui.cmd_window import ITEM_HEADER, ITEM_USB, ITEM_FILE, ITEM_INFO
        items: list[QListWidgetItem] = []

        def row(text, kind, data=None, color="#c8ccd4"):
            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            item.setData(Qt.ItemDataRole.UserRole, (kind, data))
            if kind in (ITEM_HEADER, ITEM_INFO, ITEM_USB):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            items.append(item)

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
        row("", ITEM_INFO)

        return items

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

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, self.width() - 1, self.height() - 1, RADIUS, RADIUS)

        # Плоский фон
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.setBrush(QBrush(QColor(C_BG)))
        p.drawPath(path)

        # Еле заметный верхний блик (1px)
        top = QLinearGradient(self.width() * 0.25, 0, self.width() * 0.75, 0)
        top.setColorAt(0.0, QColor(0, 0, 0, 0))
        top.setColorAt(0.5, QColor(76, 110, 245, 22))
        top.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(QRect(0, 0, self.width(), 1), QBrush(top))

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
        a = self._prop(self._btn_eff, b"opacity", 0.0, 1.0, 400,
                       QEasingCurve.Type.OutCubic)
        a.start()
        self._refs.append(a)

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

        # Собираем items заранее (без добавления в lw)
        self._pending_items = self._fill_results(usb, files, shadow, bam, prefetch)
        self._type_idx = 0

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
            self.resize(self.W, 480)

            # Fade-in панели
            a_show = QPropertyAnimation(self._result_eff, b"opacity", self)
            a_show.setDuration(280); a_show.setStartValue(0.0); a_show.setEndValue(1.0)
            a_show.start(); self._res_anim = a_show

            # Прикрепить scanline overlay
            QTimer.singleShot(300, self._attach_scanline)

            # Typewriter: добавляем строки по одной
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
        # Скроллим каждые 4 строки чтобы не лагало
        if self._type_idx % 4 == 0:
            self._result_lw.scrollToBottom()


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
