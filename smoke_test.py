"""Noninteractive packaged smoke check; never reads or changes user settings."""
def run():
    import os, base64, tempfile
    from pathlib import Path
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QMovie
    from main import Companion, SettingsDialog
    from settings import normalize_companion
    app = QApplication.instance() or QApplication([])
    class Stub:
        tray_available = False
        quiet_enabled = False
        quiet_hidden = False
        companions = {}
        def queue_save(self): pass
        def refresh_settings(self): pass
        def add_image(self, *args): pass
        def set_quiet(self, *args): pass
        def save_preset(self): pass
        def load_preset(self): pass
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)/'test.gif'
        p.write_bytes(base64.b64decode('R0lGODlhEAAQAIEAAP8AAAAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQACAAAACwAAAAAEAAQAAAIHQABCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFgQEBACH5BAEIAAEALAAAAAAQABAAgQAA/wAAAAAAAAAAAAgdAAEIHEiwoMGDCBMqXMiwocOHECNKnEixosWBAQEAOw=='))
        manager = Stub()
        c = Companion(manager, normalize_companion({'png_path':str(p), 'paused':True}))
        manager.companions[c.data['id']] = c
        d = SettingsDialog(manager)
        d.show()
        frames = []
        c.movie.frameChanged.connect(frames.append)
        QTimer.singleShot(400, app.quit)
        app.exec()
        ok = 1 in frames and not c.picture.isNull() and d.monitor.count() > 0
        c.close()
        d.close()
        return 0 if ok else 1
