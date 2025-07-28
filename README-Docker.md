# GitHub Workflow Webhook Server - Docker Setup

This document explains how to run the GitHub Workflow Webhook Server using Docker.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Build and start the services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Using Docker directly

```bash
# Build the image
docker build -t GHAWorkflowWatcher .

# Create a volume for data persistence
docker volume create workflow_data

# Run the container
docker run -d \
  --name GHAWorkflowWatcher \
  -p 8080:8080 \
  -p 8081:8081 \
  -v workflow_data:/app/data \
  GHAWorkflowWatcher
```

## Access Points

Once running, you can access:

- **Frontend Dashboard**: http://localhost:8080
- **Backend API**: http://localhost:8081
- **API Documentation (Swagger)**: http://localhost:8081/docs/
- **Health Check**: http://localhost:8081/api/v1/health

## Configuration

The container uses the following configuration:

- **Database**: Stored in `/app/data/github_workflows.db` (persisted via volume)
- **Backend Port**: 8081
- **Frontend Port**: 8080
- **Default Secret**: `workflow-dashboard-secret`

### Environment Variables

You can override configuration using environment variables:

```yaml
# docker-compose.yml
environment:
  - TZ=America/Chicago  # Set timezone
```

## Data Persistence

The database is stored in a Docker volume to persist data across container restarts:

- **Volume Name**: `workflow_data`
- **Mount Point**: `/app/data`
- **Database File**: `/app/data/github_workflows.db`

## GitHub Webhook Setup

To receive webhooks from GitHub:

1. Go to your repository Settings → Webhooks
2. Add webhook with URL: `http://your-server:8081/api/v1/webhook`
3. Set Content-Type: `application/json`
4. Select events: `Workflow jobs` and/or `Workflow runs`
5. Optionally set a secret in your config.json

## Health Monitoring

The container includes a health check that monitors:

- Backend API availability
- Database connectivity
- Service responsiveness

Check health status:
```bash
docker-compose ps
# or
docker inspect GHAWorkflowWatcher
```

## Logs

View real-time logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker logs -f GHAWorkflowWatcher
```

## Updating

To update the application:

```bash
# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Troubleshooting

### Port Conflicts
If ports 8080 or 8081 are in use, modify docker-compose.yml:
```yaml
ports:
  - "9080:8080"  # Frontend on port 9080
  - "9081:8081"  # Backend on port 9081
```

### Permission Issues
If you encounter permission issues:
```bash
# Check volume permissions
docker exec -it GHAWorkflowWatcher ls -la /app/data/
```

### Database Issues
To reset the database:
```bash
# Stop container and remove volume
docker-compose down
docker volume rm webserver_workflow_data

# Restart
docker-compose up -d
```