#!/usr/bin/env python3
"""
Script to clean up requirements.txt, removing duplicates and maintaining categories.
"""

import re

def clean_requirements_file(input_file, output_file):
    """
    Clean up a requirements.txt file by removing duplicates and maintaining categories.
    
    Args:
        input_file (str): Path to the input requirements.txt file
        output_file (str): Path to the output cleaned requirements.txt file
    """
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    # Extract package names and their versions
    packages = {}
    current_category = "# General"
    categories = {current_category: []}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Keep track of categories (lines starting with #)
        if line.startswith('#'):
            current_category = line
            if current_category not in categories:
                categories[current_category] = []
            continue
        
        # Extract package name and version using regex
        match = re.match(r'^([a-zA-Z0-9_\-]+)([<>=!~].+)?$', line)
        if match:
            package_name = match.group(1).lower()
            version_spec = match.group(2) or ''
            packages[package_name] = version_spec
            categories[current_category].append(package_name)
    
    # Write the cleaned file
    with open(output_file, 'w') as f:
        for category, package_list in categories.items():
            f.write(f"{category}\n")
            for package in package_list:
                if package in packages:
                    version = packages[package]
                    f.write(f"{package}{version}\n")
            f.write("\n")

if __name__ == "__main__":
    clean_requirements_file('requirements.txt', 'requirements_cleaned.txt')
    print("Requirements file cleaned successfully. New file: requirements_cleaned.txt") 