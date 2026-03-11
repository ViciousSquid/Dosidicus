# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Install core dependencies needed by ALL targets
RUN python -m pip install --no-cache-dir numpy>=1.21

# ------------------------------
# Headless trainer target
# ------------------------------
FROM base AS headless
# Only copy what is needed for headless training
COPY headless/ ./headless/
COPY custom_brains/ ./custom_brains/

ENTRYPOINT ["python", "headless/headless_trainer.py"]
CMD ["--ticks", "10000", "--output", "trained_brain.json"]

# ------------------------------
# GUI target (requires X11)
# ------------------------------
FROM base AS gui
# Install system libraries for GUI support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libgl1-mesa-dri \
    libglib2.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxkbcommon-x11-0 \
    libxkbcommon0 \
    libxext6 \
    libxrender1 \
    libxrandr2 \
    libxfixes3 \
    libxdamage1 \
    libxi6 \
    libxcomposite1 \
    libxcursor1 \
    libxss1 \
    libxtst6 \
    libfontconfig1 \
    libfreetype6 \
    libnss3 \
    libdbus-1-3 \
    libxcb1 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxcb-cursor0 \
    libxshmfence1 \
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    && rm -rf /var/lib/apt/lists/*

# Install GUI-specific Python dependencies
RUN python -m pip install --no-cache-dir PyQt5>=5.15

# Copy the entire project for the GUI
COPY . .

ENV QT_X11_NO_MITSHM=1
ENTRYPOINT ["python", "main.py"]
