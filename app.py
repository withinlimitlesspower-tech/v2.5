#!/usr/bin/env python3
"""
BotManager V3.0 - DEEPSEEK ONLY
Single Provider, Ultra-Fast, No Fallbacks
Zero Bloat, Maximum Performance
"""

import os
import json
import uuid
import logging
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Import handlers
from utils.file_manager import FileManager
from utils.github_handler import GitHubHandler
from utils.api_handler import APIHandler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
CORS(app)

# Initialize handlers
api_handler = APIHandler()  # DeepSeek ONLY
file_manager = FileManager()
github_handler = GitHubHandler(os.getenv('GITHUB_TOKEN'))


class ProjectPlanExtractor:
    """Extract project plans from AI responses"""
    
    VALID_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
        '.json', '.yaml', '.yml', '.toml', '.xml', '.md', '.txt',
        '.sql', '.sh', '.env', '.gitignore', '.dockerignore'
    }
    
    @classmethod
    def extract_files(cls, response: str, user_message: str = "") -> List[str]:
        """Extract file paths from AI response"""
        files = []
        
        # Remove code blocks
        response = re.sub(r'```[\s\S]*?```', '', response)
        
        # Find file paths
        path_pattern = re.compile(r'\b([a-zA-Z][\w\-/]*\.[a-zA-Z]{1,4})\b')
        matches = path_pattern.findall(response)
        
        seen = set()
        for match in matches:
            match = match.strip().strip('`*[](){}:;\'"')
            ext = '.' + match.split('.')[-1].lower() if '.' in match else ''
            if ext in cls.VALID_EXTENSIONS and match not in seen:
                seen.add(match)
                files.append(match)
        
        # Smart defaults if no files found
        if not files:
            files = cls._get_default_files(user_message)
        
        logger.info(f"Extracted {len(files)} files")
        return files[:35]  # Limit to 35 files
    
    @classmethod
    def _get_default_files(cls, message: str) -> List[str]:
        """Smart defaults based on project type"""
        msg_lower = message.lower()
        
        if 'bot' in msg_lower or 'manager' in msg_lower:
            return [
                'app.py', 'config.py', 'requirements.txt',
                'api/__init__.py', 'api/bots.py', 'api/chat.py',
                'utils/api_handler.py', 'utils/file_manager.py',
                'templates/index.html', 'static/css/style.css',
                'static/js/app.js', 'README.md'
            ]
        elif 'flask' in msg_lower:
            return [
                'app.py', 'requirements.txt',
                'templates/index.html', 'static/style.css',
                'README.md'
            ]
        else:
            return ['app.py', 'README.md']


class CodeCleaner:
    """Clean generated code"""
    
    @staticmethod
    def clean(code: str) -> str:
        if not code:
            return ""
        code = code.strip()
        if code.startswith('```'):
            lines = code.split('\n')
            if lines and lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].startswith('```'):
                lines = lines[:-1]
            code = '\n'.join(lines)
        return code.strip()


def get_smart_tokens(filepath: str) -> int:
    """Calculate optimal tokens based on file type"""
    base_name = filepath.split('/')[-1].lower()
    ext = filepath.split('.')[-1].lower() if '.' in filepath else ''
    
    # Ultra-small files
    if base_name == '__init__.py':
        return 150
    elif filepath == 'requirements.txt':
        return 250
    elif filepath.endswith('.env') or filepath.endswith('.gitignore'):
        return 200
    elif base_name == 'README.md':
        return 800
    
    # Config files
    elif ext in ['txt', 'md', 'json', 'yaml', 'yml', 'toml']:
        return 500
    
    # Frontend files
    elif ext in ['css', 'scss', 'html']:
        return 1500
    
    # Code files
    elif ext in ['py', 'js', 'ts']:
        if 'app.py' in base_name or 'main.py' in base_name:
            return 4096
        elif 'api' in filepath or 'handler' in filepath:
            return 3000
        else:
            return 2500
    
    return 1000


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve main page"""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '3.0.0',
        'provider': 'deepseek',
        'model': 'deepseek-chat',
        'fallbacks': 'NONE',
        'stats': api_handler.get_stats()
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat with DeepSeek - Get project plan"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        user_message = data.get('message', '').strip()
        project_id = data.get('project_id', str(uuid.uuid4()))

        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400

        logger.info(f"Processing chat for project {project_id}")

        # System prompt for project planning
        system_prompt = """You are an AI project planning assistant. When users describe a project:
        1. Provide a structured plan with file structure
        2. List specific files with full paths (e.g., backend/api/bots.py)
        3. Recommend technical stack
        4. Include key implementation details

        Be specific about which files need to be created."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Get response from DeepSeek
        response = api_handler.chat(messages)
        
        if not response['success']:
            return jsonify({'error': response['error']}), 500

        ai_response = response['content']
        files = ProjectPlanExtractor.extract_files(ai_response, user_message)

        project_plan = {
            'files': files,
            'description': user_message[:200]
        }

        # Save project
        project_data = {
            'id': project_id,
            'plan': project_plan,
            'description': user_message,
            'created_at': datetime.now().isoformat(),
            'status': 'planned'
        }
        file_manager.write_json(f"projects/{project_id}.json", project_data)

        logger.info(f"Files to generate: {files}")
        
        return jsonify({
            'response': ai_response,
            'project_id': project_id,
            'project_plan': project_plan,
            'tokens_used': response.get('tokens', 0)
        })

    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/generate', methods=['POST'])
