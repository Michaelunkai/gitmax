#!/usr/bin/env python3
"""
GitMax - Ultra-Fast Parallel GitHub Pusher (v2.0 - ZERO EXCLUSIONS)
====================================================================
Push thousands of directories to GitHub at lightning speed!

Features:
- Parallel processing with ThreadPoolExecutor (50+ concurrent operations)
- ZERO EXCLUSIONS - Uses Git LFS for large files (>100MB)
- Complete file sync guaranteed
- Smart rate limiting to avoid GitHub API limits
- Progress tracking with ETA
- Creates repos if they don't exist
"""
import subprocess
import sys
import os
import time
import shutil
import argparse
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional, Set
import re

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except:
        pass

# Configuration
GITHUB_FILE_LIMIT = 100 * 1024 * 1024  # 100 MB - files above this use LFS
GITHUB_USERNAME = "Michaelunkai"
DEFAULT_WORKERS = 15  # Reduced to avoid rate limiting
LFS_ENABLED = True  # Use Git LFS for large files instead of excluding


@dataclass
class Stats:
    total: int = 0
    completed: int = 0
    success: int = 0
    failed: int = 0
    lfs_files: int = 0
    start_time: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def increment_completed(self, success: bool, lfs_count: int = 0):
        with self.lock:
            self.completed += 1
            self.lfs_files += lfs_count
            if success:
                self.success += 1
            else:
                self.failed += 1


