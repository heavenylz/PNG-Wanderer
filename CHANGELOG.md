# v0.4.0-beta.1

- Independent GIF pause, monitor selection, optional Windows sign-in startup, fullscreen quiet mode and local companion groups.
- Packaged EXE smoke check and regression coverage for new preferences and behavior.

# v0.3.0-beta.2

- Restyle Settings as a native desktop utility with a companion list, grouped controls, plain labels and automatic-save guidance. Follow system colors and preserve keyboard focus indicators.

# v0.3.0-beta.1

- Add animated GIF companions using independent QMovie playback and per-frame transparency masks.
- Preserve static PNG rendering, movement modes/speed, dragging, click-through and settings compatibility.
- Release movie file handles on replacement/removal/shutdown.
- Add offscreen GUI regression tests and test dependency setup in Windows CI.

# Changelog

## 0.2.0-beta.1 — 2026-11-05

- Introduced multi-companion manager (up to 12 PNGs).
- Added three no-sprite-animation motion modes: Wander, Bounce, and Follow cursor.
- Added a dark settings dialog and a recovery-friendly system tray menu.
- Added adjustable image size, movement speed, and per-companion pause and click-through.
- Added atomic settings saving and migration from v0.1.
- Added pure-Python geometry/settings tests and a Windows GitHub Actions release pipeline.

## 0.1.0

- First prototype: one transparent PNG moving around your desktop.
