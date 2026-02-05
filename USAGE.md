# GitMax Usage Guide

## Quick Start

```bash
# Process a directory with all subdirectories
python gitmax.py -d "F:\study"

# With custom workers (default: 15)
python gitmax.py -d "F:\study" -w 30

# Dry run (see what would happen)
python gitmax.py -d "F:\study" --dry-run
```

## Process F:\study Completely

```bash
# Option 1: Use the batch file
run_all_study.bat

# Option 2: Command line
python gitmax.py -f study_paths.txt -w 15
```

## Important Notes

1. **Zero Exclusions**: ALL files are synced, including files >100MB (via Git LFS)
2. **Rate Limiting**: Using 15 workers by default to avoid GitHub API limits
3. **Retries**: Each push retries 5 times with exponential backoff
4. **Large Files**: Automatically handled with Git LFS

## Estimated Times for F:\study (15,854 dirs)

| Workers | Estimated Time |
|---------|----------------|
| 10      | ~4-5 hours     |
| 15      | ~3-4 hours     |
| 20      | ~2-3 hours     |
| 30      | ~2 hours       |

## Troubleshooting

### "Repository not found"
- The repo might not have been created yet
- Wait and retry, or manually create the repo on GitHub

### "Rate limit exceeded"
- Reduce workers: `-w 10`
- Wait a few minutes and try again

### "Large file" errors
- Make sure Git LFS is installed: `git lfs install`
- The script should handle this automatically

## Files

- `gitmax.py` - Main tool
- `study_paths.txt` - Pre-extracted 15,854 paths from F:\study
- `run.bat` - Quick launcher
- `run_study.bat` - Process F:\study recursively
- `run_all_study.bat` - Process all pre-extracted paths
