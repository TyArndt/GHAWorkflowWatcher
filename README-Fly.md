# GitHub Workflow Webhook Server - Fly.io Deployment

This guide explains how to deploy the GitHub Workflow Webhook Server to Fly.io.

## Prerequisites

1. Install the Fly CLI:
   ```bash
   # macOS
   brew install flyctl
   
   # Windows
   iwr https://fly.io/install.ps1 -useb | iex
   
   # Linux
   curl -L https://fly.io/install.sh | sh
   ```

2. Sign up and log in to Fly.io:
   ```bash
   fly auth signup
   # or
   fly auth login
   ```

## Deployment Steps

### 1. Initialize the App

```bash
# Navigate to your project directory
cd /path/to/webserver

# Launch the app (this will use the existing fly.toml)
fly launch --no-deploy
```

### 2. Create a Volume for Database Persistence

```bash
# Create a 1GB volume for the SQLite database
fly volumes create workflow_data --size 1 --region ord

# Verify volume creation
fly volumes list
```

### 3. Set Secrets (Optional)

If you want to use GitHub webhook signature verification:

```bash
# Set your GitHub webhook secret
fly secrets set GITHUB_WEBHOOK_SECRET=your-webhook-secret-here

# Set a custom shared secret for the application
fly secrets set SHARED_SECRET=your-custom-secret-here
```

### 4. Deploy the Application

```bash
# Deploy to Fly.io
fly deploy

# Check deployment status
fly status

# View logs
fly logs
```

## Configuration Details

### Machine Specifications
- **VM Size**: shared-cpu-1x (smallest available)
- **CPU**: 1 shared CPU
- **Memory**: 256MB RAM
- **Storage**: 1GB persistent volume

### Cost Optimization
The configuration uses the smallest possible machine size:
- **Shared CPU**: Most cost-effective option
- **256MB RAM**: Minimum for Python Flask applications
- **Connection limits**: Set to prevent resource exhaustion

### Networking
- **Frontend**: Accessible via HTTPS on port 443 (redirects from 80)
- **Backend API**: Accessible on port 8081
- **Health checks**: Configured for both services

### Health Monitoring
- **TCP checks**: Monitor port availability
- **HTTP checks**: Verify API health endpoint
- **Automatic rollback**: Enabled for failed deployments

## Access Your Application

After deployment, your app will be available at:

- **Frontend Dashboard**: `https://your-app-name.fly.dev`
- **Backend API**: `https://your-app-name.fly.dev:8081`
- **API Documentation**: `https://your-app-name.fly.dev:8081/docs/`

## GitHub Webhook Setup

To configure GitHub webhooks to point to your Fly.io deployment:

1. Go to your repository Settings → Webhooks
2. Add webhook with URL: `https://your-app-name.fly.dev:8081/api/v1/webhook`
3. Set Content-Type: `application/json`
4. Select events: `Workflow jobs` and/or `Workflow runs`
5. Set secret if configured

## Monitoring and Maintenance

### View Application Logs
```bash
# Real-time logs
fly logs

# Historical logs
fly logs --since 1h
```

### Scale Resources (if needed)
```bash
# Scale to larger machine (will increase cost)
fly scale vm shared-cpu-2x --memory 512

# Scale back to smallest
fly scale vm shared-cpu-1x --memory 256
```

### Update Application
```bash
# Deploy latest changes
fly deploy

# Deploy with specific tag
fly deploy --image your-registry/github-workflow-server:v1.0.0
```

### Manage Volumes
```bash
# List volumes
fly volumes list

# Extend volume size if needed
fly volumes extend workflow_data --size 2

# Create volume snapshot
fly volumes snapshots create workflow_data
```

## Cost Estimates

With the minimal configuration:
- **Compute**: ~$1.94/month (shared-cpu-1x, 256MB)
- **Storage**: ~$0.15/month (1GB volume)
- **Total**: ~$2.09/month

## Troubleshooting

### Application Won't Start
```bash
# Check app status
fly status

# View detailed logs
fly logs

# SSH into the container
fly ssh console
```

### Volume Issues
```bash
# Check volume status
fly volumes list

# If volume is corrupted, create new one
fly volumes create workflow_data_new --size 1
# Update fly.toml to use new volume
# Deploy with new volume
```

### Database Reset
If you need to reset the database:
```bash
# SSH into container
fly ssh console

# Remove database file
rm /app/data/github_workflows.db

# Restart app
fly app restart
```

## Security Considerations

1. **HTTPS**: Automatically enabled with Fly.io certificates
2. **Volume Encryption**: Fly.io volumes are encrypted at rest
3. **Private Networking**: Use Fly.io private networking for internal communication
4. **Secrets Management**: Use `fly secrets` for sensitive configuration

## Custom Domain (Optional)

To use a custom domain:
```bash
# Add your domain
fly certs add yourdomain.com

# Create DNS records as shown in the output
# Wait for certificate provisioning
fly certs show yourdomain.com
```