# The same game on 1 systems

| System | Qt platform | Screen | Font used | 10 pt in pixels | Line height |
|---|---|---|---|---|---|
| macos | cocoa | 1920x1080 | Fio UI | 13 | 18 |

Compared with **macos**:

| System | Text measurements | Window sizes | Widgets in the same place (fixed windows) | Pixels that differ |
|---|---|---|---|---|

Fixed windows: splash, main, statistics, message, menu, brain-1. The other Brain Tool tabs list what one particular squid has learned, so their contents differ between any two runs.

Pixels differ where the game itself differs between two runs (where the squid is, what it is thinking, the numbers) and at the edges of letters, which each system smooths in its own way.

## The pictures

Taken by `tools/capture_platforms.py` on GitHub's own machines (`.github/workflows/platform-screenshots.yml`). Each window is saved from the window itself, so it is what the game drew; the system's title bar is not the game's, and is in the picture of the whole screen where the system allows one to be taken.

### The tank

| macos |
|---|
| ![The tank on macos](macos/main.png) |

### Brain Tool: the network

| macos |
|---|
| ![Brain Tool: the network on macos](macos/brain-1.png) |

### Brain Tool: learning

| macos |
|---|
| ![Brain Tool: learning on macos](macos/brain-2.png) |

### Statistics

| macos |
|---|
| ![Statistics on macos](macos/statistics.png) |

### Journey

| macos |
|---|
| ![Journey on macos](macos/journey.png) |

### Language splash

| macos |
|---|
| ![Language splash on macos](macos/splash.png) |

### A message box

| macos |
|---|
| ![A message box on macos](macos/message.png) |

### A menu

| macos |
|---|
| ![A menu on macos](macos/menu.png) |

### The whole screen, with the system's own window frames

**macos**

![The whole screen on macos](macos/screen.png)

## How big the squid is

| System | Screen laid out for | Tank window | Squid | Share of the window's width | Tank scale |
|---|---|---|---|---|---|
| macos | 1920x1080 | 688x458 | 129x75 | 18.8% | 0.5123 |

On the screen the game was designed for (2880x1920) the squid is 253 pixels wide in a 1344-pixel window: 18.8%. It takes the same share on every screen.

## Which font draws what

| System | A brain emoji in Fio UI text | On the Brain Designer button | The reset arrow |
|---|---|---|---|
| macos | Dosidicus Emoji | Dosidicus Line Emoji | IBM Plex Mono |

## Each machine

- **macos**: macOS-26.7.2-arm64-arm-64bit, Python 3.11.9, Qt 5.15.14, real screen 1024x768
