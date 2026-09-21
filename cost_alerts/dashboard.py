"""Dashboard launcher and utilities for AWS Cost Alerts."""

from pathlib import Path
import webbrowser
import http.server
import socketserver


def get_dashboard_path():
    """Return the absolute Path to the packaged dashboard.html."""
    return Path(__file__).parent / "dashboard.html"


def launch_dashboard(port=8000, open_browser=True, serve=False):
    """
    Launch or serve the interactive cost alerts dashboard.
    If serve=True, starts a local HTTP server and opens http://localhost:{port}.
    Otherwise opens the local dashboard.html directly in the default browser.
    """
    dashboard_path = get_dashboard_path()
    if not dashboard_path.exists():
        raise FileNotFoundError(f"Dashboard file not found at {dashboard_path}")

    if serve:
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(dashboard_path.parent), **kwargs)

            def log_message(self, format, *args):
                pass  # suppress standard access logs

        url = f"http://localhost:{port}/dashboard.html"
        print(f"Serving dashboard at: {url}")
        print("Press Ctrl+C to stop the server.")

        server = socketserver.TCPServer(("", port), QuietHandler)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard server stopped.")
        finally:
            server.server_close()
        return url

    url = dashboard_path.as_uri()
    print(f"Opening dashboard in browser: {url}")
    if open_browser:
        webbrowser.open(url)
    return url
