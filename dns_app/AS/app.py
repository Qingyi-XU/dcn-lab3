"""
Authoritative Server (AS) for the simplified DNS-style system.

Listens on UDP port 53533 for two kinds of messages, distinguished by
whether a VALUE field is present:

  Registration request (from a Fibonacci Server):
      TYPE=A
      NAME=fibonacci.com VALUE=172.18.0.2 TTL=10

  DNS query (from a User Server):
      TYPE=A
      NAME=fibonacci.com

Records are persisted to a JSON file on disk (AS_DATA_FILE, default
/app/records.json) so that they survive process restarts, per the lab's
hint to store registrations "somewhere persistent, for example in a file".

Response formats (design choices not fully specified by the lab handout,
documented here since the handout only specifies the query-success format):
  - Successful registration : "STATUS=201\n"
  - Malformed registration   : "STATUS=400\n"
  - Successful query         : "TYPE=A\nNAME=<name> VALUE=<value> TTL=<ttl>\n"
  - Query for unknown name   : "STATUS=404\n"
  - Any other malformed msg  : "STATUS=400\n"
"""

import json
import os
import socket

HOST = "0.0.0.0"
PORT = int(os.environ.get("AS_PORT", "53533"))
DATA_FILE = os.environ.get("AS_DATA_FILE", "/app/records.json")


def load_records():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_records(records):
    tmp_path = DATA_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(records, f, indent=2)
    os.replace(tmp_path, DATA_FILE)


def parse_message(data):
    """Parse the simplified DNS-style message into a dict of uppercase keys.

    Line 1 is "TYPE=<type>". Line 2 is one or more space-separated
    KEY=VALUE tokens (NAME=..., and optionally VALUE=... TTL=...).
    """
    text = data.decode("utf-8", errors="replace")
    lines = [ln for ln in text.split("\n") if ln.strip() != ""]
    fields = {}
    if not lines:
        return fields
    if "=" in lines[0]:
        k, v = lines[0].split("=", 1)
        fields[k.strip().upper()] = v.strip()
    if len(lines) > 1:
        for token in lines[1].split():
            if "=" in token:
                k, v = token.split("=", 1)
                fields[k.strip().upper()] = v.strip()
    return fields


def build_query_response(name, value, ttl, type_="A"):
    return f"TYPE={type_}\nNAME={name} VALUE={value} TTL={ttl}\n".encode("utf-8")


def build_status(code):
    return f"STATUS={code}\n".encode("utf-8")


def handle_message(data, records):
    fields = parse_message(data)
    name = fields.get("NAME")
    type_ = fields.get("TYPE", "A")

    if not name or not type_:
        return build_status(400), records, False

    if "VALUE" in fields:
        # Registration request.
        ttl = fields.get("TTL", "10")
        records[name] = {"type": type_, "value": fields["VALUE"], "ttl": ttl}
        return build_status(201), records, True

    # DNS query (no VALUE supplied).
    record = records.get(name)
    if record is None:
        return build_status(404), records, False
    return build_query_response(name, record["value"], record["ttl"], record.get("type", type_)), records, False


def main():
    records = load_records()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"[AS] Authoritative Server listening on UDP {HOST}:{PORT}, "
          f"data file: {DATA_FILE}", flush=True)

    while True:
        data, addr = sock.recvfrom(4096)
        response, records, changed = handle_message(data, records)
        if changed:
            save_records(records)
        sock.sendto(response, addr)
        print(f"[AS] {addr} -> {data!r}  ==>  {response!r}", flush=True)


if __name__ == "__main__":
    main()
