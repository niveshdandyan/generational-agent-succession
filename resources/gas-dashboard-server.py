#!/usr/bin/env python3
"""
GAS v2 Dashboard Server
=======================
Real-time monitoring dashboard for Generational Agent Succession with Parallel Swarms.

Provides:
- Swarm overview with wave visualization
- Per-agent generation timeline
- Cross-agent knowledge accumulation
- Live succession tracking
"""

import os
import sys
import json
import signal
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Configuration from environment
GAS_DIR = os.getenv('GAS_DIR', '/workspace/project-gas')
GAS_NAME = os.getenv('GAS_NAME', 'GAS Task')
GAS_MODE = os.getenv('GAS_MODE', 'swarm')  # 'swarm' or 'sequential'
PORT = int(os.getenv('GAS_PORT', '8080'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

SERVER_START_TIME = datetime.utcnow().isoformat() + 'Z'


def read_json_file(filepath):
    """Safely read and parse a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
        logger.debug(f"Could not read JSON file {filepath}: {e}")
        return None


def get_agent_generations(agent_dir):
    """Get all generations for an agent."""
    generations = []
    gen_base = os.path.join(agent_dir, 'generations')

    if not os.path.isdir(gen_base):
        return generations

    try:
        for item in os.listdir(gen_base):
            if item.startswith('gen-'):
                try:
                    gen_num = int(item.replace('gen-', ''))
                    gen_dir = os.path.join(gen_base, item)
                    status_file = os.path.join(gen_dir, 'status.json')
                    status = read_json_file(status_file) or {
                        'generation': gen_num,
                        'status': 'pending',
                        'progress': 0,
                        'confidence': 1.0
                    }
                    generations.append(status)
                except ValueError:
                    pass
    except PermissionError:
        pass

    return sorted(generations, key=lambda x: x.get('generation', 0))


def get_agent_status(agent_id, agent_config, gas_dir):
    """Get status of a single agent including all its generations."""
    agent_dir = os.path.join(gas_dir, 'agents', agent_id)

    # Default agent info
    agent_info = {
        'id': agent_id,
        'role': agent_config.get('role', 'Unknown'),
        'wave': agent_config.get('wave', 1),
        'status': 'pending',
        'current_generation': agent_config.get('current_generation', 0),
        'total_generations': agent_config.get('total_generations', 0),
        'progress': 0,
        'generations': []
    }

    # Check agent status file
    status_file = os.path.join(agent_dir, 'status.json')
    agent_status = read_json_file(status_file)
    if agent_status:
        agent_info.update({
            'status': agent_status.get('status', 'running'),
            'progress': agent_status.get('progress', 0),
            'current_generation': agent_status.get('generation', 1)
        })

    # Get all generations for this agent
    generations = get_agent_generations(agent_dir)
    agent_info['generations'] = generations
    agent_info['total_generations'] = len(generations)

    # Calculate overall progress from latest generation
    if generations:
        latest = max(generations, key=lambda x: x.get('generation', 0))
        agent_info['progress'] = latest.get('progress', 0)
        agent_info['status'] = latest.get('status', 'running')
        agent_info['current_generation'] = latest.get('generation', 1)

    return agent_info


def get_knowledge_store(gas_dir):
    """Get accumulated knowledge statistics."""
    store_path = os.path.join(gas_dir, 'knowledge', 'store.json')
    store = read_json_file(store_path)

    if not store:
        return {
            'success_patterns': 0,
            'anti_patterns': 0,
            'domain_insights': 0,
            'total_generations': 0,
            'patterns': [],
            'agent_contributions': {}
        }

    # Count contributions by agent
    agent_contributions = {}
    for pattern in store.get('success_patterns', []):
        agent = pattern.get('source_agent', 'unknown')
        agent_contributions[agent] = agent_contributions.get(agent, 0) + 1

    return {
        'success_patterns': len(store.get('success_patterns', [])),
        'anti_patterns': len(store.get('anti_patterns', [])),
        'domain_insights': len(store.get('domain_knowledge', [])),
        'total_generations': store.get('total_generations_across_swarm', 0),
        'patterns': store.get('success_patterns', [])[:5],  # Top 5 for display
        'agent_contributions': agent_contributions
    }


def format_elapsed_time(start_time_str):
    """Format elapsed time as human-readable string."""
    try:
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=start_time.tzinfo)
        elapsed = now - start_time
        total_seconds = int(elapsed.total_seconds())

        if total_seconds < 0:
            return "0s"

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "Unknown"


def get_gas_status():
    """Gather complete GAS v2 status."""
    # Read GAS state
    state_path = os.path.join(GAS_DIR, 'gas-state.json')
    state = read_json_file(state_path) or {
        'project_name': GAS_NAME,
        'start_time': SERVER_START_TIME,
        'mode': GAS_MODE,
        'task_objective': 'Unknown',
        'swarm': {'waves': {}, 'current_wave': 1},
        'agents': {}
    }

    # Get agent statuses
    agents = {}
    agents_config = state.get('agents', {})

    for agent_id, agent_config in agents_config.items():
        agents[agent_id] = get_agent_status(agent_id, agent_config, GAS_DIR)

    # Organize by waves
    waves = state.get('swarm', {}).get('waves', {})
    wave_status = {}
    for wave_num, wave_agents in waves.items():
        wave_status[wave_num] = {
            'agents': wave_agents,
            'completed': all(
                agents.get(a, {}).get('status') == 'completed'
                for a in wave_agents
            ),
            'in_progress': any(
                agents.get(a, {}).get('status') == 'running'
                for a in wave_agents
            )
        }

    # Get knowledge statistics
    knowledge = get_knowledge_store(GAS_DIR)

    # Calculate aggregates
    total_agents = len(agents)
    completed_agents = sum(1 for a in agents.values() if a['status'] == 'completed')
    running_agents = sum(1 for a in agents.values() if a['status'] == 'running')
    total_generations = sum(a.get('total_generations', 0) for a in agents.values())

    # Succession events
    successions = []
    for agent_id, agent in agents.items():
        for i, gen in enumerate(agent.get('generations', [])[:-1]):
            if gen.get('status') in ['completed', 'needs_succession']:
                successions.append({
                    'agent': agent_id,
                    'from_gen': gen.get('generation', i + 1),
                    'to_gen': gen.get('generation', i + 1) + 1,
                    'reason': gen.get('succession_reason', 'unknown')
                })

    # Overall progress (average of all agent progress)
    if agents:
        overall_progress = sum(a.get('progress', 0) for a in agents.values()) / len(agents)
    else:
        overall_progress = 0

    return {
        'project_name': state.get('project_name', GAS_NAME),
        'task_objective': state.get('task_objective', ''),
        'mode': state.get('mode', GAS_MODE),
        'start_time': state.get('start_time', SERVER_START_TIME),
        'current_wave': state.get('swarm', {}).get('current_wave', 1),
        'agents': agents,
        'waves': wave_status,
        'knowledge': knowledge,
        'successions': successions,
        'overall_progress': round(overall_progress, 1),
        'total_agents': total_agents,
        'completed_agents': completed_agents,
        'running_agents': running_agents,
        'total_generations': total_generations,
        'elapsed_time': format_elapsed_time(state.get('start_time', SERVER_START_TIME)),
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }


def get_dashboard_html():
    """Return the GAS v2 dashboard HTML."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GAS v2 Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0f0f23 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }
        .container { max-width: 1600px; margin: 0 auto; }

        header {
            text-align: center;
            padding: 25px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 25px;
        }
        .logo {
            font-size: 2.8em;
            font-weight: bold;
            background: linear-gradient(90deg, #00d9ff, #00ff88, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .version { color: #666; font-size: 0.9em; }
        .subtitle { color: #888; margin-top: 5px; }
        .objective {
            margin-top: 12px;
            padding: 8px 18px;
            background: rgba(0,217,255,0.1);
            border-radius: 20px;
            display: inline-block;
            font-size: 0.95em;
        }

        .stats {
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 25px;
        }
        .stat {
            text-align: center;
            padding: 15px 22px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            min-width: 100px;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stat-label { font-size: 0.8em; color: #888; margin-top: 3px; }

        .main-grid {
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 20px;
        }
        @media (max-width: 1200px) {
            .main-grid { grid-template-columns: 1fr; }
        }

        .progress-section { margin-bottom: 20px; }
        .progress-label {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9em;
        }
        .progress-bar {
            height: 22px;
            background: rgba(255,255,255,0.1);
            border-radius: 11px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            border-radius: 11px;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #0f0f23;
            font-size: 0.85em;
        }

        .waves-section { margin-bottom: 25px; }
        .section-title {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #00d9ff;
        }
        .wave {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 3px solid #666;
        }
        .wave.completed { border-left-color: #00ff88; }
        .wave.in_progress { border-left-color: #00d9ff; }
        .wave-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .wave-title { font-weight: bold; }
        .wave-status {
            padding: 3px 10px;
            border-radius: 10px;
            font-size: 0.75em;
            text-transform: uppercase;
        }
        .wave-status.completed { background: rgba(0,255,136,0.2); color: #00ff88; }
        .wave-status.in_progress { background: rgba(0,217,255,0.2); color: #00d9ff; }
        .wave-status.pending { background: rgba(102,102,102,0.2); color: #888; }

        .wave-agents {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
        }
        .agent {
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 12px;
            border-left: 3px solid #666;
        }
        .agent.completed { border-left-color: #00ff88; }
        .agent.running { border-left-color: #00d9ff; animation: pulse 2s infinite; }
        .agent.failed { border-left-color: #ff6b6b; }
        .agent.needs_succession { border-left-color: #ffaa00; }

        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(0,217,255,0.3); }
            50% { box-shadow: 0 0 15px 3px rgba(0,217,255,0.15); }
        }

        .agent-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .agent-name { font-weight: bold; font-size: 0.95em; }
        .agent-status {
            padding: 2px 8px;
            border-radius: 8px;
            font-size: 0.7em;
            text-transform: uppercase;
        }
        .agent-status.completed { background: rgba(0,255,136,0.2); color: #00ff88; }
        .agent-status.running { background: rgba(0,217,255,0.2); color: #00d9ff; }
        .agent-status.failed { background: rgba(255,107,107,0.2); color: #ff6b6b; }
        .agent-status.pending { background: rgba(102,102,102,0.2); color: #888; }
        .agent-status.needs_succession { background: rgba(255,170,0,0.2); color: #ffaa00; }

        .generations {
            display: flex;
            gap: 6px;
            margin: 8px 0;
            flex-wrap: wrap;
        }
        .gen-badge {
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.7em;
            font-weight: bold;
        }
        .gen-badge.completed { background: rgba(0,255,136,0.3); color: #00ff88; }
        .gen-badge.running { background: rgba(0,217,255,0.3); color: #00d9ff; }
        .gen-badge.pending { background: rgba(102,102,102,0.3); color: #888; }

        .agent-progress {
            height: 5px;
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }
        .agent-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            transition: width 0.3s ease;
        }

        .sidebar { display: flex; flex-direction: column; gap: 20px; }

        .knowledge-section {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 18px;
        }
        .knowledge-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .knowledge-card {
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
        }
        .knowledge-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #00ff88;
        }
        .knowledge-label { color: #888; font-size: 0.8em; margin-top: 3px; }

        .successions-section {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 18px;
        }
        .succession-list {
            max-height: 200px;
            overflow-y: auto;
        }
        .succession-item {
            padding: 8px 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            margin-bottom: 8px;
            font-size: 0.85em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .succession-arrow {
            color: #ffaa00;
            font-weight: bold;
        }

        .footer {
            text-align: center;
            padding: 15px;
            color: #666;
            font-size: 0.8em;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">GAS <span class="version">v2.0</span></div>
            <div class="subtitle">Parallel Swarms + Generational Succession</div>
            <div class="objective" id="objective">Loading...</div>
        </header>

        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="total-agents">-</div>
                <div class="stat-label">Agents</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="total-gens">-</div>
                <div class="stat-label">Generations</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="patterns">-</div>
                <div class="stat-label">Patterns</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="successions">-</div>
                <div class="stat-label">Successions</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="elapsed">-</div>
                <div class="stat-label">Elapsed</div>
            </div>
        </div>

        <div class="progress-section">
            <div class="progress-label">
                <span>Overall Swarm Progress</span>
                <span id="progress-text">0%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
            </div>
        </div>

        <div class="main-grid">
            <div class="main-content">
                <div class="waves-section">
                    <div class="section-title">Wave Execution</div>
                    <div id="waves-container">
                        <div class="wave pending">
                            <div class="wave-header">
                                <span class="wave-title">Wave 1</span>
                                <span class="wave-status pending">Pending</span>
                            </div>
                            <div class="wave-agents">Loading...</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="sidebar">
                <div class="knowledge-section">
                    <div class="section-title">Accumulated Knowledge</div>
                    <div class="knowledge-grid">
                        <div class="knowledge-card">
                            <div class="knowledge-value" id="success-patterns">0</div>
                            <div class="knowledge-label">Success Patterns</div>
                        </div>
                        <div class="knowledge-card">
                            <div class="knowledge-value" id="anti-patterns">0</div>
                            <div class="knowledge-label">Anti-Patterns</div>
                        </div>
                        <div class="knowledge-card">
                            <div class="knowledge-value" id="insights">0</div>
                            <div class="knowledge-label">Insights</div>
                        </div>
                        <div class="knowledge-card">
                            <div class="knowledge-value" id="completed-agents">0</div>
                            <div class="knowledge-label">Completed</div>
                        </div>
                    </div>
                </div>

                <div class="successions-section">
                    <div class="section-title">Succession Events</div>
                    <div class="succession-list" id="succession-list">
                        <div class="succession-item">No successions yet</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="footer">
            GAS v2 Dashboard | Parallel Swarms + Generational Succession | Auto-refreshes every 2s
        </div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }

        function updateDashboard(data) {
            document.getElementById('objective').textContent = data.task_objective || 'No objective set';
            document.getElementById('total-agents').textContent = data.total_agents;
            document.getElementById('total-gens').textContent = data.total_generations;
            document.getElementById('patterns').textContent =
                data.knowledge.success_patterns + data.knowledge.anti_patterns;
            document.getElementById('successions').textContent = data.successions.length;
            document.getElementById('elapsed').textContent = data.elapsed_time;

            const progress = Math.round(data.overall_progress);
            document.getElementById('progress-text').textContent = progress + '%';
            document.getElementById('progress-fill').style.width = progress + '%';

            document.getElementById('success-patterns').textContent = data.knowledge.success_patterns;
            document.getElementById('anti-patterns').textContent = data.knowledge.anti_patterns;
            document.getElementById('insights').textContent = data.knowledge.domain_insights;
            document.getElementById('completed-agents').textContent = data.completed_agents;

            const wavesContainer = document.getElementById('waves-container');
            wavesContainer.innerHTML = '';

            const sortedWaves = Object.entries(data.waves).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));

            for (const [waveNum, wave] of sortedWaves) {
                const waveStatus = wave.completed ? 'completed' : (wave.in_progress ? 'in_progress' : 'pending');
                const waveEl = document.createElement('div');
                waveEl.className = `wave ${waveStatus}`;

                let agentsHtml = '';
                for (const agentId of wave.agents) {
                    const agent = data.agents[agentId];
                    if (!agent) continue;

                    let gensHtml = '';
                    for (const gen of agent.generations || []) {
                        gensHtml += `<span class="gen-badge ${gen.status}">G${gen.generation}</span>`;
                    }
                    if (!gensHtml && agent.current_generation > 0) {
                        gensHtml = `<span class="gen-badge running">G${agent.current_generation}</span>`;
                    }

                    agentsHtml += `
                        <div class="agent ${agent.status}">
                            <div class="agent-header">
                                <span class="agent-name">${agent.role}</span>
                                <span class="agent-status ${agent.status}">${agent.status}</span>
                            </div>
                            <div class="generations">${gensHtml || '<span class="gen-badge pending">G1</span>'}</div>
                            <div class="agent-progress">
                                <div class="agent-progress-fill" style="width: ${agent.progress}%"></div>
                            </div>
                        </div>
                    `;
                }

                waveEl.innerHTML = `
                    <div class="wave-header">
                        <span class="wave-title">Wave ${waveNum}</span>
                        <span class="wave-status ${waveStatus}">${waveStatus.replace('_', ' ')}</span>
                    </div>
                    <div class="wave-agents">${agentsHtml || '<div>No agents in this wave</div>'}</div>
                `;
                wavesContainer.appendChild(waveEl);
            }

            if (sortedWaves.length === 0 && Object.keys(data.agents).length > 0) {
                const waveEl = document.createElement('div');
                waveEl.className = 'wave in_progress';

                let agentsHtml = '';
                for (const [agentId, agent] of Object.entries(data.agents)) {
                    let gensHtml = '';
                    for (const gen of agent.generations || []) {
                        gensHtml += `<span class="gen-badge ${gen.status}">G${gen.generation}</span>`;
                    }

                    agentsHtml += `
                        <div class="agent ${agent.status}">
                            <div class="agent-header">
                                <span class="agent-name">${agent.role || agentId}</span>
                                <span class="agent-status ${agent.status}">${agent.status}</span>
                            </div>
                            <div class="generations">${gensHtml || '<span class="gen-badge running">G1</span>'}</div>
                            <div class="agent-progress">
                                <div class="agent-progress-fill" style="width: ${agent.progress}%"></div>
                            </div>
                        </div>
                    `;
                }

                waveEl.innerHTML = `
                    <div class="wave-header">
                        <span class="wave-title">Active Agents</span>
                        <span class="wave-status in_progress">Running</span>
                    </div>
                    <div class="wave-agents">${agentsHtml}</div>
                `;
                wavesContainer.appendChild(waveEl);
            }

            const successionList = document.getElementById('succession-list');
            if (data.successions.length > 0) {
                successionList.innerHTML = data.successions.map(s => `
                    <div class="succession-item">
                        <span>${s.agent}</span>
                        <span class="succession-arrow">G${s.from_gen} -> G${s.to_gen}</span>
                    </div>
                `).join('');
            } else {
                successionList.innerHTML = '<div class="succession-item">No successions yet</div>';
            }
        }

        fetchStatus();
        setInterval(fetchStatus, 2000);
    </script>
</body>
</html>'''


class GASHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        try:
            if path == '/' or path == '/index.html':
                self.serve_dashboard()
            elif path == '/api/status':
                self.serve_api_status()
            elif path == '/health':
                self.serve_health()
            else:
                self.send_error(404, 'Not Found')
        except Exception as e:
            logger.error(f"Error handling request {path}: {e}")
            self.send_error(500, str(e))

    def serve_dashboard(self):
        html = get_dashboard_html()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html.encode('utf-8')))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def serve_api_status(self):
        status = get_gas_status()
        json_data = json.dumps(status, indent=2)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(json_data.encode('utf-8')))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json_data.encode('utf-8'))

    def serve_health(self):
        health = {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        json_data = json.dumps(health)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(json_data.encode('utf-8')))
        self.end_headers()
        self.wfile.write(json_data.encode('utf-8'))


def run_server(port=PORT):
    server_address = ('', port)
    httpd = HTTPServer(server_address, GASHandler)

    def signal_handler(signum, frame):
        logger.info("Shutting down GAS v2 Dashboard...")
        httpd.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 50)
    logger.info("GAS v2 Dashboard Server")
    logger.info("=" * 50)
    logger.info(f"Port: {port}")
    logger.info(f"GAS_DIR: {GAS_DIR}")
    logger.info(f"GAS_MODE: {GAS_MODE}")
    logger.info(f"Project: {GAS_NAME}")
    logger.info("=" * 50)
    logger.info(f"Dashboard: http://localhost:{port}/")
    logger.info(f"API:       http://localhost:{port}/api/status")
    logger.info("=" * 50)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        httpd.server_close()
        logger.info("Server stopped.")


if __name__ == '__main__':
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)

    run_server(port)
