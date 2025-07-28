from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import sqlite3
import threading
import time
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
DATABASE = config['database']['path']
SECRET_KEY = config['shared']['secret']
HOST = config['frontend']['host']
PORT = config['frontend']['port']

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

def init_database():
    """Initialize the database to match backend schema"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create workflow_runs table (same as backend)
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
    
    # Insert sample data if table is empty
    cursor.execute('SELECT COUNT(*) FROM workflow_runs')
    if cursor.fetchone()[0] == 0:
        sample_data = [
            ('frontend/demo-app', 12345, 'Deploy Application', 'success', 67890, 15, 
             'https://github.com/frontend/demo-app/actions/runs/67890', 'main'),
            ('frontend/demo-app', 12346, 'Run Tests', 'pending', 67891, 16, 
             'https://github.com/frontend/demo-app/actions/runs/67891', 'feature/new-ui'),
            ('frontend/demo-app', 12347, 'Build Docker Image', 'failed', 67892, 17, 
             'https://github.com/frontend/demo-app/actions/runs/67892', 'develop'),
            ('backend/api-service', 12348, 'Database Migration', 'success', 67893, 8, 
             'https://github.com/backend/api-service/actions/runs/67893', 'main'),
            ('security/scanner', 12349, 'Security Scan', 'failed', 67894, 3, 
             'https://github.com/security/scanner/actions/runs/67894', 'security-fixes')
        ]
        
        for repo_name, workflow_id, workflow_name, conclusion, run_id, run_number, run_url, head_branch in sample_data:
            cursor.execute('''
                INSERT INTO workflow_runs 
                (repository_name, workflow_id, workflow_name, workflow_conclusion, run_id, run_number, run_url, head_branch)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (repo_name, workflow_id, workflow_name, conclusion, run_id, run_number, run_url, head_branch))
    
    conn.commit()
    conn.close()

def get_workflows(time_filter='all', conclusion_filter='all', include_ids=None, timezone_offset=0):
    """Fetch filtered workflows from database with smart filtering"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Build WHERE clause based on filters
    where_conditions = []
    params = []
    
    # Time-based filtering (adjust for user's timezone)
    if time_filter != 'all':
        # Convert timezone offset from minutes to hours for SQLite
        offset_hours = -timezone_offset / 60  # Negative because JS offset is opposite of standard
        offset_str = f"{'+' if offset_hours >= 0 else ''}{offset_hours:.1f} hours"
        
        if time_filter == 'last_hour':
            where_conditions.append(f"updated_at >= datetime('now', 'localtime', '-1 hour', '{offset_str}')")
        elif time_filter == 'current_day':
            where_conditions.append(f"date(updated_at, 'localtime', '{offset_str}') = date('now', 'localtime', '{offset_str}')")
        elif time_filter == 'previous_day':
            where_conditions.append(f"date(updated_at, 'localtime', '{offset_str}') = date('now', 'localtime', '{offset_str}', '-1 day')")
        elif time_filter == 'current_week':
            # Sunday to Saturday of current week in user's timezone
            where_conditions.append(f"date(updated_at, 'localtime', '{offset_str}') >= date('now', 'localtime', '{offset_str}', 'weekday 6', '-6 days') AND date(updated_at, 'localtime', '{offset_str}') <= date('now', 'localtime', '{offset_str}', 'weekday 6')")
        elif time_filter == 'previous_week':
            # Sunday to Saturday of previous week in user's timezone
            where_conditions.append(f"date(updated_at, 'localtime', '{offset_str}') >= date('now', 'localtime', '{offset_str}', 'weekday 6', '-13 days') AND date(updated_at, 'localtime', '{offset_str}') <= date('now', 'localtime', '{offset_str}', 'weekday 6', '-7 days')")
    
    # Smart conclusion-based filtering
    if conclusion_filter != 'all':
        if include_ids and len(include_ids) > 0:
            # Include items matching filter OR previously displayed items
            placeholders = ','.join(['?' for _ in include_ids])
            where_conditions.append(f"(workflow_conclusion = ? OR id IN ({placeholders}))")
            params.append(conclusion_filter)
            params.extend(include_ids)
        else:
            # Standard filtering
            where_conditions.append("workflow_conclusion = ?")
            params.append(conclusion_filter)
    
    # Build final query
    base_query = '''
        SELECT id, repository_name, workflow_id, workflow_name, workflow_conclusion, 
               run_id, run_number, run_url, head_branch, created_at, updated_at
        FROM workflow_runs
    '''
    
    if where_conditions:
        query = base_query + ' WHERE ' + ' AND '.join(where_conditions) + ' ORDER BY updated_at DESC'
    else:
        query = base_query + ' ORDER BY updated_at DESC'
    
    cursor.execute(query, params)
    workflows = cursor.fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    workflow_list = []
    for workflow in workflows:
        workflow_list.append({
            'id': workflow[0],
            'repository_name': workflow[1],
            'workflow_id': workflow[2],
            'name': workflow[3],  # workflow_name mapped to name for UI compatibility
            'conclusion': workflow[4],  # workflow_conclusion mapped to conclusion
            'run_id': workflow[5],
            'run_number': workflow[6],
            'run_url': workflow[7],
            'head_branch': workflow[8],
            'created_at': workflow[9],
            'updated_at': workflow[10],
            'status': 'completed' if workflow[4] in ['success', 'failed'] else 'in_progress',  # derive status from conclusion            
        })
    
    return workflow_list