def generate_code():
    """Generate code for all files in project"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        project_id = data.get('project_id')
        plan = data.get('plan', {})

        if not project_id:
            return jsonify({'error': 'Missing project_id'}), 400

        files = plan.get('files', [])
        if not files:
            return jsonify({'error': 'No files specified in plan'}), 400

        logger.info(f"🚀 Generating {len(files)} files for project {project_id}")

        generated_files = {}
        failed_files = []

        for filepath in files:
            try:
                smart_tokens = get_smart_tokens(filepath)
                logger.info(f"⚡ Generating {filepath} (tokens={smart_tokens})")

                system_prompt = f"""You are an expert programmer. Generate complete, production-ready code for {filepath}.
                
                Important:
                - Provide ONLY the code without markdown formatting
                - Include all necessary imports and dependencies
                - Add helpful comments
                - Ensure the code is functional"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate the complete code for {filepath}"}
                ]

                response = api_handler.chat(messages, max_tokens=smart_tokens)
                
                if response['success']:
                    code = CodeCleaner.clean(response['content'])
                    generated_files[filepath] = code
                    file_manager.write_file(f"projects/{project_id}/files/{filepath}", code)
                    logger.info(f"✅ Generated {filepath}")
                else:
                    failed_files.append(filepath)
                    logger.error(f"❌ Failed {filepath}: {response['error']}")

            except Exception as e:
                logger.error(f"Failed {filepath}: {str(e)}")
                failed_files.append(filepath)

        if not generated_files:
            raise Exception("No files were successfully generated")

        # Push to GitHub if token available
        repo_url = None
        if os.getenv('GITHUB_TOKEN'):
            try:
                repo_name = f"ai-project-{project_id[:8]}"
                repo_url = github_handler.create_and_push(repo_name, generated_files)
                logger.info(f"📦 Pushed to GitHub: {repo_url}")
            except Exception as e:
                logger.warning(f"GitHub push failed: {e}")

        # Update project status
        project_file = f"projects/{project_id}.json"
        if file_manager.file_exists(project_file):
            project_data = file_manager.read_json(project_file)
            project_data['status'] = 'generated'
            project_data['repo_url'] = repo_url
            project_data['generated_at'] = datetime.now().isoformat()
            file_manager.write_json(project_file, project_data)

        return jsonify({
            'success': True,
            'repo_url': repo_url,
            'generated_files': list(generated_files.keys()),
            'failed_files': failed_files if failed_files else None,
            'stats': api_handler.get_stats()
        })

    except Exception as e:
        logger.error(f"Generation error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects"""
    try:
        projects = []
        if file_manager.directory_exists('projects'):
            for file in file_manager.list_files('projects', '*.json'):
                project = file_manager.read_json(file)
                projects.append({
                    'id': project.get('id'),
                    'description': project.get('description', '')[:100],
                    'status': project.get('status', 'unknown'),
                    'created_at': project.get('created_at'),
                    'repo_url': project.get('repo_url')
                })
        
        projects.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'projects': projects})
        
    except Exception as e:
        logger.error(f"Error getting projects: {e}")
        return jsonify({'projects': [], 'error': str(e)})


@app.route('/api/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """Get specific project"""
    try:
        project_file = f"projects/{project_id}.json"
        if not file_manager.file_exists(project_file):
            return jsonify({'error': 'Project not found'}), 404
        
        project = file_manager.read_json(project_file)
        return jsonify({'project': project})
        
    except Exception as e:
        logger.error(f"Error getting project: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/project/<project_id>/files', methods=['GET'])
def get_project_files(project_id: str):
    """Get all files for a project"""
    try:
        files_dir = f"projects/{project_id}/files"
        if not file_manager.directory_exists(files_dir):
            return jsonify({'files': []})
        
        files = []
        for filepath in file_manager.list_files(files_dir, '*', recursive=True):
            content = file_manager.read_file(filepath)
            files.append({
                'path': filepath.replace(f"projects/{project_id}/files/", ""),
                'content': content
            })
        
        return jsonify({'files': files})
        
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        return jsonify({'files': [], 'error': str(e)})


@app.route('/api/project/<project_id>/download', methods=['GET'])
def download_project(project_id: str):
    """Download project as ZIP"""
    try:
        import zipfile
        import io
        
        files_dir = f"projects/{project_id}/files"
        if not file_manager.directory_exists(files_dir):
            return jsonify({'error': 'Project files not found'}), 404
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filepath in file_manager.list_files(files_dir, '*', recursive=True):
                arcname = filepath.replace(f"projects/{project_id}/files/", "")
                zf.write(filepath, arcname)
        
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'project_{project_id}.zip'
        )
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """Delete a project"""
    try:
        project_file = f"projects/{project_id}.json"
        files_dir = f"projects/{project_id}"
        
        if file_manager.file_exists(project_file):
            file_manager.delete_file(project_file)
        
        if file_manager.directory_exists(files_dir):
            file_manager.delete_directory(files_dir, force=True)
        
        logger.info(f"Deleted project {project_id}")
        return jsonify({'success': True, 'message': 'Project deleted'})
        
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    return jsonify({
        'api': api_handler.get_stats(),
        'provider': 'deepseek',
        'model': 'deepseek-chat',
        'fallbacks': 'NONE'
    })


if __name__ == '__main__':
    # Create directories
    file_manager.create_directory('projects')
    file_manager.create_directory('static')
    file_manager.create_directory('templates')
    
    logger.info("=" * 50)
    logger.info("🚀 BotManager V3.0 - DEEPSEEK ONLY")
    logger.info(f"DeepSeek API: {'✅' if os.getenv('DEEPSEEK_API_KEY') else '❌'}")
    logger.info(f"GitHub: {'✅' if os.getenv('GITHUB_TOKEN') else '❌'}")
    logger.info("=" * 50)
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
