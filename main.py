"""PNG Wanderer: static PNG and animated GIF desktop companions."""

from __future__ import annotations

import math
import random
import sys
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QPoint, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QIcon, QMouseEvent, QMovie, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QInputDialog, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
    QMessageBox, QPushButton, QSlider, QSystemTrayIcon, QVBoxLayout,
    QWidget,
)

from windows_integration import startup_enabled, set_startup, foreground_fullscreen, native_monitors
from motion import Rect, bounced_step, closest_visible, fully_visible
from settings import DEFAULT_SIZE, DEFAULT_SPEED, MODES, VERSION, normalize_companion, read_config, write_config

APP_NAME = "PNG Wanderer"
MAX_COMPANIONS = 12


def config_path() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(base) / "settings.json"


def app_icon() -> QIcon:
    """A built-in icon, independent of any user-provided PNG."""
    icon_path = Path(__file__).resolve().parent / "assets" / "app.ico"
    if icon_path.exists():
        return QIcon(str(icon_path))
    canvas = QPixmap(64, 64)
    canvas.fill(QColor("#292239"))
    painter = QPainter(canvas)
    painter.setPen(QColor("#e8dcff"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(43)
    painter.setFont(font)
    painter.drawText(canvas.rect(), Qt.AlignmentFlag.AlignCenter, "W")
    painter.end()
    return QIcon(canvas)


def image_ok(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix == ".gif":
        movie = QMovie(path)
        return movie.isValid() and movie.jumpToFrame(0)
    return suffix == ".png" and not QPixmap(path).isNull()


def display_rectangles() -> list[Rect]:
    return [Rect(g.x(), g.y(), g.width(), g.height()) for s in QApplication.screens() if (g := s.geometry()).isValid()]


def pick_image(parent: QWidget | None = None, directory: str = "") -> str:
    path, _ = QFileDialog.getOpenFileName(
        parent, "Choose a PNG or animated GIF", directory or str(Path.home()), "Companion images (*.png *.gif)"
    )
    return path


class Companion(QWidget):
    """One frameless companion window, with a real input-pass-through mode."""

    def __init__(self, manager: "Manager", config: dict) -> None:
        super().__init__()
        self.manager = manager
        self.data = config.copy()
        self.movie: QMovie | None = None
        self.original = QPixmap(self.data["png_path"])
        self.picture = QPixmap()
        self.dragging = False
        self.drag_offset = QPoint()
        self.xf = 0.0
        self.yf = 0.0
        theta = random.uniform(0, math.tau)
        self.dx, self.dy = math.cos(theta), math.sin(theta)
        self.next_turn = time.monotonic() + random.uniform(4.0, 9.0)
        self.last_time = time.monotonic()

        self.setWindowTitle(f"{APP_NAME} — {Path(self.data['png_path']).name}")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self.load_art(self.data["png_path"])
        self.resize_png(keep_center=False)
        pos = self.data.get("position")
        if pos:
            self.move(round(pos[0]), round(pos[1]))
        else:
            self.center_at_cursor()
        self.recover_position()

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.set_click_through(self.data["click_through"], save=False)

    def stop_movie(self) -> None:
        if self.movie is not None:
            self.movie.stop()
            self.movie.setFileName("")  # Release the source file immediately on Windows.
            self.movie.frameChanged.disconnect(self.movie_frame)
            self.movie.deleteLater()
            self.movie = None

    def load_art(self, path: str) -> None:
        self.stop_movie()
        if Path(path).suffix.lower() == ".gif":
            self.movie = QMovie(path, parent=self)
            # Stream frames rather than caching entire large GIFs in memory.
            self.movie.jumpToFrame(0)
            self.original = self.movie.currentPixmap()
            self.movie.frameChanged.connect(self.movie_frame)
            self.movie.start()
            self.movie.setPaused(self.data.get("animation_paused", False))
        else:
            self.original = QPixmap(path)

    def movie_frame(self, _frame: int) -> None:
        if self.movie is not None:
            self.original = self.movie.currentPixmap()
            if not self.original.isNull():
                self.resize_png(keep_center=False)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self.stop_movie()
        super().closeEvent(event)

    def allowed_rectangles(self):
        name = self.data.get("monitor", "")
        screen = next((s for s in QApplication.screens() if s.name() == name), None)
        if name and screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return display_rectangles()
        g = screen.geometry()
        return [Rect(g.x(), g.y(), g.width(), g.height())]

    def sync_coordinates(self) -> None:
        self.xf, self.yf = float(self.x()), float(self.y())

    def resize_png(self, keep_center: bool = True) -> None:
        old_center = self.geometry().center() if keep_center else None
        screens = self.allowed_rectangles()
        largest_fit = max((min(s.width, s.height) for s in screens), default=self.data["size"])
        size = max(32, min(self.data["size"], largest_fit))
        target = self.original.size().scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio
        )
        self.picture = self.original.scaled(
            target, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setFixedSize(self.picture.size())
        # Restrict input to nontransparent pixels; preserves interactions below
        # transparent portions of PNG images in normal (non-click-through) mode.
        self.setMask(QRegion(self.picture.mask()))
        if old_center is not None:
            self.move(old_center.x() - self.width() // 2, old_center.y() - self.height() // 2)
            self.recover_position()
        self.update()

    def center_at_cursor(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is not None:
            c = screen.geometry().center()
            self.move(c.x() - self.width() // 2, c.y() - self.height() // 2)
            self.recover_position()
            self.manager.queue_save()

    def recover_position(self) -> None:
        x, y = closest_visible(self.x(), self.y(), self.width(), self.height(), self.allowed_rectangles())
        self.move(x, y)
        self.sync_coordinates()

    def update_setting(self, key: str, value: object) -> None:
        if self.data.get(key) == value:
            return
        self.data[key] = value
        if key == "size":
            self.resize_png()
        elif key == "animation_paused" and self.movie is not None:
            self.movie.setPaused(bool(value))
        elif key == "monitor":
            self.resize_png()
            self.recover_position()
        elif key == "click_through":
            self.set_click_through(bool(value), save=False)
        self.manager.queue_save()
        if key != "size" and key != "speed":
            self.manager.refresh_settings()

    def set_click_through(self, value: bool, save: bool = True) -> None:
        # Users must retain a way to undo this setting through the system tray.
        value = bool(value) and self.manager.tray_available
        self.data["click_through"] = value
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, value)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, value)
        self.setVisible(not getattr(self.manager, "quiet_hidden", False))
        self.sync_coordinates()
        if save:
            self.manager.queue_save()
            self.manager.refresh_settings()

    def change_image(self, path: str) -> None:
        if not image_ok(path):
            return
        self.load_art(path)
        self.data["png_path"] = path
        self.setWindowTitle(f"{APP_NAME} — {Path(path).name}")
        self.resize_png()
        self.manager.queue_save()
        self.manager.refresh_settings()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, self.picture)
        painter.end()

    def contextMenuEvent(self, event) -> None:
        self.manager.tray_menu.exec(event.globalPos())
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_offset = event.globalPosition().toPoint() - self.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            self.sync_coordinates()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.dragging and event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.recover_position()
            self.manager.queue_save()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def snapshot(self) -> dict:
        result = self.data.copy()
        result["position"] = [self.x(), self.y()]
        return result

    def tick(self) -> None:
        now = time.monotonic()
        dt = min(max(now - self.last_time, 0.0), 0.05)
        self.last_time = now
        if self.dragging or self.data["paused"] or dt == 0:
            return
        screens = self.allowed_rectangles()
        if not screens:
            return
        speed = self.data["speed"]
        mode = self.data["mode"]
        if mode == "Follow cursor":
            mouse = QCursor.pos()
            # Keep a small gap rather than sitting directly under the pointer.
            cx, cy = self.xf + self.width() / 2, self.yf + self.height() / 2
            vx, vy = mouse.x() - cx, mouse.y() - cy
            distance = math.hypot(vx, vy)
            if distance < 85:
                return
            step = min(speed * dt, distance - 85)
            nx, ny = self.xf + vx / distance * step, self.yf + vy / distance * step
            if not fully_visible(nx, ny, self.width(), self.height(), screens):
                return
        else:
            if mode == "Wander" and now >= self.next_turn:
                theta = math.atan2(self.dy, self.dx) + random.uniform(-0.85, 0.85)
                self.dx, self.dy = math.cos(theta), math.sin(theta)
                self.next_turn = now + random.uniform(4.0, 9.0)
            nx, ny, self.dx, self.dy = bounced_step(
                self.xf, self.yf, self.dx, self.dy, speed, dt,
                self.width(), self.height(), screens,
            )
        self.xf, self.yf = nx, ny
        dest = QPoint(round(nx), round(ny))
        if dest != self.pos():
            self.move(dest)


class SettingsDialog(QDialog):
    """Compact settings window; the tray remains the escape hatch for click-through."""

    def __init__(self, manager: "Manager") -> None:
        super().__init__()
        self.manager = manager
        self.updating = False
        self.setWindowTitle(f"{APP_NAME} — Settings")
        self.setWindowIcon(app_icon())
        self.resize(760, 650)
        self.setMinimumSize(700, 620)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(16)
        head = QLabel("Your companions")
        font = head.font()
        font.setPointSize(15)
        font.setBold(True)
        head.setFont(font)
        outer.addWidget(head)

        columns = QHBoxLayout()
        columns.setSpacing(20)
        outer.addLayout(columns, 1)
        library = QVBoxLayout()
        library.setSpacing(8)
        columns.addLayout(library, 1)
        self.count_label = QLabel()
        library.addWidget(self.count_label)
        self.listing = QListWidget()
        self.listing.setMinimumWidth(230)
        self.listing.setSpacing(3)
        self.listing.currentItemChanged.connect(self.load_selected)
        library.addWidget(self.listing, 1)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add…")
        self.add_button.setToolTip("Choose a PNG or GIF from your computer")
        self.add_button.clicked.connect(lambda: self.manager.add_image(self))
        self.replace_button = QPushButton("Change…")
        self.replace_button.clicked.connect(self.replace_selected)
        self.delete_button = QPushButton("Remove")
        self.delete_button.clicked.connect(self.remove_selected)
        for button in (self.add_button, self.replace_button, self.delete_button):
            button.setAutoDefault(False)
            buttons.addWidget(button)
        library.addLayout(buttons)
        self.empty_hint = QLabel("Add a PNG or GIF to get started.")
        self.empty_hint.setWordWrap(True)
        library.addWidget(self.empty_hint)

        details = QVBoxLayout()
        details.setSpacing(14)
        columns.addLayout(details, 1)
        self.selection_label = QLabel("Select a companion")
        font = self.selection_label.font()
        font.setBold(True)
        self.selection_label.setFont(font)
        self.selection_label.setWordWrap(True)
        details.addWidget(self.selection_label)
        movement = QGroupBox("Movement")
        form = QFormLayout(movement)
        form.setContentsMargins(12, 18, 12, 12)
        form.setVerticalSpacing(14)
        self.mode = QComboBox()
        self.mode.addItems(MODES)
        self.mode.currentTextChanged.connect(lambda s: self.change("mode", s))
        form.addRow("Style", self.mode)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(10, 300)
        self.speed_slider.setSingleStep(5)
        self.speed_slider.setAccessibleName("Movement speed")
        self.speed_slider.valueChanged.connect(lambda v: self.change("speed", v))
        self.speed_label = QLabel()
        form.addRow("Speed", self._slider_row(self.speed_slider, self.speed_label))
        self.pause = QCheckBox("Pause movement")
        self.pause.toggled.connect(lambda v: self.change("paused", v))
        form.addRow(self.pause)
        details.addWidget(movement)

        appearance = QGroupBox("On your desktop")
        form = QFormLayout(appearance)
        form.setContentsMargins(12, 18, 12, 12)
        form.setVerticalSpacing(14)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(48, 512)
        self.size_slider.setSingleStep(8)
        self.size_slider.setAccessibleName("Companion size")
        self.size_slider.valueChanged.connect(lambda v: self.change("size", v))
        self.size_label = QLabel()
        form.addRow("Size", self._slider_row(self.size_slider, self.size_label))
        self.click_through = QCheckBox("Let clicks pass through")
        self.click_through.setToolTip("Turn this off from Settings or the system tray. Requires a system tray.")
        self.click_through.toggled.connect(lambda v: self.change("click_through", v))
        form.addRow(self.click_through)
        self.animation_pause = QCheckBox("Pause GIF animation")
        self.animation_pause.toggled.connect(lambda v: self.change("animation_paused", v))
        form.addRow(self.animation_pause)
        self.monitor = QComboBox()
        self.monitor.currentIndexChanged.connect(lambda _: self.change("monitor", self.monitor.currentData() or ""))
        form.addRow("Monitor", self.monitor)
        details.addWidget(appearance)
        details.addStretch(1)

        app_options = QHBoxLayout()
        self.startup = QCheckBox("Start with Windows")
        self.startup.setChecked(startup_enabled())
        self.startup.toggled.connect(self.toggle_startup)
        app_options.addWidget(self.startup)
        self.quiet = QCheckBox("Hide during fullscreen apps")
        self.quiet.setChecked(manager.quiet_enabled)
        self.quiet.toggled.connect(manager.set_quiet)
        app_options.addWidget(self.quiet)
        outer.addLayout(app_options)
        presets = QHBoxLayout()
        save_preset = QPushButton("Save group…")
        save_preset.clicked.connect(manager.save_preset)
        load_preset = QPushButton("Load group…")
        load_preset.clicked.connect(manager.load_preset)
        presets.addWidget(save_preset)
        presets.addWidget(load_preset)
        presets.addStretch()
        outer.addLayout(presets)
        footer = QHBoxLayout()
        note = QLabel("Drag to reposition. Right-click for options.\nChanges are saved automatically.")
        font = note.font()
        font.setPointSize(max(8, font.pointSize() - 1))
        note.setFont(font)
        footer.addWidget(note, 1)
        done = QPushButton("Done")
        done.setDefault(True)
        done.clicked.connect(self.hide)
        footer.addWidget(done)
        outer.addLayout(footer)
        # Keep native controls, focus indicators and the system color palette.
        self.refresh()

    def toggle_startup(self, enabled):
        try:
            set_startup(enabled)
        except OSError as error:
            self.startup.blockSignals(True)
            self.startup.setChecked(startup_enabled())
            self.startup.blockSignals(False)
            QMessageBox.warning(self, APP_NAME, str(error))

    @staticmethod
    def _slider_row(slider: QSlider, label: QLabel) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(slider, 1)
        label.setMinimumWidth(78)
        layout.addWidget(label)
        return row

    def selected(self) -> Companion | None:
        item = self.listing.currentItem()
        if not item:
            return None
        return self.manager.companions.get(item.data(Qt.ItemDataRole.UserRole))

    def refresh(self) -> None:
        key = self.selected().data["id"] if self.selected() else None
        self.updating = True
        self.listing.clear()
        for n, companion in enumerate(self.manager.companions.values(), 1):
            item = QListWidgetItem(Path(companion.data["png_path"]).name)
            item.setToolTip(companion.data["png_path"])
            item.setData(Qt.ItemDataRole.UserRole, companion.data["id"])
            self.listing.addItem(item)
        if self.listing.count():
            idx = next((i for i in range(self.listing.count()) if self.listing.item(i).data(Qt.ItemDataRole.UserRole) == key), 0)
            self.listing.setCurrentRow(idx)
        self.updating = False
        self.load_selected()
        count = len(self.manager.companions)
        self.count_label.setText(f"Companions ({count} of {MAX_COMPANIONS})")
        self.empty_hint.setVisible(count == 0)
        self.add_button.setEnabled(count < MAX_COMPANIONS)

    def load_selected(self, *args) -> None:
        if self.updating:
            return
        self.updating = True
        c = self.selected()
        for widget in (self.replace_button, self.delete_button, self.mode, self.size_slider,
                       self.speed_slider, self.pause, self.click_through, self.animation_pause, self.monitor):
            widget.setEnabled(c is not None)
        self.selection_label.setText(Path(c.data["png_path"]).name if c else "Select a companion")
        self.monitor.clear()
        self.monitor.addItem("All monitors", "")
        for screen in QApplication.screens():
            self.monitor.addItem(screen.name(), screen.name())
        if c is not None:
            d = c.data
            name = d.get("monitor", "")
            if name and self.monitor.findData(name) < 0:
                self.monitor.addItem(name + " (disconnected)", name)
            self.monitor.setCurrentIndex(max(0, self.monitor.findData(name)))
            self.animation_pause.setChecked(d.get("animation_paused", False))
            self.animation_pause.setEnabled(c.movie is not None)
            self.mode.setCurrentText(d["mode"])
            self.size_slider.setValue(d["size"])
            self.speed_slider.setValue(d["speed"])
            self.pause.setChecked(d["paused"])
            self.click_through.setChecked(d["click_through"])
            self.click_through.setEnabled(self.manager.tray_available)
            self.size_label.setText(f"{d['size']} px")
            self.speed_label.setText(f"{d['speed']} px/s")
        else:
            self.size_label.setText("—")
            self.speed_label.setText("—")
        self.updating = False

    def change(self, key: str, value: object) -> None:
        if self.updating:
            return
        c = self.selected()
        if c is None:
            return
        c.update_setting(key, value)
        if key == "size":
            self.size_label.setText(f"{value} px")
        elif key == "speed":
            self.speed_label.setText(f"{value} px/s")

    def replace_selected(self) -> None:
        c = self.selected()
        if c is None:
            return
        path = pick_image(self, str(Path(c.data["png_path"]).parent))
        if path:
            if not image_ok(path):
                QMessageBox.warning(self, APP_NAME, "Couldn't read that PNG or GIF.")
            else:
                c.change_image(path)

    def remove_selected(self) -> None:
        c = self.selected()
        if c:
            self.manager.remove(c.data["id"])


class Manager:
    def __init__(self, initial_path: str | None = None) -> None:
        self.companions: dict[str, Companion] = {}
        self.quiet_enabled = False
        self.quiet_hidden = False
        self.presets = {}
        self.loading_group = False
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(self.populate_tray_menu)
        self.tray: QSystemTrayIcon | None = None
        self.settings_dialog: SettingsDialog | None = None
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        self.app = QApplication.instance()
        self.app.aboutToQuit.connect(self.shutdown)
        self.app.screenAdded.connect(self.screen_changed)
        self.app.screenRemoved.connect(self.screen_changed)
        for screen in self.app.screens():
            screen.geometryChanged.connect(self.screen_changed)

        if self.tray_available:
            self.tray = QSystemTrayIcon(app_icon())
            self.tray.setToolTip(APP_NAME)
            self.tray.setContextMenu(self.tray_menu)
            self.tray.activated.connect(self.tray_activated)
            self.tray.show()

        self.load_preferences()
        self.quiet_timer = QTimer()
        self.quiet_timer.timeout.connect(self.check_quiet)
        self.quiet_timer.start(750)
        stored = read_config(config_path())
        for config in stored["companions"]:
            if image_ok(config["png_path"]):
                self.create(config)
        if initial_path is not None:
            if image_ok(initial_path):
                self.create(normalize_companion({"png_path": initial_path}))
            else:
                QMessageBox.warning(None, APP_NAME, "The supplied image couldn't be opened.")
        if not self.companions:
            QTimer.singleShot(0, self.first_run)

    def screen_changed(self, *args) -> None:
        for screen in self.app.screens():
            try:
                screen.geometryChanged.disconnect(self.screen_changed)
            except (RuntimeError, TypeError):
                pass
            screen.geometryChanged.connect(self.screen_changed)
        for c in self.companions.values():
            c.resize_png()
            c.recover_position()
        self.refresh_settings()
        self.queue_save()

    def first_run(self) -> None:
        if not self.add_image():
            if not self.companions:
                self.app.quit()

    def create(self, config: dict) -> None:
        if len(self.companions) >= MAX_COMPANIONS:
            return
        c = Companion(self, config)
        self.companions[c.data["id"]] = c
        c.setVisible(not self.quiet_hidden)
        self.queue_save()
        self.refresh_settings()

    def add_image(self, parent: QWidget | None = None) -> bool:
        if len(self.companions) >= MAX_COMPANIONS:
            QMessageBox.information(parent, APP_NAME, f"The limit is {MAX_COMPANIONS} companions.")
            return False
        path = pick_image(parent)
        if not path:
            return False
        if not image_ok(path):
            QMessageBox.warning(parent, APP_NAME, "Couldn't read that PNG or GIF. Please choose a valid file.")
            return False
        self.create(normalize_companion({"png_path": path, "id": uuid.uuid4().hex}))
        return True

    def remove(self, uid: str) -> None:
        c = self.companions.pop(uid, None)
        if c is not None:
            c.timer.stop()
            c.close()
            c.deleteLater()
            self.queue_save()
            self.refresh_settings()
        if not self.companions and not self.tray_available and not self.loading_group:
            self.app.quit()

    def preference_path(self):
        return config_path().with_name("preferences.json")

    def load_preferences(self):
        import json
        try:
            raw = json.loads(self.preference_path().read_text(encoding="utf-8"))
            if not isinstance(raw, dict): return
            self.quiet_enabled = raw.get("quiet") is True
            if isinstance(raw.get("presets"), dict):
                self.presets = {k: v for k, v in raw["presets"].items() if isinstance(k, str) and isinstance(v, list)}
        except (OSError, ValueError):
            pass

    def save_preferences(self):
        import json
        p = self.preference_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"quiet": self.quiet_enabled, "presets": self.presets}, indent=2), encoding="utf-8")
        tmp.replace(p)

    def set_quiet(self, value):
        self.quiet_enabled = value
        try: self.save_preferences()
        except OSError as error: QMessageBox.warning(self.settings_dialog, APP_NAME, str(error))
        self.check_quiet()

    def check_quiet(self):
        hidden = self.quiet_enabled and foreground_fullscreen(native_monitors())
        if hidden != self.quiet_hidden:
            self.quiet_hidden = hidden
            for c in self.companions.values(): c.setVisible(not hidden)

    def save_preset(self):
        name, ok = QInputDialog.getText(self.settings_dialog, "Save companion group", "Group name:")
        name = name.strip()
        if not ok or not name: return
        if name in self.presets and QMessageBox.question(self.settings_dialog, APP_NAME, "Replace this saved group?") != QMessageBox.StandardButton.Yes: return
        self.presets[name] = [c.snapshot() for c in self.companions.values()]
        try: self.save_preferences()
        except OSError as error: QMessageBox.warning(self.settings_dialog, APP_NAME, str(error))

    def load_preset(self):
        if not self.presets:
            QMessageBox.information(self.settings_dialog, APP_NAME, "Save a group first.")
            return
        name, ok = QInputDialog.getItem(self.settings_dialog, "Load companion group", "Group:", sorted(self.presets), 0, False)
        if not ok: return
        configs = [normalize_companion(c) for c in self.presets[name][:MAX_COMPANIONS]]
        valid = [c for c in configs if c is not None and image_ok(c["png_path"])]
        if not valid:
            QMessageBox.warning(self.settings_dialog, APP_NAME, "No images in this group could be opened. Your current companions are unchanged.")
            return
        if QMessageBox.question(self.settings_dialog, APP_NAME, "Replace the current companions with this group?") != QMessageBox.StandardButton.Yes: return
        self.loading_group = True
        try:
            for uid in list(self.companions): self.remove(uid)
            for config in valid:
                config["id"] = uuid.uuid4().hex
                self.create(config)
        finally: self.loading_group = False
        if len(valid) < len(configs):
            QMessageBox.information(self.settings_dialog, APP_NAME, "Some images were missing and were skipped.")

    def queue_save(self) -> None:
        self.save_timer.start(500)

    def save(self) -> None:
        try:
            write_config(config_path(), {"companions": [c.snapshot() for c in self.companions.values()]})
        except OSError:
            pass  # The app remains usable if user config can't be written.

    def shutdown(self) -> None:
        self.quiet_timer.stop()
        self.save_timer.stop()
        self.save()
        for c in self.companions.values():
            c.timer.stop()
            c.stop_movie()
        if self.tray:
            self.tray.hide()

    def refresh_settings(self) -> None:
        if self.settings_dialog is not None:
            self.settings_dialog.refresh()

    def open_settings(self) -> None:
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def pause_all(self, paused: bool) -> None:
        for c in self.companions.values():
            c.update_setting("paused", paused)

    def populate_tray_menu(self) -> None:
        m = self.tray_menu
        m.clear()
        m.addAction("Open settings…", self.open_settings)
        m.addAction("Add PNG/GIF companion…", lambda: self.add_image())
        m.addSeparator()
        companions = list(self.companions.values())
        if companions:
            all_paused = all(c.data["paused"] for c in companions)
            m.addAction("Resume all" if all_paused else "Pause all", lambda: self.pause_all(not all_paused))
            for c in companions:
                sub = m.addMenu(Path(c.data["png_path"]).name)
                uid = c.data["id"]
                action = sub.addAction("Paused")
                action.setCheckable(True)
                action.setChecked(c.data["paused"])
                action.triggered.connect(lambda checked, item=c: item.update_setting("paused", checked))
                action = sub.addAction("Click-through")
                action.setCheckable(True)
                action.setChecked(c.data["click_through"])
                action.setEnabled(self.tray_available)
                action.triggered.connect(lambda checked, item=c: item.update_setting("click_through", checked))
                sub.addAction("Center on cursor's screen", c.center_at_cursor)
                sub.addAction("Remove", lambda checked=False, value=uid: self.remove(value))
        m.addSeparator()
        m.addAction(f"About PNG Wanderer {VERSION}", self.show_about)
        m.addAction("Quit PNG Wanderer", self.app.quit)

    def show_about(self) -> None:
        QMessageBox.information(
            self.settings_dialog, APP_NAME,
            f"PNG Wanderer {VERSION}\n\nYour own PNGs and animated GIFs.\n"
            "Runs locally; no network requests or image uploads.\n"
            "Right-click the tray icon to manage companions.",
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("VibeCode")  # Preserves v0.1 settings location.
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)  # Tray can recover hidden/click-through PNGs.
    manager = Manager(sys.argv[1] if len(sys.argv) > 1 else None)
    return app.exec()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        from smoke_test import run
        raise SystemExit(run())
    raise SystemExit(main())
