# The same game on 3 systems

| System | Qt platform | Screen | Font used | 10 pt in pixels | Line height |
|---|---|---|---|---|---|
| macos | cocoa | 1920x1080 | Fio UI | 13 | 17 |
| linux-x11 | xcb | 1920x1080 | Fio UI | 13 | 18 |
| linux-wayland | wayland | 1920x1080 | Fio UI | 13 | 18 |

Compared with **macos**:

| System | Text measurements | Window sizes | Widgets in the same place (fixed windows) | Pixels that differ |
|---|---|---|---|---|
| linux-x11 | DIFFERENT | DIFFERENT | 37 of 71 | brain-1: sizes differ, brain-2: sizes differ, brain-3: sizes differ, brain-4: sizes differ, brain-5: sizes differ, brain-6: sizes differ, brain-7: sizes differ, brain-8: sizes differ, journey 15.2%, main 1.4%, menu: sizes differ, message: sizes differ, splash 1.5%, statistics 3.0% |
| linux-wayland | DIFFERENT | DIFFERENT | 37 of 71 | brain-1: sizes differ, brain-2: sizes differ, brain-3: sizes differ, brain-4: sizes differ, brain-5: sizes differ, brain-6: sizes differ, brain-7: sizes differ, brain-8: sizes differ, journey 15.3%, main 1.4%, menu: sizes differ, message: sizes differ, splash 1.5%, statistics 3.3% |

Not the same:

