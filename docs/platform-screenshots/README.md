# The same game on 4 systems

| System | Qt platform | Screen | Font used | 10 pt in pixels | Line height |
|---|---|---|---|---|---|
| windows | windows | 1920x1080 | Fio UI | 13 | 17 |
| macos | cocoa | 1920x1080 | Fio UI | 13 | 17 |
| linux-x11 | xcb | 1920x1080 | Fio UI | 13 | 18 |
| linux-wayland | wayland | 1920x1080 | Fio UI | 13 | 18 |

Compared with **windows**:

| System | Text measurements | Window sizes | Widgets in the same place (fixed windows) | Pixels that differ |
|---|---|---|---|---|
| macos | identical | DIFFERENT | 37 of 71 | brain-1: sizes differ, brain-2: sizes differ, brain-3: sizes differ, brain-4: sizes differ, brain-5: sizes differ, brain-6: sizes differ, brain-7: sizes differ, brain-8: sizes differ, journey 9.4%, main 1.3%, menu: sizes differ, message: sizes differ, splash 1.7%, statistics 3.2% |
| linux-x11 | DIFFERENT | DIFFERENT | 45 of 71 | brain-1 4.0%, brain-2 6.4%, brain-3 7.6%, brain-4 1.4%, brain-5 1.7%, brain-6 2.3%, brain-7 1.2%, brain-8 2.2%, journey 13.4%, main 1.4%, menu: sizes differ, message: sizes differ, splash 0.9%, statistics 0.8% |
| linux-wayland | DIFFERENT | DIFFERENT | 45 of 71 | brain-1 4.7%, brain-2 8.0%, brain-3 7.7%, brain-4 1.2%, brain-5 1.3%, brain-6 2.3%, brain-7 1.2%, brain-8 2.2%, journey 13.4%, main 5.0%, menu: sizes differ, message: sizes differ, splash 0.9%, statistics 1.2% |

Not the same:

