# GitHub Workflow Webhook Server

A real-time dashboard and API server for monitoring GitHub workflow runs and jobs. Receive webhook events from GitHub Actions and visualize workflow status with an interactive web interface.

![Dashboard Preview](https://img.shields.io/badge/Status-Production%20Ready-brightgreen) ![Python](https://img.shields.io/badge/Python-3.13-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![Docker](https://img.shields.io/badge/Docker-Ready-blue)

## ✨ Features

### 🔄 Real-Time Monitoring
- **Live Dashboard**: WebSocket-powered real-time updates
- **Smart Filtering**: Time-based and status-based filtering with persistence
- **Timezone Aware**: Automatic conversion to local timezone
- **Auto Refresh**: Configurable refresh rates (10s, 30s, 1min, or off)

### 📊 Interactive Dashboard
- **Modern UI**: Glassmorphism design with responsive layout
- **Visual Status**: Color-coded workflow cards with status badges
- **Smart Notifications**: Visual indicators for status changes
- **Mobile Friendly**: Optimized for all device sizes

### 🛠 Robust API
- **RESTful API**: Well-documented endpoints with Swagger UI
- **Webhook Processing**: Supports both `workflow_run` and `workflow_job` events
- **Data Persistence**: SQLite database with automatic schema management
- **Health Monitoring**: Built-in health checks and status endpoints

### 🚀 Production Ready
- **Docker Support**: Complete containerization with multi-service support
- **Cloud Deployment**: Ready-to-deploy configurations for Fly.io
- **Security**: Webhook signature verification and secure defaults
- **Monitoring**: Health checks, logging, and error handling

## 🏗 Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub Actions   │    │   Webhook Server    │    │   Frontend Dashboard │
│                 │    │                 │    │                 │
│  Workflow Runs  │────▶│  Backend API    │◄───│  Real-time UI   │
│  Workflow Jobs  │    │  (Port 8081)    │    │  (Port 8080)    │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   SQLite DB     │
                       │   (Persistent)  │
                       └─────────────────┘
```

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd webserver

# Start with Docker Compose
docker-compose up -d

# Access the services
# Frontend: http://localhost:8080
# Backend API: http://localhost:8081
# API Docs: http://localhost:8081/docs/
```

### Option 2: Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start backend service
python Backend.py &

# Start frontend service  
python frontend.py &

# Access services on localhost:8080 and localhost:8081
```

### Option 3: Fly.io Deployment

```bash
# Install Fly CLI and login
fly auth login

# Create volume for database
fly volumes create workflow_data --size 1

# Deploy to Fly.io
fly deploy
```

## 📋 Configuration

The application uses a JSON configuration file (`config.json`):

```json
{
  "database": {
    "path": "/app/data/github_workflows.db"
  },
  "backend": {
    "host": "0.0.0.0",
    "port": 8081
  },
  "frontend": {
    "host": "0.0.0.0", 
    "port": 8080
  },
  "shared": {
    "secret": "your-secret-key"
  },
  "webhook": {
    "secret": null
  }
}
```

### Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `database.path` | SQLite database file location | `github_workflows.db` |
| `backend.host` | Backend server bind address | `0.0.0.0` |
| `backend.port` | Backend server port | `8081` |
| `frontend.host` | Frontend server bind address | `0.0.0.0` |
| `frontend.port` | Frontend server port | `8080` |
| `shared.secret` | Flask session secret | Generated |
| `webhook.secret` | GitHub webhook signature secret | `null` (disabled) |

## 🔗 GitHub Webhook Setup

1. **Navigate to Repository Settings**
   - Go to your GitHub repository
   - Click Settings → Webhooks → Add webhook

2. **Configure Webhook**
   - **Payload URL**: `https://your-server.com:8081/api/v1/webhook`
   - **Content type**: `application/json`
   - **Secret**: (optional, set in config.json)
   - **Events**: Select "Workflow jobs" and/or "Workflow runs"

3. **Test Webhook**
   - Trigger a workflow in your repository
   - Check the dashboard for real-time updates

## 📊 Dashboard Features

### Time Range Filtering
- **Current Day**: Today's workflows only
- **Last Hour**: Workflows from past hour
- **Previous Day**: Yesterday's workflows
- **Current Week**: Sunday to Saturday of current week
- **Previous Week**: Sunday to Saturday of previous week
- **All Time**: No time filtering

### Status Filtering
- **All Status**: Show all workflow conclusions
- **Success**: Only successful workflows
- **Failed**: Only failed workflows  
- **Pending**: Only pending/in-progress workflows

### Auto Refresh Options
- **10 seconds**: High-frequency monitoring
- **30 seconds**: Default refresh rate
- **1 minute**: Low-frequency monitoring
- **Off**: Manual refresh only

### Smart Features
- **Filter Persistence**: Settings saved to localStorage
- **Status Change Tracking**: Visual indicators for workflows that change status
- **Timezone Conversion**: All times displayed in local timezone
- **Responsive Design**: Works on desktop, tablet, and mobile

## 🛠 API Documentation

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/webhook` | Process GitHub webhook events |
| `GET` | `/api/v1/health` | Health check endpoint |
| `GET` | `/api/v1/workflows` | Retrieve workflow data |
| `GET` | `/api/v1/` | Service information |
| `GET` | `/docs/` | Interactive API documentation |

### Example API Usage

```bash
# Check service health
curl http://localhost:8081/api/v1/health

# Get workflows with filtering
curl "http://localhost:8081/api/v1/workflows?limit=10&repository=myorg"

# View API documentation
open http://localhost:8081/docs/
```

### Webhook Payload Example

```bash
# Send test webhook (workflow_job event)
curl -X POST http://localhost:8081/api/v1/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_job" \
  -d '{
    "repository": {
      "full_name": "myorg/myrepo"
    },
    "workflow_job": {
      "id": 123456,
      "run_id": 789012,
      "workflow_name": "CI Pipeline",
      "conclusion": "success",
      "run_url": "https://github.com/myorg/myrepo/actions/runs/789012",
      "head_branch": "main"
    }
  }'
