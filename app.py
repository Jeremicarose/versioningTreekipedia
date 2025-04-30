import os
import json
import logging
import requests
import pandas as pd
import tempfile
import shutil
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from werkzeug.utils import secure_filename
from datetime import datetime

# Import configuration settings
from config import get_config

# Import CSV versioning system
from csv_version import CSVVersioningSystem

# Import Google Sheets integration
from google_sheets import GoogleSheetsManager, check_google_sheets_available

# Import the Github integration
from github_integration import init_github_integration


# Create Flask application
app = Flask(__name__)
app.config.from_object(get_config())
logger = logging.getLogger(__name__)

# Initialize directories
for directory in [app.config['CURRENT_DATA_DIR'], app.config['VERSIONS_DIR'], 
                 app.config['REPORTS_DIR'], app.config['UPLOADS_DIR'], app.config['SHEETS_DIR']]:
    os.makedirs(directory, exist_ok=True)

# Initialize the versioning system
versioning = CSVVersioningSystem(app.config['BASE_DIR'])

# Initialize Google Sheets manager
sheets_manager = GoogleSheetsManager(app.config['BASE_DIR'], app.config)
google_sheets_available = check_google_sheets_available()

# Add this after initializing other components
# Initialize GitHub integration
try:
    from github_integration import init_github_integration
    github_integration = init_github_integration(app.config)
    logger.info("GitHub integration initialized successfully")
except Exception as e:
    logger.error(f"Error initializing GitHub integration: {str(e)}")
    # Create a dummy GitHub integration that returns empty lists
    class DummyGitHubIntegration:
        def __init__(self):
            self.default_path = 'Treekipedia/Data'
        
        def list_files(self, path=None):
            return {"success": False, "error": "GitHub integration not available", "items": []}
        
        def get_file_content(self, path):
            return {"success": False, "error": "GitHub integration not available"}
        
        def download_file_to_temp(self, path):
            return {"success": False, "error": "GitHub integration not available"}
    
    github_integration = DummyGitHubIntegration()

# GitHub Repository Routes

@app.route('/github-files')
@app.route('/github-files/<path:path>')
def github_files(path=None):
    """Browse GitHub repository files"""
    # Use default path if none provided
    if path is None:
        path = getattr(github_integration, 'default_path', 'Treekipedia/Data')
    
    # Create a safe version of the listing
    try:
        # Get file listing from GitHub
        raw_listing = github_integration.list_files(path)
        
        # Create a new dictionary with safe values
        listing = {
            'success': raw_listing.get('success', False),
            'error': raw_listing.get('error', 'Unknown error'),
            'path': path
        }
        
        # Extract the file list manually
        file_list = []
        
        if listing['success'] and isinstance(raw_listing.get('items'), list):
            for item in raw_listing.get('items', []):
                if isinstance(item, dict):
                    file_info = {
                        'name': item.get('name', 'Unknown'),
                        'path': item.get('path', ''),
                        'type': item.get('type', 'file'),
                        'size': item.get('size', 0),
                        'download_url': item.get('download_url', ''),
                        'html_url': item.get('html_url', '')
                    }
                    file_list.append(file_info)
            
            # Sort: directories first, then files alphabetically
            file_list.sort(key=lambda x: (0 if x['type'] == 'dir' else 1, x['name'].lower()))
        
    except Exception as e:
        # If anything goes wrong, provide a safe fallback
        listing = {
            'success': False,
            'error': f"Error retrieving files: {str(e)}",
            'path': path
        }
        file_list = []
    
    # Calculate parent path for navigation
    parent_path = None
    if path and path != getattr(github_integration, 'default_path', 'Treekipedia/Data'):
        parts = path.split('/')
        parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else getattr(github_integration, 'default_path', 'Treekipedia/Data')
    
    # Log what we're sending to the template (for debugging)
    app.logger.info(f"GitHub files listing: success={listing['success']}, file_count={len(file_list)}")
    
    return render_template('github_files.html',
                          listing=listing,
                          file_list=file_list,
                          current_path=path,
                          parent_path=parent_path,
                          default_path=getattr(github_integration, 'default_path', 'Treekipedia/Data'))

