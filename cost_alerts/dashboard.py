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


def deploy_dashboard_to_s3(session, account_id, region="eu-north-1", bucket_name=None):
    """
    Upload dashboard.html to an S3 bucket and return both static website
    and direct presigned access URLs.
    """
    s3 = session.client("s3", region_name=region)
    bucket = bucket_name or f"aws-cost-alerts-{account_id}"
    dashboard_path = get_dashboard_path()

    if not dashboard_path.exists():
        raise FileNotFoundError(f"Dashboard file not found at {dashboard_path}")

    print(f"Checking S3 bucket '{bucket}' in {region}...")
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": region}
            )
        print(f"Created S3 bucket: {bucket}")
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"Using existing S3 bucket: {bucket}")
        else:
            print(f"Note on bucket creation: {exc}")

    print(f"Uploading {dashboard_path.name} to s3://{bucket}/index.html...")
    s3.upload_file(
        str(dashboard_path),
        bucket,
        "index.html",
        ExtraArgs={"ContentType": "text/html"}
    )

    try:
        s3.put_bucket_website(
            Bucket=bucket,
            WebsiteConfiguration={"IndexDocument": {"Suffix": "index.html"}}
        )
    except Exception:
        pass

    website_url = f"http://{bucket}.s3-website.{region}.amazonaws.com"
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": "index.html"},
        ExpiresIn=604800,  # 7 days
    )

    print("\n" + "=" * 50)
    print("Dashboard Deployed Successfully to Amazon S3!")
    print(f"Public Website URL : {website_url}")
    print(f"Direct Access URL  : {presigned_url}")
    print("=" * 50)

    return {
        "bucket": bucket,
        "website_url": website_url,
        "presigned_url": presigned_url
    }

