package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

const (
	GitHubFileLimitMB = 100
	GitHubFileLimit   = GitHubFileLimitMB * 1024 * 1024
	DefaultWorkers    = 20
	GitHubUsername    = "Michaelunkai"
)

// Stats for tracking progress
type Stats struct {
	Total      int64
	Completed  int64
	Success    int64
	Failed     int64
	Skipped    int64
	StartTime  time.Time
}

// DirJob represents a directory to process
type DirJob struct {
	Path     string
	RepoName string
}

// Result of processing a directory
type Result struct {
	Path    string
	Success bool
	Message string
	RepoURL string
}

var (
	stats       Stats
	ghToken     string
	verbose     bool
	dryRun      bool
	statsMutex  sync.Mutex
)

func main() {
	// Parse flags
	inputFile := flag.String("f", "", "File containing directory paths (one per line)")
	inputDir := flag.String("d", "", "Single directory to process recursively")
	workers := flag.Int("w", DefaultWorkers, "Number of parallel workers")
	flag.BoolVar(&verbose, "v", false, "Verbose output")
	flag.BoolVar(&dryRun, "dry-run", false, "Dry run (don't actually push)")
	depth := flag.Int("depth", 20, "Max directory depth for recursive scan")
	flag.Parse()

	// Also accept positional argument
	if *inputDir == "" && *inputFile == "" && len(flag.Args()) > 0 {
		*inputDir = flag.Args()[0]
	}

	if *inputDir == "" && *inputFile == "" {
		fmt.Println("GitMax - Ultra-fast parallel git push to GitHub")
		fmt.Println()
		fmt.Println("Usage:")
		fmt.Println("  gitmax -d <directory>     Process directory recursively")
		fmt.Println("  gitmax -f <file>          Process paths from file")
		fmt.Println("  gitmax <directory>        Process directory recursively")
		fmt.Println()
		fmt.Println("Flags:")
		fmt.Println("  -w <num>     Number of parallel workers (default: 20)")
		fmt.Println("  -depth <num> Max directory depth (default: 20)")
		fmt.Println("  -v           Verbose output")
		fmt.Println("  -dry-run     Don't actually push")
		os.Exit(1)
	}

	// Get GitHub token from gh CLI
	ghToken = getGitHubToken()
	if ghToken == "" {
		fmt.Println("⚠ Warning: No GitHub token found. Run 'gh auth login' first.")
		fmt.Println("  Continuing without token (repo creation may fail)...")
	}

	// Collect directories to process
	var dirs []string
	if *inputFile != "" {
		dirs = readDirsFromFile(*inputFile)
	} else {
		dirs = scanDirectories(*inputDir, *depth)
	}

	if len(dirs) == 0 {
		fmt.Println("No directories found to process")
		os.Exit(1)
	}

	// Initialize stats
	stats = Stats{
		Total:     int64(len(dirs)),
		StartTime: time.Now(),
	}

	fmt.Printf("\n")
	fmt.Printf("╔══════════════════════════════════════════════════════════════╗\n")
	fmt.Printf("║  GitMax - Ultra-Fast Parallel GitHub Pusher                  ║\n")
	fmt.Printf("╠══════════════════════════════════════════════════════════════╣\n")
	fmt.Printf("║  Directories: %-46d ║\n", len(dirs))
	fmt.Printf("║  Workers:     %-46d ║\n", *workers)
	fmt.Printf("║  Dry Run:     %-46v ║\n", dryRun)
	fmt.Printf("╚══════════════════════════════════════════════════════════════╝\n")
	fmt.Printf("\n")

	// Create job channel
	jobs := make(chan DirJob, len(dirs))
	results := make(chan Result, len(dirs))

	// Start workers
	var wg sync.WaitGroup
	for i := 0; i < *workers; i++ {
		wg.Add(1)
		go worker(i, jobs, results, &wg)
	}

	// Start progress reporter
	done := make(chan bool)
	go progressReporter(done)

	// Queue jobs
	for _, dir := range dirs {
		repoName := pathToRepoName(dir)
		jobs <- DirJob{Path: dir, RepoName: repoName}
	}
	close(jobs)

	// Collect results in background
	go func() {
		for range results {
			// Results processed by worker
		}
	}()

	// Wait for workers
	wg.Wait()
	close(results)
	done <- true

	// Print final stats
	printFinalStats()
}

func getGitHubToken() string {
	// Try gh CLI first
	cmd := exec.Command("gh", "auth", "token")
	output, err := cmd.Output()
	if err == nil {
		return strings.TrimSpace(string(output))
	}

	// Try environment variable
	if token := os.Getenv("GITHUB_TOKEN"); token != "" {
		return token
	}

	return ""
}

