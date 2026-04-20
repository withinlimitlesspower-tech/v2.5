"""
GitHub Handler for BotManager V2.5 - Enhanced AI Project Generator with Multi-Bot Support

This module handles all GitHub operations including:
- Repository creation and management
- File uploads and commits
- Branch management
- GitHub API interactions
"""

import os
import json
import base64
import requests
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GitHubHandler:
    """Handler for GitHub API operations"""
    
    def __init__(self, github_token: str = None):
        """
        Initialize GitHub handler with authentication token.
        
        Args:
            github_token: GitHub personal access token. If None, tries to get from environment.
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass as argument.")
        
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        # Rate limiting tracking
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0
        
    def _check_rate_limit(self) -> None:
        """Check and handle GitHub API rate limits"""
        if self.rate_limit_remaining < 10:
            reset_time = self.rate_limit_reset
            current_time = time.time()
            
            if reset_time > current_time:
                sleep_time = reset_time - current_time + 1
                logger.warning(f"Rate limit low. Sleeping for {sleep_time:.1f} seconds")
                time.sleep(sleep_time)
                
                # Refresh rate limit info
                self._get_rate_limit()
    
    def _get_rate_limit(self) -> Dict[str, Any]:
        """Get current rate limit information"""
        try:
            response = requests.get(f"{self.base_url}/rate_limit", headers=self.headers)
            response.raise_for_status()
            
            rate_data = response.json()['resources']['core']
            self.rate_limit_remaining = rate_data['remaining']
            self.rate_limit_reset = rate_data['reset']
            
            logger.debug(f"Rate limit: {self.rate_limit_remaining} remaining, resets at {self.rate_limit_reset}")
            return rate_data
        except Exception as e:
            logger.error(f"Failed to get rate limit: {e}")
            return {}
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make authenticated request to GitHub API with rate limit handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for requests.request
            
        Returns:
            Response object
        """
        self._check_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        
        # Ensure headers are included
        if 'headers' not in kwargs:
            kwargs['headers'] = self.headers
        else:
            kwargs['headers'].update(self.headers)
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            
            # Update rate limit info from response headers
            if 'X-RateLimit-Remaining' in response.headers:
                self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
            if 'X-RateLimit-Reset' in response.headers:
                self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])
            
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def create_repository(self, name: str, description: str = "", private: bool = True, 
                         auto_init: bool = True, gitignore_template: str = "Python") -> Dict[str, Any]:
        """
        Create a new GitHub repository.
        
        Args:
            name: Repository name
            description: Repository description
            private: Whether repository is private
            auto_init: Initialize with README
            gitignore_template: Gitignore template to use
            
        Returns:
            Repository information
        """
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
            "gitignore_template": gitignore_template
        }
        
        try:
            response = self._make_request("POST", "/user/repos", json=data)
            repo_info = response.json()
            logger.info(f"Created repository: {repo_info['html_url']}")
            return repo_info
        except Exception as e:
            logger.error(f"Failed to create repository: {e}")
            raise
    
    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Get repository information.
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            
        Returns:
            Repository information
        """
        try:
            response = self._make_request("GET", f"/repos/{owner}/{repo}")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get repository: {e}")
            raise
    
    def delete_repository(self, owner: str, repo: str) -> bool:
        """
        Delete a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            True if successful
        """
        try:
            self._make_request("DELETE", f"/repos/{owner}/{repo}")
            logger.info(f"Deleted repository: {owner}/{repo}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete repository: {e}")
            return False
    
    def create_file(self, owner: str, repo: str, path: str, content: str, 
                   message: str = "Add file", branch: str = "main") -> Dict[str, Any]:
        """
        Create or update a file in repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in repository
            content: File content
            message: Commit message
            branch: Target branch
            
        Returns:
            Commit information
        """
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode()).decode()
        
        data = {
            "message": message,
            "content": encoded_content,
            "branch": branch
        }
        
        try:
            response = self._make_request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create file {path}: {e}")
            raise
    
    def create_directory(self, owner: str, repo: str, directory_path: str, 
                        files: Dict[str, str], commit_message: str = "Add directory",
                        branch: str = "main") -> List[Dict[str, Any]]:
        """
        Create multiple files in a directory.
        
        Args:
            owner: Repository owner
            repo: Repository name
            directory_path: Directory path in repository
            files: Dictionary of {filename: content}
            commit_message: Commit message
            branch: Target branch
            
        Returns:
            List of commit information for each file
        """
        commits = []
        
        for filename, content in files.items():
            file_path = f"{directory_path}/{filename}" if directory_path else filename
            
            try:
                commit_info = self.create_file(
                    owner=owner,
                    repo=repo,
                    path=file_path,
                    content=content,
                    message=f"{commit_message}: {filename}",
                    branch=branch
                )
                commits.append(commit_info)
                logger.info(f"Created file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to create file {file_path}: {e}")
                # Continue with other files
                continue
        
        return commits
    
    def get_file_content(self, owner: str, repo: str, path: str, 
                        branch: str = "main") -> Optional[str]:
        """
        Get file content from repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in repository
            branch: Target branch
            
        Returns:
            File content as string, or None if not found
        """
        try:
            response = self._make_request("GET", f"/repos/{owner}/{repo}/contents/{path}?ref={branch}")
            file_data = response.json()
            
            if 'content' in file_data:
                # Decode base64 content
                content = base64.b64decode(file_data['content']).decode('utf-8')
                return content
            else:
                logger.error(f"File {path} not found or not a file")
                return None
        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return None
    
    def list_files(self, owner: str, repo: str, path: str = "", 
                  branch: str = "main") -> List[Dict[str, Any]]:
        """
        List files in a directory.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Directory path (empty for root)
            branch: Target branch
            
        Returns:
            List of file/directory information
        """
        try:
            endpoint = f"/repos/{owner}/{repo}/contents/{path}" if path else f"/repos/{owner}/{repo}/contents"
            response = self._make_request("GET", f"{endpoint}?ref={branch}")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def create_branch(self, owner: str, repo: str, branch_name: str, 
                     from_branch: str = "main") -> bool:
        """
        Create a new branch from existing branch.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch_name: New branch name
            from_branch: Source branch
            
        Returns:
            True if successful
        """
        try:
            # Get SHA of the source branch
            ref_response = self._make_request("GET", f"/repos/{owner}/{repo}/git/refs/heads/{from_branch}")
            sha = ref_response.json()['object']['sha']
            
            # Create new branch
            data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": sha
            }
            
            self._make_request("POST", f"/repos/{owner}/{repo}/git/refs", json=data)
            logger.info(f"Created branch: {branch_name} from {from_branch}")
            return True
        except Exception as e:
            logger.error(f"Failed to create branch: {e}")
            return False
    
    def create_pull_request(self, owner: str, repo: str, title: str, 
                           head: str, base: str = "main", 
                           body: str = "") -> Dict[str, Any]:
        """
        Create a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            head: Source branch
            base: Target branch
            body: PR description
            
        Returns:
            Pull request information
        """
        data = {
            "title": title,
            "head": head,
            "base": base,
            "body": body
        }
        
        try:
            response = self._make_request("POST", f"/repos/{owner}/{repo}/pulls", json=data)
            pr_info = response.json()
            logger.info(f"Created pull request: {pr_info['html_url']}")
            return pr_info
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            raise
    
    def get_user_info(self) -> Dict[str, Any]:
        """
        Get authenticated user information.
        
        Returns:
            User information
        """
        try:
            response = self._make_request("GET", "/user")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise
    
    def list_repositories(self, visibility: str = "all", affiliation: str = "owner") -> List[Dict[str, Any]]:
        """
        List repositories for authenticated user.
        
        Args:
            visibility: 'all', 'public', or 'private'
            affiliation: Comma-separated list of 'owner', 'collaborator', 'organization_member'
            
        Returns:
            List of repositories
        """
        try:
            params = {
                "visibility": visibility,
                "affiliation": affiliation,
                "per_page": 100
            }
            
            response = self._make_request("GET", "/user/repos", params=params)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
            return []
    
    def create_issue(self, owner: str, repo: str, title: str, 
                    body: str = "", labels: List[str] = None) -> Dict[str, Any]:
        """
        Create an issue in repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: Issue title
            body: Issue description
            labels: List of labels
            
        Returns:
            Issue information
        """
        data = {
            "title": title,
            "body": body
        }
        
        if labels:
            data["labels"] = labels
        
        try:
            response = self._make_request("POST", f"/repos/{owner}/{repo}/issues", json=data)
            issue_info = response.json()
            logger.info(f"Created issue: {issue_info['html_url']}")
            return issue_info
        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            raise
    
    def upload_project_structure(self, owner: str, repo: str, project_structure: Dict[str, Any],
                               base_branch: str = "main") -> Dict[str, Any]:
        """
        Upload complete project structure to repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            project_structure: Nested dictionary representing project structure
            base_branch: Target branch
            
        Returns:
            Summary of upload operation
        """
        summary = {
            "total_files": 0,
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        def process_directory(current_path: str, structure: Dict[str, Any], parent_path: str = ""):
            """Recursively process directory structure"""
            for item_name, item_content in structure.items():
                item_path = f"{parent_path}/{item_name}" if parent_path else item_name
                full_path = f"{current_path}/{item_name}" if current_path else item_name
                
                if isinstance(item_content, dict):
                    # It's a directory
                    process_directory(full_path, item_content, item_path)
                else:
                    # It's a file
                    summary["total_files"] += 1
                    try:
                        self.create_file(
                            owner=owner,
                            repo=repo,
                            path=full_path,
                            content=item_content,
                            message=f"Add {item_path}",
                            branch=base_branch
                        )
                        summary["successful"] += 1
                        logger.info(f"Uploaded file: {full_path}")
                    except Exception as e:
                        summary["failed"] += 1
                        summary["errors"].append({
                            "file": full_path,
                            "error": str(e)
                        })
                        logger.error(f"Failed to upload {full_path}: {e}")
        
        try:
            process_directory("", project_structure)
            logger.info(f"Upload complete: {summary['successful']}/{summary['total_files']} files uploaded")
            return summary
        except Exception as e:
            logger.error(f"Failed to upload project structure: {e}")
            summary["errors"].append({"error": str(e)})
            return summary
    
    def check_repository_exists(self, owner: str, repo: str) -> bool:
        """
        Check if repository exists.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            True if repository exists
        """
        try:
            self._make_request("GET", f"/repos/{owner}/{repo}")
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise
    
    def get_latest_commit(self, owner: str, repo: str, branch: str = "main") -> Dict[str, Any]:
        """
        Get latest commit information for a branch.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            
        Returns:
            Commit information
        """
        try:
            response = self._make_request("GET", f"/repos/{owner}/{repo}/commits/{branch}")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get latest commit: {e}")
            raise


# Utility functions for common operations
def create_bot_repository(github_handler: GitHubHandler, bot_name: str, 
                         bot_description: str = "", bot_files: Dict[str, str] = None,
                         private: bool = True) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Create a repository for a bot with initial files.
    
    Args:
        github_handler: GitHubHandler instance
        bot_name: Name of the bot (and repository)
        bot_description: Description for the repository
        bot_files: Dictionary of {filename: content} for initial files
        private: Whether repository is private
        
    Returns:
        Tuple of (repository_info, commit_infos)
    """
    if bot_files is None:
        bot_files = {
            "README.md": f"# {bot_name}\n\n{bot_description}",
            "requirements.txt": "# Bot dependencies\n",
            "bot.py": "# Main bot file\n\nprint('Hello from bot!')"
        }
    
    # Create repository
    repo_info = github_handler.create_repository(
        name=bot_name,
        description=bot_description,
        private=private,
        auto_init=False  # We'll add our own files
    )
    
    # Add initial files
    commits = []
    for filename, content in bot_files.items():
        try:
            commit_info = github_handler.create_file(
                owner=repo_info['owner']['login'],
                repo=repo_info['name'],
                path=filename,
                content=content,
                message=f"Initial commit: Add {filename}"
            )
            commits.append(commit_info)
        except Exception as e:
            logger.error(f"Failed to add file {filename}: {e}")
    
    return repo_info, commits


