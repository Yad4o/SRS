# Nginx Reverse Proxy + TLS Setup

Closes Issue #10 from the production-readiness review: the `nginx` service
in `docker-compose.yml` previously had no `nginx.conf` and no SSL
certificates to mount, so it would fail to start if uncommented. This doc
covers both local development and production TLS setup.

## What changed

- `nginx.conf` (repo root) — reverse proxy + TLS termination config.
  HTTP (port 80) redirects to HTTPS, except for the ACME HTTP-01 challenge
  path used by Certbot. HTTPS (port 443) terminates TLS and proxies to the
  `api` service on the internal Docker network.
- `ssl/` — empty directory (with a `README.md`) where cert material is
  mounted at runtime. Real certs/keys are gitignored — never commit them.
- `scripts/generate-dev-cert.sh` — generates a self-signed cert for local
  HTTPS testing.
- `docker-compose.yml` — the `nginx` service block is now active (it was
  previously commented out).

## Local development

```bash
./scripts/generate-dev-cert.sh
docker compose --env-file .env up -d
curl -k https://localhost/health
```

`-k` (or `--insecure`) is required for curl/browsers since the dev cert is
self-signed. This is expected and fine for local testing — never use a
self-signed cert in production.

## Production: Let's Encrypt / Certbot

1. Point your domain's DNS A record at the server's public IP.
2. Bring the stack up first **without** a cert so nginx can serve the
   HTTP-01 ACME challenge on port 80 (nginx will fail health checks on
   443 until a cert exists — that's fine for this bootstrap step; what
   matters is port 80 being reachable).
3. Run Certbot against the running nginx container, using the webroot
   method so it can write the challenge file to the path nginx already
   serves from (`/var/www/certbot`, referenced in `nginx.conf`):

   ```bash
   docker run --rm \
     -v "$(pwd)/ssl:/etc/letsencrypt/live/yourdomain.com" \
     -v certbot-webroot:/var/www/certbot \
     certbot/certbot certonly --webroot \
     -w /var/www/certbot \
     -d yourdomain.com \
     --email you@yourdomain.com --agree-tos --no-eff-email
   ```

4. Certbot writes `fullchain.pem` and `privkey.pem` into the mounted
   `ssl/` directory. Restart nginx so it picks up the new cert:

   ```bash
   docker compose restart nginx
   ```

5. **Renewal**: Let's Encrypt certs expire every 90 days. Add a cron job
   (or systemd timer) that re-runs `certbot renew` and reloads nginx,
   e.g. a nightly cron entry:

   ```cron
   0 3 * * * docker run --rm -v /path/to/ssl:/etc/letsencrypt/live/yourdomain.com certbot/certbot renew --webroot -w /var/www/certbot && docker compose -f /path/to/docker-compose.yml restart nginx
   ```

## Production: managed certificate (cloud load balancer / provider)

If you're fronting the stack with a cloud load balancer (AWS ALB, GCP Load
Balancer, Cloudflare, Render/Railway's built-in TLS, etc.) that already
terminates TLS for you, you generally don't need the `nginx` service at
all — point the load balancer directly at the `api` container's port 8000
and skip this section entirely. Use whichever model fits your hosting
provider; both are valid.

## Security notes

- `nginx.conf` pins `ssl_protocols TLSv1.2 TLSv1.3` — older TLS versions
  are disabled.
- `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`,
  and `Referrer-Policy` headers are set at the proxy layer as
  defence-in-depth on top of the app's own handling.
- A `limit_req_zone` is configured at the nginx layer as an additional
  abuse-prevention layer in front of the app's own SlowAPI rate limiting
  (`AUTH_RATE_LIMIT_LOGIN`, `AUTH_RATE_LIMIT_FORGOT_PASSWORD`, etc.) —
  these are independent, complementary controls, not a replacement for
  each other.
- Never commit `ssl/fullchain.pem` or `ssl/privkey.pem` — both are
  gitignored. If a key is ever committed by mistake, treat it as
  compromised: revoke/reissue the certificate, don't just delete it from
  a future commit (git history retains it).
