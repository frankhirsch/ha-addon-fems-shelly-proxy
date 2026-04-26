ARG BUILD_FROM
FROM ${BUILD_FROM:-python:3.12-alpine}

# iproute2 für ip addr add/del (IP-Aliase)
RUN apk add --no-cache iproute2 py3-pip py3-aiohttp

WORKDIR /app
COPY shelly_proxy.py .
COPY run.sh .
COPY config.yaml .
RUN chmod +x run.sh

ENTRYPOINT ["/app/run.sh"]
