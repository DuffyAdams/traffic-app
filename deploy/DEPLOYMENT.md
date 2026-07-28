# Deployment Notes

This app is designed to run the Python backend on `127.0.0.1:5002` and put Nginx in front of it.

## Files

- `deploy/traffic-app.service`
- `deploy/nginx-traffic-app.conf`

## Assumptions

- Server OS is Ubuntu or Debian.
- The repo is located at `/home/ubuntu/projects/san-diego-traffic-watch`.
- The backend uses the existing `.env` file in the repo root.

## Nginx

Use the provided config as the vhost for `traffic-app.duffyadams.com`.
The HTTP server block redirects to HTTPS and leaves an ACME challenge path available for Certbot.

## systemd

The service file starts the backend package with `python -m backend` and keeps it running.
It expects the virtual environment at `/home/ubuntu/projects/san-diego-traffic-watch/venv`.