@app.route('/github-download/<path:path>')
def github_download(path):
    """Download a file from GitHub repository"""
    try:
        app.logger.info(f"Attempting to download file from GitHub: {path}")
        
        # Download file directly from raw GitHub URL
        raw_url = f"https://raw.githubusercontent.com/{app.config.get('GITHUB_REPO_OWNER', 'SilviProtocol')}/{app.config.get('GITHUB_REPO_NAME', 'silvi-open')}/{app.config.get('GITHUB_BRANCH', 'master')}/{path}"
        
        try:
            response = requests.get(raw_url, stream=True)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Create a temporary file to store the download
            filename = os.path.basename(path)
            temp_dir = tempfile.mkdtemp()
            temp_file = os.path.join(temp_dir, filename)
            
            # Write the content to the temporary file
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            app.logger.info(f"Successfully downloaded {path} to {temp_file}")
            
            # Send the file to the user
            return send_file(temp_file, as_attachment=True, download_name=filename)
            
        except requests.RequestException as e:
            error_msg = f"Error downloading file from GitHub: {str(e)}"
            app.logger.error(error_msg)
            flash(error_msg)
            return redirect(url_for('github_files', path=os.path.dirname(path) if '/' in path else None))
        
    except Exception as e:
        error_msg = f"Error processing download: {str(e)}"
        app.logger.error(error_msg)
        flash(error_msg)
        return redirect(url_for('github_files'))

@app.route('/github-import/<path:path>')
def github_import(path):
    """Import a CSV file from GitHub into the versioning system"""
    try:
        # Check if file is a CSV
        if not path.lower().endswith('.csv'):
            flash('Only CSV files can be imported')
            return redirect(url_for('github_files', path=os.path.dirname(path)))
        
        # Download file to temporary location
        result = github_integration.download_file_to_temp(path)
        
        if not result['success']:
            flash(f'Error importing file: {result.get("error", "Unknown error")}')
            return redirect(url_for('github_files'))
        
        # Redirect to review page with the temporary file
        temp_file = result['temp_file']
        filename = result['filename']
        
        # Compare with current version
        current_csv = os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv')
        
        # Check if repository is initialized
        if not os.path.exists(current_csv):
            # Redirect to initialize with this file
            return redirect(url_for('initialize', github_file=temp_file, github_filename=filename))
        
        # Compare files
        comparison = versioning.compare_csv(current_csv, temp_file)
        
        # Get sample of data
        try:
            df = pd.read_csv(temp_file, nrows=10)
            sample_data = df.to_dict('records')
            columns = df.columns.tolist()
        except Exception as e:
            sample_data = []
            columns = []
            flash(f'Error reading CSV: {str(e)}')
        
        return render_template('review.html', 
                              filename=filename,
                              upload_path=temp_file,
                              comparison=comparison,
                              sample_data=sample_data,
                              columns=columns,
                              from_github=True,
                              github_path=path)
    except Exception as e:
        flash(f'Error importing file: {str(e)}')
        return redirect(url_for('github_files'))

