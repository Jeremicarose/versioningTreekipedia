#!/usr/bin/env python3
"""
CSV to MediaWiki Importer
Imports species data from versioned CSVs to MediaWiki articles
"""

import os
import pandas as pd
import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('wiki_importer')

# MediaWiki API settings - update these for your installation
WIKI_URL = "http://localhost:8080/wiki/api.php"
WIKI_USERNAME = "Admin"  # Your MediaWiki admin username
WIKI_PASSWORD = "secure_password"  # Your MediaWiki admin password

# Path to your current CSV data file
CSV_PATH = "/usr/local/var/www/data/current/species_data.csv"
# Path to your version metadata file
METADATA_PATH = "/usr/local/var/www/version_metadata.json"

def get_login_token():
    """Get login token from MediaWiki API"""
    session = requests.Session()
    params = {
        'action': 'query',
        'meta': 'tokens',
        'type': 'login',
        'format': 'json'
    }
    response = session.get(url=WIKI_URL, params=params)
    data = response.json()
    return data['query']['tokens']['logintoken'], session

def login(token, session):
    """Login to MediaWiki API"""
    params = {
        'action': 'login',
        'lgname': WIKI_USERNAME,
        'lgpassword': WIKI_PASSWORD,
        'lgtoken': token,
        'format': 'json'
    }
    response = session.post(WIKI_URL, data=params)
    data = response.json()
    if data.get('login', {}).get('result') != 'Success':
        logger.error(f"Login failed: {data}")
        return False, None
    return True, session

def get_csrf_token(session):
    """Get CSRF token for editing pages"""
    params = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    }
    response = session.get(url=WIKI_URL, params=params)
    data = response.json()
    return data['query']['tokens']['csrftoken']

def create_or_update_page(session, csrf_token, title, content):
    """Create or update a wiki page"""
    params = {
        'action': 'edit',
        'title': title,
        'text': content,
        'summary': f'Automated update from CSV versioning system - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        'token': csrf_token,
        'format': 'json'
    }
    response = session.post(WIKI_URL, data=params)
    data = response.json()
    if 'error' in data:
        logger.error(f"Error editing page {title}: {data['error']}")
        return False
    return True

def import_species_to_wiki():
    """Import all species data to wiki pages"""
    try:
        # Read current version metadata to get version number
        try:
            with open(METADATA_PATH, 'r') as f:
                metadata = json.load(f)
                current_version = metadata['current_version']
        except Exception as e:
            logger.error(f"Error reading version metadata: {str(e)}")
            current_version = "Unknown"
            
        # Read CSV data
        try:
            df = pd.read_csv(CSV_PATH)
            logger.info(f"Successfully read CSV with {len(df)} rows and {len(df.columns)} columns")
        except Exception as e:
            logger.error(f"Error reading CSV data: {str(e)}")
            return False
        
        # Get login credentials
        try:
            login_token, session = get_login_token()
            success, session = login(login_token, session)
            
            if not success:
                logger.error("Failed to login to MediaWiki")
                return False
            
            # Get CSRF token for editing
            csrf_token = get_csrf_token(session)
            logger.info("Successfully authenticated with MediaWiki")
        except Exception as e:
            logger.error(f"Error authenticating with MediaWiki: {str(e)}")
            return False
        
        # Process each species
        success_count = 0
        error_count = 0
        
        for idx, row in df.iterrows():
            try:
                # Get species ID (or use index if not available)
                species_id = str(row.get('species', f"Species-{idx}"))
                
                # Create wiki page title
                page_title = f"Species:{species_id}"
                
                # Build page content using template
                content = f"""{{{{Species
|species={species_id}
|common_name={row.get('common_name', '')}
|scientific_name={row.get('scientific_name', '')}
|height={row.get('height', '')}
|age={row.get('age', '')}
|location={row.get('location', '')}
|version={current_version}
|last_updated={datetime.now().strftime('%Y-%m-%d')}
}}}}

== Description ==
''This species entry was automatically imported from the Treekipedia versioning system.''

== Data History ==
* Current version: {current_version}
* [http://localhost:5001/version/{current_version} View version details]
* [http://localhost:5001/github-files View source files]
"""
                
                # Create or update the page
                result = create_or_update_page(session, csrf_token, page_title, content)
                if result:
                    success_count += 1
                    if idx % 10 == 0:  # Log progress every 10 species
                        logger.info(f"Progress: {idx+1}/{len(df)} species processed")
                else:
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing species {idx}: {str(e)}")
                error_count += 1
                
        logger.info(f"Import complete: {success_count} species imported successfully, {error_count} errors")
                
        # Create/update category page for organization
        try:
            category_content = """
This category contains all tree species in the Treekipedia database.

{{#ask: [[Category:Species]]
|?common_name=Common Name
|?scientific_name=Scientific Name
|?height=Height
|?location=Location
|format=table
|sort=species
|order=ascending
}}
"""
            create_or_update_page(session, csrf_token, "Category:Species", category_content)
            logger.info("Created/updated Species category page")
        except Exception as e:
            logger.error(f"Error creating category page: {str(e)}")
        
        # Create/update Main Page if needed
        try:
            main_page_content = """
= Welcome to Treekipedia Wiki =

This wiki contains information about tree species from around the world.

== Browse Species ==

{{#ask: [[Category:Species]]
|limit=10
|?common_name=Common Name
|?scientific_name=Scientific Name
|format=table
|sort=species
|order=ascending
}}

[[:Category:Species|View all species]]

== Tools ==

* [http://localhost:5001/ Treekipedia Versioning System]
* [http://localhost:5001/github-files Repository Files]
* [http://localhost:5001/google-sheets Google Sheets Integration]
"""
            create_or_update_page(session, csrf_token, "Main Page", main_page_content)
            logger.info("Created/updated Main Page")
        except Exception as e:
            logger.error(f"Error creating main page: {str(e)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error importing species data: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting species import to MediaWiki")
    result = import_species_to_wiki()
    if result:
        logger.info("Import completed successfully")
    else:
        logger.error("Import failed")