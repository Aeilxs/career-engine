"""Validate the human-approved Compose envelope (does not need a Docker daemon)."""

import json
import subprocess
import sys
from pathlib import Path


def fail(reason: str) -> None:
    raise SystemExit(f"Runtime contract failed: {reason}")


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    compose = json.loads(result.stdout)
    services = compose.get("services", {})
    if set(services) != {"app"}:
        fail(f"expected exactly one app service, got {list(services)}")
    app = services["app"]
    if app.get("privileged", False) or app.get("network_mode") == "host":
        fail("privileged mode or host networking is forbidden")
    if "ALL" not in app.get("cap_drop", []):
        fail("must drop all Linux capabilities")
    published = app.get("ports", [])
    if len(published) != 1:
        fail("expected one localhost-only published port")
    port = published[0]
    if port.get("host_ip") != "127.0.0.1" or int(port.get("target", 0)) != 8000:
        fail("expected host 127.0.0.1 -> container port 8000")
    mounts = app.get("volumes", [])
    persistent = [mount for mount in mounts if mount.get("target") == "/data"]
    if len(persistent) != 1 or persistent[0].get("type") != "bind":
        fail("/data must have exactly one local bind mount")
    source = Path(persistent[0]["source"])
    if source != repo / "data":
        fail("/data must bind ./data from repo host")
    env = app.get("environment", {})
    if env.get("CAREER_DATA_DIR") != "/data":
        fail("application data directory must be /data")
    print("Runtime contract PASS: single container, localhost, local bind mount, nonprivileged")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stderr, file=sys.stderr)
        raise SystemExit(error.returncode) from error
