# The same game on 3 systems

| System | Qt platform | Screen | Font used | 10 pt in pixels | Line height |
|---|---|---|---|---|---|
| windows | windows | 1920x1080 | Fio UI | 13 | 18 |
| linux-x11 | xcb | 1920x1080 | Fio UI | 13 | 18 |
| linux-wayland | wayland | 1920x1080 | Fio UI | 13 | 18 |

Compared with **windows**:

| System | Text measurements | Window sizes | Widgets in the same place (fixed windows) | Pixels that differ |
|---|---|---|---|---|
| linux-x11 | identical | identical | 70 of 70 | brain-1 0.9%, brain-2 3.5%, brain-3 2.3%, brain-4 0.6%, brain-5 0.8%, brain-6 0.9%, brain-7 0.8%, brain-8 1.1%, journey 5.2%, main 1.1%, menu 2.5%, message 3.1%, splash 0.4%, statistics 2.0% |
| linux-wayland | identical | identical | 70 of 70 | brain-1 0.9%, brain-2 2.1%, brain-3 2.4%, brain-4 0.6%, brain-5 0.9%, brain-6 0.9%, brain-7 0.9%, brain-8 1.1%, journey 5.2%, main 1.1%, menu 2.5%, message 3.6%, splash 0.4%, statistics 2.0% |

Fixed windows: splash, main, statistics, message, menu, brain-1. The other Brain Tool tabs list what one particular squid has learned, so their contents differ between any two runs.

Pixels differ where the game itself differs between two runs (where the squid is, what it is thinking, the numbers) and at the edges of letters, which each system smooths in its own way.

## The pictures

Taken by `tools/capture_platforms.py` on GitHub's own machines (`.github/workflows/platform-screenshots.yml`). Each window is saved from the window itself, so it is what the game drew; the system's title bar is not the game's, and is in the picture of the whole screen where the system allows one to be taken.

### The tank

| windows | linux-x11 | linux-wayland |
|---|---|---|
| ![The tank on windows](windows/main.png) | ![The tank on linux-x11](linux-x11/main.png) | ![The tank on linux-wayland](linux-wayland/main.png) |

### Brain Tool: the network

| windows | linux-x11 | linux-wayland |
|---|---|---|
| ![Brain Tool: the network on windows](windows/brain-1.png) | ![Brain Tool: the network on linux-x11](linux-x11/brain-1.png) | ![Brain Tool: the network on linux-wayland](linux-wayland/brain-1.png) |

### Brain Tool: learning

| windows | linux-x11 | linux-wayland |
|---|---|---|
| ![Brain Tool: learning on windows](windows/brain-2.png) | ![Brain Tool: learning on linux-x11](linux-x11/brain-2.png) | ![Brain Tool: learning on linux-wayland](linux-wayland/brain-2.png) |

### Statistics

| windows | linux-x11 | linux-wayland |
|---|---|---|
| ![Statistics on windows](windows/statistics.png) | ![Statistics on linux-x11](linux-x11/statistics.png) | ![Statistics on linux-wayland](linux-wayland/statistics.png) |

### Journey

| windows | linux-x11 | linux-wayland |
|---|---|---|
| ![Journey on windows](windows/journey.png) | ![Journey on linux-x11](linux-x11/journey.png) | ![Journey on linux-wayland](linux-wayland/journey.png) |

### Language splash

| windows | linux-x11 | linux-wayland |
|---|---|---|
| ![Language splash on windows](windows/splash.png) | ![Language splash on linux-x11](linux-x11/splash.png) | ![Language splash on linux-wayland](linux-wayland/splash.png) |

### A message box

| windows | linux-x11 | linux-wayland |
|---|---|---|
| ![A message box on windows](windows/message.png) | ![A message box on linux-x11](linux-x11/message.png) | ![A message box on linux-wayland](linux-wayland/message.png) |

### A menu

| windows | linux-x11 | linux-wayland |
|---|---|---|
| ![A menu on windows](windows/menu.png) | ![A menu on linux-x11](linux-x11/menu.png) | ![A menu on linux-wayland](linux-wayland/menu.png) |

### The whole screen, with the system's own window frames

**windows**

![The whole screen on windows](windows/screen.png)

**linux-x11**

![The whole screen on linux-x11](linux-x11/screen.png)

## Each machine

- **windows**: Windows-10-10.0.26100-SP0, Python 3.11.9, Qt 5.15.2, real screen 1920x1080
- **linux-x11**: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39, Python 3.11.18, Qt 5.15.14, real screen 1920x1080
- **linux-wayland**: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39, Python 3.11.18, Qt 5.15.14, real screen 1920x1080
