#!/usr/bin/env python

import os
import sys
import re
import json
import shutil
import argparse
from pathlib import Path
from typing import List, Dict, Callable, Set
import asyncio
import aiofiles
import magic
import fnmatch
from glob import glob
from datetime import datetime
import subprocess

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

WHITESPACE_DEPENDENT_EXTENSIONS = ['.md', '.txt', '.rtf']
DEFAULT_IGNORES = [
    '.git', '.svn', '.hg', '.idea', '.vscode',
    'node_modules', 'venv', 'env', '__pycache__',
    '*.pyc', '*.pyo', '*.pyd', '*.db', '*.sqlite3',
    '*.log', '*.sql', '*.swp', '*.swo',
    '*.bak', '*.tmp', '*.temp',
    '*.o', '*.obj', '*.exe', '*.dll', '*.so', '*.dylib',
    '*.jar', '*.war', '*.ear', '*.sar', '*.class',
    '*.lock', '*.DS_Store', 'Thumbs.db'
]


def format_log(message: str, emoji: str = '') -> str:
    return f"{emoji} {message}"

async def read_ignore_file(input_dir: str, filename: str = '.aidigestignore') -> List[str]:
    ignore_file_path = Path(input_dir) / filename
    try:
        async with aiofiles.open(ignore_file_path, 'r', encoding='utf-8') as file:
            content = await file.read()
        print(format_log(f"Found {filename} file in {input_dir}.", '📄'))
        return [line.strip() for line in content.splitlines() if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print(format_log(f"No {filename} file found in {input_dir}.", '❓'))
        return []

def display_included_files(included_files: List[str]) -> None:
    print(format_log('Files included in the output:', '📋'))
    for index, file in enumerate(included_files, start=1):
        print(f"{index}. {file}")

def remove_whitespace(content: str) -> str:
    # Preserve some formatting while removing excess whitespace
    content = re.sub(r'[\t ]+', ' ', content)  # Replace tabs and multiple spaces with a single space
    content = re.sub(r'\n\s*\n', '\n\n', content)  # Replace multiple newlines with double newlines
    return content.strip()

def escape_triple_backticks(content: str) -> str:
    return content.replace('```', '\\`\\`\\`')

def estimate_token_count(content: str) -> int:
    # More sophisticated token count estimation
    # This is a simplified version and might need further refinement
    tokens = re.findall(r'\b\w+\b|[^\w\s]', content)
    return len(tokens)

async def is_text_file(file_path: str) -> bool:
    try:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        return file_type.startswith('text/') or file_type in ['application/json', 'application/xml']
    except Exception as e:
        print(format_log(f"Error determining file type for {file_path}: {str(e)}", '⚠️'))
        return False

def get_file_type(file_path: str) -> str:
    try:
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)
    except Exception as e:
        print(format_log(f"Error getting file type for {file_path}: {str(e)}", '⚠️'))
        return "unknown"

def should_treat_as_binary(file_path: str) -> bool:
    return not is_text_file(file_path)

class IgnoreFilter:
    def __init__(self, patterns: List[str]):
        self.patterns = [os.path.normpath(pattern) for pattern in patterns]

    def ignores(self, path: str) -> bool:
        relative_path = os.path.normpath(os.path.relpath(path))
        for pattern in self.patterns:
            pattern = os.path.normpath(pattern)
            if relative_path == pattern or relative_path.startswith(os.path.join(pattern, '')):
                return True
        return False

def collect_files(input_patterns: List[str], exclude_patterns: List[str]) -> Set[str]:
    all_files = set()
    exclude_filter = IgnoreFilter(exclude_patterns)

    for input_pattern in input_patterns:
        matched_paths = glob(input_pattern, recursive=True)
        for path in matched_paths:
            if os.path.isfile(path):
                if not exclude_filter.ignores(path):
                    all_files.add(os.path.abspath(path))
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    # Build full paths
                    root = os.path.abspath(root)
                    # Exclude directories
                    dirs[:] = [d for d in dirs if not exclude_filter.ignores(os.path.join(root, d))]
                    # Process files
                    for file in files:
                        file_path = os.path.join(root, file)
                        if not exclude_filter.ignores(file_path):
                            all_files.add(os.path.abspath(file_path))
    return all_files

