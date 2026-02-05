#!/usr/bin/env python3
"""
Convert gitit one-liner to directory list
"""
import sys
import re

def convert_oneliner(input_file: str, output_file: str = None):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract paths from "gitit <path>" patterns
    # Handle both ; and ;  separators
    paths = re.findall(r'gitit\s+([^;]+)', content)
    paths = [p.strip() for p in paths if p.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_paths = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique_paths.append(p)
    
    print(f"Found {len(unique_paths)} unique directories")
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(unique_paths))
        print(f"Written to {output_file}")
    else:
        for p in unique_paths:
            print(p)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_oneliner.py <input_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    convert_oneliner(input_file, output_file)