def clone_repository_structure(github_handler: GitHubHandler, source_owner: str, 
                              source_repo: str, target_owner: str, 
                              target_repo: str, branch: str = "main") -> Dict[str, Any]:
    """
    Clone repository structure (without history) to a new repository.
    
    Args:
        github_handler: GitHubHandler instance
        source_owner: Source repository owner
        source_repo: Source repository name
        target_owner: Target repository owner
        target_repo: Target repository name
        branch: Branch to clone from
        
    Returns:
        Summary of clone operation
    """
    summary = {
        "source": f"{source_owner}/{source_repo}",
        "target": f"{target_owner}/{target_repo}",
        "total_files": 0,
        "cloned": 0,
        "failed": 0,
        "errors": []
    }
    
    def clone_directory(path: str = ""):
        """Recursively clone directory"""
        files = github_handler.list_files(source_owner, source_repo, path, branch)
        
        for file_info in files:
            if file_info['type'] == 'file':
                summary["total_files"] += 1
                try:
                    # Get file content
                    content = github_handler.get_file_content(
                        source_owner, source_repo, file_info['path'], branch
                    )
                    
                    if content:
                        # Create file in target repository
                        github_handler.create_file(
                            owner=target_owner,
                            repo=target_repo,
                            path=file_info['path'],
                            content=content,
                            message=f"Clone from {source_owner}/{source_repo}: {file_info['path']}"
                        )
                        summary["cloned"] += 1
                        logger.info(f"Cloned file: {file_info['path']}")
                    else:
                        summary["failed"] += 1
                        summary["errors"].append({
                            "file": file_info['path'],
                            "error": "Failed to get file content"
                        })
                except Exception as e:
                    summary["failed"] += 1
                    summary["errors"].append({
                        "file": file_info['path'],
                        "error": str(e)
                    })
                    logger.error(f"Failed to clone {file_info['path']}: {e}")
            
            elif file_info['type'] == 'dir':
                # Recursively clone subdirectory
                clone_directory(file_info['path'])
    
    try:
        # Start cloning from root
        clone_directory()
        logger.info(f"Clone complete: {summary['cloned']}/{summary['total_files']} files cloned")
        return summary
    except Exception as e:
        logger.error(f"Failed to clone repository: {e}")
        summary["errors"].append({"error": str(e)})
        return summary


# Example usage
if __name__ == "__main__":
    # Example: Initialize GitHub handler and create a repository
    try:
        # Get token from environment
        token = os.getenv("GITHUB_TOKEN")
        
        if not token:
            print("Please set GITHUB_TOKEN environment variable")
        else:
            gh = GitHubHandler(token)
            
            # Test: Get user info
            user_info = gh.get_user_info()
            print(f"Authenticated as: {user_info['login']}")
            
            # Test: Create a test repository
            test_repo = gh.create_repository(
                name="test-bot-repo",
                description="Test repository for BotManager",
                private=True
            )
            print(f"Created repository: {test_repo['html_url']}")
            
            # Test: Add a file
            commit = gh.create_file(
                owner=user_info['login'],
                repo="test-bot-repo",
                path="test.py",
                content="# Test file\nprint('Hello from test bot!')\n",
                message="Add test file"
            )
            print(f"Created file: {commit['content']['name']}")
            
    except Exception as e:
        print(f"Error: {e}")