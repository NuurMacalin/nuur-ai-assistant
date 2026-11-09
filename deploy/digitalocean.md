# DigitalOcean deployment

This project runs on a Linux Droplet with Docker Engine and the Docker Compose
plugin. Deployment is prepared here; creating a Droplet and changing DNS are
separate actions. DigitalOcean access is not stored in this repository.

## Prepare the Droplet

1. Create an Ubuntu Droplet with Docker installed, or install Docker Engine and
   the Compose plugin on an existing Droplet.
2. Add your SSH public key when creating the Droplet. Keep the private key on
   your own computer.
3. Point your chosen domain's A record at the Droplet IP. Open inbound TCP ports
   22, 80, and 443. Qdrant is accessible only within the Docker network.
4. Connect using your SSH client:

```sh
ssh root@YOUR_DROPLET_IP
git clone https://github.com/NuurMacalin/nuur-ai-assistant.git
cd nuur-ai-assistant
cp .env.example app/.env
chmod 600 app/.env
nano app/.env
```

Set a working `GOOGLE_API_KEY` and change `SITE_ADDRESS` to the real hostname,
for example `ai.your-domain.com`. The server environment is excluded from both
Git and the Docker build context.

## Transfer the knowledge documents privately

PDFs are not published in GitHub or baked into the app image. The local Qdrant
database does not travel with a Git push. From your own computer, upload every
PDF in `app/data` to the cloned checkout on your Droplet:

```powershell
.\deploy\upload-knowledge.ps1 -ServerHost YOUR_DROPLET_IP
```

The upload helper uses your existing SSH authentication. It sends PDFs only;
configure the API key separately in the server's `app/.env`.

On the first deployment, the indexer embeds all uploaded PDFs with the configured
Google API and stores them in Qdrant. Subsequent deployments add missing documents
and skip already indexed chunks. Repeated runs preserve the index without paying
to embed the same chunks again. If no PDFs are uploaded, startup can reuse an
existing populated collection; a fresh database requires the private PDFs first.

For a replacement document set, index into a new `QDRANT_COLLECTION` and switch
the app after verification. Append imports preserve old data rather than erasing it.

## Start and verify

On the Droplet:

```sh
bash deploy/start.sh --https
curl --fail https://YOUR_DOMAIN/health
curl --fail https://YOUR_DOMAIN/ready
```

The script builds the image, starts Qdrant, indexes every uploaded PDF, checks Gemini
with synthetic text, and starts the web server. Caddy manages HTTPS when the
configured hostname resolves to this server and ports 80/443 are reachable.

For an initial local HTTP check on the Droplet, use `bash deploy/start.sh` and
`curl http://127.0.0.1:8000/health`. To open that private port from your computer:

```sh
ssh -L 8000:127.0.0.1:8000 root@YOUR_DROPLET_IP
```

Then open `http://127.0.0.1:8000` locally. The app port is bound to loopback;
public traffic goes through Caddy.

## Updates and diagnostics

```sh
git pull --ff-only
bash deploy/start.sh --https
docker compose --env-file app/.env -f compose.production.yml logs --tail=100 web
docker compose --env-file app/.env -f compose.production.yml exec web python -m app.check_services --google
```

Changing a key in `app/.env` requires recreating the web container so Docker
loads the new environment:

```sh
docker compose --env-file app/.env -f compose.production.yml up -d --force-recreate web
```

Qdrant data persists in the `nuur-ai_qdrant_data` Docker volume. Back up this
volume or use Qdrant snapshots before changing storage or upgrading Qdrant.
Do not remove production volumes when updating the application.

References: [DigitalOcean SSH access](https://docs.digitalocean.com/products/droplets/how-to/connect-with-ssh/),
[Docker Engine installation](https://docs.docker.com/engine/install/ubuntu/),
[Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https),
[Qdrant installation and storage](https://qdrant.tech/documentation/installation/).
