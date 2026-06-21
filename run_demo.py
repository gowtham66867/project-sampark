from __future__ import annotations

import argparse
import json
import mimetypes
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sampark.console import print_run
from sampark.core.impact import project_impact
from sampark.core.orchestrator import SamparkOrchestrator
from sampark.data.mock_data import get_bank_mitra, get_customer, list_customers

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "sampark" / "web"


class SamparkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/customers":
            self.write_json([asdict(customer) for customer in list_customers()])
            return
        if parsed.path == "/api/run":
            customer_id = parse_qs(parsed.query).get("customer", ["c001"])[0]
            try:
                customer = get_customer(customer_id)
            except KeyError:
                self.write_json({"error": "unknown_customer", "customer_id": customer_id}, status=404)
                return
            run = SamparkOrchestrator().run(customer, get_bank_mitra())
            payload = run.to_dict()
            payload["impact"] = project_impact()
            self.write_json(payload)
            return
        self.serve_static(parsed.path)

    def write_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        target = WEB / ("index.html" if path in ("/", "") else path.lstrip("/"))
        if not target.exists() or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), SamparkHandler)
    print(f"Project Sampark console running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Project Sampark console.")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Project Sampark prototype.")
    parser.add_argument("--cli", action="store_true", help="Print a CLI demo instead of opening the web console.")
    parser.add_argument("--customer", default="c001", choices=[f"c{index:03d}" for index in range(1, 11)])
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()

    if args.cli:
        print_run(args.customer)
    else:
        serve(args.port)


if __name__ == "__main__":
    main()
