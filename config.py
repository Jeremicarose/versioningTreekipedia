import os

# Base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Configuration for the Flask application
class Config:
    # Secret key for sessions and CSRF protection - change in production!
    SECRET_KEY = os.environ.get('SECRET_KEY', 'treekipedia-dev-key')
    
    # Debug mode - disable in production
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 't']
    
    # Base directory
    BASE_DIR = BASE_DIR
    
    # Data directories
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    CURRENT_DATA_DIR = os.path.join(DATA_DIR, 'current')
    VERSIONS_DIR = os.path.join(DATA_DIR, 'versions')
    
    # Reports and temporary storage
    REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
    UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
    
    # Sample size for data previews (number of rows)
    SAMPLE_SIZE = 100
    
    # Maximum file size for uploads (in bytes)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # Column name for species identifier
    # This is used to track changes to specific species
    SPECIES_ID_COLUMN = 'species'  # Change to match your actual ID column
    
    # Database settings (for future integration)
    POSTGRES_URI = os.environ.get('POSTGRES_URI', 'postgresql://postgres:password@localhost:5432/treekipedia')
    BLAZEGRAPH_ENDPOINT = os.environ.get('BLAZEGRAPH_ENDPOINT', 'http://localhost:9999/blazegraph/sparql')

# Production configuration
class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Must be set in production
    
    # Set to secure storage locations in production
    DATA_DIR = os.environ.get('DATA_DIR', Config.DATA_DIR)
    CURRENT_DATA_DIR = os.environ.get('CURRENT_DATA_DIR', Config.CURRENT_DATA_DIR)
    VERSIONS_DIR = os.environ.get('VERSIONS_DIR', Config.VERSIONS_DIR)
    REPORTS_DIR = os.environ.get('REPORTS_DIR', Config.REPORTS_DIR)
    UPLOADS_DIR = os.environ.get('UPLOADS_DIR', Config.UPLOADS_DIR)

# Development configuration
class DevelopmentConfig(Config):
    DEBUG = True
    
# Testing configuration
class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    
    # Use temporary directories for testing
    import tempfile
    DATA_DIR = tempfile.mkdtemp(prefix='treekipedia_test_data_')
    CURRENT_DATA_DIR = os.path.join(DATA_DIR, 'current')
    VERSIONS_DIR = os.path.join(DATA_DIR, 'versions')
    REPORTS_DIR = tempfile.mkdtemp(prefix='treekipedia_test_reports_')
    UPLOADS_DIR = tempfile.mkdtemp(prefix='treekipedia_test_uploads_')

# Configuration lookup
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Get configuration class based on environment
def get_config():
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])