# Routes
@app.route('/')
def index():
    """Home page showing version history"""
    versions = get_all_versions()
    has_data = os.path.exists(os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv'))
    
    return render_template('index.html', versions=versions, has_data=has_data)

@app.route('/initialize', methods=['GET', 'POST'])
def initialize():
    """Initialize the repository with first CSV"""
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        message = request.form.get('message', 'Initial import')
        contributor = request.form.get('contributor', 'System')
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            # Save uploaded file
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOADS_DIR'], filename)
            file.save(upload_path)
            
            # Initialize repository
            success = versioning.initialize(upload_path, message, contributor)
            
            if success:
                flash(f'Repository initialized with {filename}')
                return redirect(url_for('index'))
            else:
                flash('Error initializing repository')
                return redirect(request.url)
    
    # GET request or initialization failed
    return render_template('initialize.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Upload a new CSV file for versioning"""
    if not os.path.exists(os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv')):
        flash('Repository not initialized. Please initialize first.')
        return redirect(url_for('initialize'))
    
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            # Save uploaded file
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOADS_DIR'], f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
            file.save(upload_path)
            
            # Compare with current version
            current_csv = os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv')
            comparison = versioning.compare_csv(current_csv, upload_path)
            
            # Get sample of data
            try:
                df = pd.read_csv(upload_path, nrows=10)
                sample_data = df.to_dict('records')
                columns = df.columns.tolist()
            except Exception as e:
                sample_data = []
                columns = []
                flash(f'Error reading CSV: {str(e)}')
            
            return render_template('review.html', 
                                  filename=filename,
                                  upload_path=upload_path,
                                  comparison=comparison,
                                  sample_data=sample_data,
                                  columns=columns)
    
    # GET request
    return render_template('upload.html')

@app.route('/submit_version', methods=['POST'])
def submit_version():
    """Process a new version after review"""
    if request.method == 'POST':
        upload_path = request.form.get('upload_path')
        message = request.form.get('message')
        contributor = request.form.get('contributor')
        version_type = request.form.get('version_type', 'patch')
        
        # Check if this is from a Google Sheet
        from_sheet = request.form.get('from_sheet') == 'true'
        
        if not all([upload_path, message, contributor]):
            flash('All fields are required')
            return redirect(url_for('upload'))
        
        # Add the new version
        success = versioning.add_version(upload_path, message, contributor, version_type)
        
        if success:
            # Get the new version number
            with open(os.path.join(app.config['BASE_DIR'], 'version_metadata.json'), 'r') as f:
                metadata = json.load(f)
                current_version = metadata['current_version']
            
            # Update Google Sheet version info if applicable
            if from_sheet and 'synced_sheet_id' in session:
                sheet_id = session.pop('synced_sheet_id')
                sheets_manager.update_sheet_sync_status(sheet_id, current_version)
                # Add Google Sheet reference to the commit message
                sheet = sheets_manager.get_sheet_by_id(sheet_id)
                if sheet:
                    # Update message in version metadata to include sheet reference
                    for version in metadata['versions']:
                        if version['version'] == current_version:
                            version['message'] = f"{message} [From Google Sheet: {sheet['name']}]"
                            version['sheet_id'] = sheet_id
                            break
                    
                    # Save updated metadata
                    with open(os.path.join(app.config['BASE_DIR'], 'version_metadata.json'), 'w') as f:
                        json.dump(metadata, f, indent=2)
            
            flash(f'Successfully created version {current_version}')
            return redirect(url_for('version_detail', version_id=current_version))
        else:
            flash('Error creating version')
            return redirect(url_for('upload'))
    
    return redirect(url_for('upload'))

@app.route('/version/<version_id>')
def version_detail(version_id):
    """Show details for a specific version"""
    # Get version metadata
    try:
        with open(os.path.join(app.config['BASE_DIR'], 'version_metadata.json'), 'r') as f:
            metadata = json.load(f)
            
        version_info = None
        for version in metadata['versions']:
            if version['version'] == version_id:
                version_info = version
                break
        
        if version_id == 'current':
            version_info = {
                'version': 'current',
                'is_current': True,
                'timestamp': datetime.now().isoformat(),
                'message': 'Current working version',
                'contributor': 'System'
            }
        
        if not version_info:
            flash(f'Version {version_id} not found')
            return redirect(url_for('index'))
        
        # Get the CSV file path
        if version_id == metadata['current_version'] or version_id == 'current':
            csv_path = os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv')
        else:
            csv_path = os.path.join(app.config['VERSIONS_DIR'], f"species_data_{version_id}.csv")
        
        # Get a sample of the data
        try:
            df = pd.read_csv(csv_path, nrows=app.config['SAMPLE_SIZE'])
            sample_data = df.to_dict('records')
            columns = df.columns.tolist()
        except Exception as e:
            sample_data = []
            columns = []
            flash(f'Error reading CSV: {str(e)}')
        
        # Get change report if available
        report_path = os.path.join(app.config['REPORTS_DIR'], f"changes_{version_id}.json")
        report = None
        if os.path.exists(report_path):
            with open(report_path, 'r') as f:
                report = json.load(f)
        
        return render_template('version_detail.html',
                              version_id=version_id,
                              version_info=version_info,
                              sample_data=sample_data,
                              columns=columns,
                              report=report)
    except Exception as e:
        flash(f'Error loading version: {str(e)}')
        return redirect(url_for('index'))

@app.route('/download/<version_id>')
def download_version(version_id):
    """Download a specific version as CSV"""
    # Get version metadata
    try:
        with open(os.path.join(app.config['BASE_DIR'], 'version_metadata.json'), 'r') as f:
            metadata = json.load(f)
        
        # Get the CSV file path
        if version_id == metadata['current_version'] or version_id == 'current':
            csv_path = os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv')
            download_name = f"species_data_current.csv"
        else:
            csv_path = os.path.join(app.config['VERSIONS_DIR'], f"species_data_{version_id}.csv")
            download_name = f"species_data_{version_id}.csv"
        
        if not os.path.exists(csv_path):
            flash(f'CSV file for version {version_id} not found')
            return redirect(url_for('index'))
        
        return send_file(csv_path, as_attachment=True, download_name=download_name)
    except Exception as e:
        flash(f'Error downloading version: {str(e)}')
        return redirect(url_for('index'))

@app.route('/report/<version_id>')
def download_report(version_id):
    """Download a change report for a specific version"""
    report_path = os.path.join(app.config['REPORTS_DIR'], f"changes_{version_id}.json")
    
    if not os.path.exists(report_path):
        flash(f'Report for version {version_id} not found')
        return redirect(url_for('index'))
    
    return send_file(report_path, as_attachment=True, download_name=f"changes_{version_id}.json")

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    """Compare two versions"""
    # Get all versions
    versions = get_all_versions()
    
    if request.method == 'POST':
        version1 = request.form.get('version1')
        version2 = request.form.get('version2')
        
        if not version1 or not version2:
            flash('Please select two versions to compare')
            return redirect(url_for('compare'))
        
        # Get the CSV file paths
        with open(os.path.join(app.config['BASE_DIR'], 'version_metadata.json'), 'r') as f:
            metadata = json.load(f)
        
        if version1 == 'current':
            csv1_path = os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv')
        else:
            csv1_path = os.path.join(app.config['VERSIONS_DIR'], f"species_data_{version1}.csv")
        
        if version2 == 'current':
            csv2_path = os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv')
        else:
            csv2_path = os.path.join(app.config['VERSIONS_DIR'], f"species_data_{version2}.csv")
        
        # Compare the two versions
        comparison = versioning.compare_csv(csv1_path, csv2_path)
        
        return render_template('compare.html', 
                              versions=versions, 
                              comparison=comparison,
                              version1=version1,
                              version2=version2)
    
    # GET request
    return render_template('compare.html', versions=versions)

# Google Sheets Integration Routes

@app.route('/google-sheets')
def google_sheets():
    """Google Sheets integration page"""
    if not google_sheets_available:
        flash('Google Sheets API packages are not installed. Please run `pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client`')
    
    # Get all connected sheets
    connected_sheets = sheets_manager.get_all_sheets()
    
    return render_template('google_sheets.html', 
                          connected_sheets=connected_sheets,
                          google_sheets_available=google_sheets_available)

@app.route('/connect-sheet', methods=['POST'])
def connect_sheet():
    """Connect a new Google Sheet"""
    if not google_sheets_available:
        flash('Google Sheets API packages are not installed')
        return redirect(url_for('google_sheets'))
    
    sheet_url = request.form.get('sheet_url')
    sheet_name = request.form.get('sheet_name')
    sheet_description = request.form.get('sheet_description', '')
    species_id_column = request.form.get('species_id_column', app.config['SPECIES_ID_COLUMN'])
    
    if not all([sheet_url, sheet_name]):
        flash('Sheet URL and name are required')
        return redirect(url_for('google_sheets'))
    
    # Connect the sheet
    result = sheets_manager.connect_sheet(sheet_url, sheet_name, sheet_description, species_id_column)
    
    if result['success']:
        flash(f'Successfully connected Google Sheet: {sheet_name}')
    else:
        flash(f'Error connecting Google Sheet: {result.get("error", "Unknown error")}')
    
    return redirect(url_for('google_sheets'))

@app.route('/disconnect-sheet', methods=['POST'])
def disconnect_sheet():
    """Disconnect a Google Sheet"""
    sheet_id = request.form.get('sheet_id')
    
    if not sheet_id:
        flash('Sheet ID is required')
        return redirect(url_for('google_sheets'))
    
    # Disconnect the sheet
    result = sheets_manager.disconnect_sheet(sheet_id)
    
    if result['success']:
        flash(f'Successfully disconnected Google Sheet: {result["sheet"]["name"]}')
    else:
        flash(f'Error disconnecting Google Sheet: {result.get("error", "Unknown error")}')
    
    return redirect(url_for('google_sheets'))

@app.route('/sync-sheet/<sheet_id>')
def sync_sheet(sheet_id):
    """Sync a Google Sheet with the versioning system"""
    if not google_sheets_available:
        flash('Google Sheets API packages are not installed')
        return redirect(url_for('google_sheets'))
    
    # Get sheet info
    sheet = sheets_manager.get_sheet_by_id(sheet_id)
    if not sheet:
        flash('Sheet not found')
        return redirect(url_for('google_sheets'))
    
    # Sync the sheet
    result = sheets_manager.sync_sheet(sheet_id)
    
    if result['success']:
        # Show review page for changes
        csv_path = result['csv_path']
        
        # Compare with current version
        current_csv = os.path.join(app.config['CURRENT_DATA_DIR'], 'species_data.csv')
        comparison = versioning.compare_csv(current_csv, csv_path)
        
        # Get sample of data
        try:
            df = pd.read_csv(csv_path, nrows=10)
            sample_data = df.to_dict('records')
            columns = df.columns.tolist()
        except Exception as e:
            sample_data = []
            columns = []
            flash(f'Error reading CSV: {str(e)}')
        
        # Store sheet_id for use in submit_version
        session['synced_sheet_id'] = sheet_id
        
        return render_template('review.html', 
                              filename=f"Google Sheet: {sheet['name']}",
                              upload_path=csv_path,
                              comparison=comparison,
                              sample_data=sample_data,
                              columns=columns,
                              from_sheet=True,
                              sheet=sheet)
    else:
        flash(f'Error syncing Google Sheet: {result.get("error", "Unknown error")}')
        return redirect(url_for('google_sheets'))

@app.route('/sheet-history/<sheet_id>')
def sheet_history(sheet_id):
    """View version history for a specific sheet"""
    # Get sheet info
    sheet = sheets_manager.get_sheet_by_id(sheet_id)
    if not sheet:
        flash('Sheet not found')
        return redirect(url_for('google_sheets'))
    
    # Get all versions
    versions = get_all_versions()
    
    # Filter versions related to this sheet if available
    sheet_versions = []
    if 'versions' in sheet:
        sheet_version_ids = [v['version_id'] for v in sheet['versions']]
        sheet_versions = [v for v in versions if v['version'] in sheet_version_ids]
    
    return render_template('sheet_history.html',
                          sheet=sheet,
                          versions=sheet_versions)

# Helper functions
def get_all_versions():
    """Get list of all versions from metadata"""
    try:
        metadata_path = os.path.join(app.config['BASE_DIR'], 'version_metadata.json')
        if not os.path.exists(metadata_path):
            return []
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Add current flag to current version
        for version in metadata['versions']:
            version['is_current'] = (version['version'] == metadata['current_version'])
        
        # Sort by version (assuming semantic versions like v1.0.0)
        sorted_versions = sorted(metadata['versions'], 
                                key=lambda x: [int(n) for n in x['version'][1:].split('.')], 
                                reverse=True)
        
        return sorted_versions
    except Exception as e:
        print(f"Error getting versions: {str(e)}")
        return []

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        # Initialize the application
        os.makedirs(app.config['CURRENT_DATA_DIR'], exist_ok=True)
        os.makedirs(app.config['VERSIONS_DIR'], exist_ok=True)
        os.makedirs(app.config['REPORTS_DIR'], exist_ok=True)
        os.makedirs(app.config['UPLOADS_DIR'], exist_ok=True)
        os.makedirs(app.config['SHEETS_DIR'], exist_ok=True)
        print("Application initialized successfully.")
        sys.exit(0)
    
    # Run the web server
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=5001)