```

## 📁 Project Structure

```
webserver/
├── Backend.py              # Flask API server with Swagger docs
├── frontend.py             # Flask frontend with SocketIO
├── config.json             # Application configuration
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container definition
├── docker-compose.yml     # Multi-service container setup
├── entrypoint.sh          # Container startup script
├── fly.toml               # Fly.io deployment configuration
├── .dockerignore          # Docker build exclusions
├── README.md              # This file
├── README-Docker.md       # Docker deployment guide
├── README-Fly.md          # Fly.io deployment guide
└── payload.json           # Example webhook payload
```

## 🔧 Development

### Local Development Setup

```bash
# Clone repository
git clone <repository-url>
cd webserver

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start development servers
python Backend.py &   # Backend on port 8081
python frontend.py &  # Frontend on port 8080
```

### Database Schema

The application uses SQLite with the following schema:

```sql
CREATE TABLE workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_name TEXT NOT NULL,
    workflow_id INTEGER NOT NULL,
    workflow_name TEXT NOT NULL,
    workflow_conclusion TEXT,
    run_id INTEGER,
    run_number INTEGER,
    run_url TEXT,
    head_branch TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_repository_workflow 
ON workflow_runs(repository_name, workflow_id);
```

### Adding New Features

1. **Backend Changes**: Modify `Backend.py` for API endpoints
2. **Frontend Changes**: Modify `frontend.py` for UI features
3. **Database Changes**: Update schema in `DatabaseManager.init_database()`
4. **Configuration**: Add new settings to `config.json`

## 🚀 Deployment Options

### 1. Docker Deployment
- **Production ready**: Multi-service container
- **Data persistence**: Volume-mounted database
- **Easy scaling**: docker-compose configuration
- **Cost**: Self-hosted infrastructure costs

[📖 Docker Deployment Guide](README-Docker.md)

### 2. Fly.io Deployment
- **Cloud hosting**: Global edge deployment
- **Cost effective**: ~$2/month for minimal resources
- **Auto scaling**: Built-in load balancing
- **HTTPS included**: Free TLS certificates

[📖 Fly.io Deployment Guide](README-Fly.md)

### 3. Local Development
- **Quick setup**: Direct Python execution
- **Development**: Hot reload and debugging
- **Testing**: Local webhook testing with ngrok

## 🛡 Security Considerations

### Webhook Security
- **Signature Verification**: Optional GitHub webhook secret verification
- **Input Validation**: Comprehensive payload validation
- **Error Handling**: Secure error responses without information leakage

### Application Security
- **Non-root Execution**: Docker containers run as non-root user
- **Secret Management**: Secure configuration handling
- **HTTPS**: Force HTTPS in production deployments
- **Input Sanitization**: SQL injection prevention with parameterized queries

### Production Hardening
```json
{
  "webhook": {
    "secret": "your-secure-webhook-secret"
  },
  "shared": {
    "secret": "your-secure-session-secret"
  }
}
```

## 📊 Monitoring & Observability

### Health Checks
- **Application Health**: `/api/v1/health` endpoint
- **Database Connectivity**: Automatic connection testing
- **Service Status**: Real-time status monitoring

### Logging
- **Structured Logging**: JSON formatted logs
- **Log Levels**: Configurable log verbosity
- **Error Tracking**: Comprehensive error logging

### Metrics
- **Request Metrics**: API endpoint performance
- **Workflow Metrics**: Processing statistics
- **System Metrics**: Resource utilization

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit changes**: `git commit -m 'Add amazing feature'`
4. **Push to branch**: `git push origin feature/amazing-feature`
5. **Open Pull Request**

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation
- Ensure Docker builds succeed

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Getting Help
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Documentation**: See README files in this repository

### Common Issues

**Port Conflicts**
```bash
# Change ports in config.json
{
  "backend": { "port": 9081 },
  "frontend": { "port": 9080 }
}
```

**Database Permissions**
```bash
# Fix database permissions
chmod 644 github_workflows.db
chown user:user github_workflows.db
```

**Webhook Not Receiving**
1. Check firewall settings
2. Verify webhook URL is accessible
3. Check GitHub webhook delivery logs
4. Validate webhook secret configuration

## 🎯 Roadmap

- [ ] **Multi-repository Support**: Dashboard for multiple repositories
- [ ] **Advanced Filtering**: Custom date ranges and complex queries
- [ ] **Notification System**: Email/Slack notifications for workflow status
- [ ] **Metrics Dashboard**: Historical analytics and trend analysis
- [ ] **User Authentication**: Multi-user support with role-based access
- [ ] **API Rate Limiting**: Enhanced security and performance
- [ ] **Backup System**: Automated database backups
- [ ] **Plugin System**: Extensible architecture for custom integrations

---

**Made with ❤️ for the GitHub Actions community**