
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    xvfb \
    x11-apps \
    xdotool \
    scrot \
    xterm \
    && rm -rf /var/lib/apt/lists/*

# start xvfb on display :99
ENV DISPLAY=:99

# entrypoint: start xvfb and keep container running
CMD Xvfb :99 -screen 0 1280x720x24 & sleep infinity
