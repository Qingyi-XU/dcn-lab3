FROM python:3.11-slim

RUN apt-get update \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN groupadd -g 799 nyu && \
    useradd -r -u 999 -g nyu nyu

# Set up a working folder and install the pre-reqs
WORKDIR /app

# AS only uses the Python standard library (socket, json, os), no
# third-party packages are required.

USER nyu

COPY --chown=nyu:nyu . .

EXPOSE 53533/udp

CMD [ "python", "./app.py" ]
