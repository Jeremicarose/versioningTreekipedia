#!/usr/bin/env python3
"""
Github integration for treekipedia

This module provide functionality to fetch file directlyfrom github repository
"""
import os
import json
import requests
from datetime import datetime
import logging
import tempfile

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('github_integration')

class GitHubIntegration:
    """
    Github integration for fetching files from public repositories
    """
    def __init__(self, repo_owner="SilviProtocol", repo_name="silvi-open", branch="master", default_path="Treekipedia/Data"):
        """Initialize github integration with repository info"""
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self.default_path = default_path
        self.api_base_url = "https://api.github.com"
        self.raw_content_base_url = "https://raw.githubusercontent.com"

        # Cache for directory listings to reduce API calls
        self.cache = {}
        self.cache_expiry = 300 # 5 min

        logger.info("Initialized Github integration for {repo_owner}/{repo_name}:{branch}")

    def list_files(self, path=None):
        """
        List files in a specific directory of therepository

        Args:
           path (str): Path within the repository

        Returns:
            dict: Success flag and list of files/directories   
        """    
        path = path or self.default_path
        cache_key = f"list:{path}"

        #Check cache first
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if datetime.now().timestamp() - cache_entry['timestamp'] < self.cache_expiry:
                logger.info(f"Using cached listing for {path}")
                return cache_entry['data']
            
        try: 
            # Make Api request to get contents
            url = f"{self.api_base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{path}"
            params = {"ref": self.branch}
            response = requests.get(url, params=params)
            response.raise_for_status()

            contents = response.json()
            result = {"success": True, "path":path, "items": []}

            # Handle case when contents is not a list
            if not isinstance(contents, list):
                logger.warning(f"Expected directory listing but got a file: {path}")
                return {"success": False, "error": "path is not a directory", "items": []}

            # Process directories and files
            for item in contents:
                if not isinstance(item, dict) or "name" not in item:
                    continue
                item_info = {
                    "name": item["name"],
                    "path": item["path"],
                    "type": item["type"],
                    "size": item.get("size", 0),
                    "download_url": item.get("download_url", ""),
                    "html_url": item.get("html_url", "")
                }  

                # Add additional info for different file types
                if item["type"] == "file":
                    # Determine file type
                    file_extention = os.path.splitext(item["name"])[1].lower()
                    if file_extention in ['.csv', '.xlsx', '.xls']:
                        item_info["category"] = "data"
                    elif file_extention in ['.json', '.geojson']:
                        item_info["category"] = "geo"
                    elif file_extention in ['.jpg', '.jpeg', '.png', '.gif']:
                        item_info["category"] = "image"
                    elif file_extention in ['.md', ',txt']:
                        item_info["category"] = "document"
                    else:
                        item_info["category"] = "other"

                result["items"].append(item_info)                  

            # Sort: directories first, then files alphabetically
            result["items"].sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower())) 

            # Update cache
            self.cache[cache_key] = {
                'timestamp': datetime.now().timestamp(),
                'data': result
            }   

            return result
        
        except requests.RequestException as e:
            error_msg = f"Error fetching directory listing from Github: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "items": []}
        except Exception as e:
            error_msg = f"Unexpected error in list_files: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "items": []}
        
    def get_file_content(self, path):
        """
        Get the content of a specific file
        Args:
             path (str: Path to the file within the repository

         Returns:
             dict: Success flag and file content or error    
        """   
        try:
            # Check if path exists and is a file
            url = f"{self.api_base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{path}"
            params = {"ref": self.branch}

            response = requests.get(url, params=params)
            response.raise_for_status()

            content = response.json()

            # If content is not a dict or doesnt have a download_url its not a file
            if not isinstance(content, dict) or "download_url" not in content:
                return {"success": False, "error": "Path is not a file"}
            
            # For larger files, redirect to the raw content URL
            if content.get("size", 0) > 1024 * 1024:   # > 1MB
                return {
                    "success": True,
                    "path": path,
                    "redirect_url": content.get["download_url"],
                    "size": content.get("size", 0),
                    "is_large": True
                }
            
            # For smaller files, get the raw content
            raw_response = requests.get(content["download_url"])
            raw_response.raise_for_status()

            return {
                "success": True,
                "path": path,
                "content": raw_response.content,
                "size": content.get("size", 0),
                "is_large": False
            }
        except requests.RequestException as e:
            error_msg = f"Error fetching file content from Github: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error in get_file_content: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
    def download_file_to_temp(self, path):
        """
        Download a file to a temporary location

        Args:
            path (str): Path to the file within the repository

        Returns:
             dict: Success flag and push to temporary files or error
        """ 
        try:
            # Get raw content URL
            url = f"{self.row_content_base_url}/{self.repo_owner}/{self.repo_name}/{self.branch}/{path}"

            # Make request to download file
            response = requests.get(url, stream=True)
            response.raise_for_status()

            # Create temporary file
            filename = os.path.basename(path)
            temp_dir = tempfile.mkdtemp()
            temp_file = os.path.join(temp_dir, filename)

            # Write content to temporary file
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded file from Github: {path} -> {temp_file}")

            return {
                "success": True,
                "path": path,
                "temp_file": temp_file,
                "filename": filename
            }     
        except requests.RequestException as e:
            error_msg = f"Error downloading file from Github: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error in download_file_to_temp: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

def init_github_integration(config=None):
    """
    Initialize the Github integration for the web application

    Args:
         config (dict): Configuration for Github integration

    Returns:
         GithubIntegration: Initialized Github integration     
    """              
    if not config:
        return GitHubIntegration()
    
    repo_owner = config.get('GITHUB_REPO_OWNER', 'SilviProtocol')
    repo_name = config.get('GITHUB_REPO_NAME', 'silvi-open')
    branch = config.get('GITHUB_BRANCH', 'master')
    default_path = config.get('GITHUB_DEFAULT_PATH', 'Treekipedia/Data')

    return GitHubIntegration(repo_owner, repo_name, branch, default_path)