- linux-x11 / message: `{'class': 'QMessageBox', 'name': '', 'x': 0, 'y': 0, 'w': 346, 'h': 133}` on macos, `{'class': 'QMessageBox', 'name': '', 'x': 0, 'y': 0, 'w': 279, 'h': 127}` on linux-x11
- linux-x11 / message: `{'class': 'QLabel', 'name': 'qt_msgboxex_icon_label', 'x': 24, 'y': 15, 'w': 32, 'h': 32}` on macos, `{'class': 'QLabel', 'name': 'qt_msgboxex_icon_label', 'x': 11, 'y': 11, 'w': 32, 'h': 32}` on linux-x11
- linux-x11 / message: `{'class': 'QLabel', 'name': 'qt_msgbox_label', 'x': 70, 'y': 15, 'w': 252, 'h': 18}` on macos, `{'class': 'QLabel', 'name': 'qt_msgbox_label', 'x': 62, 'y': 11, 'w': 206, 'h': 18}` on linux-x11
- linux-x11 / message: `{'class': 'QDialogButtonBox', 'name': 'qt_msgbox_buttonbox', 'x': 70, 'y': 85, 'w': 252, 'h': 28}` on macos, `{'class': 'QDialogButtonBox', 'name': 'qt_msgbox_buttonbox', 'x': 11, 'y': 90, 'w': 257, 'h': 26}` on linux-x11
- linux-x11 / message: `{'class': 'QPushButton', 'name': '', 'x': 70, 'y': 85, 'w': 80, 'h': 28}` on macos, `{'class': 'QPushButton', 'name': '', 'x': 16, 'y': 90, 'w': 80, 'h': 26}` on linux-x11
- linux-x11 / message: `{'class': 'QPushButton', 'name': '', 'x': 156, 'y': 85, 'w': 80, 'h': 28}` on macos, `{'class': 'QPushButton', 'name': '', 'x': 102, 'y': 90, 'w': 80, 'h': 26}` on linux-x11
- linux-x11 / message: `{'class': 'QPushButton', 'name': '', 'x': 242, 'y': 85, 'w': 80, 'h': 28}` on macos, `{'class': 'QPushButton', 'name': '', 'x': 188, 'y': 90, 'w': 80, 'h': 26}` on linux-x11
- linux-x11 / message: `{'class': 'QLabel', 'name': 'qt_msgbox_informativelabel', 'x': 70, 'y': 41, 'w': 252, 'h': 36}` on macos, `{'class': 'QLabel', 'name': 'qt_msgbox_informativelabel', 'x': 62, 'y': 35, 'w': 206, 'h': 49}` on linux-x11
- linux-x11 / menu: `{'class': 'QMenu', 'name': '', 'x': 0, 'y': 0, 'w': 228, 'h': 177}` on macos, `{'class': 'QMenu', 'name': '', 'x': 0, 'y': 0, 'w': 284, 'h': 184}` on linux-x11
- linux-x11 / brain-1: `{'class': 'SquidBrainWindow', 'name': '', 'x': 0, 'y': 0, 'w': 1024, 'h': 646}` on macos, `{'class': 'SquidBrainWindow', 'name': '', 'x': 0, 'y': 0, 'w': 1300, 'h': 980}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QWidget', 'name': '', 'x': 0, 'y': 0, 'w': 1024, 'h': 646}` on macos, `{'class': 'QWidget', 'name': '', 'x': 0, 'y': 0, 'w': 1300, 'h': 980}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QTabWidget', 'name': '', 'x': 9, 'y': 9, 'w': 1006, 'h': 628}` on macos, `{'class': 'QTabWidget', 'name': '', 'x': 9, 'y': 9, 'w': 1282, 'h': 962}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QStackedWidget', 'name': 'qt_tabwidget_stackedwidget', 'x': 11, 'y': 42, 'w': 1002, 'h': 593}` on macos, `{'class': 'QStackedWidget', 'name': 'qt_tabwidget_stackedwidget', 'x': 11, 'y': 39, 'w': 1278, 'h': 930}` on linux-x11
- linux-x11 / brain-1: `{'class': 'NetworkTab', 'name': '', 'x': 11, 'y': 42, 'w': 1002, 'h': 593}` on macos, `{'class': 'NetworkTab', 'name': '', 'x': 11, 'y': 39, 'w': 1278, 'h': 930}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 51, 'w': 984, 'h': 23}` on macos, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 48, 'w': 1260, 'h': 23}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QLabel', 'name': '', 'x': 24, 'y': 51, 'w': 70, 'h': 23}` on macos, `{'class': 'QLabel', 'name': '', 'x': 24, 'y': 48, 'w': 70, 'h': 23}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QLabel', 'name': '', 'x': 103, 'y': 51, 'w': 92, 'h': 23}` on macos, `{'class': 'QLabel', 'name': '', 'x': 103, 'y': 48, 'w': 92, 'h': 23}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QLabel', 'name': '', 'x': 204, 'y': 51, 'w': 142, 'h': 23}` on macos, `{'class': 'QLabel', 'name': '', 'x': 204, 'y': 48, 'w': 142, 'h': 23}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QWidget', 'name': '', 'x': 896, 'y': 51, 'w': 104, 'h': 23}` on macos, `{'class': 'QWidget', 'name': '', 'x': 1172, 'y': 48, 'w': 104, 'h': 23}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QLabel', 'name': '', 'x': 900, 'y': 53, 'w': 96, 'h': 19}` on macos, `{'class': 'QLabel', 'name': '', 'x': 1176, 'y': 50, 'w': 96, 'h': 19}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 80, 'w': 984, 'h': 402}` on macos, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 77, 'w': 1260, 'h': 740}` on linux-x11
- linux-x11 / brain-1: `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 89, 'w': 966, 'h': 384}` on macos, `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 86, 'w': 1242, 'h': 722}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 576, 'w': 31, 'h': 50}` on macos, `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 910, 'w': 31, 'h': 50}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QComboBox', 'name': '', 'x': 57, 'y': 588, 'w': 100, 'h': 26}` on macos, `{'class': 'QComboBox', 'name': '', 'x': 57, 'y': 922, 'w': 94, 'h': 26}` on linux-x11
- linux-x11 / brain-1: [1024, 646] on macos, [1300, 980] on linux-x11
- linux-x11 / brain-2: [1024, 646] on macos, [1300, 980] on linux-x11
- linux-x11 / brain-3: [1024, 646] on macos, [1300, 980] on linux-x11
- linux-x11 / brain-4: [1024, 646] on macos, [1300, 980] on linux-x11
- linux-x11 / brain-5: [1024, 646] on macos, [1300, 980] on linux-x11
- linux-x11 / brain-6: [1024, 646] on macos, [1300, 980] on linux-x11
- linux-x11 / brain-7: [1024, 646] on macos, [1300, 980] on linux-x11
- linux-x11 / brain-8: [1024, 646] on macos, [1300, 980] on linux-x11
- linux-x11 / menu: [228, 177] on macos, [284, 184] on linux-x11
- linux-x11 / message: [346, 133] on macos, [279, 127] on linux-x11
- linux-wayland / brain-1: [1024, 646] on macos, [1300, 980] on linux-wayland
- linux-wayland / brain-2: [1024, 646] on macos, [1300, 980] on linux-wayland
- linux-wayland / brain-3: [1024, 646] on macos, [1300, 980] on linux-wayland
- linux-wayland / brain-4: [1024, 646] on macos, [1300, 980] on linux-wayland
- linux-wayland / brain-5: [1024, 646] on macos, [1300, 980] on linux-wayland
- linux-wayland / brain-6: [1024, 646] on macos, [1300, 980] on linux-wayland
- linux-wayland / brain-7: [1024, 646] on macos, [1300, 980] on linux-wayland
- linux-wayland / brain-8: [1024, 646] on macos, [1300, 980] on linux-wayland
- linux-wayland / menu: [228, 177] on macos, [284, 184] on linux-wayland
- linux-wayland / message: [346, 133] on macos, [279, 127] on linux-wayland

