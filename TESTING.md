# v0.3 GIF regression checks

Install requirements-test.txt and run `python -m unittest discover -s tests -v`.
The image tests use Qt offscreen and generate their fixtures with Pillow (test dependency only).

Manual Windows release gate:
- Add PNG and GIF companions together, up to 12. Confirm independent playback and unchanged static PNGs.
- Try transparent, finite-loop, infinite-loop and single-frame GIFs; check timing, disposal and transparency.
- Resize while playing, switch all three movement modes, adjust travel speed, pause/resume movement and drag. GIF timing must remain unchanged.
- Replace PNG with GIF, GIF with PNG and GIF with GIF repeatedly; remove companions and quit. Source files should be deletable afterward.
- Exercise click-through, recover through tray, restart with saved PNG/GIF paths, and missing/corrupt sources.
- Test monitors with negative coordinates, different scaling, gaps and hot-plugging.
- Build EXE and test on a clean Windows machine without Python, including GIF playback (Qt GIF image plugin must be bundled).

# Windows beta testing checklist

Before publishing a stable release, run `start.bat` or the Windows EXE on a real Windows 10/11 desktop.

- [ ] Launch with a valid PNG and with no settings yet; canceling file picker closes cleanly.
- [ ] PNG is displayed without animation, flipping or distortion.
- [ ] Left-drag and right-click work; clicking transparent parts of the PNG reaches the underlying window.
- [ ] Add two different PNGs, change speed and size separately, replace and remove an image.
- [ ] Check all three motion modes: Wander, Bounce, Follow cursor.
- [ ] Pause an image and Pause all; resume normally.
- [ ] Enable click-through in Settings; interact with apps behind it; use system tray to disable it.
- [ ] Close Settings while in click-through mode; reopen Settings by double-clicking the tray icon.
- [ ] Restart; confirm paths, modes, speeds, click-through and positions persist.
- [ ] Remove or rename an image file and restart; app should skip missing PNG and let you choose again.
- [ ] Test one 1080p display, side-by-side displays, vertically offset displays, and disconnected displays.
- [ ] Check the taskbar/system tray menu and exit cleanly.
- [ ] Test the packaged EXE separately from the Python source folder.
- [ ] Check Windows SmartScreen prompts for unsigned builds (do not advise users to bypass security protections).
- [ ] Verify that GitHub Actions' Windows build job succeeds and the EXE artifact launches.

## Build gate

The project currently has passing **unit tests** for settings and movement geometry, but Windows GUI interactions and the packaged binary are **not yet tested in this environment**. Keep its version a beta until the manual checklist and Actions build pass.
