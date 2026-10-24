from flask import Blueprint, render_template
from flask_login import login_required

from routes.admin import (
    get_agents as admin_get_agents,
    create_agent as admin_create_agent,
    update_agent as admin_update_agent,
    delete_agent as admin_delete_agent,
    batch_update_agents as admin_batch_update_agents,
)


agent_bp = Blueprint('agent', __name__, url_prefix='/agent')


@agent_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('admin/dashboard.html')


@agent_bp.route('/agents')
@login_required
def agents_page():
    return render_template('admin/agents.html')


@agent_bp.route('/api/agents', methods=['GET'])
@login_required
def get_agents():
    return admin_get_agents()


@agent_bp.route('/api/agents', methods=['POST'])
@login_required
def create_agent():
    return admin_create_agent()


@agent_bp.route('/api/agents/<int:agent_id>', methods=['PUT'])
@login_required
def update_agent(agent_id):
    return admin_update_agent(agent_id)


@agent_bp.route('/api/agents/<int:agent_id>', methods=['DELETE'])
@login_required
def delete_agent(agent_id):
    return admin_delete_agent(agent_id)


@agent_bp.route('/api/agents/batch-update', methods=['POST'])
@login_required
def batch_update_agents():
    return admin_batch_update_agents()