func readDirsFromFile(filename string) []string {
	file, err := os.Open(filename)
	if err != nil {
		fmt.Printf("Error opening file: %v\n", err)
		return nil
	}
	defer file.Close()

	var dirs []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" && !strings.HasPrefix(line, "#") {
			dirs = append(dirs, line)
		}
	}
	return dirs
}

func scanDirectories(root string, maxDepth int) []string {
	var dirs []string
	rootDepth := strings.Count(filepath.Clean(root), string(os.PathSeparator))

	filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}

		// Check depth
		currentDepth := strings.Count(filepath.Clean(path), string(os.PathSeparator)) - rootDepth
		if currentDepth > maxDepth {
			if info.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}

		if info.IsDir() {
			// Skip .git directories
			if info.Name() == ".git" {
				return filepath.SkipDir
			}
			dirs = append(dirs, path)
		}
		return nil
	})

	return dirs
}

func pathToRepoName(path string) string {
	// Get the folder name
	name := filepath.Base(path)
	
	// Clean up the name
	name = strings.ToLower(name)
	name = strings.ReplaceAll(name, " ", "-")
	
	// Remove invalid characters
	var result strings.Builder
	for _, c := range name {
		if (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '_' {
			result.WriteRune(c)
		}
	}
	
	name = result.String()
	if name == "" {
		name = "repo"
	}
	
	return name
}

func worker(id int, jobs <-chan DirJob, results chan<- Result, wg *sync.WaitGroup) {
	defer wg.Done()

	for job := range jobs {
		result := processDirectory(job)
		results <- result

		// Update stats
		atomic.AddInt64(&stats.Completed, 1)
		if result.Success {
			atomic.AddInt64(&stats.Success, 1)
		} else {
			atomic.AddInt64(&stats.Failed, 1)
		}
	}
}

func processDirectory(job DirJob) Result {
	result := Result{Path: job.Path}

	// Check if directory exists
	if _, err := os.Stat(job.Path); os.IsNotExist(err) {
		result.Message = "Directory does not exist"
		return result
	}

	if dryRun {
		result.Success = true
		result.Message = "Dry run - would push"
		result.RepoURL = fmt.Sprintf("https://github.com/%s/%s", GitHubUsername, job.RepoName)
		return result
	}

	// 1. Clean and init git
	gitDir := filepath.Join(job.Path, ".git")
	os.RemoveAll(gitDir)

	if err := runGit(job.Path, "init", "-b", "main"); err != nil {
		result.Message = fmt.Sprintf("git init failed: %v", err)
		return result
	}

	// Configure git
	runGit(job.Path, "config", "user.name", GitHubUsername)
	runGit(job.Path, "config", "user.email", GitHubUsername+"@users.noreply.github.com")
	runGit(job.Path, "config", "core.autocrlf", "false")

	// 2. Create .gitignore for large files
	createGitignore(job.Path)

	// 3. Stage all files
	if err := runGit(job.Path, "add", "-A"); err != nil {
		result.Message = fmt.Sprintf("git add failed: %v", err)
		return result
	}

	// 4. Commit
	timestamp := time.Now().Format("2006-01-02 15:04:05")
	runGit(job.Path, "commit", "-m", fmt.Sprintf("Auto commit %s", timestamp), "--allow-empty")

	// 5. Create GitHub repo if needed
	repoURL := fmt.Sprintf("https://github.com/%s/%s.git", GitHubUsername, job.RepoName)
	ensureGitHubRepo(job.RepoName)

	// 6. Add remote and push
	runGit(job.Path, "remote", "remove", "origin")
	runGit(job.Path, "remote", "add", "origin", repoURL)
	runGit(job.Path, "branch", "-M", "main")

	if err := runGit(job.Path, "push", "--set-upstream", "origin", "main", "--force"); err != nil {
		result.Message = fmt.Sprintf("git push failed: %v", err)
		return result
	}

	result.Success = true
	result.Message = "Success"
	result.RepoURL = strings.TrimSuffix(repoURL, ".git")
	return result
}

func runGit(dir string, args ...string) error {
	cmd := exec.Command("git", args...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GIT_TERMINAL_PROMPT=0")
	
	output, err := cmd.CombinedOutput()
	if err != nil && verbose {
		fmt.Printf("git %s in %s: %s\n", strings.Join(args, " "), dir, string(output))
	}
	return err
}

func createGitignore(dir string) {
	var largeFiles []string

	filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}

		// Skip .git
		if strings.Contains(path, ".git") {
			return nil
		}

		if !info.IsDir() && info.Size() > GitHubFileLimit {
			rel, _ := filepath.Rel(dir, path)
			// Use forward slashes for .gitignore
			rel = strings.ReplaceAll(rel, "\\", "/")
			largeFiles = append(largeFiles, rel)
		}
		return nil
	})

	if len(largeFiles) > 0 {
		gitignorePath := filepath.Join(dir, ".gitignore")
		content := ""
		
		// Read existing
		if data, err := ioutil.ReadFile(gitignorePath); err == nil {
			content = string(data)
		}

		// Append large files
		content += "\n# gitit: auto-excluded large files (>100MB)\n"
		for _, f := range largeFiles {
			content += f + "\n"
		}

		ioutil.WriteFile(gitignorePath, []byte(content), 0644)
	}
}

