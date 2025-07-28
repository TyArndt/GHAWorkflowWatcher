#!/usr/bin/env python3
"""
GitHub Workflow Webhook Server
Receives GitHub workflow run webhooks and stores data in SQLite database
"""

import os
import json
import sqlite3
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields, Namespace
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Flask-RESTX for Swagger documentation
api = Api(
    app,
    version='1.0.0',
    title='GitHub Workflow Webhook API',
    description='API for receiving GitHub workflow webhooks and managing workflow data',
    doc='/docs/',
    prefix='/api/v1'
)

def load_config(config_path='config.json'):
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"Config file {config_path} not found")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise

# Load configuration
config = load_config()
DATABASE_PATH = config['database']['path']
WEBHOOK_SECRET = config['webhook']['secret']
PORT = config['backend']['port']
HOST = config['backend']['host']

class DatabaseManager:
    """Handles SQLite database operations"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_runs (
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
                )
            ''')
            
            # Create index for better query performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_repository_workflow 
                ON workflow_runs(repository_name, workflow_id)
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_workflow_run(self, repo_name, workflow_id, workflow_name, 
                          workflow_conclusion, run_id=None, run_number=None,
                          run_url=None, head_branch=None):
        """Insert or update a workflow run record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if record already exists
            cursor.execute('''
                SELECT id FROM workflow_runs 
                WHERE repository_name = ? AND workflow_id = ? AND run_id = ?
            ''', (repo_name, workflow_id, run_id))
            
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Update existing record
                cursor.execute('''
                    UPDATE workflow_runs 
                    SET workflow_name = ?, workflow_conclusion = ?, 
                        run_number = ?, run_url = ?, head_branch = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (workflow_name, workflow_conclusion, run_number, run_url, head_branch, existing_record[0]))
                logger.info(f"Updated workflow run: {repo_name}/{workflow_name} (ID: {run_id})")
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO workflow_runs 
                    (repository_name, workflow_id, workflow_name, workflow_conclusion, 
                     run_id, run_number, run_url, head_branch)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (repo_name, workflow_id, workflow_name, workflow_conclusion, 
                      run_id, run_number, run_url, head_branch))
                logger.info(f"Inserted new workflow run: {repo_name}/{workflow_name} (ID: {run_id})")
            
            conn.commit()

# Initialize database manager
db_manager = DatabaseManager(DATABASE_PATH)

# Create API namespaces
webhook_ns = Namespace('webhook', description='GitHub webhook operations')
health_ns = Namespace('health', description='Health check operations')
workflows_ns = Namespace('workflows', description='Workflow data operations')

api.add_namespace(webhook_ns)
api.add_namespace(health_ns)
api.add_namespace(workflows_ns)

# API Models
repository_model = api.model('Repository', {
    'full_name': fields.String(required=True, description='Repository full name (owner/repo)')
})

workflow_run_model = api.model('WorkflowRun', {
    'workflow_id': fields.Integer(required=True, description='GitHub workflow ID'),
    'name': fields.String(required=True, description='Workflow name'),
    'conclusion': fields.String(description='Workflow conclusion (success, failed, pending)'),
    'id': fields.Integer(description='Workflow run ID'),
    'run_number': fields.Integer(description='Workflow run number'),
    'html_url': fields.String(description='GitHub workflow run URL'),
    'head_branch': fields.String(description='Git branch name')
})

workflow_job_model = api.model('WorkflowJob', {
    'id': fields.Integer(required=True, description='GitHub job ID'),
    'run_id': fields.Integer(description='GitHub run ID'),
    'run_url': fields.String(description='GitHub run URL'),
    'workflow_name': fields.String(required=True, description='Workflow name'),
    'name': fields.String(description='Job name'),
    'conclusion': fields.String(description='Job conclusion (success, failed, pending)'),
    'head_branch': fields.String(description='Git branch name')
})

github_webhook_model = api.model('GitHubWebhook', {
    'repository': fields.Nested(repository_model, required=True),
    'workflow_run': fields.Nested(workflow_run_model, description='Workflow run data (for workflow_run events)'),
    'workflow_job': fields.Nested(workflow_job_model, description='Workflow job data (for workflow_job events)')
})

workflow_response_model = api.model('WorkflowResponse', {
    'id': fields.Integer(description='Database record ID'),
    'repository_name': fields.String(description='Repository full name'),
    'workflow_id': fields.Integer(description='Workflow ID'),
    'workflow_name': fields.String(description='Workflow name'),
    'workflow_conclusion': fields.String(description='Workflow conclusion'),
    'run_id': fields.Integer(description='Run ID'),
    'run_number': fields.Integer(description='Run number'),
    'run_url': fields.String(description='Run URL'),
    'head_branch': fields.String(description='Git branch'),
    'created_at': fields.String(description='Creation timestamp'),
    'updated_at': fields.String(description='Last update timestamp')
})

success_response_model = api.model('SuccessResponse', {
    'message': fields.String(description='Success message')
})

error_response_model = api.model('ErrorResponse', {
    'error': fields.String(description='Error message')
})

health_response_model = api.model('HealthResponse', {
    'status': fields.String(description='Health status'),
    'database': fields.String(description='Database connection status'),
    'timestamp': fields.String(description='Check timestamp')
})

def verify_webhook_signature(payload_body, signature_header):
    """Verify GitHub webhook signature if secret is configured"""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret is configured
    
    if not signature_header:
        return False
    
    try:
        hash_object = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            msg=payload_body,
            digestmod=hashlib.sha256
        )
        expected_signature = "sha256=" + hash_object.hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False

@webhook_ns.route('')
class GitHubWebhook(Resource):
    @webhook_ns.doc('process_webhook')
    @webhook_ns.expect(github_webhook_model)
    @webhook_ns.response(200, 'Webhook processed successfully', success_response_model)
    @webhook_ns.response(400, 'Bad request', error_response_model)
    @webhook_ns.response(401, 'Invalid signature', error_response_model)
    @webhook_ns.response(500, 'Internal server error', error_response_model)
    @webhook_ns.param('X-GitHub-Event', 'GitHub event type (workflow_run or workflow_job)', 'header', required=True)
    @webhook_ns.param('X-Hub-Signature-256', 'GitHub webhook signature', 'header')
    def post(self):
        """
        Process GitHub webhook events
        
        Accepts GitHub webhook events for workflow_run and workflow_job.
        Extracts workflow information and stores it in the database.
        
        Supported events:
        - workflow_run: Complete workflow execution events
        - workflow_job: Individual job execution events
        """
        try:
            # Get request data
            payload_body = request.get_data()
            signature_header = request.headers.get('X-Hub-Signature-256')
            event_type = request.headers.get('X-GitHub-Event')
            
            # Verify webhook signature
            if not verify_webhook_signature(payload_body, signature_header):
                logger.warning("Invalid webhook signature")
                return {'error': 'Invalid signature'}, 401
            
            # Process workflow_run and workflow_job events
            if event_type not in ['workflow_run', 'workflow_job']:
                logger.info(f"Ignoring event type: {event_type}")
                return {'message': 'Event type not supported'}, 200
            
            # Parse JSON payload
            payload = request.get_json()
            if not payload:
                return {'error': 'Invalid JSON payload'}, 400
            
            repository = payload.get('repository', {})
            repo_name = repository.get('full_name')
            
            if event_type == 'workflow_run':
                # Extract workflow run data
                workflow_run = payload.get('workflow_run', {})
                workflow_id = workflow_run.get('workflow_id')
                workflow_name = workflow_run.get('name')
                workflow_conclusion = workflow_run.get('conclusion')
                run_id = workflow_run.get('id')
                run_number = workflow_run.get('run_number')
                run_url = workflow_run.get('html_url')
                head_branch = workflow_run.get('head_branch')
            else:  # workflow_job
                # Extract workflow job data
                workflow_job = payload.get('workflow_job', {})
                workflow_id = workflow_job.get('id')  # Use job ID as workflow_id
                workflow_name = workflow_job.get('workflow_name', workflow_job.get('name'))
                workflow_conclusion = workflow_job.get('conclusion')
                run_id = workflow_job.get('run_id')
                run_number = None  # Not available in workflow_job
                run_url = workflow_job.get('run_url')
                head_branch = workflow_job.get('head_branch')
            
            # Validate required fields
            if not all([repo_name, workflow_id, workflow_name]):
                missing_fields = []
                if not repo_name: missing_fields.append('repository.full_name')
                if not workflow_id: missing_fields.append(f'{event_type}.workflow_id' if event_type == 'workflow_run' else f'{event_type}.id')
                if not workflow_name: missing_fields.append(f'{event_type}.name')
                
                logger.error(f"Missing required fields: {missing_fields}")
                return {'error': f'Missing required fields: {missing_fields}'}, 400
            
            # Store in database
            db_manager.insert_workflow_run(
                repo_name=repo_name,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                workflow_conclusion=workflow_conclusion,
                run_id=run_id,
                run_number=run_number,
                run_url=run_url,
                head_branch=head_branch
            )
            
            return {'message': 'Webhook processed successfully'}, 200
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return {'error': 'Internal server error'}, 500

@health_ns.route('')
class HealthCheck(Resource):
    @health_ns.doc('health_check')
    @health_ns.response(200, 'Service is healthy', health_response_model)
    @health_ns.response(500, 'Service is unhealthy', error_response_model)
    def get(self):
        """
        Health check endpoint
        
        Returns the current health status of the service including database connectivity.
        """
        try:
            # Test database connection
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
            
            return {
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, 500

workflows_list_model = api.model('WorkflowsList', {
    'workflows': fields.List(fields.Nested(workflow_response_model)),
    'count': fields.Integer(description='Number of workflows returned')
})

@workflows_ns.route('')
class WorkflowsList(Resource):
    @workflows_ns.doc('get_workflows')
    @workflows_ns.response(200, 'Workflows retrieved successfully', workflows_list_model)
    @workflows_ns.response(500, 'Internal server error', error_response_model)
    @workflows_ns.param('limit', 'Maximum number of workflows to return (default: 50)', type=int)
    @workflows_ns.param('repository', 'Filter by repository name (partial match)', type=str)
    def get(self):
        """
        Get workflow runs from database
        
        Retrieves workflow run data with optional filtering and pagination.
        """
        try:
            limit = request.args.get('limit', 50, type=int)
            repo_filter = request.args.get('repository')
            
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                if repo_filter:
                    cursor.execute('''
                        SELECT * FROM workflow_runs 
                        WHERE repository_name LIKE ?
                        ORDER BY created_at DESC 
                        LIMIT ?
                    ''', (f'%{repo_filter}%', limit))
                else:
                    cursor.execute('''
                        SELECT * FROM workflow_runs 
                        ORDER BY created_at DESC 
                        LIMIT ?
                    ''', (limit,))
                
                rows = cursor.fetchall()
                workflows = [dict(row) for row in rows]
                
            return {
                'workflows': workflows,
                'count': len(workflows)
            }, 200
            
        except Exception as e:
            logger.error(f"Error fetching workflows: {e}")
            return {'error': 'Internal server error'}, 500

info_response_model = api.model('ServiceInfo', {
    'service': fields.String(description='Service name'),
    'version': fields.String(description='Service version'),
    'endpoints': fields.Raw(description='Available endpoints'),
    'database': fields.String(description='Database path'),
    'swagger_docs': fields.String(description='Swagger documentation URL')
})

@api.route('/')
class ServiceInfo(Resource):
    @api.doc('service_info')
    @api.response(200, 'Service information', info_response_model)
    def get(self):
        """
        Get service information
        
        Returns basic information about the GitHub Workflow Webhook API service.
        """
        return {
            'service': 'GitHub Workflow Webhook Server',
            'version': '1.0.0',
            'endpoints': {
                'webhook': '/api/v1/webhook (POST)',
                'health': '/api/v1/health (GET)',
                'workflows': '/api/v1/workflows (GET)',
            },
            'database': DATABASE_PATH,
            'swagger_docs': '/docs/'
        }, 200

if __name__ == '__main__':
    logger.info(f"Starting GitHub Workflow Webhook Server on {HOST}:{PORT}")
    logger.info(f"Database: {DATABASE_PATH}")
    logger.info(f"Webhook secret configured: {'Yes' if WEBHOOK_SECRET else 'No'}")
    logger.info("Configuration loaded from config.json")
    
    app.run(host=HOST, port=PORT, debug=False)