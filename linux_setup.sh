#!/usr/bin/env bash
# =============================================================
#  Dosidicus - Linux Setup & Launch Script
#  https://github.com/ViciousSquid/Dosidicus
# =============================================================
#
# If you hit a Qt platform error like `could not load the Qt platform plugin "xcb", run the following:
# sudo apt install libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0

set -e

REPO_URL="https://github.com/ViciousSquid/Dosidicus.git"
# Use the current directory where the script lives
INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$INSTALL_DIR/.venv"

# ── Colours ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}▸ $*${NC}"; }
success() { echo -e "${GREEN}✔ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
error()   { echo -e "${RED}✖ $*${NC}"; exit 1; }

echo -e "${BOLD}"
echo "  DOSIDICUS  by ViciousSquid"
echo -e "${NC}"
echo -e "  ${BOLD}Tamagotchi squid with a neural network${NC}"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Check Python ───────────────────────────────────────────
info "Checking Python version..."
if ! command -v python3 &>/dev/null; then
    error "python3 not found. Install it with: sudo apt install python3"
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 9) ]]; then
    error "Python 3.9+ required. Found: $PY_VER"
fi
success "Python $PY_VER found"

# ── 2. Check / install system deps ───────────────────────────
info "Checking system dependencies..."

MISSING_PKGS=()
for pkg in git python3-venv python3-dev; do
    if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

# PyQt5 often needs these on Linux
for pkg in libxcb-xinerama0 libxcb-cursor0 libgl1 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0; do
    if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    warn "Missing packages: ${MISSING_PKGS[*]}"
    echo -e "  Installing with sudo..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq "${MISSING_PKGS[@]}"
    success "System packages installed"
else
    success "All system packages present"
fi

# ── 3. Clone or update repo ───────────────────────────────────
# If we are already inside a git repo, just pull.
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Repo already exists at $INSTALL_DIR — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only
    success "Updated to latest"
elif [[ ! -f "$INSTALL_DIR/main.py" ]]; then
    info "Cloning Dosidicus into $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    success "Cloned successfully"
fi

cd "$INSTALL_DIR"

# ── 4. Create virtualenv ──────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    success "Virtual environment created"
else
    success "Virtual environment already exists"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── 5. Install Python dependencies ───────────────────────────
info "Installing Python dependencies..."
pip install --upgrade pip --quiet

if [[ -f "requirements.txt" ]]; then
    pip install -r requirements.txt --quiet
else
    pip install --quiet "PyQt5>=5.15" "numpy>=1.21"
fi

# Optional but recommended for PyQt5
pip install --quiet "pyqt5-sip" 2>/dev/null || true

success "Python packages installed"

# ── 6. Create launcher script ─────────────────────────────────
LAUNCHER="$INSTALL_DIR/run.sh"
cat > "$LAUNCHER" << LAUNCH
#!/usr/bin/env bash
DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
source "\$DIR/.venv/bin/activate"

# Fix for Qt/XCB issues on some Linux setups
export QT_QPA_PLATFORM="\${QT_QPA_PLATFORM:-xcb}"
# Crucial: This ensures main.py can find the 'src' folder
export PYTHONPATH="\$DIR:\$PYTHONPATH"

cd "\$DIR"
exec python3 main.py "\$@"
LAUNCH
chmod +x "$LAUNCHER"
success "Launcher script created: $LAUNCHER"

# ── 7. Create desktop shortcut (optional) ────────────────────
DESKTOP_FILE="$HOME/.local/share/applications/dosidicus.desktop"
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Name=Dosidicus
Comment=Tamagotchi squid with a neural network
Exec=$LAUNCHER
Icon=$INSTALL_DIR/images/icon.png
Terminal=false
Type=Application
Categories=Game;Simulation;
DESKTOP
success "Desktop shortcut created"

# ── 8. Done! ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  Setup complete!"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}To launch Dosidicus:${NC}"
echo -e "    ${CYAN}$LAUNCHER${NC}"
echo ""
echo -e "  ${BOLD}Or from any terminal:${NC}"
echo -e "    ${CYAN}cd $INSTALL_DIR && source .venv/bin/activate && python3 main.py${NC}"
echo ""
echo -e "  ${BOLD}Headless/training mode:${NC}"
echo -e "    ${CYAN}cd $INSTALL_DIR && source .venv/bin/activate && python3 headless/headless_trainer.py${NC}"
echo ""

# ── 9. Offer to launch now ────────────────────────────────────
read -rp "  Launch Dosidicus now? [y/N] " REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    info "Launching..."
    exec "$LAUNCHER"
fi
