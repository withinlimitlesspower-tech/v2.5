"""
Configuration Manager for BotManager V2.5 - Enhanced AI Project Generator with Multi-Bot Support

This module handles all configuration loading, validation, and management for the BotManager system.
It supports loading from environment variables, Replit Secrets, and configuration files.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import yaml
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BotType(Enum):
    """Enumeration of supported bot types"""
    DISCORD = "discord"
    TELEGRAM = "telegram"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    CUSTOM = "custom"


class AIService(Enum):
    """Enumeration of supported AI services"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    LOCAL = "local"


@dataclass
class AIConfig:
    """Configuration for AI service integration"""
    service: AIService = AIService.OPENAI
    api_key: str = ""
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000
    api_base: Optional[str] = None
    api_version: Optional[str] = None
    organization: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate AI configuration"""
        if not self.api_key and self.service != AIService.LOCAL:
            logger.warning(f"API key not set for {self.service.value}")
            return False
        return True


@dataclass
class BotConfig:
    """Configuration for individual bot instances"""
    name: str = ""
    bot_type: BotType = BotType.DISCORD
    enabled: bool = True
    token: str = ""
    prefix: str = "!"
    admin_ids: List[str] = field(default_factory=list)
    channel_ids: List[str] = field(default_factory=list)
    ai_enabled: bool = True
    ai_config: AIConfig = field(default_factory=AIConfig)
    
    def validate(self) -> bool:
        """Validate bot configuration"""
        if not self.name:
            logger.error("Bot name is required")
            return False
        if not self.token and self.bot_type != BotType.CUSTOM:
            logger.error(f"Token required for {self.bot_type.value} bot")
            return False
        return True


@dataclass
class DatabaseConfig:
    """Configuration for database connections"""
    type: str = "sqlite"  # sqlite, postgresql, mongodb
    host: str = "localhost"
    port: int = 5432
    name: str = "botmanager.db"
    username: str = ""
    password: str = ""
    connection_string: Optional[str] = None
    
    def get_connection_string(self) -> str:
        """Generate connection string based on database type"""
        if self.connection_string:
            return self.connection_string
            
        if self.type == "sqlite":
            return f"sqlite:///{self.name}"
        elif self.type == "postgresql":
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"
        elif self.type == "mongodb":
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"
        else:
            return ""


@dataclass
class LoggingConfig:
    """Configuration for logging system"""
    level: str = "INFO"
    file: str = "botmanager.log"
    max_size: int = 10485760  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class SecurityConfig:
    """Security-related configuration"""
    encryption_key: str = ""
    jwt_secret: str = ""
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds


@dataclass
class MonitoringConfig:
    """Configuration for monitoring and metrics"""
    enabled: bool = True
    port: int = 9090
    metrics_endpoint: str = "/metrics"
    health_check_endpoint: str = "/health"
    prometheus_enabled: bool = True


@dataclass
class ProjectGeneratorConfig:
    """Configuration for project generation features"""
    template_path: str = "templates/"
    output_path: str = "generated_projects/"
    default_language: str = "python"
    supported_languages: List[str] = field(default_factory=lambda: ["python", "javascript", "typescript"])
    auto_dependencies: bool = True
    version_control: bool = True


class ConfigManager:
    """
    Main configuration manager for BotManager V2.5
    
    Handles loading, validation, and access to all configuration settings
    from multiple sources (environment variables, files, Replit Secrets)
    """
    
    def __init__(self, config_file: str = "config.yaml", env_prefix: str = "BOTMANAGER_"):
        """
        Initialize configuration manager
        
        Args:
            config_file: Path to configuration file (YAML or JSON)
            env_prefix: Prefix for environment variables
        """
        self.config_file = config_file
        self.env_prefix = env_prefix
        self.config: Dict[str, Any] = {}
        self.bots: Dict[str, BotConfig] = {}
        
        # Initialize default configuration
        self._init_defaults()
        
        # Load configuration from various sources
        self.load_configuration()
        
        # Validate configuration
        self.validate()
    
    def _init_defaults(self):
        """Initialize default configuration values"""
        self.config = {
            "app": {
                "name": "BotManager V2.5",
                "version": "2.5.0",
                "debug": False,
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 1,
            },
            "database": DatabaseConfig().__dict__,
            "logging": LoggingConfig().__dict__,
            "security": SecurityConfig().__dict__,
            "monitoring": MonitoringConfig().__dict__,
            "project_generator": ProjectGeneratorConfig().__dict__,
            "bots": [],
            "ai": AIConfig().__dict__,
        }
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        logger.info("Loading configuration from environment variables")
        
        # App configuration
        self.config["app"]["debug"] = os.getenv(f"{self.env_prefix}DEBUG", "false").lower() == "true"
        self.config["app"]["host"] = os.getenv(f"{self.env_prefix}HOST", self.config["app"]["host"])
        self.config["app"]["port"] = int(os.getenv(f"{self.env_prefix}PORT", self.config["app"]["port"]))
        
        # AI configuration
        ai_service = os.getenv(f"{self.env_prefix}AI_SERVICE", "openai").lower()
        self.config["ai"]["service"] = ai_service
        self.config["ai"]["api_key"] = os.getenv(f"{self.env_prefix}AI_API_KEY", "")
        self.config["ai"]["model"] = os.getenv(f"{self.env_prefix}AI_MODEL", self.config["ai"]["model"])
        
        # Database configuration
        self.config["database"]["type"] = os.getenv(f"{self.env_prefix}DB_TYPE", self.config["database"]["type"])
        self.config["database"]["host"] = os.getenv(f"{self.env_prefix}DB_HOST", self.config["database"]["host"])
        self.config["database"]["name"] = os.getenv(f"{self.env_prefix}DB_NAME", self.config["database"]["name"])
        
        # Security configuration
        self.config["security"]["encryption_key"] = os.getenv(
            f"{self.env_prefix}ENCRYPTION_KEY", 
            self.config["security"]["encryption_key"]
        )
        self.config["security"]["jwt_secret"] = os.getenv(
            f"{self.env_prefix}JWT_SECRET", 
            self.config["security"]["jwt_secret"]
        )
    
    def _load_from_file(self):
        """Load configuration from file (YAML or JSON)"""
        if not os.path.exists(self.config_file):
            logger.warning(f"Configuration file {self.config_file} not found")
            return
        
        try:
            with open(self.config_file, 'r') as f:
                if self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
                    file_config = yaml.safe_load(f)
                elif self.config_file.endswith('.json'):
                    file_config = json.load(f)
                else:
                    logger.error(f"Unsupported configuration file format: {self.config_file}")
                    return
            
            # Deep merge configuration
            self._deep_merge(self.config, file_config)
            logger.info(f"Loaded configuration from {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")
    
    def _load_from_replit_secrets(self):
        """
        Load configuration from Replit Secrets
        
        Note: In Replit, secrets are exposed as environment variables
        """
        logger.info("Loading configuration from Replit Secrets")
        
        # Check if we're running in Replit
        if os.getenv("REPL_ID"):
            logger.info("Running in Replit environment")
            
            # Load bot tokens from secrets
            bot_secrets = {}
            for key, value in os.environ.items():
                if key.startswith("BOT_TOKEN_"):
                    bot_name = key[10:].lower()  # Remove "BOT_TOKEN_" prefix
                    bot_secrets[bot_name] = value
            
            # Update bot configurations with tokens from secrets
            for bot_config in self.config.get("bots", []):
                bot_name = bot_config.get("name", "").lower()
                if bot_name in bot_secrets and not bot_config.get("token"):
                    bot_config["token"] = bot_secrets[bot_name]
                    logger.info(f"Loaded token for bot '{bot_name}' from Replit Secrets")
    
    def _deep_merge(self, target: Dict, source: Dict):
        """Deep merge source dictionary into target dictionary"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def load_configuration(self):
        """Load configuration from all available sources"""
        logger.info("Loading BotManager V2.5 configuration...")
        
        # Load from file first (as base configuration)
        self._load_from_file()
        
        # Load from environment variables (overrides file)
        self._load_from_env()
        
        # Load from Replit Secrets (overrides environment)
        self._load_from_replit_secrets()
        
        # Parse bot configurations
        self._parse_bot_configs()
        
        logger.info("Configuration loaded successfully")
    
    def _parse_bot_configs(self):
        """Parse and validate bot configurations"""
        self.bots = {}
        
        for bot_data in self.config.get("bots", []):
            try:
                # Create bot configuration
                bot_config = BotConfig(
                    name=bot_data.get("name", ""),
                    bot_type=BotType(bot_data.get("type", "discord")),
                    enabled=bot_data.get("enabled", True),
                    token=bot_data.get("token", ""),
                    prefix=bot_data.get("prefix", "!"),
                    admin_ids=bot_data.get("admin_ids", []),
                    channel_ids=bot_data.get("channel_ids", []),
                    ai_enabled=bot_data.get("ai_enabled", True),
                )
                
                # Add AI configuration if specified
                if "ai_config" in bot_data:
                    ai_data = bot_data["ai_config"]
                    bot_config.ai_config = AIConfig(
                        service=AIService(ai_data.get("service", "openai")),
                        api_key=ai_data.get("api_key", self.config["ai"]["api_key"]),
                        model=ai_data.get("model", self.config["ai"]["model"]),
                        temperature=ai_data.get("temperature", self.config["ai"]["temperature"]),
                        max_tokens=ai_data.get("max_tokens", self.config["ai"]["max_tokens"]),
                    )
                else:
                    # Use global AI config
                    bot_config.ai_config = AIConfig(**self.config["ai"])
                
                # Store bot configuration
                self.bots[bot_config.name] = bot_config
                logger.info(f"Loaded configuration for bot: {bot_config.name}")
                
            except Exception as e:
                logger.error(f"Error parsing bot configuration: {e}")
    
    def validate(self) -> bool:
        """Validate all configuration settings"""
        logger.info("Validating configuration...")
        
        # Validate AI configuration
        ai_config = AIConfig(**self.config["ai"])
        if not ai_config.validate():
            logger.warning("AI configuration validation failed")
        
        # Validate bot configurations
        valid_bots = []
        for bot_name, bot_config in self.bots.items():
            if bot_config.validate():
                valid_bots.append(bot_name)
            else:
                logger.error(f"Bot configuration validation failed for: {bot_name}")
        
        if not valid_bots:
            logger.error("No valid bot configurations found")
            return False
        
        logger.info(f"Configuration validated successfully. {len(valid_bots)} bots configured.")
        return True
    
    def get_bot_config(self, bot_name: str) -> Optional[BotConfig]:
        """Get configuration for a specific bot"""
        return self.bots.get(bot_name)
    
    def get_all_bots(self) -> Dict[str, BotConfig]:
        """Get all bot configurations"""
        return self.bots
    
    def get_enabled_bots(self) -> Dict[str, BotConfig]:
        """Get only enabled bot configurations"""
        return {name: config for name, config in self.bots.items() if config.enabled}
    
    def get_app_config(self) -> Dict[str, Any]:
        """Get application configuration"""
        return self.config.get("app", {})
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        return DatabaseConfig(**self.config.get("database", {}))
    
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration"""
        return LoggingConfig(**self.config.get("logging", {}))
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration"""
        return SecurityConfig(**self.config.get("security", {}))
    
    def get_monitoring_config(self) -> MonitoringConfig:
        """Get monitoring configuration"""
        return MonitoringConfig(**self.config.get("monitoring", {}))
    
    def get_project_generator_config(self) -> ProjectGeneratorConfig:
        """Get project generator configuration"""
        return ProjectGeneratorConfig(**self.config.get("project_generator", {}))
    
    def save_config(self, file_path: Optional[str] = None):
        """Save current configuration to file"""
        if not file_path:
            file_path = self.config_file
        
        try:
            # Convert dataclasses to dictionaries
            save_config = self.config.copy()
            save_config["bots"] = [asdict(bot) for bot in self.bots.values()]
            
            with open(file_path, 'w') as f:
                if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                    yaml.dump(save_config, f, default_flow_style=False)
                elif file_path.endswith('.json'):
                    json.dump(save_config, f, indent=2)
                else:
                    # Default to YAML
                    yaml.dump(save_config, f, default_flow_style=False)
            
            logger.info(f"Configuration saved to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def reload(self):
        """Reload configuration from all sources"""
        logger.info("Reloading configuration...")
        self._init_defaults()
        self.load_configuration()
        return self.validate()


# Global configuration instance
config_manager = ConfigManager()

# Convenience accessors
def get_config() -> ConfigManager:
    """Get the global configuration manager instance"""
    return config_manager

def get_bot_config(bot_name: str) -> Optional[BotConfig]:
    """Get configuration for a specific bot (convenience function)"""
    return config_manager.get_bot_config(bot_name)

def get_all_bots() -> Dict[str, BotConfig]:
    """Get all bot configurations (convenience function)"""
    return config_manager.get_all_bots()

def get_enabled_bots() -> Dict[str, BotConfig]:
    """Get enabled bot configurations (convenience function)"""
    return config_manager.get_enabled_bots()


# Example usage and testing
if __name__ == "__main__":
    # Test the configuration manager
    print("Testing BotManager V2.5 Configuration Manager")
    print("=" * 50)
    
    # Display loaded configuration
    print(f"App Name: {config_manager.get_app_config().get('name')}")
    print(f"Version: {config_manager.get_app_config().get('version')}")
    print(f"Debug Mode: {config_manager.get_app_config().get('debug')}")
    
    # Display bot configurations
    bots = config_manager.get_all_bots()
    print(f"\nLoaded {len(bots)} bot(s):")
    for bot_name, bot_config in bots.items():
        print(f"  - {bot_name} ({bot_config.bot_type.value}) - {'Enabled' if bot_config.enabled else 'Disabled'}")
    
    # Display database configuration
    db_config = config_manager.get_database_config()
    print(f"\nDatabase: {db_config.type}://{db_config.host}/{db_config.name}")
    
    print("\nConfiguration test completed successfully!")