# The same game on 4 systems

| System | Qt platform | Screen | Font used | 10 pt in pixels | Line height |
|---|---|---|---|---|---|
| windows | windows | 1920x1080 | Fio UI | 13 | 18 |
| macos | cocoa | 1920x1080 | Fio UI | 13 | 18 |
| linux-x11 | xcb | 1920x1080 | Fio UI | 13 | 18 |
| linux-wayland | wayland | 1920x1080 | Fio UI | 13 | 18 |

Compared with **windows**:

| System | Text measurements | Window sizes | Widgets in the same place (fixed windows) | Pixels that differ |
|---|---|---|---|---|
| macos | identical | DIFFERENT | 63 of 70 | brain-1 2.4%, brain-2 7.6%, brain-3 2.1%, brain-4 1.1%, brain-5 1.1%, brain-6 0.8%, brain-7 0.7%, brain-8 1.0%, journey 5.0%, main 1.0%, menu: sizes differ, message 2.7%, splash 0.4%, statistics 1.7% |
| linux-x11 | identical | identical | 64 of 70 | brain-1 2.4%, brain-2 7.1%, brain-3 1.8%, brain-4 1.1%, brain-5 0.9%, brain-6 0.9%, brain-7 0.9%, brain-8 1.1%, journey 5.2%, main 1.1%, menu 2.5%, message 3.1%, splash 0.4%, statistics 1.6% |
| linux-wayland | identical | identical | 64 of 70 | brain-1 2.4%, brain-2 7.9%, brain-3 2.3%, brain-4 0.9%, brain-5 0.9%, brain-6 0.9%, brain-7 0.9%, brain-8 1.1%, journey 5.2%, main 1.2%, menu 2.5%, message 3.6%, splash 0.4%, statistics 1.6% |

Not the same:

- macos / menu: `{'class': 'QMenu', 'name': '', 'x': 0, 'y': 0, 'w': 284, 'h': 184}` on windows, `{'class': 'QMenu', 'name': '', 'x': 0, 'y': 0, 'w': 219, 'h': 184}` on macos
- macos / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 77, 'w': 960, 'h': 379}` on windows, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 77, 'w': 960, 'h': 380}` on macos
- macos / brain-1: `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 86, 'w': 942, 'h': 361}` on windows, `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 86, 'w': 942, 'h': 362}` on macos
- macos / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 462, 'w': 960, 'h': 82}` on windows, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 463, 'w': 960, 'h': 81}` on macos
- macos / brain-1: `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 462, 'w': 903, 'h': 82}` on windows, `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 463, 'w': 903, 'h': 81}` on macos
- macos / brain-1: `{'class': 'QWidget', 'name': '', 'x': 933, 'y': 479, 'w': 47, 'h': 47}` on windows, `{'class': 'QWidget', 'name': '', 'x': 933, 'y': 480, 'w': 47, 'h': 47}` on macos
- macos / brain-1: `{'class': 'QPushButton', 'name': '', 'x': 933, 'y': 483, 'w': 47, 'h': 38}` on windows, `{'class': 'QPushButton', 'name': '', 'x': 933, 'y': 484, 'w': 47, 'h': 38}` on macos
- macos / menu: [284, 184] on windows, [219, 184] on macos
- linux-x11 / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 77, 'w': 960, 'h': 379}` on windows, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 77, 'w': 960, 'h': 380}` on linux-x11
- linux-x11 / brain-1: `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 86, 'w': 942, 'h': 361}` on windows, `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 86, 'w': 942, 'h': 362}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 462, 'w': 960, 'h': 82}` on windows, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 463, 'w': 960, 'h': 81}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 462, 'w': 903, 'h': 82}` on windows, `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 463, 'w': 903, 'h': 81}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QWidget', 'name': '', 'x': 933, 'y': 479, 'w': 47, 'h': 47}` on windows, `{'class': 'QWidget', 'name': '', 'x': 933, 'y': 480, 'w': 47, 'h': 47}` on linux-x11
- linux-x11 / brain-1: `{'class': 'QPushButton', 'name': '', 'x': 933, 'y': 483, 'w': 47, 'h': 38}` on windows, `{'class': 'QPushButton', 'name': '', 'x': 933, 'y': 484, 'w': 47, 'h': 38}` on linux-x11
- linux-wayland / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 77, 'w': 960, 'h': 379}` on windows, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 77, 'w': 960, 'h': 380}` on linux-wayland
- linux-wayland / brain-1: `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 86, 'w': 942, 'h': 361}` on windows, `{'class': 'BrainWidget', 'name': '', 'x': 29, 'y': 86, 'w': 942, 'h': 362}` on linux-wayland
- linux-wayland / brain-1: `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 462, 'w': 960, 'h': 82}` on windows, `{'class': 'QWidget', 'name': '', 'x': 20, 'y': 463, 'w': 960, 'h': 81}` on linux-wayland
- linux-wayland / brain-1: `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 462, 'w': 903, 'h': 82}` on windows, `{'class': 'QLabel', 'name': '', 'x': 20, 'y': 463, 'w': 903, 'h': 81}` on linux-wayland
- linux-wayland / brain-1: `{'class': 'QWidget', 'name': '', 'x': 933, 'y': 479, 'w': 47, 'h': 47}` on windows, `{'class': 'QWidget', 'name': '', 'x': 933, 'y': 480, 'w': 47, 'h': 47}` on linux-wayland
- linux-wayland / brain-1: `{'class': 'QPushButton', 'name': '', 'x': 933, 'y': 483, 'w': 47, 'h': 38}` on windows, `{'class': 'QPushButton', 'name': '', 'x': 933, 'y': 484, 'w': 47, 'h': 38}` on linux-wayland

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
