# docker-lab-server

Playground for docker home lab server config.

This repository is home to my home lab docker server configuration.

This server runs Ubuntu 24 as a virtual machine on my Proxmox server.

## Services

These are the services currently configured and running on this server.

- Traefik - Reverse proxy and tls provider.
- Portainer - Dashboard to view and manage running containers.
- LiteLLM - LLM Proxy Server.

## Planned Additions

These are the services I plan to add to this server or ideas for services to add.

- Watchtower - Automatic updates for running containers
- Grafana, Prometheus, cAdvisor, node_exporter - Monitoring system
- OpenWeb-UI - LLM Chat Client (Currently running as an LXC but could be migrated here)

## Setup

1. Install Docker (Using Ubuntu App store)
2. Setup traefik shared network

```bash
sudo docker network create traefiknet
```

3. Navigate to the folder of the service you want to run. (Usually start with traefik)
    1. If needed, create a .env file with any secrets or config.
    1. Run the docker compose command to start the container in the background:
        ```bash
        sudo docker compose up -d
        ```
    3. Repeate for any other services.

