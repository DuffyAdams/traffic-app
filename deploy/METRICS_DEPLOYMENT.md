# Metrics Dashboard Deployment

This dashboard is a separate static web app served from `metrics.duffyadams.com`.
It reuses the existing traffic backend through `/api/dashboard_metrics` and `/api/incident_stats`.

## Files

- `metrics-app/index.html`
- `metrics-app/styles.css`
- `metrics-app/app.js`
- `deploy/nginx-metrics.duffyadams.com.conf`

## Nginx

Use the provided nginx config for the `metrics.duffyadams.com` vhost.
The site serves the static dashboard from `/home/ubuntu/projects/san-diego-traffic-watch/metrics-app` and proxies `/api/` to the existing backend on `127.0.0.1:5002`.

## Certbot

Bring up the HTTP vhost first, point DNS for `metrics.duffyadams.com` to the server, then issue a separate certificate for `metrics.duffyadams.com`.
