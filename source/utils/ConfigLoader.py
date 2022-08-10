import json
from .Config import Config

class ConfigLoader:
    """Functionality to load the application configuration
    """
    def load(filename:str = 'config.json') -> Config:
        """Load the application configuration

        Args:
            filename (str, optional): The configuration file name. Defaults to 'config.json'.

        Returns:
            Config: The application configuration or None on error during load.
        """
        with open(file=filename, mode='r') as f:
            config_object = json.load(f)
        
        config = Config()
        if config.load(config_object) == True:
            return config

        return None