- macos / message: `{'class': 'QMessageBox', 'name': '', 'x': 0, 'y': 0, 'w': 279, 'h': 128}` on windows, `{'class': 'QMessageBox', 'name': '', 'x': 0, 'y': 0, 'w': 346, 'h': 133}` on macos
- macos / message: `{'class': 'QLabel', 'name': 'qt_msgboxex_icon_label', 'x': 11, 'y': 11, 'w': 32, 'h': 32}` on windows, `{'class': 'QLabel', 'name': 'qt_msgboxex_icon_label', 'x': 24, 'y': 15, 'w': 32, 'h': 32}` on macos
- macos / message: `{'class': 'QLabel', 'name': 'qt_msgbox_label', 'x': 62, 'y': 11, 'w': 206, 'h': 18}` on windows, `{'class': 'QLabel', 'name': 'qt_msgbox_label', 'x': 70, 'y': 15, 'w': 252, 'h': 18}` on macos
- macos / message: `{'class': 'QDialogButtonBox', 'name': 'qt_msgbox_buttonbox', 'x': 11, 'y': 91, 'w': 257, 'h': 26}` on windows, `{'class': 'QDialogButtonBox', 'name': 'qt_msgbox_buttonbox', 'x': 70, 'y': 85, 'w': 252, 'h': 28}` on macos
- macos / message: `{'class': 'QPushButton', 'name': '', 'x': 16, 'y': 91, 'w': 80, 'h': 26}` on windows, `{'class': 'QPushButton', 'name': '', 'x': 70, 'y': 85, 'w': 80, 'h': 28}` on macos
- macos / message: `{'class': 'QPushButton', 'name': '', 'x': 102, 'y': 91, 'w': 80, 'h': 26}` on windows, `{'class': 'QPushButton', 'name': '', 'x': 156, 'y': 85, 'w': 80, 'h': 28}` on macos
- macos / message: `{'class': 'QPushButton', 'name': '', 'x': 188, 'y': 91, 'w': 80, 'h': 26}` on windows, `{'class': 'QPushButton', 'name': '', 'x': 242, 'y': 85, 'w': 80, 'h': 28}` on macos
- macos / message: `{'class': 'QLabel', 'name': 'qt_msgbox_informativelabel', 'x': 62, 'y': 35, 'w': 206, 'h': 50}` on windows, `{'class': 'QLabel', 'name': 'qt_msgbox_informativelabel', 'x': 70, 'y': 41, 'w': 252, 'h': 36}` on macos
- macos / menu: `{'class': 'QMenu', 'name': '', 'x': 0, 'y': 0, 'w': 284, 'h': 177}` on windows, `{'class': 'QMenu', 'name': '', 'x': 0, 'y': 0, 'w': 228, 'h': 177}` on macos
- macos / brain-1: `{'class': 'SquidBrainWindow', 'name': '', 'x': 0, 'y': 0, 'w': 1300, 'h': 980}` on windows, `{'class': 'SquidBrainWindow', 'name': '', 'x': 0, 'y': 0, 'w': 1024, 'h': 649}` on macos
- macos / brain-1: `{'class': 'QWidget', 'name': '', 'x': 0, 'y': 0, 'w': 1300, 'h': 980}` on windows, `{'class': 'QWidget', 'name': '', 'x': 0, 'y': 0, 'w': 1024, 'h': 649}` on macos
- macos / brain-1: `{'class': 'QTabWidget', 'name': '', 'x': 9, 'y': 9, 'w': 1282, 'h': 962}` on windows, `{'class': 'QTabWidget', 'name': '', 'x': 9, 'y': 9, 'w': 1006, 'h': 631}` on macos
- macos / brain-1: `{'class': 'QStackedWidget', 'name': 'qt_tabwidget_stackedwidget', 'x': 11, 'y': 38, 'w': 1278, 'h': 931}` on windows, `{'class': 'QStackedWidget', 'name': 'qt_tabwidget_stackedwidget', 'x': 11, 'y': 42, 'w': 1002, 'h': 596}` on macos
- macos / brain-1: `{'class': 'NetworkTab', 'name': '', 'x': 11, 'y': 38, 'w': 1278, 'h': 931}` on windows, `{'class': 'NetworkTab', 'name': '', 'x': 11, 'y': 42, 'w': 1002, 'h': 596}` on macos
- macos / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 47, 'w': 1260, 'h': 23}` on windows, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 51, 'w': 984, 'h': 23}` on macos
- macos / brain-1: `{'class': 'QLabel', 'name': '', 'x': 24, 'y': 47, 'w': 70, 'h': 23}` on windows, `{'class': 'QLabel', 'name': '', 'x': 24, 'y': 51, 'w': 70, 'h': 23}` on macos
- macos / brain-1: `{'class': 'QLabel', 'name': '', 'x': 103, 'y': 47, 'w': 92, 'h': 23}` on windows, `{'class': 'QLabel', 'name': '', 'x': 103, 'y': 51, 'w': 92, 'h': 23}` on macos
- macos / brain-1: `{'class': 'QLabel', 'name': '', 'x': 204, 'y': 47, 'w': 142, 'h': 23}` on windows, `{'class': 'QLabel', 'name': '', 'x': 204, 'y': 51, 'w': 142, 'h': 23}` on macos
- macos / brain-1: `{'class': 'QWidget', 'name': '', 'x': 1172, 'y': 47, 'w': 104, 'h': 23}` on windows, `{'class': 'QWidget', 'name': '', 'x': 896, 'y': 51, 'w': 104, 'h': 23}` on macos
- macos / brain-1: `{'class': 'QLabel', 'name': '', 'x': 1176, 'y': 49, 'w': 96, 'h': 19}` on windows, `{'class': 'QLabel', 'name': '', 'x': 900, 'y': 53, 'w': 96, 'h': 19}` on macos
- macos / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 76, 'w': 1260, 'h': 739}` on windows, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 80, 'w': 984, 'h': 405}` on macos
- macos / brain-1: `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 85, 'w': 1242, 'h': 721}` on windows, `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 89, 'w': 966, 'h': 387}` on macos
- macos / brain-1: `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 910, 'w': 31, 'h': 50}` on windows, `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 579, 'w': 31, 'h': 50}` on macos
- macos / brain-1: `{'class': 'QComboBox', 'name': '', 'x': 57, 'y': 922, 'w': 96, 'h': 26}` on windows, `{'class': 'QComboBox', 'name': '', 'x': 57, 'y': 591, 'w': 100, 'h': 26}` on macos
- macos / brain-1: [1300, 980] on windows, [1024, 649] on macos
- macos / brain-2: [1300, 980] on windows, [1024, 649] on macos
- macos / brain-3: [1300, 980] on windows, [1024, 649] on macos
- macos / brain-4: [1300, 980] on windows, [1024, 649] on macos
- macos / brain-5: [1300, 980] on windows, [1024, 649] on macos
- macos / brain-6: [1300, 980] on windows, [1024, 649] on macos
- macos / brain-7: [1300, 980] on windows, [1024, 649] on macos
- macos / brain-8: [1300, 980] on windows, [1024, 649] on macos
- macos / menu: [284, 177] on windows, [228, 177] on macos
- macos / message: [279, 128] on windows, [346, 133] on macos
- linux-x11 / menu: [284, 177] on windows, [284, 184] on linux-x11
- linux-x11 / message: [279, 128] on windows, [279, 127] on linux-x11
- linux-wayland / menu: [284, 177] on windows, [284, 184] on linux-wayland
- linux-wayland / message: [279, 128] on windows, [279, 127] on linux-wayland

