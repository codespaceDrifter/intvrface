"""
Docker wrapper for agent containers with xvfb + noVNC.

noVNC flow (for human monitoring in browser):
    x11vnc inside container on port 5900 (internal)
    websockify bridges websocket:6080 to vnc:5900
    docker -p maps host_port:6080 so browser connects via localhost:host_port/vnc.html
    multi-agent: increment novnc_port for each (6080, 6081, 6082...)

Usage:
    c = Container("agent_1", novnc_port=6080)
    c.start()
    # open browser to localhost:6080/vnc.html

    c.screenshot()
    c.type_text("hello")
    c.click(1)
    c.run("ls /home")

    c.stop()
"""

import subprocess
import time
from pathlib import Path


DOCKERFILE = """
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# xvfb: virtual framebuffer (fake display for headless GUI)
# x11-apps: basic X11 apps for testing
# xdotool: simulate keyboard/mouse
# scrot: screenshots (for model perception)
# xterm: terminal emulator
# x11vnc: VNC server
# websockify + novnc: browser-based VNC client
RUN apt-get update && apt-get install -y \\
    xvfb \\
    x11-apps \\
    xdotool \\
    scrot \\
    xterm \\
    x11vnc \\
    novnc \\
    websockify \\
    && rm -rf /var/lib/apt/lists/*

# display :99 is inside container only (isolated per container)
ENV DISPLAY=:99

# start xvfb + vnc + websockify (6080->5900) + xterm with logging, keep alive
# websockify bridges websocket:6080 to vnc:5900 for noVNC
CMD Xvfb :99 -screen 0 1280x720x24 & \
    x11vnc -display :99 -forever -nopw -listen 0.0.0.0 -rfbport 5900 & \
    websockify --web /usr/share/novnc 6080 localhost:5900 & \
    sleep 1 && xterm -l -lf /home/agent/term.log & \
    sleep infinity
"""


# data stored in ~/intvrface/
WORKSPACE_ROOT = Path.home() / "intvrface" / "workspace"


class Container:
    """Controls a docker container with xvfb inside."""

    def __init__(self, name: str, image: str = "intvrface_sandbox", novnc_port: int = 6080):
        self.name = name
        self.image = image
        self.novnc_port = novnc_port  # browser connects to localhost:novnc_port/vnc.html
        self.workspace = WORKSPACE_ROOT / name
        self._running = False

    def build(self):
        """Build the docker image (run once)."""
        build_dir = Path.home() / "intvrface" / "docker_build"
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "Dockerfile").write_text(DOCKERFILE)

        print("Building docker image...")
        subprocess.run(
            ["docker", "build", "-t", self.image, str(build_dir)],
            check=True,
        )
        print(f"Image '{self.image}' built.")

    def start(self):
        """Start the container. Reuses existing container if present (persistent)."""
        # check if image exists, build if not
        result = subprocess.run(
            ["docker", "images", "-q", self.image],
            capture_output=True, text=True
        )
        if not result.stdout.strip():
            print(f"Image '{self.image}' not found, building...", flush=True)
            self.build()
        else:
            print(f"Image '{self.image}' already exists", flush=True)

        # check if container already exists
        result = subprocess.run(
            ["docker", "ps", "-a", "-q", "-f", f"name={self.name}"],
            capture_output=True, text=True
        )

        if result.stdout.strip():
            # container exists, just start it
            print(f"Container '{self.name}' already exists, resuming...", flush=True)
            subprocess.run(["docker", "start", self.name], check=True)
        else:
            # create new container
            print(f"Container '{self.name}' not found, creating...", flush=True)
            cmd = ["docker", "run", "-d", "--name", self.name,
                   "-p", f"{self.novnc_port}:6080"]  # expose websockify for noVNC

            assert self.workspace
            self.workspace.mkdir(parents=True, exist_ok=True)
            cmd.extend(["-v", f"{self.workspace.absolute()}:/home/agent", self.image])
            subprocess.run(cmd, check=True)

        # wait for xvfb to be ready (verify with xdotool)
        for _ in range(10):
            result = self.run("xdotool getdisplaygeometry")
            if "1280" in result:
                break
            time.sleep(0.5)
        self._running = True
        print(f"Container running. Workspace: {self.workspace}")

    def stop(self):
        """Stop the container (preserves state, can resume later)."""
        subprocess.run(["docker", "stop", self.name], capture_output=True)
        self._running = False
        print("Container stopped (state preserved).")

    def destroy(self):
        """Stop AND remove the container (lose all state)."""
        subprocess.run(["docker", "stop", self.name], capture_output=True)
        subprocess.run(["docker", "rm", self.name], capture_output=True)
        self._running = False
        print("Container destroyed.")

    def run(self, cmd: str) -> str:
        """Run a shell command inside the container, return output."""
        result = subprocess.run(
            ["docker", "exec", self.name, "bash", "-c", cmd],
            capture_output=True, text=True,
        )
        return result.stdout + result.stderr

    def screenshot(self) -> Path:
        """Take screenshot, return path in workspace."""
        self.run("mkdir -p /home/agent/screenshots")
        self.run("scrot /home/agent/screenshots/screen.png")
        return self.workspace / "screenshots" / "screen.png"

    def click(self, button: int = 1):
        """Click mouse button. 1=left, 3=right."""
        self.run(f"xdotool click {button}")

    def mousedown(self, button: int = 1):
        """Push down mouse button. 1=left, 3=right."""
        self.run(f"xdotool mousedown {button}")

    def mouseup(self, button: int = 1):
        """Release mouse button. 1=left, 3=right."""
        self.run(f"xdotool mouseup {button}")

    def scroll(self, direction: str):
        """Scroll up or down. xdotool uses click 4=up, 5=down."""
        button = 4 if direction == "up" else 5
        self.run(f"xdotool click {button}")

    def type_text(self, text: str):
        """Type text on keyboard."""
        # escape special chars for shell
        escaped = text.replace("'", "'\\''")
        self.run(f"xdotool type '{escaped}'")

    def key(self, key: str):
        """Press a key combo. e.g. 'Return', 'ctrl+c', 'alt+Tab'."""
        self.run(f"xdotool key {key}")

    def move(self, x: int, y: int):
        """Move mouse to x,y."""
        self.run(f"xdotool mousemove {x} {y}")