def monitor_database():
    """Monitor database changes and emit updates"""
    last_update = None
    
    while True:
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(updated_at) FROM workflow_runs')
            current_update = cursor.fetchone()[0]
            conn.close()
            
            if last_update is None:
                last_update = current_update
            elif current_update != last_update:
                # Database has been updated
                workflows = get_workflows()
                socketio.emit('workflow_update', {'workflows': workflows})
                last_update = current_update
                
        except Exception as e:
            logger.error(f"Database monitoring error: {e}")
            
        time.sleep(2)  # Check every 2 seconds

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workflow Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            color: white;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .status-indicator {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
            text-transform: uppercase;
            margin-left: 10px;
        }
        
        .last-updated {
            text-align: center;
            color: rgba(255,255,255,0.8);
            margin-bottom: 20px;
            font-size: 0.9rem;
        }
        
        .workflows-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        
        .workflow-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .workflow-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }
        
        .workflow-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: var(--status-color);
        }
        
        .workflow-card.success::before {
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
        }
        
        .workflow-card.failed::before {
            background: linear-gradient(90deg, #f44336, #FF5722);
        }
        
        .workflow-card.pending::before {
            background: linear-gradient(90deg, #FF9800, #FFC107);
        }
        
        .workflow-card.status-changed {
            border: 2px solid rgba(33, 150, 243, 0.5);
            box-shadow: 0 0 10px rgba(33, 150, 243, 0.3);
        }
        
        .workflow-card.status-changed::after {
            content: 'Status Changed';
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(33, 150, 243, 0.9);
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .workflow-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }
        
        .workflow-name {
            font-size: 1.3rem;
            font-weight: 600;
            color: #2c3e50;
            flex: 1;
        }
        
        .conclusion-badge {
            padding: 6px 12px;
            border-radius: 25px;
            font-size: 0.8rem;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .conclusion-success {
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
            box-shadow: 0 2px 8px rgba(76, 175, 80, 0.3);
        }
        
        .conclusion-failed {
            background: linear-gradient(135deg, #f44336, #d32f2f);
            color: white;
            box-shadow: 0 2px 8px rgba(244, 67, 54, 0.3);
        }
        
        .conclusion-pending {
            background: linear-gradient(135deg, #FF9800, #f57c00);
            color: white;
            box-shadow: 0 2px 8px rgba(255, 152, 0, 0.3);
        }
        
        .workflow-details {
            color: #546e7a;
            line-height: 1.6;
        }
        
        .workflow-meta {
            display: flex;
            justify-content: space-between;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(0,0,0,0.1);
            font-size: 0.85rem;
            color: #78909c;
        }
        
        .status-text {
            font-weight: 500;
            text-transform: capitalize;
        }
        
        .pulse {
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 25px;
            font-size: 0.8rem;
            font-weight: bold;
            z-index: 1000;
        }
        
        .connected {
            background: rgba(76, 175, 80, 0.9);
            color: white;
        }
        
        .disconnected {
            background: rgba(244, 67, 54, 0.9);
            color: white;
        }
        
        .filters-container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .filters-row {
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .filter-label {
            color: white;
            font-weight: 600;
            font-size: 0.9rem;
        }
        
        .filter-select {
            padding: 8px 12px;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 8px;
            background: rgba(255,255,255,0.9);
            color: #333;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .filter-select:hover {
            background: white;
            border-color: #2196F3;
        }
        
        .filter-select:focus {
            outline: none;
            border-color: #2196F3;
            box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.2);
        }
        
        @media (max-width: 768px) {
            .workflows-grid {
                grid-template-columns: 1fr;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .filters-row {
                flex-direction: column;
                align-items: stretch;
                gap: 15px;
            }
            
            .filter-group {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="connection-status" id="connectionStatus">Connected</div>
    
    <div class="container">
        <div class="header">
            <h1>🔄 Workflow Dashboard</h1>
            <p>Real-time workflow monitoring system</p>
        </div>
        
        <div class="last-updated" id="lastUpdated">
            Last updated: <span id="updateTime">Loading...</span>
        </div>
        
        <div class="filters-container">
            <div class="filters-row">
                <div class="filter-group">
                    <label class="filter-label">Time Range</label>
                    <select id="timeFilter" class="filter-select">
                        <option value="current_day">Current Day</option>
                        <option value="last_hour">Last Hour</option>
                        <option value="previous_day">Previous Day</option>
                        <option value="current_week">Current Week (Sun-Sat)</option>
                        <option value="previous_week">Previous Week (Sun-Sat)</option>
                        <option value="all">All Time</option>
                    </select>
                </div>
                
                <div class="filter-group">
                    <label class="filter-label">Status</label>
                    <select id="conclusionFilter" class="filter-select">
                        <option value="all">All Status</option>
                        <option value="success">Success</option>
                        <option value="failed">Failed</option>
                        <option value="pending">Pending</option>
                    </select>
                </div>
                
                <div class="filter-group">
                    <label class="filter-label">Auto Refresh</label>
                    <select id="refreshRateFilter" class="filter-select">
                        <option value="10">10 seconds</option>
                        <option value="30">30 seconds</option>
                        <option value="60">1 minute</option>
                        <option value="off">Off</option>
                    </select>
                </div>
            </div>
        </div>
        
        <div class="workflows-grid" id="workflowsContainer">
            <!-- Workflows will be populated here -->
        </div>
    </div>

    <script>
        const socket = io();
        
        // Filter persistence functions
        function saveFilterState() {
            const filterState = {
                time_filter: currentFilters.time_filter,
                conclusion_filter: currentFilters.conclusion_filter,
                refresh_rate: currentRefreshRate
            };
            localStorage.setItem('workflowDashboardFilters', JSON.stringify(filterState));
        }
        
        function loadFilterState() {
            try {
                const saved = localStorage.getItem('workflowDashboardFilters');
                if (saved) {
                    const filterState = JSON.parse(saved);
                    return {
                        time_filter: filterState.time_filter || 'current_day',
                        conclusion_filter: filterState.conclusion_filter || 'all',
                        refresh_rate: filterState.refresh_rate || 10
                    };
                }
            } catch (e) {
                console.warn('Failed to load filter state:', e);
            }
            return {
                time_filter: 'current_day',
                conclusion_filter: 'all',
                refresh_rate: 10
            };
        }
        
        // Initialize filter state from localStorage
        const savedState = loadFilterState();
        
        // Store current filter state
        let currentFilters = {
            time_filter: savedState.time_filter,
            conclusion_filter: savedState.conclusion_filter
        };
        
        // Refresh rate management
        let refreshInterval = null;
        let currentRefreshRate = savedState.refresh_rate;
        
        // Track displayed workflows for smart filtering
        let displayedWorkflowIds = new Set();
        
        // Timezone utility functions
        function getLocalTimezoneOffset() {
            // Get timezone offset in minutes (negative for UTC+, positive for UTC-)
            return new Date().getTimezoneOffset();
        }
        
        function convertUTCToLocal(utcDateString) {
            if (!utcDateString) return 'N/A';
            
            try {
                // Parse UTC date and convert to local time
                const utcDate = new Date(utcDateString + (utcDateString.includes('Z') ? '' : 'Z'));
                return utcDate.toLocaleString();
            } catch (e) {
                console.warn('Failed to parse date:', utcDateString, e);
                return utcDateString;
            }
        }
        
        function getLocalDateString(date = new Date()) {
            // Get YYYY-MM-DD format in local timezone
            return date.toLocaleDateString('en-CA'); // en-CA gives YYYY-MM-DD format
        }
        
        function getLocalDateTimeString(date = new Date()) {
            // Get YYYY-MM-DD HH:MM:SS format in local timezone
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const seconds = String(date.getSeconds()).padStart(2, '0');
            return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
        }
        
        socket.on('connect', function() {
            document.getElementById('connectionStatus').textContent = 'Connected';
            document.getElementById('connectionStatus').className = 'connection-status connected';
            console.log('Connected to server');
        });
        
        socket.on('disconnect', function() {
            document.getElementById('connectionStatus').textContent = 'Disconnected';
            document.getElementById('connectionStatus').className = 'connection-status disconnected';
            console.log('Disconnected from server');
        });
        
        socket.on('workflow_update', function(data) {
            // Database change detected - if auto-refresh is off, update immediately
            if (currentRefreshRate === 'off') {
                requestWorkflows();
            }
            // If auto-refresh is on, let the timer handle updates
        });
        
        function updateWorkflows(workflows) {
            const container = document.getElementById('workflowsContainer');
            
            // Store previous IDs before updating
            const previousIds = new Set(displayedWorkflowIds);
            
            // Update displayed workflow IDs for smart filtering
            displayedWorkflowIds.clear();
            workflows.forEach(workflow => displayedWorkflowIds.add(workflow.id));
            
            container.innerHTML = workflows.map(workflow => {
                // Check if this workflow doesn't match current filter (status changed)
                const statusChanged = currentFilters.conclusion_filter !== 'all' && 
                                    workflow.conclusion !== currentFilters.conclusion_filter &&
                                    previousIds.has(workflow.id);
                
                return `
                <div class="workflow-card ${workflow.conclusion} pulse ${statusChanged ? 'status-changed' : ''}">
                    <div class="workflow-header">
                        <div class="workflow-name">${workflow.name}</div>
                        <div class="conclusion-badge conclusion-${workflow.conclusion}">
                            ${workflow.conclusion}
                        </div>
                    </div>
                    
                    <div class="workflow-details">
                        <p><strong>Repo:</strong> <span class="status-text">${workflow.repository_name}</span></p>
                        <p><strong>Branch:</strong> ${workflow.head_branch }</p>
                        <p><strong>Run:</strong> ${workflow.run_url ? `<a href="${workflow.run_url}" target="_blank" style="color: #2196F3; text-decoration: none;">#${workflow.run_number}</a>` : `#${workflow.run_number || 'N/A'}`}</p>
                    </div>
                    
                    <div class="workflow-meta">
                        <span><strong>Updated:</strong> ${convertUTCToLocal(workflow.updated_at)}</span>
                    </div>
                </div>
                `;
            }).join('');
            
            // Remove pulse animation after a short delay
            setTimeout(() => {
                document.querySelectorAll('.pulse').forEach(el => {
                    el.classList.remove('pulse');
                });
            }, 2000);
        }
        
        function updateLastUpdatedTime() {
            document.getElementById('updateTime').textContent = new Date().toLocaleString();
        }
        
        function startAutoRefresh() {
            // Clear existing interval
            if (refreshInterval) {
                clearInterval(refreshInterval);
                refreshInterval = null;
            }
            
            // Start new interval if rate is not 'off'
            if (currentRefreshRate !== 'off') {
                refreshInterval = setInterval(function() {
                    requestWorkflows();
                }, currentRefreshRate * 1000);
            }
        }
        
        function handleRefreshRateChange() {
            const refreshRate = document.getElementById('refreshRateFilter').value;
            currentRefreshRate = refreshRate === 'off' ? 'off' : parseInt(refreshRate);
            
            // Save refresh rate to localStorage
            saveFilterState();
            
            startAutoRefresh();
        }
        
        function requestWorkflows(clearTracking = false) {
            if (clearTracking) {
                displayedWorkflowIds.clear();
            }
            
            const requestData = {
                ...currentFilters,
                include_ids: Array.from(displayedWorkflowIds),
                timezone_offset: getLocalTimezoneOffset()
            };
            
            socket.emit('get_workflows', requestData);
        }
        
        function applyFilters() {
            const timeFilter = document.getElementById('timeFilter').value;
            const conclusionFilter = document.getElementById('conclusionFilter').value;
            
            // Update current filter state
            currentFilters = {
                time_filter: timeFilter,
                conclusion_filter: conclusionFilter
            };
            
            // Save filter state to localStorage
            saveFilterState();
            
            // Clear tracking when filters change manually
            requestWorkflows(true);
        }
        
        // Add event listeners for filters
        document.addEventListener('DOMContentLoaded', function() {
            // Set dropdown values from saved state
            document.getElementById('timeFilter').value = currentFilters.time_filter;
            document.getElementById('conclusionFilter').value = currentFilters.conclusion_filter;
            document.getElementById('refreshRateFilter').value = currentRefreshRate.toString();
            
            // Add event listeners
            document.getElementById('timeFilter').addEventListener('change', applyFilters);
            document.getElementById('conclusionFilter').addEventListener('change', applyFilters);
            document.getElementById('refreshRateFilter').addEventListener('change', handleRefreshRateChange);
            
            // Start auto refresh with saved rate
            startAutoRefresh();
        });
        
        // Request initial data
        requestWorkflows(true);
        
        socket.on('initial_workflows', function(data) {
            updateWorkflows(data.workflows);
            updateLastUpdatedTime();
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    workflows = get_workflows()
    emit('initial_workflows', {'workflows': workflows})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('get_workflows')
def handle_get_workflows(data=None):
    time_filter = data.get('time_filter', 'all') if data else 'all'
    conclusion_filter = data.get('conclusion_filter', 'all') if data else 'all'
    include_ids = data.get('include_ids', []) if data else []
    timezone_offset = data.get('timezone_offset', 0) if data else 0
    workflows = get_workflows(time_filter, conclusion_filter, include_ids, timezone_offset)
    emit('initial_workflows', {'workflows': workflows})

def simulate_database_changes():
    """Simulate database changes for demonstration"""
    import random
    
    while True:
        time.sleep(10)  # Wait 10 seconds between updates
        
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            
            # Randomly update a workflow
            cursor.execute('SELECT id FROM workflow_runs ORDER BY RANDOM() LIMIT 1')
            workflow_id = cursor.fetchone()[0]
            
            # Random conclusions
            conclusions = ['success', 'failed', 'pending']
            new_conclusion = random.choice(conclusions)
            
            cursor.execute('''
                UPDATE workflow_runs 
                SET workflow_conclusion = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_conclusion, workflow_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated workflow {workflow_id} to {new_conclusion}")
            
        except Exception as e:
            logger.error(f"Simulation error: {e}")

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Start database monitoring thread
    monitor_thread = threading.Thread(target=monitor_database, daemon=True)
    monitor_thread.start()
    
    # Start simulation thread (optional - for demonstration)
    #simulation_thread = threading.Thread(target=simulate_database_changes, daemon=True)
    #simulation_thread.start()
    
    logger.info(f"Starting Workflow Dashboard on {HOST}:{PORT}")
    logger.info(f"Database: {DATABASE}")
    logger.info("Configuration loaded from config.json")
    logger.info(f"Access the dashboard at: http://{HOST}:{PORT}")
    
    # Run the Flask-SocketIO app
    socketio.run(app, debug=True, host=HOST, port=PORT)