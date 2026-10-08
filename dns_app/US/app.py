"""
User Server (US) for the simplified DNS-style system.

HTTP endpoint (Flask), listening on port 8080:

  GET /fibonacci?hostname=fibonacci.com&fs_port=9090&number=10&as_ip=Y&as_port=Z

  Required query parameters: hostname, fs_port, number, as_ip, as_port.
  If any is missing, returns 400.

  Otherwise, US:
    1. Sends a DNS query to the Authoritative Server at (as_ip, as_port)
       over UDP, using the simplified message format:
           TYPE=A
           NAME=<hostname>
    2. Parses the AS response ("TYPE=A\\nNAME=... VALUE=<ip> TTL=<ttl>\\n")
       to obtain the Fibonacci Server's IP address.
    3. Calls the resolved Fibonacci Server: GET http://<ip>:<fs_port>/fibonacci?number=<number>
    4. Relays the Fibonacci Server's status code and JSON body back to the
       original caller.

  If the hostname cannot be resolved (AS returns STATUS=404, or times out),
  US returns 404. If the resolved Fibonacci Server cannot be reached,
  US returns 502.
"""

import os
import socket

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

UDP_TIMEOUT_SECONDS = 3.0
HTTP_TIMEOUT_SECONDS = 5.0

REQUIRED_PARAMS = ["hostname", "fs_port", "number", "as_ip", "as_port"]


def build_query_message(hostname, type_="A"):
    return f"TYPE={type_}\nNAME={hostname}\n".encode("utf-8")


def parse_dns_response(data):
    """Parse an AS response into a dict of uppercase keys.

    Handles both the query-success format
        TYPE=A
        NAME=<name> VALUE=<ip> TTL=<ttl>
    and the plain status format
        STATUS=<code>
    """
    text = data.decode("utf-8", errors="replace")
    lines = [ln for ln in text.split("\n") if ln.strip() != ""]
    fields = {}
    for line in lines:
        for token in line.split():
            if "=" in token:
                k, v = token.split("=", 1)
                fields[k.strip().upper()] = v.strip()
    return fields


@app.route("/fibonacci", methods=["GET"])
def get_fibonacci():
    missing = [p for p in REQUIRED_PARAMS if not request.args.get(p)]
    if missing:
        return jsonify({"error": "missing required query parameter(s)", "missing": missing}), 400

    hostname = request.args.get("hostname")
    number = request.args.get("number")
    as_ip = request.args.get("as_ip")

    try:
        fs_port = int(request.args.get("fs_port"))
        as_port = int(request.args.get("as_port"))
    except ValueError:
        return jsonify({"error": "fs_port and as_port must be integers"}), 400

    # Step 1-2: resolve hostname via the Authoritative Server (DNS query over UDP).
    query = build_query_message(hostname)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT_SECONDS)
    try:
        sock.sendto(query, (as_ip, as_port))
        data, _ = sock.recvfrom(4096)
    except socket.timeout:
        return jsonify({"error": "authoritative server did not respond"}), 504
    finally:
        sock.close()

    fields = parse_dns_response(data)
    resolved_ip = fields.get("VALUE")
    if not resolved_ip:
        return jsonify({"error": f"could not resolve hostname '{hostname}'",
                         "as_response": data.decode("utf-8", errors="replace")}), 404

    # Step 3: call the resolved Fibonacci Server.
    fs_url = f"http://{resolved_ip}:{fs_port}/fibonacci"
    try:
        resp = requests.get(fs_url, params={"number": number}, timeout=HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return jsonify({"error": "fibonacci server unreachable", "detail": str(exc)}), 502

    # Step 4: relay the Fibonacci Server's response back to the caller.
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    return jsonify(body), resp.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("US_PORT", "8080")))