Fixed windows: splash, main, statistics, message, menu, brain-1. The other Brain Tool tabs list what one particular squid has learned, so their contents differ between any two runs.

Pixels differ where the game itself differs between two runs (where the squid is, what it is thinking, the numbers) and at the edges of letters, which each system smooths in its own way.

## The pictures

Taken by `tools/capture_platforms.py` on GitHub's own machines (`.github/workflows/platform-screenshots.yml`). Each window is saved from the window itself, so it is what the game drew; the system's title bar is not the game's, and is in the picture of the whole screen where the system allows one to be taken.

### The tank

| macos | linux-x11 | linux-wayland |
|---|---|---|
| ![The tank on macos](macos/main.png) | ![The tank on linux-x11](linux-x11/main.png) | ![The tank on linux-wayland](linux-wayland/main.png) |

### Brain Tool: the network

| macos | linux-x11 | linux-wayland |
|---|---|---|
| ![Brain Tool: the network on macos](macos/brain-1.png) | ![Brain Tool: the network on linux-x11](linux-x11/brain-1.png) | ![Brain Tool: the network on linux-wayland](linux-wayland/brain-1.png) |

### Brain Tool: learning

| macos | linux-x11 | linux-wayland |
|---|---|---|
| ![Brain Tool: learning on macos](macos/brain-2.png) | ![Brain Tool: learning on linux-x11](linux-x11/brain-2.png) | ![Brain Tool: learning on linux-wayland](linux-wayland/brain-2.png) |

### Statistics

| macos | linux-x11 | linux-wayland |
|---|---|---|
| ![Statistics on macos](macos/statistics.png) | ![Statistics on linux-x11](linux-x11/statistics.png) | ![Statistics on linux-wayland](linux-wayland/statistics.png) |

### Journey

| macos | linux-x11 | linux-wayland |
|---|---|---|
| ![Journey on macos](macos/journey.png) | ![Journey on linux-x11](linux-x11/journey.png) | ![Journey on linux-wayland](linux-wayland/journey.png) |

### Language splash

| macos | linux-x11 | linux-wayland |
|---|---|---|
| ![Language splash on macos](macos/splash.png) | ![Language splash on linux-x11](linux-x11/splash.png) | ![Language splash on linux-wayland](linux-wayland/splash.png) |

### A message box

| macos | linux-x11 | linux-wayland |
|---|---|---|
| ![A message box on macos](macos/message.png) | ![A message box on linux-x11](linux-x11/message.png) | ![A message box on linux-wayland](linux-wayland/message.png) |

### A menu

| macos | linux-x11 | linux-wayland |
|---|---|---|
| ![A menu on macos](macos/menu.png) | ![A menu on linux-x11](linux-x11/menu.png) | ![A menu on linux-wayland](linux-wayland/menu.png) |

### The whole screen, with the system's own window frames

**macos**

![The whole screen on macos](macos/screen.png)

**linux-x11**

![The whole screen on linux-x11](linux-x11/screen.png)

## Each machine

- **macos**: macOS-26.7.2-arm64-arm-64bit, Python 3.11.9, Qt 5.15.14, real screen 1024x768
- **linux-x11**: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39, Python 3.11.18, Qt 5.15.14, real screen 1920x1080
- **linux-wayland**: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39, Python 3.11.18, Qt 5.15.14, real screen 1920x1080
