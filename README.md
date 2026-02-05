# GitMax 🚀

**Ultra-Fast Parallel GitHub Pusher** - Push thousands of directories to GitHub at lightning speed!

## Features

- ⚡ **Parallel Processing** - 30+ concurrent operations
- 📊 **Real-time Progress** - Live progress bar with ETA
- 🔄 **Smart Rate Limiting** - Avoids GitHub API limits
- 📁 **Large File Handling** - Auto-excludes files >100MB
- 🆕 **Auto-creates Repos** - Creates GitHub repos if they don't exist
- 💪 **Force Push** - Always fresh git init, no history issues

## Performance

| Directories | Sequential (gitit) | GitMax (30 workers) | Speedup |
|-------------|-------------------|---------------------|---------|
| 29          | ~7 minutes        | 18 seconds          | 24x     |
| 100         | ~25 minutes       | ~1 minute           | 25x     |
| 15,000      | ~62 hours         | ~2.5 hours          | 25x+    |

## Usage

### Basic Usage
```bash
# Process a single directory tree
python gitmax.py -d "F:\study"

# Process with custom number of workers
python gitmax.py -d "F:\study" -w 50

# Dry run (don't actually push)
python gitmax.py -d "F:\study" --dry-run
```

### Using Batch Files
```bash
# Process any directory
run.bat F:\study

# Process F:\study specifically
run_study.bat
```

### From File
```bash
# Process directories listed in a file
python gitmax.py -f paths.txt

# File format (one path per line):
# F:\study\AI_ML
# F:\study\Docker
# etc...
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-d, --directory` | Directory to process recursively | - |
| `-f, --file` | File containing directory paths | - |
| `-w, --workers` | Number of parallel workers | 30 |
| `--depth` | Max directory depth | 20 |
| `-v, --verbose` | Verbose output | False |
| `--dry-run` | Don't actually push | False |

## Requirements

- Python 3.8+
- Git installed and in PATH
- GitHub CLI (`gh`) logged in: `gh auth login`

## How It Works

1. **Scan** - Collects all directories up to specified depth
2. **Queue** - Creates job queue for worker threads
3. **Process** - Each worker:
   - Removes existing `.git` folder
   - Initializes fresh git repo
   - Creates `.gitignore` for large files (>100MB)
   - Stages and commits all files
   - Creates GitHub repo if needed
   - Force pushes to GitHub
4. **Report** - Shows real-time progress and final statistics

## Configuration

Edit `gitmax.py` to change:
- `GITHUB_USERNAME` - Your GitHub username (default: "Michaelunkai")
- `DEFAULT_WORKERS` - Default number of parallel workers (default: 30)
- `GITHUB_FILE_LIMIT` - Max file size before exclusion (default: 100MB)

## Comparison with gitit

| Feature | gitit | GitMax |
|---------|-------|--------|
| Speed | Sequential | 30+ parallel |
| Progress | Per-directory | Real-time bar |
| ETA | No | Yes |
| Large files | Handled | Handled |
| Repo creation | Yes | Yes |

## License

MIT
