#!/usr/bin/env python3
"""
BotManager V3.0 - DEEPSEEK V3.2 ONLY
Model: deepseek-chat (V3.2)
Single Provider, Ultra-Fast, No Fallbacks
Max Output: 8192 tokens
Zero Bloat, Maximum Performance
"""

import os
import json
import uuid
import logging
import time
import re
import zipfile
import io
from datetime import datetime
from typing import Dict, List, Optional, Any

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Import handlers
from utils.file_manager import FileManager
from utils.github_handler import GitHubHandler
from utils.api_handler import APIHandler  # DeepSeek V3.2

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
api_handler = APIHandler()  # DeepSeek V3.2 ONLY
file_manager = FileManager()
github_handler = GitHubHandler(os.getenv('GITHUB_TOKEN')) if os.getenv('GITHUB_TOKEN') else None


class ProjectPlanExtractor:
    """Extract project plans from AI responses"""
    
    VALID_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
        '.json', '.yaml', '.yml', '.toml', '.xml', '.md', '.txt',
        '.sql', '.sh', '.env', '.gitignore', '.dockerignore'
    }
    
    INVALID_PATTERNS = [
        r'logging\.', r'logger\.', r'session\.', r'request\.', r'response\.',
        r'\.basi', r'\.INFO', r'\.getL', r'\.secr', r'\.envi', r'ron\.get',
        r'\.get\(', r'\.setd', r'\.modi', r'\.appe', r'\.erro', r'\.warn',
    ]
    
    @classmethod
    def extract_files(cls, response: str, user_message: str = "") -> List[str]:
        """Extract file paths from AI response"""
        files = []
        
        # Remove code blocks
        response = re.sub(r'```[\s\S]*?```', '', response)
        
        # Pattern 1: Paths with slashes
        path_pattern = re.compile(r'\b([a-zA-Z][\w\-/]*\.[a-zA-Z]{1,4})\b')
        matches = path_pattern.findall(response)
        
        # Pattern 2: List items
        list_pattern = re.compile(r'[-*•]\s*[`]?([\w\-/]+\.[\w]+)[`]?')
        matches.extend(list_pattern.findall(response))
        
        # Pattern 3: Numbered lists
        numbered_pattern = re.compile(r'\d+\.\s*[`]?([\w\-/]+\.[\w]+)[`]?')
        matches.extend(numbered_pattern.findall(response))
        
        seen = set()
        for match in matches:
            match = match.strip().strip('`*[](){}:;\'"')
            
            # Validate
            if not match or len(match) < 3 or len(match) > 100:
                continue
            if '.' not in match:
                continue
                
            ext = '.' + match.split('.')[-1].lower()
            if ext not in cls.VALID_EXTENSIONS:
                continue
                
            # Check invalid patterns
            invalid = False
            for pattern in cls.INVALID_PATTERNS:
                if re.search(pattern, match, re.IGNORECASE):
                    invalid = True
                    break
            if invalid:
                continue
                
            if match not in seen:
                seen.add(match)
                files.append(match)
        
        # Smart defaults if no files found
        if not files:
            files = cls._get_default_files(user_message)
        
        # Limit to 35 files
        if len(files) > 35:
            priority = ['.py', '.js', '.html', '.css', '.json', '.md']
            priority_files = [f for f in files if any(f.endswith(ext) for ext in priority)]
            other_files = [f for f in files if f not in priority_files]
            files = priority_files + other_files[:35 - len(priority_files)]
        
        logger.info(f"📁 Extracted {len(files)} valid files")
        return files
    
    @classmethod
    def _get_default_files(cls, message: str) -> List[str]:
        """Smart defaults based on project type"""
        msg_lower = message.lower()
        
        if 'bot manager' in msg_lower or 'multi-bot' in msg_lower:
            return [
                'app.py', 'config.py', 'requirements.txt',
                'api/__init__.py', 'api/bots.py', 'api/chat.py',
                'api/analytics.py', 'services/bot_manager.py',
                'models/bot_model.py', 'utils/api_handler.py',
                'utils/file_manager.py', 'templates/index.html',
                'static/css/style.css', 'static/js/app.js', 'README.md'
            ]
        elif 'flask' in msg_lower:
            return [
                'app.py', 'requirements.txt',
                'templates/index.html', 'static/style.css',
                'static/script.js', 'README.md'
            ]
        elif 'weather' in msg_lower:
            return ['index.html', 'style.css', 'script.js', 'README.md']
        elif 'calculator' in msg_lower:
            return ['index.html', 'style.css', 'script.js', 'README.md']
        elif 'todo' in msg_lower:
            return ['index.html', 'style.css', 'script.js', 'README.md']
        elif 'react' in msg_lower:
            return [
                'src/App.js', 'src/index.js', 'public/index.html',
                'package.json', 'README.md'
            ]
        else:
            return ['app.py', 'requirements.txt', 'README.md']


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
    """
    Calculate optimal tokens based on file type
    DeepSeek V3.2 max: 8192
    """
    base_name = filepath.split('/')[-1].lower()
    ext = filepath.split('.')[-1].lower() if '.' in filepath else ''
    
    # 🚀 ULTRA-FAST: Tiny files
    if base_name == '__init__.py':
        return 150
    elif filepath == 'requirements.txt':
        return 250
    elif filepath.endswith('.env') or filepath.endswith('.gitignore'):
        return 200
    elif base_name == 'package.json':
        return 400
    elif base_name == 'README.md':
        return 800
    
    # ⚡ FAST: Config files
    elif ext in ['txt', 'md', 'json', 'yaml', 'yml', 'toml']:
        if 'config' in base_name or 'settings' in base_name:
            return 500
        else:
            return 400
    
    # 🎨 MEDIUM: Frontend files
    elif ext in ['css', 'scss', 'html']:
        if 'dark' in base_name or 'theme' in base_name:
            return 800
        else:
            return 1500
    
    # 💻 COMPLEX: Code files
    elif ext in ['py', 'js', 'ts', 'jsx', 'tsx']:
        if base_name in ['app.py', 'main.py', 'server.py', 'index.js']:
            return 4096
        elif 'api' in filepath or 'routes' in filepath:
            return 3000
        elif 'service' in filepath or 'manager' in filepath or 'handler' in filepath:
            return 3500
        elif 'model' in filepath or 'schema' in filepath:
            return 2000
        elif 'util' in filepath or 'helper' in filepath:
            return 2000
        else:
            return 2500
    
    # Default
    return 1000