def create_output_directory(base_dir: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(base_dir, "aidigest", timestamp)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def write_info_file(output_dir: str, command: str):
    info_file = os.path.join(output_dir, "info.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(info_file, "w") as f:
        f.write(f"Command: {command}\n")
        f.write(f"Timestamp: {timestamp}\n")

async def aggregate_files(input_patterns: List[str], exclude_patterns: List[str], base_output_dir: str, use_default_ignores: bool, remove_whitespace_flag: bool, show_output_files: bool, command: str) -> None:
    output_dir = create_output_directory(base_output_dir)
    output_file = os.path.join(output_dir, "aidigest")

    write_info_file(output_dir, command)

    user_ignore_patterns = await read_ignore_file(os.getcwd())  # Read from current directory
    default_ignore = IgnoreFilter(DEFAULT_IGNORES if use_default_ignores else [])
    custom_ignore = IgnoreFilter(user_ignore_patterns + exclude_patterns)

    if use_default_ignores:
        print(format_log('Using default ignore patterns.', '🚫'))
    else:
        print(format_log('Default ignore patterns disabled.', '✅'))

    if remove_whitespace_flag:
        print(format_log('Whitespace removal enabled (except for whitespace-dependent languages).', '🧹'))
    else:
        print(format_log('Whitespace removal disabled.', '📝'))

    all_files = collect_files(input_patterns, exclude_patterns)

    print(format_log(f"Found {len(all_files)} files. Applying filters...", '🔍'))

    output = ''
    included_count = 0
    default_ignored_count = 0
    custom_ignored_count = 0
    binary_and_svg_file_count = 0
    included_files = []

    for file in all_files:
        relative_path = os.path.relpath(file)
        if os.path.abspath(output_file) == file:
            continue
        if use_default_ignores and default_ignore.ignores(file):
            default_ignored_count += 1
            continue
        if custom_ignore.ignores(file):
            custom_ignored_count += 1
            continue

        if await is_text_file(file):
            try:
                async with aiofiles.open(file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    content = escape_triple_backticks(content)
                    if remove_whitespace_flag and not any(file.endswith(ext) for ext in WHITESPACE_DEPENDENT_EXTENSIONS):
                        content = remove_whitespace(content)
                    output += f"# {relative_path}\n\n```{Path(file).suffix[1:]}\n{content}\n```\n\n"
                    included_count += 1
                    included_files.append(relative_path)
            except Exception as e:
                print(format_log(f"Error reading file {file}: {str(e)}", '⚠️'))
        else:
            file_type = get_file_type(file)
            output += f"# {relative_path}\n\n"
            if file_type == 'image/svg+xml':
                output += f"This is a file of the type: SVG Image\n\n"
            else:
                output += f"This is a binary file of the type: {file_type}\n\n"
            binary_and_svg_file_count += 1
            included_count += 1
            included_files.append(relative_path)

    async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
        await f.write(output)

    file_size_in_bytes = os.path.getsize(output_file)

    if file_size_in_bytes != len(output.encode('utf-8')):
        raise ValueError('File size mismatch after writing')

    print(format_log(f"Files aggregated successfully into {output_file}", '✅'))
    print(format_log(f"Total files found: {len(all_files)}", '📚'))
    print(format_log(f"Files included in output: {included_count}", '📎'))
    if use_default_ignores:
        print(format_log(f"Files ignored by default patterns: {default_ignored_count}", '🚫'))
    if custom_ignored_count > 0:
        print(format_log(f"Files ignored by .aidigestignore and exclude patterns: {custom_ignored_count}", '🚫'))
    print(format_log(f"Binary and SVG files included: {binary_and_svg_file_count}", '📦'))

    if file_size_in_bytes > MAX_FILE_SIZE:
        print(format_log(f"Warning: Output file size ({file_size_in_bytes / 1024 / 1024:.2f} MB) exceeds 10 MB.", '⚠️'))
        print(format_log('Token count estimation skipped due to large file size.', '⚠️'))
        print(format_log('Consider adding more files to .aidigestignore to reduce the output size.', '💡'))
    else:
        token_count = estimate_token_count(output)
        print(format_log(f"Estimated token count: {token_count}", '🔢'))
        print(format_log('Note: Token count is an approximation using GPT-4 tokenizer. For ChatGPT, it should be accurate. For Claude, it may be ±20% approximately.', '⚠️'))

    if show_output_files:
        display_included_files(included_files)

    print(format_log(f"Done! Wrote code base to {output_file}", '✅'))
    print(format_log(f"Info file written to {os.path.join(output_dir, 'info.txt')}", '📄'))

    # Set LATEST_AIDIGEST environment variable
    os.environ['LATEST_AIDIGEST'] = output_file
    print(format_log(f"LATEST_AIDIGEST set to: {output_file}", '🔗'))

def list_recent_outputs(base_dir: str):
    aidigest_dir = os.path.join(base_dir, "aidigest")
    if not os.path.isdir(aidigest_dir):
        print(format_log(f"No aidigest folder found in {base_dir}", '❌'))
        return

    recent_folders = sorted([f for f in os.listdir(aidigest_dir) if os.path.isdir(os.path.join(aidigest_dir, f))], reverse=True)[:5]

    if not recent_folders:
        print(format_log(f"No aidigest outputs found in {aidigest_dir}", '❌'))
        return

    print(format_log("Recent aidigest outputs:", '📋'))
    for folder in recent_folders:
        info_file = os.path.join(aidigest_dir, folder, "info.txt")
        if os.path.isfile(info_file):
            print(f"Timestamp: {folder}")
            with open(info_file, 'r') as f:
                print(f.read())
            print("----------------------------------------")

    latest_folder = recent_folders[0]
    latest_aidigest = os.path.join(aidigest_dir, latest_folder, "aidigest")
    if os.path.isfile(latest_aidigest):
        os.environ['LATEST_AIDIGEST'] = os.path.realpath(latest_aidigest)
        print(format_log(f"LATEST_AIDIGEST set to: {os.environ['LATEST_AIDIGEST']}", '🔗'))
    else:
        print(format_log("No aidigest file found in the most recent folder", '⚠️'))

def open_latest_aidigest():
    if 'LATEST_AIDIGEST' in os.environ and os.path.isfile(os.environ['LATEST_AIDIGEST']):
        subprocess.run(['vim', os.environ['LATEST_AIDIGEST']])
    else:
        print(format_log("LATEST_AIDIGEST is not set or the file does not exist. Run aidigest or use -l option first.", '⚠️'))

def main():
    parser = argparse.ArgumentParser(description='Aggregate files into a single Markdown file')
    parser.add_argument('input', nargs='*', default=['.'], help='Input files or directories (glob patterns supported)')
    parser.add_argument('-o', '--output', type=str, default=os.getcwd(), help='Base output directory (default: current working directory)')
    parser.add_argument('--exclude', nargs='*', default=[], help='Exclude patterns (glob syntax supported)')
    parser.add_argument('--no-default-ignores', action='store_false', dest='default_ignores', help='Disable default ignore patterns')
    parser.add_argument('--whitespace-removal', action='store_true', help='Enable whitespace removal')
    parser.add_argument('--show-output-files', action='store_true', help='Display a list of files included in the output')
    parser.add_argument('-l', '--list', action='store_true', help='List recent aidigest outputs')
    parser.add_argument('-v', '--view', action='store_true', help='Open the latest aidigest file in Vim')
    
    args = parser.parse_args()
    
    if args.list:
        list_recent_outputs(args.output)
    elif args.view:
        open_latest_aidigest()
    else:
        command = ' '.join(sys.argv)
        asyncio.run(aggregate_files(args.input, args.exclude, args.output, args.default_ignores, args.whitespace_removal, args.show_output_files, command))

if __name__ == "__main__":
    main()