Fixed windows: splash, main, statistics, message, menu, brain-1. The other Brain Tool tabs list what one particular squid has learned, so their contents differ between any two runs.

Pixels differ where the game itself differs between two runs (where the squid is, what it is thinking, the numbers) and at the edges of letters, which each system smooths in its own way.

## The pictures

Taken by `tools/capture_platforms.py` on GitHub's own machines (`.github/workflows/platform-screenshots.yml`). Each window is saved from the window itself, so it is what the game drew; the system's title bar is not the game's, and is in the picture of the whole screen where the system allows one to be taken.

### The tank

| windows | macos | linux-x11 | linux-wayland |
|---|---|---|---|
| ![The tank on windows](windows/main.png) | ![The tank on macos](macos/main.png) | ![The tank on linux-x11](linux-x11/main.png) | ![The tank on linux-wayland](linux-wayland/main.png) |

### Brain Tool: the network

| windows | macos | linux-x11 | linux-wayland |
|---|---|---|---|
| ![Brain Tool: the network on windows](windows/brain-1.png) | ![Brain Tool: the network on macos](macos/brain-1.png) | ![Brain Tool: the network on linux-x11](linux-x11/brain-1.png) | ![Brain Tool: the network on linux-wayland](linux-wayland/brain-1.png) |

### Brain Tool: learning

| windows | macos | linux-x11 | linux-wayland |
|---|---|---|---|
| ![Brain Tool: learning on windows](windows/brain-2.png) | ![Brain Tool: learning on macos](macos/brain-2.png) | ![Brain Tool: learning on linux-x11](linux-x11/brain-2.png) | ![Brain Tool: learning on linux-wayland](linux-wayland/brain-2.png) |

### Statistics

| windows | macos | linux-x11 | linux-wayland |
|---|---|---|---|
| ![Statistics on windows](windows/statistics.png) | ![Statistics on macos](macos/statistics.png) | ![Statistics on linux-x11](linux-x11/statistics.png) | ![Statistics on linux-wayland](linux-wayland/statistics.png) |

### Journey

| windows | macos | linux-x11 | linux-wayland |
|---|---|---|---|
| ![Journey on windows](windows/journey.png) | ![Journey on macos](macos/journey.png) | ![Journey on linux-x11](linux-x11/journey.png) | ![Journey on linux-wayland](linux-wayland/journey.png) |

### Language splash

| windows | macos | linux-x11 | linux-wayland |
|---|---|---|---|
| ![Language splash on windows](windows/splash.png) | ![Language splash on macos](macos/splash.png) | ![Language splash on linux-x11](linux-x11/splash.png) | ![Language splash on linux-wayland](linux-wayland/splash.png) |

### A message box

| windows | macos | linux-x11 | linux-wayland |
|---|---|---|---|
| ![A message box on windows](windows/message.png) | ![A message box on macos](macos/message.png) | ![A message box on linux-x11](linux-x11/message.png) | ![A message box on linux-wayland](linux-wayland/message.png) |

### A menu

| windows | macos | linux-x11 | linux-wayland |
|---|---|---|---|
| ![A menu on windows](windows/menu.png) | ![A menu on macos](macos/menu.png) | ![A menu on linux-x11](linux-x11/menu.png) | ![A menu on linux-wayland](linux-wayland/menu.png) |

### The whole screen, with the system's own window frames

**windows**

![The whole screen on windows](windows/screen.png)

**macos**

![The whole screen on macos](macos/screen.png)

**linux-x11**

![The whole screen on linux-x11](linux-x11/screen.png)

## Each machine

- **windows**: Windows-10-10.0.26100-SP0, Python 3.11.9, Qt 5.15.2, real screen 1920x1080
- **macos**: macOS-26.7.2-arm64-arm-64bit, Python 3.11.9, Qt 5.15.14, real screen 1024x768
- **linux-x11**: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39, Python 3.11.18, Qt 5.15.14, real screen 1920x1080
- **linux-wayland**: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39, Python 3.11.18, Qt 5.15.14, real screen 1920x1080