def extract_project_name(message: str, max_length: int = 30) -> str:
    """Extract project name from message"""
    words = message.strip().split()[:5]
    name = ' '.join(words).title()
    if len(name) > max_length:
        name = name[:max_length-3] + '...'
    return name


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
        'model_version': '3.2',
        'max_output_tokens': 8192,
        'fallbacks': 'NONE',
        'github_connected': github_handler is not None,
        'stats': api_handler.get_stats()
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat with DeepSeek V3.2 - Get project plan"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        user_message = data.get('message', '').strip()
        project_id = data.get('project_id', str(uuid.uuid4()))

        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400

        logger.info(f"💬 Processing chat for project {project_id}")

        # System prompt for project planning
        system_prompt = """You are an AI project planning assistant powered by DeepSeek V3.2. 
        When users describe a project:
        
        1. Provide a structured plan with file structure
        2. List specific files with full paths (e.g., backend/api/bots.py)
        3. Recommend technical stack
        4. Include key implementation details
        5. Suggest appropriate architecture
        
        Be specific about which files need to be created. Use proper file extensions."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Get response from DeepSeek V3.2
        response = api_handler.chat(messages, max_tokens=2000)
        
        if not response['success']:
            logger.error(f"Chat failed: {response['error']}")
            return jsonify({'error': response['error']}), 500

        ai_response = response['content']
        files = ProjectPlanExtractor.extract_files(ai_response, user_message)

        project_plan = {
            'files': files,
            'description': ai_response[:500]
        }

        project_name = extract_project_name(user_message)

        # Save project
        project_data = {
            'id': project_id,
            'name': project_name,
            'plan': project_plan,
            'description': user_message,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'status': 'planned',
            'model': 'deepseek-chat'
        }
        
        file_manager.create_directory('projects')
        file_manager.write_json(f"projects/{project_id}.json", project_data)

        logger.info(f"📋 Files to generate: {files}")
        
        return jsonify({
            'response': ai_response,
            'project_id': project_id,
            'project_name': project_name,
            'project_plan': project_plan,
            'tokens_used': response.get('tokens', 0),
            'model': 'deepseek-chat'
        })

    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/generate', methods=['POST'])
def generate_code():
    """Generate code for all files using DeepSeek V3.2"""
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

        # Load project data
        project_file = f"projects/{project_id}.json"
        if not file_manager.file_exists(project_file):
            return jsonify({'error': f'Project {project_id} not found'}), 404
        
        project_data = file_manager.read_json(project_file)
        description = project_data.get('description', 'AI Generated Project')

        generated_files = {}
        failed_files = []
        total_tokens = 0

        for idx, filepath in enumerate(files, 1):
            try:
                smart_tokens = get_smart_tokens(filepath)
                logger.info(f"⚡ [{idx}/{len(files)}] Generating {filepath} (tokens={smart_tokens})")

                system_prompt = f"""You are an expert programmer. Generate complete, production-ready code for {filepath}.
                
                Project: {description}
                
                Important:
                - Provide ONLY the code without markdown formatting
                - Include all necessary imports and dependencies
                - Add helpful comments
                - Follow best practices
                - Ensure the code is functional"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate the complete code for {filepath}"}
                ]

                response = api_handler.chat(messages, temperature=0.3, max_tokens=smart_tokens)
                
                if response['success']:
                    code = CodeCleaner.clean(response['content'])
                    generated_files[filepath] = code
                    
                    # Save file
                    file_path = f"projects/{project_id}/files/{filepath}"
                    file_manager.write_file(file_path, code)
                    
                    total_tokens += response.get('tokens', 0)
                    logger.info(f"   ✅ Generated {filepath} ({response.get('tokens', 0)} tokens)")
                else:
                    failed_files.append(filepath)
                    logger.error(f"   ❌ Failed {filepath}: {response['error']}")

            except Exception as e:
                logger.error(f"   ❌ Exception {filepath}: {str(e)}")
                failed_files.append(filepath)

        if not generated_files:
            raise Exception("No files were successfully generated")

        # Push to GitHub if configured
        repo_url = None
        if github_handler:
            try:
                repo_name = f"ai-project-{project_id[:8]}"
                repo_url = github_handler.create_and_push(repo_name, generated_files)
                logger.info(f"📦 Pushed to GitHub: {repo_url}")
            except Exception as e:
                logger.warning(f"GitHub push failed: {e}")

        # Update project status
        project_data['status'] = 'generated'
        project_data['repo_url'] = repo_url
        project_data['generated_at'] = datetime.now().isoformat()
        project_data['updated_at'] = datetime.now().isoformat()
        project_data['total_tokens_used'] = total_tokens
        project_data['files_generated'] = len(generated_files)
        project_data['files_failed'] = len(failed_files)
        file_manager.write_json(project_file, project_data)

        return jsonify({
            'success': True,
            'repo_url': repo_url,
            'generated_files': list(generated_files.keys()),
            'failed_files': failed_files if failed_files else None,
            'total_tokens': total_tokens,
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
                try:
                    project = file_manager.read_json(file)
                    projects.append({
                        'id': project.get('id'),
                        'name': project.get('name', 'Untitled'),
                        'description': project.get('description', '')[:100],
                        'status': project.get('status', 'unknown'),
                        'created_at': project.get('created_at'),
                        'generated_at': project.get('generated_at'),
                        'repo_url': project.get('repo_url'),
                        'files_generated': project.get('files_generated', 0),
                        'model': project.get('model', 'deepseek-chat')
                    })
                except Exception as e:
                    logger.error(f"Error loading {file}: {e}")
        
        projects.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        logger.info(f"📚 Found {len(projects)} projects")
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
            try:
                content = file_manager.read_file(filepath)
                rel_path = filepath.replace(files_dir + '/', '')
                files.append({
                    'path': rel_path,
                    'content': content,
                    'size': len(content)
                })
            except Exception as e:
                logger.error(f"Error reading {filepath}: {e}")
        
        return jsonify({'files': files})
        
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        return jsonify({'files': [], 'error': str(e)})


@app.route('/api/project/<project_id>/download', methods=['GET'])
def download_project(project_id: str):
    """Download project as ZIP"""
    try:
        files_dir = f"projects/{project_id}/files"
        if not file_manager.directory_exists(files_dir):
            return jsonify({'error': 'Project files not found'}), 404
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filepath in file_manager.list_files(files_dir, '*', recursive=True):
                arcname = filepath.replace(files_dir + '/', '')
                zf.write(filepath, arcname)
        
        memory_file.seek(0)
        
        project_data = file_manager.read_json(f"projects/{project_id}.json")
        project_name = project_data.get('name', project_id)[:20]
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{project_name}_{project_id[:8]}.zip'
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
        
        logger.info(f"🗑️ Deleted project {project_id}")
        return jsonify({'success': True, 'message': 'Project deleted'})
        
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/project/<project_id>/status', methods=['GET'])
def get_project_status(project_id: str):
    """Get project generation status"""
    try:
        project_file = f"projects/{project_id}.json"
        if not file_manager.file_exists(project_file):
            return jsonify({'status': 'not_found'})
        
        project = file_manager.read_json(project_file)
        return jsonify({
            'status': project.get('status', 'unknown'),
            'repo_url': project.get('repo_url'),
            'files_generated': project.get('files_generated', 0),
            'updated_at': project.get('updated_at')
        })
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    api_stats = api_handler.get_stats()
    
    # Count projects
    project_count = 0
    if file_manager.directory_exists('projects'):
        project_count = len(file_manager.list_files('projects', '*.json'))
    
    return jsonify({
        'api': api_stats,
        'projects_total': project_count,
        'provider': 'deepseek',
        'model': 'deepseek-chat',
        'version': '3.2',
        'max_tokens': 8192,
        'fallbacks': 'NONE',
        'github_connected': github_handler is not None
    })


@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    """Test DeepSeek V3.2 connection"""
    try:
        is_healthy = api_handler.health_check()
        return jsonify({
            'connected': is_healthy,
            'provider': 'deepseek',
            'model': 'deepseek-chat',
            'version': '3.2'
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    # Create necessary directories
    file_manager.create_directory('projects')
    file_manager.create_directory('static')
    file_manager.create_directory('templates')
    
    # Create default index.html if not exists
    if not file_manager.file_exists('templates/index.html'):
        default_html = """<!DOCTYPE html>
<html>
<head>
    <title>BotManager V3 - DeepSeek V3.2</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <h1>🤖 BotManager V3.0</h1>
    <p>DeepSeek V3.2 - Ready</p>
    <p>Model: deepseek-chat | Max Tokens: 8192</p>
</body>
</html>"""
        file_manager.write_file('templates/index.html', default_html)
    
    logger.info("=" * 60)
    logger.info("🚀 BotManager V3.0 Starting...")
    logger.info(f"🤖 Provider: DeepSeek V3.2 (deepseek-chat)")
    logger.info(f"📊 Max Output Tokens: 8192")
    logger.info(f"🔑 DeepSeek API: {'✅ Configured' if os.getenv('DEEPSEEK_API_KEY') else '❌ MISSING'}")
    logger.info(f"📦 GitHub: {'✅ Connected' if github_handler else '❌ Not configured'}")
    logger.info(f"🔄 Fallbacks: NONE (DeepSeek ONLY)")
    logger.info(f"⚡ Smart Tokens: ENABLED")
    logger.info("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
