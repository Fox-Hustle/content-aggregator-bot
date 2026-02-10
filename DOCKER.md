# 🐳 Docker Deployment Guide

This guide covers how to run the Content Aggregator Bot using Docker and Docker Compose.

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+
- `.env` file configured (see [README.md](README.md) for configuration details)
- `config/sources.yaml` configured with your sources

## 🚀 Quick Start

### Production Deployment

1. **Prepare configuration files:**
```bash
# Copy environment template
cp env.example .env

# Edit .env with your credentials
nano .env

# Configure your sources
nano config/sources.yaml
```

2. **Build and start the bot:**
```bash
docker-compose up -d
```

3. **View logs:**
```bash
docker-compose logs -f
```

4. **Stop the bot:**
```bash
docker-compose down
```

### Development Deployment

Development mode includes:
- Live code reloading (source code mounted as volume)
- Debug logging enabled (`-v` flag)
- Interactive terminal access

1. **Start in development mode:**
```bash
docker-compose -f docker-compose.dev.yml up
```

2. **Rebuild after dependency changes:**
```bash
docker-compose -f docker-compose.dev.yml up --build
```

## 📁 Volume Mounts

### Production (`docker-compose.yml`)

| Volume | Purpose | Type |
|--------|---------|------|
| `./data` | SQLite database persistence | Bind mount |
| `./logs` | Log files | Bind mount |
| `bot-sessions` | Telegram session files | Named volume |
| `./config/sources.yaml` | Sources configuration (read-only) | Bind mount |

### Development (`docker-compose.dev.yml`)

| Volume | Purpose | Type |
|--------|---------|------|
| `./app` | Live code editing | Bind mount |
| `./config` | Configuration files | Bind mount |
| `./data` | SQLite database persistence | Bind mount |
| `./logs` | Log files | Bind mount |
| `bot-sessions-dev` | Telegram session files | Named volume |

## 🔧 Common Tasks

### First-Time Setup (Telegram Authentication)

On the first run, you'll need to authenticate with Telegram:

```bash
# Start the container interactively
docker-compose run --rm bot

# You'll be prompted to enter:
# 1. Your phone number (international format: +1234567890)
# 2. Verification code from Telegram
# 3. 2FA password (if enabled)

# After successful authentication, the session is saved to the bot-sessions volume
```

### View Logs

```bash
# Follow logs in real-time
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100

# View logs for specific time period
docker-compose logs --since 30m
```

### Restart the Bot

```bash
# Restart without rebuilding
docker-compose restart

# Restart with rebuild
docker-compose up -d --build
```

### Update the Bot

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

### Access Container Shell

```bash
# Access running container
docker-compose exec bot /bin/bash

# Or start a new container with shell
docker-compose run --rm bot /bin/bash
```

### Clean Up

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes (⚠️ deletes session data)
docker-compose down -v

# Remove containers, volumes, and images
docker-compose down -v --rmi all
```

## 🔍 Troubleshooting

### Container Exits Immediately

Check the logs:
```bash
docker-compose logs bot
```

Common issues:
- Missing or invalid `.env` file
- Invalid Telegram credentials
- Missing `config/sources.yaml`

### "Permission Denied" on Volumes

Ensure the directories exist and have proper permissions:
```bash
mkdir -p data logs
chmod 755 data logs
```

### Session Files Not Persisting

Session files are stored in a named Docker volume. To inspect:
```bash
# List volumes
docker volume ls | grep bot-sessions

# Inspect volume
docker volume inspect content-aggregator-bot_bot-sessions
```

To backup session:
```bash
# Create backup
docker run --rm -v content-aggregator-bot_bot-sessions:/source -v $(pwd):/backup alpine tar czf /backup/session-backup.tar.gz -C /source .

# Restore backup
docker run --rm -v content-aggregator-bot_bot-sessions:/target -v $(pwd):/backup alpine tar xzf /backup/session-backup.tar.gz -C /target
```

### Database Issues

Reset the database (⚠️ deletes all data):
```bash
docker-compose down
rm -rf data/
docker-compose up -d
```

### Network Issues

Reset Docker network:
```bash
docker-compose down
docker network prune
docker-compose up -d
```

## ⚙️ Environment Variables

All environment variables from `.env` are passed to the container. See [README.md](README.md) for the complete list of available variables.

Key variables for Docker deployment:
- `TELEGRAM_BOT_TOKEN` - Required
- `TELEGRAM_TARGET_CHAT_ID` - Required
- `TELEGRAM_API_ID` - Required
- `TELEGRAM_API_HASH` - Required
- `VK_ACCESS_TOKEN` - Required if using VK sources
- `LOG_LEVEL` - Automatically set to `DEBUG` in dev mode

## 🏗️ Building Custom Images

### Build Production Image

```bash
docker build -t content-aggregator-bot:latest .
```

### Build with Different Python Version

```bash
docker build --build-arg PYTHON_VERSION=3.13 -t content-aggregator-bot:py313 .
```

### Multi-Platform Build

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t content-aggregator-bot:latest .
```

## 📊 Resource Limits

To limit resource usage, add to `docker-compose.yml`:

```yaml
services:
  bot:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

## 🔐 Security Best Practices

1. **Never commit `.env` files** - Already included in `.gitignore`
2. **Use secrets for sensitive data** in production:
   ```yaml
   services:
     bot:
       secrets:
         - telegram_bot_token
   secrets:
     telegram_bot_token:
       file: ./secrets/telegram_bot_token.txt
   ```
3. **Run as non-root user** - Consider adding to Dockerfile:
   ```dockerfile
   RUN useradd -m -u 1000 botuser
   USER botuser
   ```
4. **Keep images updated** - Regularly rebuild to get security patches

## 📈 Monitoring

### Health Checks

Add to `docker-compose.yml`:
```yaml
services:
  bot:
    # ... existing config ...
    healthcheck:
      test: ["CMD-SHELL", "pgrep -f 'python -m app' || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Logging to External Systems

Configure Docker logging driver in `docker-compose.yml`:
```yaml
services:
  bot:
    logging:
      driver: "syslog"
      options:
        syslog-address: "tcp://192.168.0.100:514"
        tag: "content-aggregator-bot"
```

## 🆘 Support

For issues specific to Docker deployment, please check:
1. Docker logs: `docker-compose logs`
2. Container status: `docker-compose ps`
3. System resources: `docker stats`

For application-level issues, see [README.md](README.md#-решение-проблем).
