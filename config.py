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
    SHEETS_DIR = os.path.join(BASE_DIR, 'sheets')
    
    # Sample size for data previews (number of rows)
    SAMPLE_SIZE = 100
    
    # Maximum file size for uploads (in bytes)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # Column name for species identifier
    # This is used to track changes to specific species
    SPECIES_ID_COLUMN = 'species'  # Change to match your actual ID column
    
    # Google Sheets API settings
    GOOGLE_CREDENTIALS_FILE = os.environ.get('GOOGLE_CREDENTIALS_FILE', 
                                          os.path.join(BASE_DIR, 'credentials.json'))
    GOOGLE_TOKEN_FILE = os.environ.get('GOOGLE_TOKEN_FILE', 
                                    os.path.join(BASE_DIR, 'token.json'))
    # Allowed domains for Google Sheets (empty list means any domain is allowed)
    GOOGLE_ALLOWED_DOMAINS = os.environ.get('GOOGLE_ALLOWED_DOMAINS', '').split(',')

    # GitHub repository settings
    GITHUB_REPO_OWNER = os.environ.get('GITHUB_REPO_OWNER', 'SilviProtocol')
    GITHUB_REPO_NAME = os.environ.get('GITHUB_REPO_NAME', 'silvi-open')
    GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'master')
    GITHUB_DEFAULT_PATH = os.environ.get('GITHUB_DEFAULT_PATH', 'Treekipedia/Data')
    
    # Session config (needed for Google Sheets session variables)
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds
    
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
    SHEETS_DIR = os.environ.get('SHEETS_DIR', Config.SHEETS_DIR)
    
    # More secure session configuration for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 43200  # 12 hours in seconds

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
    SHEETS_DIR = tempfile.mkdtemp(prefix='treekipedia_test_sheets_')

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