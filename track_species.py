import pandas as pd
import json
import os
import sys
import subprocess
from datetime import datetime

def track_species_changes(csv_file, output_log=None):
    """
    Track changes to species in a CSV file and generate a detailed log
    
    Args:
        csv_file: Path to the CSV file
        output_log: Path to write the change log (optional)
    """
    # Check if we're tracking this file for the first time
    history_file = f"{csv_file}.history.json"
    
    if not os.path.exists(history_file):
        # First time tracking this file
        df = pd.read_csv(csv_file)
        
        # Create initial history
        history = {
            "versions": [
                {
                    "version": 1,
                    "timestamp": datetime.now().isoformat(),
                    "commit_message": "Initial species data",
                    "record_count": len(df),
                    "species_count": len(df["species"].unique()) if "species" in df.columns else "N/A"
                }
            ],
            "current_version": 1
        }
        
        # Save the current data as the baseline
        df.to_csv(f"{csv_file}.v1.backup", index=False)
        
        # Write history file
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
            
        print(f"Initialized tracking for {csv_file}")
        if output_log:
            with open(output_log, 'w') as f:
                f.write(f"# Species Data Change Log\n\n")
                f.write(f"## Version 1 - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write(f"* Initial data with {len(df)} records\n")
                f.write(f"* Species count: {len(df['species'].unique()) if 'species' in df.columns else 'N/A'}\n")
        
        return
    
    # Load history
    with open(history_file, 'r') as f:
        history = json.load(f)
    
    current_version = history["current_version"]
    next_version = current_version + 1
    
    # Load the previous version and current version
    prev_df = pd.read_csv(f"{csv_file}.v{current_version}.backup")
    current_df = pd.read_csv(csv_file)
    
    # Analyze changes
    changes = {
        "added_species": [],
        "removed_species": [],
        "modified_species": [],
        "total_records_before": len(prev_df),
        "total_records_after": len(current_df)
    }
    
    # Check for species column
    if "species" in current_df.columns and "species" in prev_df.columns:
        # Get unique species in each version
        prev_species = set(prev_df["species"].unique())
        current_species = set(current_df["species"].unique())
        
        # Find added and removed species
        changes["added_species"] = list(current_species - prev_species)
        changes["removed_species"] = list(prev_species - current_species)
        
        # Find modified species (same name but different attributes)
        common_species = prev_species.intersection(current_species)
        
        for species in common_species:
            prev_data = prev_df[prev_df["species"] == species]
            current_data = current_df[current_df["species"] == species]
            
            # Check if anything changed
            if not prev_data.equals(current_data):
                changes["modified_species"].append(species)
                
                # Detailed analysis of what changed
                if len(prev_data) == 1 and len(current_data) == 1:
                    # Simple case: one row per species
                    prev_row = prev_data.iloc[0]
                    current_row = current_data.iloc[0]
                    
                    for column in current_df.columns:
                        if column in prev_df.columns:
                            if prev_row[column] != current_row[column]:
                                changes.setdefault("field_changes", {}).setdefault(species, {})[column] = {
                                    "from": prev_row[column],
                                    "to": current_row[column]
                                }
    
    # Save backup of current version
    current_df.to_csv(f"{csv_file}.v{next_version}.backup", index=False)
    
    # Update history
    commit_msg = input("Enter a description of the changes: ")
    
    history["versions"].append({
        "version": next_version,
        "timestamp": datetime.now().isoformat(),
        "commit_message": commit_msg,
        "record_count": len(current_df),
        "species_count": len(current_df["species"].unique()) if "species" in current_df.columns else "N/A",
        "changes": changes
    })
    
    history["current_version"] = next_version
    
    # Write updated history
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)
    
    # Generate log entry
    log_entry = f"## Version {next_version} - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    log_entry += f"* {commit_msg}\n"
    
    if changes["added_species"]:
        log_entry += f"* Added species: {', '.join(changes['added_species'])}\n"
    
    if changes["removed_species"]:
        log_entry += f"* Removed species: {', '.join(changes['removed_species'])}\n"
    
    if changes["modified_species"]:
        log_entry += f"* Modified species: {', '.join(changes['modified_species'])}\n"
        
        # Add details of what changed
        if "field_changes" in changes:
            for species, fields in changes["field_changes"].items():
                log_entry += f"  * {species} changes:\n"
                for field, values in fields.items():
                    log_entry += f"    * {field}: {values['from']} → {values['to']}\n"
    
    log_entry += f"* Total records: {changes['total_records_before']} → {changes['total_records_after']}\n"
    
    print(log_entry)
    
    # Append to log file if provided
    if output_log:
        with open(output_log, 'a') as f:
            f.write(f"\n{log_entry}")
    
    # Now run the DVC commands
    subprocess.run(["dvc", "add", csv_file])
    subprocess.run(["git", "add", f"{csv_file}.dvc"])
    subprocess.run(["git", "commit", "-m", f"Update species data: {commit_msg}"])
    
    print(f"\nChanges tracked successfully in version {next_version}")
    print(f"DVC and Git have been updated. Use 'git tag -a \"v{next_version}\" -m \"{commit_msg}\"' if you want to tag this version.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python track_species.py your_species_file.csv [changelog.md]")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_log = sys.argv[2] if len(sys.argv) > 2 else f"{csv_file}.changelog.md"
    
    track_species_changes(csv_file, output_log)