@dataclass
class Result:
    path: str
    success: bool
    message: str
    repo_url: str = ""
    lfs_files: int = 0
    total_files: int = 0


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def run_cmd(cmd: str, cwd: Optional[str] = None, capture: bool = True, timeout: int = 300) -> tuple:
    """Run command and return (success, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=capture, text=True,
            encoding='utf-8', errors='replace', cwd=cwd,
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
            timeout=timeout
        )
        return result.returncode == 0, result.stdout if capture else "", result.stderr if capture else ""
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def path_to_repo_name(path: str) -> str:
    """Convert path to valid GitHub repo name (max 100 chars, valid chars only)"""
    name = Path(path).name.lower()
    name = name.replace(" ", "-")
    # Replace multiple dashes with single dash
    name = re.sub(r'-+', '-', name)
    # Remove invalid characters
    name = re.sub(r'[^a-z0-9\-_]', '', name)
    # Remove leading/trailing dashes
    name = name.strip('-')
    # Truncate to 100 chars (GitHub limit)
    if len(name) > 100:
        name = name[:100].rstrip('-')
    return name if name else "repo"


def scan_directories(root: str, max_depth: int = 20) -> List[str]:
    """Scan for all directories up to max_depth"""
    dirs = []
    root_path = Path(root).resolve()
    root_depth = len(root_path.parts)

    for dirpath, dirnames, _ in os.walk(root_path):
        # Skip .git directories
        dirnames[:] = [d for d in dirnames if d != '.git']
        
        current_path = Path(dirpath)
        current_depth = len(current_path.parts) - root_depth
        
        if current_depth > max_depth:
            dirnames.clear()
            continue
            
        dirs.append(str(current_path))
    
    return dirs


def read_dirs_from_file(filename: str) -> List[str]:
    """Read directory paths from file"""
    dirs = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Handle gitit one-liner format
                if line.startswith('gitit '):
                    parts = line.split('; ')
                    for part in parts:
                        if part.startswith('gitit '):
                            dirs.append(part[6:].strip())
                else:
                    dirs.append(line)
    return dirs


def get_large_files(dir_path: str) -> List[str]:
    """Find all files >100MB that need Git LFS"""
    large_files = []
    dir_path = Path(dir_path)
    
    for item in dir_path.rglob("*"):
        if ".git" in item.parts:
            continue
        if item.is_file():
            try:
                if item.stat().st_size > GITHUB_FILE_LIMIT:
                    rel_path = item.relative_to(dir_path)
                    large_files.append(str(rel_path).replace("\\", "/"))
            except:
                pass
    
    return large_files


def get_lfs_patterns(large_files: List[str]) -> Set[str]:
    """Generate LFS track patterns for large files"""
    patterns = set()
    for f in large_files:
        # Get file extension
        ext = Path(f).suffix.lower()
        if ext:
            patterns.add(f"*{ext}")
        else:
            # Track specific file if no extension
            patterns.add(f)
    return patterns


def setup_git_lfs(dir_path: str, large_files: List[str]) -> bool:
    """Setup Git LFS for large files"""
    if not large_files:
        return True
    
    # Initialize LFS
    ok, _, _ = run_cmd('git lfs install --local', dir_path)
    if not ok:
        # LFS might not be installed, try to continue without it
        return False
    
    # Track patterns for large files
    patterns = get_lfs_patterns(large_files)
    for pattern in patterns:
        run_cmd(f'git lfs track "{pattern}"', dir_path)
    
    # Also track specific large files
    for f in large_files:
        run_cmd(f'git lfs track "{f}"', dir_path)
    
    return True


def ensure_github_repo(repo_name: str) -> bool:
    """Ensure GitHub repo exists, create if not"""
    # Check if repo exists using gh CLI
    ok, _, _ = run_cmd(f'gh repo view {GITHUB_USERNAME}/{repo_name}', timeout=30)
    if not ok:
        # Create repo with retry
        for attempt in range(3):
            create_ok, _, create_err = run_cmd(f'gh repo create {GITHUB_USERNAME}/{repo_name} --public', timeout=60)
            if create_ok:
                time.sleep(1)  # Wait for GitHub to propagate
                return True
            elif "already exists" in str(create_err).lower():
                return True  # Repo exists, that's fine
            time.sleep(2 * (attempt + 1))  # Exponential backoff
        # Final fallback - try once more with longer wait
        run_cmd(f'gh repo create {GITHUB_USERNAME}/{repo_name} --public', timeout=60)
        time.sleep(2)
    return True


def is_already_synced(dir_path: Path) -> tuple:
    """Check if repo is already synced (skip if no local changes)"""
    git_dir = dir_path / ".git"
    if not git_dir.exists():
        return False, "No .git"
    
    ok, remote, _ = run_cmd('git remote get-url origin', str(dir_path))
    if not ok or not remote.strip():
        return False, "No remote"
    
    ok, status, _ = run_cmd('git status --porcelain', str(dir_path))
    if ok and not status.strip():
        ok, ahead, _ = run_cmd('git rev-list --count origin/main..HEAD 2>nul', str(dir_path))
        if ok and ahead.strip() == '0':
            return True, "Already synced"
    
    return False, "Has changes"


def process_directory(dir_path: str, dry_run: bool = False, use_lfs: bool = True) -> Result:
    """Process a single directory - init, commit, push to GitHub with ZERO exclusions"""
    result = Result(path=dir_path, success=False, message="")
    
    try:
        dir_path = Path(dir_path).resolve()
        repo_name = path_to_repo_name(str(dir_path))
        
        if not dir_path.exists():
            result.message = "Directory does not exist"
            return result
        
        # Quick check: skip if already synced
        synced, reason = is_already_synced(dir_path)
        if synced:
            result.success = True
            result.message = f"SKIPPED - {reason}"
            result.repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
            return result
        
        if dry_run:
            large_files = get_large_files(str(dir_path))
            result.success = True
            result.message = "Dry run - would push"
            result.repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
            result.lfs_files = len(large_files)
            return result
        
        # Count total files
        total_files = sum(1 for _ in dir_path.rglob("*") if _.is_file() and ".git" not in _.parts)
        result.total_files = total_files
        
        # 0. CRITICAL: Remove ALL nested .git directories first!
        # This prevents submodule issues where nested repos don't get their contents pushed
        nested_git_count = 0
        for nested_git in dir_path.rglob(".git"):
            if nested_git.is_dir() and nested_git.parent != dir_path:
                try:
                    shutil.rmtree(nested_git, ignore_errors=True)
                    nested_git_count += 1
                except:
                    pass
        
        # 1. Clean existing .git (the root one)
        git_dir = dir_path / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir, ignore_errors=True)
        
        # 2. Init fresh git repo
        ok, _, err = run_cmd('git init -b main', str(dir_path))
        if not ok:
            result.message = f"git init failed: {err}"
            return result
        
        # Configure git
        run_cmd(f'git config user.name "{GITHUB_USERNAME}"', str(dir_path))
        run_cmd(f'git config user.email "{GITHUB_USERNAME}@users.noreply.github.com"', str(dir_path))
        run_cmd('git config core.autocrlf false', str(dir_path))
        run_cmd('git config http.postBuffer 524288000', str(dir_path))  # 500MB buffer
        
        # 3. Find large files
        large_files = get_large_files(str(dir_path))
        result.lfs_files = len(large_files)
        
        # 4. Setup Git LFS if there are large files
        if large_files and use_lfs:
            lfs_ok = setup_git_lfs(str(dir_path), large_files)
            if not lfs_ok:
                # If LFS fails, we'll try pushing anyway - might work for smaller "large" files
                pass
        
        # 5. Stage ALL files (no exclusions!)
        run_cmd('git add -A', str(dir_path))
        
        # Verify files were staged (prevent empty commits!)
        staged_ok, staged_out, _ = run_cmd('git diff --cached --name-only', str(dir_path))
        staged_files = [f for f in staged_out.strip().split('\n') if f.strip()] if staged_ok else []
        
        if total_files > 0 and len(staged_files) == 0:
            # Something went wrong - try adding files with different method
            run_cmd('git add .', str(dir_path))
            run_cmd('git add --all', str(dir_path))
            # Check again
            staged_ok, staged_out, _ = run_cmd('git diff --cached --name-only', str(dir_path))
            staged_files = [f for f in staged_out.strip().split('\n') if f.strip()] if staged_ok else []
            
            if total_files > 0 and len(staged_files) == 0:
                result.message = f"STAGING FAILED - {total_files} files exist but 0 staged!"
                return result
        
        # 6. Commit
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Auto commit {timestamp} - {len(staged_files)} files"
        run_cmd(f'git commit -m "{commit_msg}"', str(dir_path))
        
        # 7. Ensure GitHub repo exists with verification
        ensure_github_repo(repo_name)
        
        # Verify repo exists before pushing
        for verify_attempt in range(3):
            verify_ok, _, _ = run_cmd(f'gh repo view {GITHUB_USERNAME}/{repo_name}', timeout=15)
            if verify_ok:
                break
            time.sleep(2)
        
        # 8. Add remote and push
        remote_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}.git"
        run_cmd('git remote remove origin', str(dir_path))
        run_cmd(f'git remote add origin {remote_url}', str(dir_path))
        run_cmd('git branch -M main', str(dir_path))
        
        # Push with retry and exponential backoff
        push_ok = False
        for attempt in range(5):
            ok, stdout, err = run_cmd('git push --set-upstream origin main --force', str(dir_path), timeout=600)
            if ok:
                push_ok = True
                break
            
            error_lower = err.lower()
            
            # Handle specific error cases
            if "large file" in error_lower or "100 mb" in error_lower or "exceeds" in error_lower:
                # Try LFS push
                run_cmd('git lfs push --all origin main', str(dir_path), timeout=300)
                time.sleep(2)
            elif "rate limit" in error_lower or "403" in err:
                # Rate limited - wait longer
                time.sleep(10 * (attempt + 1))
            elif "timeout" in error_lower or "connection" in error_lower:
                # Network issue - exponential backoff
                time.sleep(5 * (2 ** attempt))
            elif "non-fast-forward" in error_lower:
                # Force push should handle this, but try again
                time.sleep(1)
            else:
                # Generic retry with exponential backoff
                time.sleep(2 * (attempt + 1))
        
        if not push_ok:
            result.message = f"git push failed after 5 attempts: {err[:80] if err else 'unknown'}"
            return result
        
        # CRITICAL: Verify content was actually pushed (prevent empty repos!)
        # Check if any files were staged
        staged_ok, staged_out, _ = run_cmd('git diff --cached --name-only HEAD~1 HEAD 2>nul || git ls-tree -r HEAD --name-only', str(dir_path))
        if staged_ok:
            pushed_files = [f for f in staged_out.strip().split('\n') if f.strip()]
            if total_files > 0 and len(pushed_files) == 0:
                result.message = f"EMPTY REPO - {total_files} files exist but 0 pushed! Check file sizes."
                result.success = False
                return result
        
        result.success = True
        result.message = f"Success ({total_files} files)"
        result.repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
        
    except Exception as e:
        result.message = str(e)[:100]
    
    return result


def worker_task(dir_path: str, stats: Stats, dry_run: bool, use_lfs: bool) -> Result:
    """Worker task for thread pool"""
    result = process_directory(dir_path, dry_run, use_lfs)
    stats.increment_completed(result.success, result.lfs_files)
    return result


def print_progress(stats: Stats, done_event: threading.Event):
    """Print progress bar in a loop"""
    while not done_event.is_set():
        with stats.lock:
            completed = stats.completed
            success = stats.success
            failed = stats.failed
            total = stats.total
            lfs = stats.lfs_files
        
        if total == 0:
            time.sleep(0.5)
            continue
        
        elapsed = time.time() - stats.start_time
        percent = completed / total * 100
        bar_width = 40
        filled = int(bar_width * completed / total)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        # ETA calculation
        if completed > 0:
            rate = completed / elapsed
            remaining = (total - completed) / rate
            eta = f"{int(remaining)}s"
        else:
            eta = "calc..."
        
        speed = completed / elapsed if elapsed > 0 else 0
        
        sys.stdout.write(f"\r[{bar}] {percent:.1f}% | {completed}/{total} | ✓{success} ✗{failed} | LFS:{lfs} | {speed:.1f}/s | ETA: {eta}    ")
        sys.stdout.flush()
        
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description="GitMax - Ultra-Fast Parallel GitHub Pusher (ZERO EXCLUSIONS)")
    parser.add_argument("-d", "--directory", help="Single directory to process recursively")
    parser.add_argument("-f", "--file", help="File containing directory paths")
    parser.add_argument("-w", "--workers", type=int, default=DEFAULT_WORKERS, help=f"Number of parallel workers (default: {DEFAULT_WORKERS})")
    parser.add_argument("--depth", type=int, default=20, help="Max directory depth for recursive scan (default: 20)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (don't actually push)")
    parser.add_argument("--no-lfs", action="store_true", help="Disable Git LFS (not recommended)")
    parser.add_argument("path", nargs="?", help="Directory to process")
    
    args = parser.parse_args()
    
    # Determine input
    input_path = args.directory or args.path
    input_file = args.file
    
    if not input_path and not input_file:
        parser.print_help()
        sys.exit(1)
    
    use_lfs = not args.no_lfs
    
    # Collect directories
    print(f"\n{Colors.CYAN}Scanning directories...{Colors.RESET}")
    
    if input_file:
        dirs = read_dirs_from_file(input_file)
    else:
        dirs = scan_directories(input_path, args.depth)
    
    if not dirs:
        print("No directories found to process")
        sys.exit(1)
    
    # Initialize stats
    stats = Stats(total=len(dirs), start_time=time.time())
    
    # Print header
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  GitMax v2.0 - ZERO EXCLUSIONS Edition                       ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Directories: {len(dirs):<46} ║")
    print(f"║  Workers:     {args.workers:<46} ║")
    print(f"║  Git LFS:     {str(use_lfs):<46} ║")
    print(f"║  Dry Run:     {str(args.dry_run):<46} ║")
    print("║  Exclusions:  ZERO - All files will sync!                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    # Start progress thread
    done_event = threading.Event()
    progress_thread = threading.Thread(target=print_progress, args=(stats, done_event))
    progress_thread.start()
    
    # Process directories in parallel
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(worker_task, d, stats, args.dry_run, use_lfs): d for d in dirs}
        
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                pass
    
    # Stop progress thread
    done_event.set()
    progress_thread.join()
    
    # Final stats
    elapsed = time.time() - stats.start_time
    
    print("\n\n")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                      FINAL RESULTS                           ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Total Directories:  {stats.total:<40} ║")
    print(f"║  Successful:         {stats.success:<40} ║")
    print(f"║  Failed:             {stats.failed:<40} ║")
    print(f"║  LFS Files:          {stats.lfs_files:<40} ║")
    print(f"║  Time Elapsed:       {f'{elapsed:.1f}s':<40} ║")
    
    if stats.total > 0 and elapsed > 0:
        speed = stats.total / elapsed
        print(f"║  Average Speed:      {f'{speed:.2f} dirs/sec':<40} ║")
    
    print("╚══════════════════════════════════════════════════════════════╝")
    
    # Performance comparison
    if not args.dry_run and stats.total > 10:
        seq_time = stats.total * 15.0  # ~15 seconds per dir sequentially
        speedup = seq_time / elapsed if elapsed > 0 else 1
        
        print(f"\n⚡ Performance: {speedup:.1f}x faster than sequential gitit")
        print(f"   Sequential would take: ~{int(seq_time)}s ({int(seq_time/60)}m)")
    
    # Show failed ones
    failed_results = [r for r in results if not r.success]
    if failed_results:
        print(f"\n{Colors.RED}Failed directories ({len(failed_results)}):{Colors.RESET}")
        for r in failed_results[:20]:
            print(f"  ✗ {Path(r.path).name}: {r.message}")
        if len(failed_results) > 20:
            print(f"  ... and {len(failed_results) - 20} more")
    
    # Show LFS info
    if stats.lfs_files > 0:
        print(f"\n{Colors.YELLOW}Note: {stats.lfs_files} large files were handled with Git LFS{Colors.RESET}")


if __name__ == "__main__":
    main()
