"""
Fibonacci Server (FS) for the simplified DNS-style system.

HTTP endpoints (Flask), listening on port 9090:

  PUT /register
      Body (JSON): {"hostname": "...", "ip": "...", "as_ip": "...", "as_port": "..."}
      Registers <hostname> -> <ip> with the Authoritative Server (AS) over
      UDP, using the simplified DNS message format:
          TYPE=A
          NAME=<hostname> VALUE=<ip> TTL=10
      Returns 201 on success (per the lab handout), 400 if the request body
      is missing any of the four required fields, 502 if the AS rejects the
      registration, and 504 if the AS does not respond in time.

  GET /fibonacci?number=X
      Returns the Fibonacci number for sequence index X as JSON with status
      200, or 400 if X is missing or not a non-negative integer.
"""

import json
import os
import socket

from flask import Flask, jsonify, request

app = Flask(__name__)

AS_TTL_DEFAULT = "10"
UDP_TIMEOUT_SECONDS = 3.0


def build_registration_message(hostname, ip, ttl=AS_TTL_DEFAULT, type_="A"):
    return f"TYPE={type_}\nNAME={hostname} VALUE={ip} TTL={ttl}\n".encode("utf-8")


def parse_status(data):
    """Parse a 'STATUS=<code>' response from the AS into an int, or None."""
    text = data.decode("utf-8", errors="replace")
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("STATUS="):
            try:
                return int(line.split("=", 1)[1])
            except ValueError:
                return None
    return None


def fibonacci(n):
    """Iterative Fibonacci, fib(0) = 0, fib(1) = 1, fib(n) = fib(n-1) + fib(n-2)."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@app.route("/register", methods=["PUT"])
def register():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "request body must be JSON"}), 400

    required = ["hostname", "ip", "as_ip", "as_port"]
    missing = [f for f in required if f not in body or body[f] in (None, "")]
    if missing:
        return jsonify({"error": "missing required field(s)", "missing": missing}), 400

    hostname = body["hostname"]
    ip = body["ip"]
    as_ip = body["as_ip"]
    try:
        as_port = int(body["as_port"])
    except (TypeError, ValueError):
        return jsonify({"error": "as_port must be an integer"}), 400

    message = build_registration_message(hostname, ip)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT_SECONDS)
    try:
        sock.sendto(message, (as_ip, as_port))
        data, _ = sock.recvfrom(4096)
    except socket.timeout:
        return jsonify({"error": "authoritative server did not respond"}), 504
    finally:
        sock.close()

    status = parse_status(data)
    if status == 201:
        return jsonify({"message": f"{hostname} registered with AS"}), 201
    return jsonify({"error": "registration rejected by authoritative server",
                     "as_response": data.decode("utf-8", errors="replace")}), 502


@app.route("/fibonacci", methods=["GET"])
def get_fibonacci():
    number_str = request.args.get("number")
    if number_str is None:
        return jsonify({"error": "missing required query parameter: number"}), 400
    try:
        n = int(number_str)
    except ValueError:
        return jsonify({"error": "number must be an integer"}), 400
    if n < 0:
        return jsonify({"error": "number must be a non-negative integer"}), 400

    return jsonify({"number": n, "fibonacci": fibonacci(n)}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("FS_PORT", "9090")))
