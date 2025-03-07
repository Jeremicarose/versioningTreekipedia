#!/usr/bin/env python3
"""
CSV Versioning System for Treekipedia

This script provides a complete workflow for versioning CSV files using DVC.
It tracks changes between versions and maintains a comprehensive history.

Author: Treekipedia Team
"""

import os
import sys
import shutil
import subprocess
import json
import pandas as pd
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('csv_version')

class CSVVersioningSystem:
    def __init__(self, base_dir=None):
        """Initialize the versioning system with directory structure"""
        # Set base directory (default to current directory)
        self.base_dir = base_dir or os.getcwd()
        
        # Define directory structure
        self.data_dir = os.path.join(self.base_dir, "data")
        self.current_dir = os.path.join(self.data_dir, "current")
        self.versions_dir = os.path.join(self.data_dir, "versions")
        self.reports_dir = os.path.join(self.base_dir, "reports")
        
        # Create directories if they don't exist
        for directory in [self.data_dir, self.current_dir, self.versions_dir, self.reports_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Define file paths
        self.current_csv = os.path.join(self.current_dir, "species_data.csv")
        self.metadata_file = os.path.join(self.base_dir, "version_metadata.json")
        
        logger.info(f"Initialized versioning system in {self.base_dir}")
    
    def initialize(self, csv_file, message="Initial import", contributor="System"):
        """Initialize the repository with the first CSV file"""
        # Check if repository is already initialized
        if os.path.exists(self.current_csv):
            logger.warning("Repository already initialized. Use add_version instead.")
            return False
        
        # Check if file exists
        if not os.path.exists(csv_file):
            logger.error(f"File not found: {csv_file}")
            return False
        
        # Copy the file to the current directory
        shutil.copy(csv_file, self.current_csv)
        logger.info(f"Copied {csv_file} to {self.current_csv}")
        
        # Initialize DVC if not already initialized
        if not os.path.exists(os.path.join(self.base_dir, ".dvc")):
            try:
                subprocess.run(["dvc", "init"], cwd=self.base_dir, check=True)
                subprocess.run(["git", "add", ".dvc", ".dvcignore"], cwd=self.base_dir, check=True)
                subprocess.run(["git", "commit", "-m", "Initialize DVC repository"], cwd=self.base_dir, check=True)
                logger.info("Initialized DVC repository")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error initializing DVC: {str(e)}")
                return False
        
        # Track the current CSV with DVC
        try:
            subprocess.run(["dvc", "add", self.current_csv], cwd=self.base_dir, check=True)
            logger.info(f"Added {self.current_csv} to DVC")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error adding file to DVC: {str(e)}")
            return False
        
        # Read CSV and get stats
        try:
            df = pd.read_csv(self.current_csv)
            stats = {
                "row_count": len(df),
                "column_count": len(df.columns)
            }
        except Exception as e:
            logger.error(f"Error reading CSV: {str(e)}")
            stats = {"row_count": 0, "column_count": 0}
        
        # Create initial metadata
        metadata = {
            "versions": [
                {
                    "version": "v1.0.0",
                    "timestamp": datetime.now().isoformat(),
                    "message": message,
                    "contributor": contributor,
                    "file": self.current_csv,
                    "stats": stats
                }
            ],
            "current_version": "v1.0.0",
            "latest": {
                "major": 1,
                "minor": 0,
                "patch": 0
            }
        }
        
        # Save metadata
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info("Created version metadata file")
        
        # Commit changes to Git
        try:
            subprocess.run(["git", "add", f"{self.current_csv}.dvc", self.metadata_file], cwd=self.base_dir, check=True)
            subprocess.run(["git", "commit", "-m", f"v1.0.0: {message}"], cwd=self.base_dir, check=True)
            subprocess.run(["git", "tag", "-a", "v1.0.0", "-m", message], cwd=self.base_dir, check=True)
            logger.info("Committed changes to Git")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error committing to Git: {str(e)}")
            return False
        
        logger.info(f"Repository initialized with {csv_file} as version v1.0.0")
        return True
    
    def add_version(self, csv_file, message, contributor="User", version_type="patch"):
        """Add a new version of the CSV file"""
        # Check if repository is initialized
        if not os.path.exists(self.current_csv):
            logger.error("Repository not initialized. Use initialize first.")
            return False
        
        # Check if file exists
        if not os.path.exists(csv_file):
            logger.error(f"File not found: {csv_file}")
            return False
        
        # Load metadata
        try:
            with open(self.metadata_file, "r") as f:
                metadata = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading metadata: {str(e)}")
            return False
        
        # Generate new version number
        latest = metadata["latest"]
        if version_type == "major":
            new_version = f"v{latest['major'] + 1}.0.0"
            latest["major"] += 1
            latest["minor"] = 0
            latest["patch"] = 0
        elif version_type == "minor":
            new_version = f"v{latest['major']}.{latest['minor'] + 1}.0"
            latest["minor"] += 1
            latest["patch"] = 0
        else:  # patch
            new_version = f"v{latest['major']}.{latest['minor']}.{latest['patch'] + 1}"
            latest["patch"] += 1
        
        logger.info(f"Creating new version: {new_version}")
        
        # Create version file
        version_file = os.path.join(self.versions_dir, f"species_data_{new_version}.csv")
        
        # Backup current version
        shutil.copy(self.current_csv, version_file)
        logger.info(f"Backed up current version to {version_file}")
        
        # Compare the files and generate report
        comparison = self.compare_csv(self.current_csv, csv_file)
        
        # Save comparison report
        report_file = os.path.join(self.reports_dir, f"changes_{new_version}.json")
        with open(report_file, "w") as f:
            json.dump(comparison, f, indent=2)
        logger.info(f"Generated change report at {report_file}")
        
        # Update current version with new file
        shutil.copy(csv_file, self.current_csv)
        logger.info(f"Updated current version with {csv_file}")
        
        # Track files with DVC
        try:
            subprocess.run(["dvc", "add", self.current_csv], cwd=self.base_dir, check=True)
            subprocess.run(["dvc", "add", version_file], cwd=self.base_dir, check=True)
            logger.info("Added files to DVC")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error adding files to DVC: {str(e)}")
            return False
        
        # Read CSV and get stats
        try:
            df = pd.read_csv(self.current_csv)
            stats = {
                "row_count": len(df),
                "column_count": len(df.columns)
            }
        except Exception as e:
            logger.error(f"Error reading CSV: {str(e)}")
            stats = {"row_count": 0, "column_count": 0}
        
        # Update metadata
        new_entry = {
            "version": new_version,
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "contributor": contributor,
            "file": version_file,
            "previous_version": metadata["current_version"],
            "stats": stats,
            "changes": comparison["summary"] if "summary" in comparison else {}
        }
        
        metadata["versions"].append(new_entry)
        metadata["current_version"] = new_version
        metadata["latest"] = latest
        
        # Save updated metadata
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info("Updated metadata file")
        
        # Commit changes to Git
        try:
            subprocess.run(["git", "add", 
                            f"{self.current_csv}.dvc", 
                            f"{version_file}.dvc", 
                            self.metadata_file,
                            report_file], 
                           cwd=self.base_dir, check=True)
            subprocess.run(["git", "commit", "-m", f"{new_version}: {message}"], cwd=self.base_dir, check=True)
            subprocess.run(["git", "tag", "-a", new_version, "-m", message], cwd=self.base_dir, check=True)
            logger.info("Committed changes to Git")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error committing to Git: {str(e)}")
            return False
        
        logger.info(f"Successfully created version {new_version}")
        return True
    
    def compare_csv(self, original_file, modified_file, id_column="species"):
        """Compare two CSV files and identify changes"""
        logger.info(f"Comparing {original_file} and {modified_file}")
        
        # Load both CSV files
        try:
            df1 = pd.read_csv(original_file, low_memory=False)
            df2 = pd.read_csv(modified_file, low_memory=False)
        except Exception as e:
            logger.error(f"Error loading CSV files: {e}")
            return {"error": str(e)}
        
        # Get basic info
        changes = {
            "comparison_date": datetime.now().isoformat(),
            "files": {
                "original": {
                    "path": original_file,
                    "row_count": len(df1),
                    "column_count": len(df1.columns)
                },
                "modified": {
                    "path": modified_file,
                    "row_count": len(df2),
                    "column_count": len(df2.columns)
                }
            },
            "summary": {},
            "details": {}
        }
        
        # Check column differences
        v1_cols = set(df1.columns)
        v2_cols = set(df2.columns)
        
        added_cols = list(v2_cols - v1_cols)
        removed_cols = list(v1_cols - v2_cols)
        common_cols = list(v1_cols.intersection(v2_cols))
        
        changes["summary"]["columns"] = {
            "added": added_cols,
            "removed": removed_cols,
            "common_count": len(common_cols)
        }
        
        # Use provided ID column or try to find a suitable one
        if id_column and id_column in common_cols:
            # Use the specified column
            id_col = id_column
        else:
            # Try to identify a primary key column
            potential_key_cols = []
            for col in common_cols:
                if df1[col].nunique() == len(df1) and df2[col].nunique() == len(df2):
                    potential_key_cols.append(col)
            
            # Use the first potential key column or None
            id_col = potential_key_cols[0] if potential_key_cols else None
        
        if id_col:
            logger.info(f"Using '{id_col}' as identifier column")
            
            # Get sets of IDs
            ids_v1 = set(df1[id_col])
            ids_v2 = set(df2[id_col])
            
            # Find added and removed rows
            added_ids = list(ids_v2 - ids_v1)
            removed_ids = list(ids_v1 - ids_v2)
            common_ids = list(ids_v1.intersection(ids_v2))
            
            changes["summary"]["rows"] = {
                "added_count": len(added_ids),
                "removed_count": len(removed_ids),
                "common_count": len(common_ids),
                "modified_count": 0  # Will update this later
            }
            
            # Sample of added/removed for display
            changes["details"]["added_rows"] = added_ids[:20] if len(added_ids) > 0 else []
            changes["details"]["removed_rows"] = removed_ids[:20] if len(removed_ids) > 0 else []
            
            # Check for modified rows
            modified_rows = []
            
            for id_val in common_ids:
                row1 = df1[df1[id_col] == id_val].iloc[0]
                row2 = df2[df2[id_col] == id_val].iloc[0]
                
                # Compare values for common columns
                differences = {}
                for col in common_cols:
                    # Handle NaN values
                    val1 = row1[col]
                    val2 = row2[col]
                    
                    # Check if values are different
                    if pd.isna(val1) and pd.isna(val2):
                        continue  # Both are NaN, considered equal
                    elif pd.isna(val1) or pd.isna(val2):
                        differences[col] = {
                            "from": str(val1) if not pd.isna(val1) else "NULL",
                            "to": str(val2) if not pd.isna(val2) else "NULL"
                        }
                    elif val1 != val2:
                        differences[col] = {
                            "from": str(val1),
                            "to": str(val2)
                        }
                
                if differences:
                    modified_rows.append({
                        "id": id_val,
                        "changes": differences
                    })
            
            # Update modified count
            changes["summary"]["rows"]["modified_count"] = len(modified_rows)
            
            # Store sample of modified rows (for display)
            changes["details"]["modified_rows"] = modified_rows[:50] if modified_rows else []
            
        else:
            logger.warning("No suitable ID column found. Using basic row comparison.")
            # No ID column, do basic row count comparison
            changes["summary"]["rows"] = {
                "original_count": len(df1),
                "modified_count": len(df2),
                "difference": len(df2) - len(df1)
            }
        
        # Generate human-readable report
        report_txt = f"Comparison Report\n"
        report_txt += f"=================\n\n"
        report_txt += f"Original: {original_file}\n"
        report_txt += f"Modified: {modified_file}\n\n"
        report_txt += f"Rows: {len(df1)} → {len(df2)} ({len(df2) - len(df1):+d})\n"
        report_txt += f"Columns: {len(df1.columns)} → {len(df2.columns)} ({len(df2.columns) - len(df1.columns):+d})\n\n"
        
        if added_cols:
            report_txt += f"Added columns: {', '.join(added_cols)}\n"
        if removed_cols:
            report_txt += f"Removed columns: {', '.join(removed_cols)}\n"
        
        if id_col:
            report_txt += f"\nUsing '{id_col}' as identifier:\n"
            report_txt += f"  Added rows: {len(added_ids)}\n"
            report_txt += f"  Removed rows: {len(removed_ids)}\n"
            report_txt += f"  Modified rows: {len(modified_rows)}\n"
        
        changes["report_text"] = report_txt
        return changes
    
    def list_versions(self):
        """List all versions in the repository"""
        # Load metadata
        try:
            with open(self.metadata_file, "r") as f:
                metadata = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading metadata: {str(e)}")
            return []
        
        return metadata["versions"]
    
    def get_version(self, version_id):
        """Get information about a specific version"""
        # Load metadata
        try:
            with open(self.metadata_file, "r") as f:
                metadata = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading metadata: {str(e)}")
            return None
        
        # Find the version
        for version in metadata["versions"]:
            if version["version"] == version_id:
                return version
        
        return None
    
    def checkout_version(self, version):
        """Checkout a specific version of the data"""
        # Load metadata
        try:
            with open(self.metadata_file, "r") as f:
                metadata = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading metadata: {str(e)}")
            return False
        
        # Checkout the Git tag
        try:
            subprocess.run(["git", "checkout", version], cwd=self.base_dir, check=True)
            logger.info(f"Checked out Git tag {version}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error checking out Git tag: {str(e)}")
            return False
        
        # Checkout the DVC files
        try:
            subprocess.run(["dvc", "checkout"], cwd=self.base_dir, check=True)
            logger.info("Checked out DVC files")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error checking out DVC files: {str(e)}")
            return False
        
        logger.info(f"Successfully checked out version {version}")
        return True

# Main function for command line usage
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="CSV Versioning System")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Initialize command
    init_parser = subparsers.add_parser("init", help="Initialize repository with first CSV")
    init_parser.add_argument("file", help="CSV file to add")
    init_parser.add_argument("--message", "-m", default="Initial import", help="Version message")
    init_parser.add_argument("--contributor", "-c", default="System", help="Contributor name")
    
    # Add version command
    add_parser = subparsers.add_parser("add", help="Add a new version")
    add_parser.add_argument("file", help="CSV file to add")
    add_parser.add_argument("--message", "-m", required=True, help="Version message")
    add_parser.add_argument("--contributor", "-c", default="User", help="Contributor name")
    add_parser.add_argument("--type", "-t", choices=["patch", "minor", "major"], default="patch", 
                           help="Version type: patch (1.0.0 -> 1.0.1), minor (1.0.0 -> 1.1.0), major (1.0.0 -> 2.0.0)")
    
    # List versions command
    subparsers.add_parser("list", help="List all versions")
    
    # Checkout version command
    checkout_parser = subparsers.add_parser("checkout", help="Checkout a specific version")
    checkout_parser.add_argument("version", help="Version to checkout (e.g., v1.0.0)")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two CSV files")
    compare_parser.add_argument("original", help="Original CSV file")
    compare_parser.add_argument("modified", help="Modified CSV file")
    compare_parser.add_argument("--id-column", default="species", help="Column to use as identifier")
    
    args = parser.parse_args()
    
    # Create versioning system
    versioning = CSVVersioningSystem()
    
    if args.command == "init":
        versioning.initialize(args.file, args.message, args.contributor)
    elif args.command == "add":
        versioning.add_version(args.file, args.message, args.contributor, args.type)
    elif args.command == "list":
        versions = versioning.list_versions()
        print("\nVersion History:")
        print("===============")
        for version in versions:
            print(f"\n{version['version']} - {version['timestamp']}")
            print(f"  Message: {version['message']}")
            print(f"  Contributor: {version['contributor']}")
            
            if "stats" in version:
                print(f"  Rows: {version['stats']['row_count']}")
                print(f"  Columns: {version['stats']['column_count']}")
            
            if "changes" in version and "rows" in version["changes"]:
                changes = version["changes"]["rows"]
                if "added_count" in changes:
                    print(f"  Changes: +{changes['added_count']} added, -{changes['removed_count']} removed, {changes['modified_count']} modified")
    elif args.command == "checkout":
        versioning.checkout_version(args.version)
    elif args.command == "compare":
        comparison = versioning.compare_csv(args.original, args.modified, args.id_column)
        print(comparison["report_text"])
    else:
        parser.print_help()

if __name__ == "__main__":
    main()