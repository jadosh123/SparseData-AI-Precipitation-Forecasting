from pathlib import Path

def get_project_root() -> Path:
    """
    Finds and returns the project root by traversing upwards from the current 
    file's directory until a .toml file (such as pyproject.toml) is found.
    
    Returns:
        Path: The absolute path to the project's root directory.
        
    Raises:
        FileNotFoundError: If the root of the file system is reached without finding a .toml file.
    """
    current_path = Path(__file__).resolve().parent
    
    while current_path != current_path.parent:
        # Check if there are any .toml files in the current directory
        if list(current_path.glob("*.toml")):
            return current_path
            
        # Move up one level
        current_path = current_path.parent
        
    raise FileNotFoundError("Could not find the project root (no .toml file found in any parent directories).")
