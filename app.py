import os
import json
import pandas as pd
import tempfile
import shutil
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from datetime import datetime

# Import configuration settings
from config import get_config

# Import CSV versioning system
from csv_version import CSVVersioningSystem

# Create Flask application
app = Flask(__name__)
app.config.from_object(get_config())

# Initialize directories
for directory in [app.config['CURRENT_DATA_DIR'], app.config['VERSIONS_DIR'], 
                 app.config['REPORTS_DIR'], app.config['UPLOADS_DIR']]:
    os.makedirs(directory, exist_ok=True)

# Initialize the versioning system
versioning = CSVVersioningSystem(app.config['BASE_DIR'])

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
            success = versioning.initialize(upload_path, message)
            
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
        
        if not version_info:
            flash(f'Version {version_id} not found')
            return redirect(url_for('index'))
        
        # Get the CSV file path
        if version_id == metadata['current_version']:
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
        print("Application initialized successfully.")
        sys.exit(0)
    
    # Run the web server
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=5000)