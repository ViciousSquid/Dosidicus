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
| macos | identical | identical | 70 of 70 | brain-1 0.6%, brain-2 4.3%, brain-3 1.5%, brain-4 0.3%, brain-5 0.8%, brain-6 0.8%, brain-7 0.7%, brain-8 1.0%, journey 5.0%, main 5.0%, menu 2.2%, message 2.7%, splash 0.4%, statistics 1.7% |
| linux-x11 | identical | identical | 70 of 70 | brain-1 1.2%, brain-2 7.5%, brain-3 2.3%, brain-4 0.6%, brain-5 0.9%, brain-6 0.9%, brain-7 0.9%, brain-8 1.1%, journey 5.2%, main 1.1%, menu 2.5%, message 3.1%, splash 0.4%, statistics 1.6% |
| linux-wayland | identical | identical | 70 of 70 | brain-1 0.6%, brain-2 4.0%, brain-3 2.3%, brain-4 0.6%, brain-5 1.5%, brain-6 0.9%, brain-7 0.8%, brain-8 1.1%, journey 5.2%, main 4.1%, menu 2.5%, message 3.6%, splash 0.4%, statistics 2.5% |

Not the same:

- macos / where the brain_tool window is put: [526, 40, 1300, 920] on windows, [519, 40, 1300, 920] on macos
- linux-x11 / where the brain_tool window is put: [526, 40, 1300, 920] on windows, [519, 40, 1300, 920] on linux-x11
- linux-wayland / where the brain_tool window is put: [526, 40, 1300, 920] on windows, [516, 10, 1300, 920] on linux-wayland
- linux-wayland / where the tank window is put: [0, 40, 688, 458] on windows, [-3, 10, 688, 458] on linux-wayland

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

**linux-wayland**

![The whole screen on linux-wayland](linux-wayland/screen.png)

## Where the game puts its windows

Opened by the game itself and left where it put them: left, top, width, height on the screen. The picture of the whole screen for each system is further down.

| System | Tank | Brain tool | Statistics | Decorations |
|---|---|---|---|---|
| windows | 0, 40, 688, 458 | 526, 40, 1300, 920 | not shown | 1517, 661, 382, 310 |
| macos | 0, 40, 688, 458 | 519, 40, 1300, 920 | not shown | 1517, 661, 382, 310 |
| linux-x11 | 0, 40, 688, 458 | 519, 40, 1300, 920 | not shown | 1517, 661, 382, 310 |
| linux-wayland | -3, 10, 688, 458 | 516, 10, 1300, 920 | not shown | 1517, 661, 382, 310 |

The aquarium opens at the top left and stays above the other windows for its first five seconds: windows: on top after 2 s True, after 9 s False; macos: on top after 2 s True, after 9 s False; linux-x11: on top after 2 s True, after 9 s False; linux-wayland: on top after 2 s True, after 9 s False.

A Wayland compositor decides where a window goes and does not tell the program, so there the game can ask for a size but not a place, and reports 0, 0 for all of them.

## How big the squid is

| System | Screen laid out for | Tank window | Squid | Share of the window's width | Tank scale |
|---|---|---|---|---|---|
| windows | 1920x1080 | 688x458 | 129x75 | 18.8% | 0.5123 |
| macos | 1920x1080 | 688x458 | 129x75 | 18.8% | 0.5123 |
| linux-x11 | 1920x1080 | 688x458 | 129x75 | 18.8% | 0.5123 |
| linux-wayland | 1920x1080 | 688x458 | 129x75 | 18.8% | 0.5123 |

On the screen the game was designed for (2880x1920) the squid is 253 pixels wide in a 1344-pixel window: 18.8%. It takes the same share on every screen.

## Which font draws what

| System | A brain emoji in Fio UI text | On the Brain Designer button | The reset arrow |
|---|---|---|---|
| windows | Dosidicus Emoji | Dosidicus Line Emoji | IBM Plex Mono |
| macos | Dosidicus Emoji | Dosidicus Line Emoji | IBM Plex Mono |
| linux-x11 | Dosidicus Emoji | Dosidicus Line Emoji | IBM Plex Mono |
| linux-wayland | Dosidicus Emoji | Dosidicus Line Emoji | IBM Plex Mono |

## Each machine

- **windows**: Windows-10-10.0.26100-SP0, Python 3.11.9, Qt 5.15.2, real screen 1920x1080
- **macos**: macOS-26.7.2-arm64-arm-64bit, Python 3.11.9, Qt 5.15.14, real screen 1920x1080
- **linux-x11**: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39, Python 3.11.18, Qt 5.15.14, real screen 1920x1080
- **linux-wayland**: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39, Python 3.11.18, Qt 5.15.14, real screen 1920x1080