func ensureGitHubRepo(repoName string) {
	if ghToken == "" {
		// Try using gh CLI
		exec.Command("gh", "repo", "create", GitHubUsername+"/"+repoName, "--public").Run()
		return
	}

	// Check if repo exists
	url := fmt.Sprintf("https://api.github.com/repos/%s/%s", GitHubUsername, repoName)
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("Authorization", "token "+ghToken)
	
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == 404 {
		// Create repo
		createURL := "https://api.github.com/user/repos"
		body := fmt.Sprintf(`{"name":"%s","private":false}`, repoName)
		req, _ := http.NewRequest("POST", createURL, strings.NewReader(body))
		req.Header.Set("Authorization", "token "+ghToken)
		req.Header.Set("Content-Type", "application/json")
		
		resp, err := client.Do(req)
		if err == nil {
			resp.Body.Close()
		}
		time.Sleep(500 * time.Millisecond) // Rate limit buffer
	}
}

func progressReporter(done chan bool) {
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-done:
			return
		case <-ticker.C:
			printProgress()
		}
	}
}

func printProgress() {
	completed := atomic.LoadInt64(&stats.Completed)
	success := atomic.LoadInt64(&stats.Success)
	failed := atomic.LoadInt64(&stats.Failed)
	total := stats.Total
	
	elapsed := time.Since(stats.StartTime)
	
	if total == 0 {
		return
	}

	percent := float64(completed) / float64(total) * 100
	barWidth := 40
	filled := int(float64(barWidth) * float64(completed) / float64(total))
	bar := strings.Repeat("█", filled) + strings.Repeat("░", barWidth-filled)

	// Calculate ETA
	eta := "calculating..."
	if completed > 0 {
		rate := float64(completed) / elapsed.Seconds()
		remaining := float64(total - completed) / rate
		eta = fmt.Sprintf("%v", time.Duration(remaining)*time.Second)
	}

	// Speed
	speed := float64(completed) / elapsed.Seconds()

	fmt.Printf("\r[%s] %.1f%% | %d/%d | ✓%d ✗%d | %.1f/s | ETA: %s    ",
		bar, percent, completed, total, success, failed, speed, eta)
}

func printFinalStats() {
	elapsed := time.Since(stats.StartTime)
	
	fmt.Printf("\n\n")
	fmt.Printf("╔══════════════════════════════════════════════════════════════╗\n")
	fmt.Printf("║                      FINAL RESULTS                           ║\n")
	fmt.Printf("╠══════════════════════════════════════════════════════════════╣\n")
	fmt.Printf("║  Total Directories:  %-40d ║\n", stats.Total)
	fmt.Printf("║  Successful:         %-40d ║\n", stats.Success)
	fmt.Printf("║  Failed:             %-40d ║\n", stats.Failed)
	fmt.Printf("║  Time Elapsed:       %-40s ║\n", elapsed.Round(time.Second))
	
	if stats.Total > 0 && elapsed.Seconds() > 0 {
		speed := float64(stats.Total) / elapsed.Seconds()
		fmt.Printf("║  Average Speed:      %-40s ║\n", fmt.Sprintf("%.2f dirs/sec", speed))
	}
	
	fmt.Printf("╚══════════════════════════════════════════════════════════════╝\n")
	
	// Performance comparison
	if !dryRun && stats.Total > 100 {
		seqTime := float64(stats.Total) * 15.0 // ~15 seconds per dir sequentially
		actualTime := elapsed.Seconds()
		speedup := seqTime / actualTime
		
		fmt.Printf("\n⚡ Performance: %.1fx faster than sequential gitit\n", speedup)
		fmt.Printf("   Sequential would take: ~%s\n", time.Duration(seqTime)*time.Second)
	}
}
