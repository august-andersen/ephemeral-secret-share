import argparse
import getpass
import logging
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from .crypto import encrypt_secret
from .server import create_app, start_cleanup_thread, store_secret


def parse_duration(s: str) -> timedelta:
    m = re.fullmatch(r"(\d+)\s*(h|m)", s.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"Invalid duration '{s}'. Use format like 1h, 30m, 24h."
        )
    value, unit = int(m.group(1)), m.group(2)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(minutes=value)


def _ensure_cloudflared():
    """Check if cloudflared is installed, auto-install via brew if not."""
    if shutil.which("cloudflared"):
        return True

    if not shutil.which("brew"):
        print("Error: cloudflared is not installed and brew is not available.", file=sys.stderr)
        print("Install it manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/", file=sys.stderr)
        print("Or use --local to run without a tunnel.", file=sys.stderr)
        return False

    print("Installing cloudflared via brew...")
    result = subprocess.run(["brew", "install", "cloudflared"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to install cloudflared: {result.stderr}", file=sys.stderr)
        return False

    print("cloudflared installed.")
    return True


def _wait_for_port(port: int, timeout: float = 5.0):
    """Wait until the local port is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _start_tunnel(port: int) -> tuple[subprocess.Popen, str | None]:
    """Start cloudflared tunnel and return (process, public_url)."""
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    url = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        line = proc.stderr.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue
        text = line.decode("utf-8", errors="replace")
        match = re.search(r"(https://[a-zA-Z0-9-]+\.trycloudflare\.com)", text)
        if match and "api.trycloudflare" not in match.group(1):
            url = match.group(1)
            break

    # Drain stderr in background so the process doesn't block
    def _drain():
        try:
            for _ in proc.stderr:
                pass
        except Exception:
            pass
    threading.Thread(target=_drain, daemon=True).start()

    return proc, url


def _make_server(app, host, port):
    """Create a werkzeug server without printing the startup banner."""
    from werkzeug.serving import make_server
    return make_server(host, port, app)


def main():
    parser = argparse.ArgumentParser(
        prog="ess",
        description="Share secrets via one-time links. Client-side encrypted.",
    )
    parser.add_argument("secret", nargs="?", help="The secret text to share.")
    parser.add_argument(
        "--expires", "-e", type=parse_duration, default=None,
        help="Time until the secret expires (e.g., 1h, 30m, 24h).",
    )
    parser.add_argument(
        "--port", "-p", type=int, default=8080,
        help="Port to run the server on (default: 8080).",
    )
    parser.add_argument(
        "--local", "-l", action="store_true",
        help="Run on localhost only (no public tunnel).",
    )
    args = parser.parse_args()

    # Get the secret
    if args.secret:
        secret = args.secret
    elif not sys.stdin.isatty():
        secret = sys.stdin.read().rstrip("\n")
    else:
        secret = getpass.getpass("Enter secret: ")

    if not secret:
        print("Error: No secret provided.", file=sys.stderr)
        sys.exit(1)

    # Encrypt
    secret_id = uuid.uuid4().hex[:8]
    ciphertext_b64, key_b64url = encrypt_secret(secret)

    # Compute expiry
    expires_at = None
    if args.expires:
        expires_at = datetime.now(timezone.utc) + args.expires

    # Store
    store_secret(secret_id, ciphertext_b64, expires_at)

    # Suppress Flask/werkzeug logs
    start_cleanup_thread()
    app = create_app()
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    tunnel_proc = None
    base_url = f"http://localhost:{args.port}"

    if not args.local:
        if not _ensure_cloudflared():
            sys.exit(1)

        # Start Flask in a background thread using make_server (no banner)
        srv = _make_server(app, "127.0.0.1", args.port)
        server_thread = threading.Thread(target=srv.serve_forever, daemon=True)
        server_thread.start()

        # Wait for Flask to be ready before starting tunnel
        if not _wait_for_port(args.port):
            print("Error: Server failed to start.", file=sys.stderr)
            sys.exit(1)

        print("Starting tunnel...", flush=True)
        tunnel_proc, public_url = _start_tunnel(args.port)

        if not public_url:
            print("Error: Failed to get public URL from cloudflared.", file=sys.stderr)
            tunnel_proc.kill()
            sys.exit(1)

        base_url = public_url

    # Build link
    link = f"{base_url}/s/{secret_id}#{key_b64url}"

    print(flush=True)
    print("Secret encrypted and stored.", flush=True)
    print(flush=True)
    print("Share this link (one-time use):", flush=True)
    print(f"  {link}", flush=True)
    print(flush=True)
    if args.expires:
        total_seconds = int(args.expires.total_seconds())
        if total_seconds >= 3600:
            label = f"{total_seconds // 3600} hour{'s' if total_seconds >= 7200 else ''}"
        else:
            label = f"{total_seconds // 60} minute{'s' if total_seconds >= 120 else ''}"
        print(f"Expires in {label} if not viewed.", flush=True)
        print(flush=True)
    print(f"Server running on port {args.port} — press Ctrl+C to stop.", flush=True)
    print("Waiting for secret to be viewed...", flush=True)

    try:
        if args.local:
            app.run(host="0.0.0.0", port=args.port)
        else:
            server_thread.join()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        if tunnel_proc:
            tunnel_proc.terminate()
            tunnel_proc.wait()
