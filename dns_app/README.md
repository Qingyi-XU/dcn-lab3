# dns_app

Simplified authoritative DNS system (Lab 3, Problem 2) made of three services.

- `AS/` Authoritative Server: UDP port 53533, stores and answers Type A records.
- `FS/` Fibonacci Server: HTTP port 9090, `PUT /register` and `GET /fibonacci?number=X`.
- `US/` User Server: HTTP port 8080, `GET /fibonacci?hostname=&fs_port=&number=&as_ip=&as_port=`.
- `deploy_dns.yml` Kubernetes deployment (extra credit), nodePorts AS 30001, FS 30002, US 30003.

Each subfolder has its own Dockerfile. Example (Docker user-defined network):

    docker network create lab3
    docker build -t <user>/as:latest ./AS
    docker build -t <user>/fs:latest ./FS
    docker build -t <user>/us:latest ./US
    docker run -d --network lab3 --name as -p 53533:53533/udp <user>/as:latest
    docker run -d --network lab3 --name fs -p 9090:9090 <user>/fs:latest
    docker run -d --network lab3 --name us -p 8080:8080 <user>/us:latest
    docker inspect lab3        # read the container IPs

Register the Fibonacci Server with the AS:

    curl -X PUT http://localhost:9090/register -H "Content-Type: application/json" \
      -d '{"hostname":"fibonacci.com","ip":"<FS_IP>","as_ip":"<AS_IP>","as_port":"53533"}'

Query through the User Server:

    curl "http://localhost:8080/fibonacci?hostname=fibonacci.com&fs_port=9090&number=10&as_ip=<AS_IP>&as_port=53533"
