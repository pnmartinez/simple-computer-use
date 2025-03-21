FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1 \
    XAUTHORITY=/tmp/.Xauthority \
    LANG=C.UTF-8 \
    LANGUAGE=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    xvfb x11-utils xauth x11-apps x11vnc \
    scrot imagemagick wmctrl xdotool fluxbox \
    git wget curl unzip \
    libgl1-mesa-glx libegl1-mesa libxrandr2 \
    libxss1 libxxf86vm1 libxi6 \
    libxtst6 libxt6 libxfixes3 \
    ffmpeg libsm6 libxext6 libgl1-mesa-dri \
    software-properties-common \
    gnome-screenshot python3-pil python3-pil.imagetk \
    xserver-xorg-video-dummy \
    python3-tk python3-dev \
    locales && \
    locale-gen en_US.UTF-8 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt /app/

# Install any needed Python packages
RUN pip3 install --no-cache-dir -r requirements.txt && \
    pip3 install --no-cache-dir --upgrade pillow pyautogui pydbus python-xlib

# Copy the current directory contents into the container at /app
COPY . /app/

# Create directories for X11
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix

# Create an entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint to a script that starts Xvfb and the voice control server
ENTRYPOINT ["/app/entrypoint.sh"]
