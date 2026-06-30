# ssl/

This directory is where nginx expects TLS certificate material at runtime:

```
ssl/fullchain.pem   — certificate (+ chain)
ssl/privkey.pem     — private key
```

**Never commit real certificates or private keys to this repo.** Both
filenames above are excluded via `.gitignore`. This directory exists only
so the path is present for the `./ssl:/etc/nginx/ssl:ro` volume mount in
`docker-compose.yml`.

- **Local development:** run `./scripts/generate-dev-cert.sh` to generate a
  self-signed cert here.
- **Production:** issue a real certificate (Let's Encrypt/Certbot or your
  provider's managed cert) and place it here, or mount it from wherever
  your provider stores it. See `docs/deployment/NGINX.md`.
