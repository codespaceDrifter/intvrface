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
import hashlib
import time
from pathlib import Path

DOCKERFILE = """
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# xvfb: virtual framebuffer (fake display for headless GUI)
# x11-apps: basic X11 apps for testing
# xdotool: simulate keyboard/mouse
# imagemagick: screenshots via import command (scrot doesn't work with xvfb)
# xterm: terminal emulator
# x11vnc: VNC server
# websockify + novnc: browser-based VNC client
RUN apt-get update && apt-get install -y \\
    xvfb \\
    x11-apps \\
    xdotool \\
    imagemagick \\
    xterm \\
    x11vnc \\
    novnc \\
    websockify \\
    firefox \\
    openbox \\
    && rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99
ENV MOZ_DISABLE_CONTENT_SANDBOX=1
"""

# startup command — passed at runtime, change freely without rebuild
STARTUP_CMD = (
    "Xvfb :99 -screen 0 1280x720x24 & "
    "sleep 2 && "
    # disable X11 screen blanking/screensaver (semicolons so failure doesn't break chain)
    "xset s off; xset -dpms; "
    "x11vnc -display :99 -forever -nopw -listen 0.0.0.0 -rfbport 5900 & "
    "websockify --web /usr/share/novnc 6080 localhost:5900 & "
    # openbox: lightweight window manager (alt+Tab, alt+F4, window decorations)
    "openbox & "
    # script -f: logs terminal to file with immediate flush (xterm -l has buffering issues)
    "sleep 3 && xterm -e 'script -f /home/agent/term.log' & "
    "sleep infinity"
)


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

    def _dockerfile_hash(self) -> str:
        return hashlib.md5(DOCKERFILE.encode()).hexdigest()[:12]

    def build(self):
        """Build the docker image. Writes hash to detect changes."""
        build_dir = Path.home() / "intvrface" / "docker_build"
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "Dockerfile").write_text(DOCKERFILE)

        print("Building docker image...")
        subprocess.run(
            ["docker", "build", "-t", self.image, str(build_dir)],
            check=True,
        )
        # store hash so we know when Dockerfile changes
        (build_dir / "hash").write_text(self._dockerfile_hash())
        print(f"Image '{self.image}' built.")

    def _needs_rebuild(self) -> bool:
        """Check if image is missing or Dockerfile changed since last build."""
        result = subprocess.run(
            ["docker", "images", "-q", self.image],
            capture_output=True, text=True
        )
        if not result.stdout.strip():
            return True
        hash_file = Path.home() / "intvrface" / "docker_build" / "hash"
        if not hash_file.exists():
            return True
        return hash_file.read_text().strip() != self._dockerfile_hash()

    def start(self):
        """Start the container. Auto-rebuilds image if Dockerfile changed."""
        if self._needs_rebuild():
            # nuke old containers using this image — they're stale
            print("Dockerfile changed or image missing, rebuilding...", flush=True)
            self._cleanup_all_containers()
            subprocess.run(["docker", "rmi", self.image], capture_output=True)
            self.build()

        # check if container already exists
        result = subprocess.run(
            ["docker", "ps", "-a", "-q", "-f", f"name=^{self.name}$"],
            capture_output=True, text=True
        )

        if result.stdout.strip():
            print(f"Container '{self.name}' exists, resuming...", flush=True)
            subprocess.run(["docker", "start", self.name], check=True)
        else:
            print(f"Creating container '{self.name}'...", flush=True)
            self.workspace.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                "docker", "run", "-d", "--name", self.name,
                "-p", f"{self.novnc_port}:6080",
                "-v", f"{self.workspace.absolute()}:/home/agent",
                self.image,
                "bash", "-c", STARTUP_CMD,
            ], check=True)

        # wait for xvfb to be ready
        for _ in range(10):
            result = self.run("xdotool getdisplaygeometry")
            if "1280" in result:
                break
            time.sleep(0.5)
        # wait for xterm to spawn then focus it once
        # windowfocus works without a WM (windowactivate doesn't)
        for _ in range(10):
            result = self.run("xdotool search --class XTerm")
            if result.strip():
                wid = result.strip().split('\n')[0]
                self.run(f"xdotool windowfocus --sync {wid}")
                break
            time.sleep(0.5)
        self._running = True
        print(f"Container running. Workspace: {self.workspace}")

    def _cleanup_all_containers(self):
        """Remove all containers using this image (for rebuild)."""
        result = subprocess.run(
            ["docker", "ps", "-a", "-q", "--filter", f"ancestor={self.image}"],
            capture_output=True, text=True
        )
        for cid in result.stdout.strip().split('\n'):
            if cid:
                subprocess.run(["docker", "rm", "-f", cid], capture_output=True)

    def stop(self):
        """Stop the container (preserves state, can resume later)."""
        subprocess.run(["docker", "stop", self.name], capture_output=True)
        self._running = False
        print("Container stopped (state preserved).")

    def destroy(self):
        """Stop AND remove the container, workspace, and context."""
        # clean root-owned workspace files via a temporary container
        if self.workspace.exists():
            subprocess.run([
                "docker", "run", "--rm",
                "-v", f"{self.workspace.absolute()}:/cleanup",
                "ubuntu:22.04", "rm", "-rf", "/cleanup"
            ], capture_output=True)
        subprocess.run(["docker", "stop", self.name], capture_output=True)
        subprocess.run(["docker", "rm", self.name], capture_output=True)
        self._running = False
        import shutil
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        context_dir = Path.home() / "intvrface" / "context" / self.name
        if context_dir.exists():
            shutil.rmtree(context_dir)
        print("Container destroyed.")

    def run(self, cmd: str) -> str:
        """Run a shell command inside the container, return output."""
        result = subprocess.run(
            ["docker", "exec", self.name, "bash", "-c", cmd],
            capture_output=True, text=True,
        )
        return result.stdout + result.stderr

    def read_file(self, path: str) -> str:
        """Read a file inside the container. No shell involved."""
        result = subprocess.run(
            ["docker", "exec", self.name, "cat", path],
            capture_output=True, text=True,
        )
        return result.stdout

    def write_file(self, path: str, content: str):
        """Write content to a file inside the container via stdin. No shell escaping needed."""
        self.run(f"mkdir -p $(dirname '{path}')")
        subprocess.run(
            ["docker", "exec", "-i", self.name, "tee", path],
            input=content.encode(),
            capture_output=True,
        )

    def screenshot(self) -> Path:
        """Take screenshot, return path in workspace."""
        self.run("mkdir -p /home/agent/screenshots")
        # xwd reads framebuffer silently (no focus stealing), convert does no X11
        self.run("xwd -root -silent | convert xwd:- png:/home/agent/screenshots/screen.png")
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
        escaped = text.replace("'", "'\\''")
        self.run(f"xdotool type '{escaped}'")

    def key(self, combo: str):
        """Press a key combo. e.g. 'Return', 'ctrl+c', 'alt+Tab'."""
        self.run(f"xdotool key {combo}")

    def move(self, x: int, y: int):
        """Move mouse to x,y."""
        self.run(f"xdotool mousemove {x} {y}")
