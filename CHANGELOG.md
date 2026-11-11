# Changelog

## 3.5.0

Everything since 3.2.0.

### Multiplayer over the internet

- **Friend codes.** Two players anywhere can link their tanks: each presses
  *Get my code* in the Friends window, sends the code to the other, and enters
  the other's. Codes are 15 letters and digits in three groups, such as
  `4KQ7M-2D0HX-9T1VB`; a mistyped code is refused rather than followed, and
  *Copy code* puts it on the clipboard. A direct IP address works too.
- **Phones and computers together.** The Android game now uses the same
  network as the desktop game. A phone's squid can visit a computer's tank and
  a computer's squid can visit a phone's, with the same codes. The phone has a
  new *Menu > Friends (internet play)* screen.
- **Up to four squid in a tank:** the resident and three visitors.
- **A squid keeps its colour** in other tanks: a pink squid is pink wherever
  it visits.
- **Visitors' names** above their heads are easier to read.
- **Safer by default.** A tank ignores anyone on the internet who does not
  show its code's invitation, and stops accepting codes for a minute if
  somebody starts guessing.
- **Fixed:** a friend who was also on your home network could be let in twice,
  which broke the visit.
- **Fixed:** a tank whose squid was away could "remember" meeting a visitor it
  never saw.
- `Dosidicus --network-self-test` checks that multiplayer works in your copy
  of the game, without opening a window.

Linking tanks only makes a visit possible. Each squid still decides for itself
whether to go. The steps are in `plugins/multiplayer/README`.

### The squid's mind

- **Learning now improves the squid.** Actions are taught by what they lead
  to, and neurons are grown only for something the squid could not otherwise
  represent.
- **Its own model of its world.** The squid forms beliefs about what its
  actions cause, acts on them, and drops the ones it finds to be wrong. They
  are shown in plain words.
- **It sees plants.** The old plant-distance sense is replaced by
  `can_see_plant`, grown the first time the squid sees one.
- **Aggression is a statistic** once the squid has grown the neuron for it. It
  appears beside Sleepiness, with a border that flashes for five seconds.
- **A grown neuron swells into place** in the brain view, as hatching ones do.
- **One journey view** through a squid's life, with going online marked as the
  choice it is.

### The tank

- **Every score change floats up out of the squid:** gains in green, losses in
  red, in a larger, shadowed font.
- **One icon above the squid's head at a time,** sitting just above it. The
  neurogenesis icon always takes priority.
- **Feed, Clean and Medicine** span the window, are a little taller, and are
  pastel green, blue and red.
- **The message banner** sits flush with the bottom of the window.
- **Headstones** can be moved but never resized or removed.
- **The squid, food and decorations scale with the tank,** so the squid is the
  same share of the tank on every screen.

### The same on every system

- **One look on Windows, macOS and Linux (X11 and Wayland):** the game's own
  font (Fio UI), style, sizes and emoji, so windows, menus and buttons match
  to the pixel.
- **Windows open in the same places.** The aquarium opens at the top left and
  stays on top for its first five seconds.
- **The brain view fits its window,** rescales when the window is resized, and
  draws back as the squid grows new neurons.
- **Brain tab buttons:** a plain black-and-white brain for the Brain Designer,
  a floppy disk for *Load brain*, grouped closer together.
- **On a Mac, shortcuts use Control** and are spelled out ("Ctrl+Shift+B"), so
  menus read the same everywhere.
- **Fixed:** the game did not start on macOS when its emoji font was refused
  by the system.
- **Fixed:** the game crashed on Windows consoles that cannot print emoji.
- **Fixed:** on a Mac that had run an earlier version, the game could fail to
  open at all because of a leftover link in its settings folder.

### Builds and releases

- **One Mac download for every Mac:** a universal DMG for Apple Silicon and
  Intel, ad-hoc signed and started on both before it is published.
- **A build run by hand is a release.** Running *Build (Nuitka)* from the
  Actions tab publishes one GitHub release with every artifact: Windows x64
  and ARM64, the macOS apps and DMGs, Linux, and the signed Android APK.
- **A built game never writes into its own folder,** which had broken the
  Mac app's signature.
- **Every build checks its own multiplayer networking** inside the compiled
  game on Windows, macOS and Linux.

### Known limits

- Internet play has been tested through simulated home routers, not yet on
  real ones. Some routers and many mobile-data connections cannot be got
  through; on a phone, use Wi-Fi.
- The phone's internet play has been tested as the real app on Linux, not yet
  on a device.
- On Wayland the compositor decides where windows open.
- Friend codes from earlier builds (20 characters) no longer work.
