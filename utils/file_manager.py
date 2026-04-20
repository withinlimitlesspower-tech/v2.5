"""
File Manager Utility for BotManager V2.5
Handles all file operations including reading, writing, and managing project files.
"""

import os
import json
import yaml
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FileManager:
    """Enhanced file management utility for BotManager V2.5"""
    
    def __init__(self, base_path: str = "."):
        """
        Initialize FileManager with a base directory.
        
        Args:
            base_path: Base directory for file operations (default: current directory)
        """
        self.base_path = Path(base_path).resolve()
        self.ensure_directory_exists(self.base_path)
        logger.info(f"FileManager initialized with base path: {self.base_path}")
    
    def ensure_directory_exists(self, directory_path: Union[str, Path]) -> Path:
        """
        Ensure a directory exists, create it if it doesn't.
        
        Args:
            directory_path: Path to the directory
            
        Returns:
            Path object of the created/existing directory
        """
        path = Path(directory_path) if isinstance(directory_path, str) else directory_path
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def read_file(self, file_path: str, encoding: str = "utf-8") -> str:
        """
        Read content from a file.
        
        Args:
            file_path: Path to the file (relative to base_path)
            encoding: File encoding (default: utf-8)
            
        Returns:
            File content as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If there's an error reading the file
        """
        full_path = self.base_path / file_path
        
        if not full_path.exists():
            logger.error(f"File not found: {full_path}")
            raise FileNotFoundError(f"File not found: {full_path}")
        
        try:
            with open(full_path, 'r', encoding=encoding) as file:
                content = file.read()
            logger.debug(f"Successfully read file: {full_path}")
            return content
        except Exception as e:
            logger.error(f"Error reading file {full_path}: {str(e)}")
            raise IOError(f"Error reading file: {str(e)}")
    
    def write_file(self, file_path: str, content: str, encoding: str = "utf-8", 
                   overwrite: bool = True) -> bool:
        """
        Write content to a file.
        
        Args:
            file_path: Path to the file (relative to base_path)
            content: Content to write
            encoding: File encoding (default: utf-8)
            overwrite: Whether to overwrite existing file (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        full_path = self.base_path / file_path
        
        # Check if file exists and we shouldn't overwrite
        if full_path.exists() and not overwrite:
            logger.warning(f"File already exists and overwrite=False: {full_path}")
            return False
        
        # Ensure directory exists
        self.ensure_directory_exists(full_path.parent)
        
        try:
            with open(full_path, 'w', encoding=encoding) as file:
                file.write(content)
            logger.info(f"Successfully wrote file: {full_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing file {full_path}: {str(e)}")
            return False
    
    def read_json(self, file_path: str) -> Dict[str, Any]:
        """
        Read and parse JSON file.
        
        Args:
            file_path: Path to the JSON file (relative to base_path)
            
        Returns:
            Parsed JSON data as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        content = self.read_file(file_path)
        try:
            data = json.loads(content)
            logger.debug(f"Successfully parsed JSON from: {file_path}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file {file_path}: {str(e)}")
            raise
    
    def write_json(self, file_path: str, data: Dict[str, Any], 
                   indent: int = 2, sort_keys: bool = False) -> bool:
        """
        Write data to a JSON file.
        
        Args:
            file_path: Path to the JSON file (relative to base_path)
            data: Data to write as JSON
            indent: JSON indentation (default: 2)
            sort_keys: Whether to sort dictionary keys (default: False)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            json_content = json.dumps(data, indent=indent, sort_keys=sort_keys)
            return self.write_file(file_path, json_content)
        except Exception as e:
            logger.error(f"Error writing JSON to {file_path}: {str(e)}")
            return False
    
    def read_yaml(self, file_path: str) -> Dict[str, Any]:
        """
        Read and parse YAML file.
        
        Args:
            file_path: Path to the YAML file (relative to base_path)
            
        Returns:
            Parsed YAML data as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        content = self.read_file(file_path)
        try:
            data = yaml.safe_load(content)
            logger.debug(f"Successfully parsed YAML from: {file_path}")
            return data if data is not None else {}
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in file {file_path}: {str(e)}")
            raise
    
    def write_yaml(self, file_path: str, data: Dict[str, Any]) -> bool:
        """
        Write data to a YAML file.
        
        Args:
            file_path: Path to the YAML file (relative to base_path)
            data: Data to write as YAML
            
        Returns:
            True if successful, False otherwise
        """
        try:
            yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False)
            return self.write_file(file_path, yaml_content)
        except Exception as e:
            logger.error(f"Error writing YAML to {file_path}: {str(e)}")
            return False
    
    def list_files(self, directory_path: str = ".", pattern: str = "*", 
                   recursive: bool = False) -> List[str]:
        """
        List files in a directory.
        
        Args:
            directory_path: Directory path (relative to base_path)
            pattern: Glob pattern for filtering files
            recursive: Whether to search recursively (default: False)
            
        Returns:
            List of file paths relative to base_path
        """
        full_path = self.base_path / directory_path
        
        if not full_path.exists():
            logger.warning(f"Directory not found: {full_path}")
            return []
        
        try:
            if recursive:
                files = list(full_path.rglob(pattern))
            else:
                files = list(full_path.glob(pattern))
            
            # Convert to relative paths
            relative_files = [str(f.relative_to(self.base_path)) for f in files if f.is_file()]
            logger.debug(f"Found {len(relative_files)} files in {directory_path}")
            return relative_files
        except Exception as e:
            logger.error(f"Error listing files in {directory_path}: {str(e)}")
            return []
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists.
        
        Args:
            file_path: Path to the file (relative to base_path)
            
        Returns:
            True if file exists, False otherwise
        """
        full_path = self.base_path / file_path
        exists = full_path.exists() and full_path.is_file()
        logger.debug(f"File exists check for {file_path}: {exists}")
        return exists
    
    def directory_exists(self, directory_path: str) -> bool:
        """
        Check if a directory exists.
        
        Args:
            directory_path: Path to the directory (relative to base_path)
            
        Returns:
            True if directory exists, False otherwise
        """
        full_path = self.base_path / directory_path
        exists = full_path.exists() and full_path.is_dir()
        logger.debug(f"Directory exists check for {directory_path}: {exists}")
        return exists
    
    def create_directory(self, directory_path: str) -> bool:
        """
        Create a directory (and parent directories if needed).
        
        Args:
            directory_path: Path to the directory (relative to base_path)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            full_path = self.base_path / directory_path
            full_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {full_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating directory {directory_path}: {str(e)}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file.
        
        Args:
            file_path: Path to the file (relative to base_path)
            
        Returns:
            True if successful, False otherwise
        """
        full_path = self.base_path / file_path
        
        if not full_path.exists():
            logger.warning(f"File not found for deletion: {full_path}")
            return False
        
        try:
            full_path.unlink()
            logger.info(f"Deleted file: {full_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {str(e)}")
            return False
    
    def delete_directory(self, directory_path: str, force: bool = False) -> bool:
        """
        Delete a directory.
        
        Args:
            directory_path: Path to the directory (relative to base_path)
            force: Whether to force deletion (remove non-empty directories)
            
        Returns:
            True if successful, False otherwise
        """
        full_path = self.base_path / directory_path
        
        if not full_path.exists():
            logger.warning(f"Directory not found for deletion: {full_path}")
            return False
        
        try:
            if force:
                shutil.rmtree(full_path)
                logger.info(f"Force deleted directory: {full_path}")
            else:
                full_path.rmdir()
                logger.info(f"Deleted directory: {full_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting directory {directory_path}: {str(e)}")
            return False
    
    def copy_file(self, source_path: str, destination_path: str, 
                  overwrite: bool = True) -> bool:
        """
        Copy a file from source to destination.
        
        Args:
            source_path: Source file path (relative to base_path)
            destination_path: Destination file path (relative to base_path)
            overwrite: Whether to overwrite existing file (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        source_full = self.base_path / source_path
        dest_full = self.base_path / destination_path
        
        if not source_full.exists():
            logger.error(f"Source file not found: {source_full}")
            return False
        
        if dest_full.exists() and not overwrite:
            logger.warning(f"Destination file exists and overwrite=False: {dest_full}")
            return False
        
        # Ensure destination directory exists
        self.ensure_directory_exists(dest_full.parent)
        
        try:
            shutil.copy2(source_full, dest_full)
            logger.info(f"Copied file from {source_path} to {destination_path}")
            return True
        except Exception as e:
            logger.error(f"Error copying file {source_path} to {destination_path}: {str(e)}")
            return False
    
    def copy_directory(self, source_path: str, destination_path: str, 
                       overwrite: bool = True) -> bool:
        """
        Copy a directory recursively from source to destination.
        
        Args:
            source_path: Source directory path (relative to base_path)
            destination_path: Destination directory path (relative to base_path)
            overwrite: Whether to overwrite existing files (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        source_full = self.base_path / source_path
        dest_full = self.base_path / destination_path
        
        if not source_full.exists():
            logger.error(f"Source directory not found: {source_full}")
            return False
        
        try:
            if dest_full.exists() and overwrite:
                shutil.rmtree(dest_full)
            
            shutil.copytree(source_full, dest_full, dirs_exist_ok=overwrite)
            logger.info(f"Copied directory from {source_path} to {destination_path}")
            return True
        except Exception as e:
            logger.error(f"Error copying directory {source_path} to {destination_path}: {str(e)}")
            return False
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get information about a file.
        
        Args:
            file_path: Path to the file (relative to base_path)
            
        Returns:
            Dictionary with file information
        """
        full_path = self.base_path / file_path
        
        if not full_path.exists():
            return {"error": "File not found"}
        
        try:
            stat = full_path.stat()
            return {
                "path": str(file_path),
                "absolute_path": str(full_path),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_file": full_path.is_file(),
                "is_directory": full_path.is_dir(),
                "extension": full_path.suffix,
                "name": full_path.name,
                "parent": str(full_path.parent.relative_to(self.base_path))
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {str(e)}")
            return {"error": str(e)}
    
    def find_files(self, pattern: str, start_directory: str = ".", 
                   recursive: bool = True) -> List[str]:
        """
        Find files matching a pattern.
        
        Args:
            pattern: Glob pattern to match
            start_directory: Directory to start search (relative to base_path)
            recursive: Whether to search recursively (default: True)
            
        Returns:
            List of matching file paths relative to base_path
        """
        start_full = self.base_path / start_directory
        
        if not start_full.exists():
            logger.warning(f"Start directory not found: {start_full}")
            return []
        
        try:
            if recursive:
                matches = list(start_full.rglob(pattern))
            else:
                matches = list(start_full.glob(pattern))
            
            # Filter files only and convert to relative paths
            files = [str(m.relative_to(self.base_path)) for m in matches if m.is_file()]
            logger.debug(f"Found {len(files)} files matching pattern '{pattern}'")
            return files
        except Exception as e:
            logger.error(f"Error finding files with pattern '{pattern}': {str(e)}")
            return []
    
    def backup_file(self, file_path: str, backup_suffix: str = ".bak") -> bool:
        """
        Create a backup of a file.
        
        Args:
            file_path: Path to the file (relative to base_path)
            backup_suffix: Suffix for backup file (default: ".bak")
            
        Returns:
            True if successful, False otherwise
        """
        if not self.file_exists(file_path):
            logger.error(f"Cannot backup non-existent file: {file_path}")
            return False
        
        backup_path = file_path + backup_suffix
        return self.copy_file(file_path, backup_path, overwrite=True)
    
    def restore_backup(self, file_path: str, backup_suffix: str = ".bak", 
                       remove_backup: bool = True) -> bool:
        """
        Restore a file from backup.
        
        Args:
            file_path: Path to the file (relative to base_path)
            backup_suffix: Suffix for backup file (default: ".bak")
            remove_backup: Whether to remove backup after restore (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        backup_path = file_path + backup_suffix
        
        if not self.file_exists(backup_path):
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        # Copy backup to original location
        success = self.copy_file(backup_path, file_path, overwrite=True)
        
        # Remove backup if requested and copy was successful
        if success and remove_backup:
            self.delete_file(backup_path)
        
        return success
    
    def get_file_size(self, file_path: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            file_path: Path to the file (relative to base_path)
            
        Returns:
            File size in bytes, or -1 if error
        """
        full_path = self.base_path / file_path
        
        if not full_path.exists():
            return -1
        
        try:
            return full_path.stat().st_size
        except Exception as e:
            logger.error(f"Error getting file size for {file_path}: {str(e)}")
            return -1
    
    def append_to_file(self, file_path: str, content: str, 
                       encoding: str = "utf-8") -> bool:
        """
        Append content to a file.
        
        Args:
            file_path: Path to the file (relative to base_path)
            content: Content to append
            encoding: File encoding (default: utf-8)
            
        Returns:
            True if successful, False otherwise
        """
        full_path = self.base_path / file_path
        
        # Ensure directory exists
        self.ensure_directory_exists(full_path.parent)
        
        try:
            with open(full_path, 'a', encoding=encoding) as file:
                file.write(content)
            logger.debug(f"Appended content to file: {full_path}")
            return True
        except Exception as e:
            logger.error(f"Error appending to file {file_path}: {str(e)}")
            return False
    
    def read_lines(self, file_path: str, encoding: str = "utf-8") -> List[str]:
        """
        Read all lines from a file.
        
        Args:
            file_path: Path to the file (relative to base_path)
            encoding: File encoding (default: utf-8)
            
        Returns:
            List of lines from the file
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If there's an error reading the file
        """
        content = self.read_file(file_path, encoding)
        return content.splitlines()
    
    def write_lines(self, file_path: str, lines: List[str], 
                    encoding: str = "utf-8", overwrite: bool = True) -> bool:
        """
        Write lines to a file.
        
        Args:
            file_path: Path to the file (relative to base_path)
            lines: List of lines to write
            encoding: File encoding (default: utf-8)
            overwrite: Whether to overwrite existing file (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        content = '\n'.join(lines)
        return self.write_file(file_path, content, encoding, overwrite)
    
    def merge_files(self, source_files: List[str], destination_file: str, 
                    separator: str = "\n", encoding: str = "utf-8") -> bool:
        """
        Merge multiple files into one.
        
        Args:
            source_files: List of source file paths (relative to base_path)
            destination_file: Destination file path (relative to base_path)
            separator: Separator between file contents (default: newline)
            encoding: File encoding (default: utf-8)
            
        Returns:
            True if successful, False otherwise
        """
        merged_content = []
        
        for source_file in source_files:
            if self.file_exists(source_file):
                try:
                    content = self.read_file(source_file, encoding)
                    merged_content.append(content)
                except Exception as e:
                    logger.error(f"Error reading file {source_file} for merge: {str(e)}")
                    return False
            else:
                logger.warning(f"Source file not found for merge: {source_file}")
        
        final_content = separator.join(merged_content)
        return self.write_file(destination_file, final_content, encoding)
    
    def change_base_path(self, new_base_path: str) -> None:
        """
        Change the base path for file operations.
        
        Args:
            new_base_path: New base directory path
        """
        old_base = self.base_path
        self.base_path = Path(new_base_path).resolve()
        self.ensure_directory_exists(self.base_path)
        logger.info(f"Changed base path from {old_base} to {self.base_path}")


# Singleton instance for convenience
_file_manager_instance = None

def get_file_manager(base_path: str = ".") -> FileManager:
    """
    Get or create a FileManager instance (singleton pattern).
    
    Args:
        base_path: Base directory for file operations
        
    Returns:
        FileManager instance
    """
    global _file_manager_instance
    
    if _file_manager_instance is None:
        _file_manager_instance = FileManager(base_path)
    elif base_path != ".":
        _file_manager_instance.change_base_path(base_path)
    
    return _file_manager_instance


# Example usage and testing
if __name__ == "__main__":
    # Create a FileManager instance
    fm = FileManager("test_directory")
    
    # Test basic operations
    test_data = {"name": "Test", "value": 123, "list": [1, 2, 3]}
    
    # Write and read JSON
    fm.write_json("test.json", test_data)
    read_data = fm.read_json("test.json")
    print(f"JSON test: {read_data == test_data}")
    
    # Write and read YAML
    fm.write_yaml("test.yaml", test_data)
    yaml_data = fm.read_yaml("test.yaml")
    print(f"YAML test: {yaml_data == test_data}")
    
    # List files
    files = fm.list_files()
    print(f"Files in directory: {files}")
    
    # Get file info
    if fm.file_exists("test.json"):
        info = fm.get_file_info("test.json")
        print(f"File info: {info}")
    
    # Cleanup
    fm.delete_file("test.json")
    fm.delete_file("test.yaml")
    fm.delete_directory("test_directory", force=True)
    
    print("FileManager tests completed!")