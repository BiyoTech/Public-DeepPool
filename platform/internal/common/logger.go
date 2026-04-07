// Package common provides a level-aware logger that transparently wraps the standard log package.
//
// Existing code uses log.Printf("[LEVEL] ...") everywhere. Instead of rewriting 200+ call sites,
// we intercept the standard logger's output via a custom io.Writer that parses the [LEVEL] tag
// from each line and drops messages below the configured threshold.
//
// Supported levels (lowest to highest): debug, info, warning, error, fatal.
// Default level: debug (all messages printed).
package common

import (
	"io"
	"log"
	"os"
	"strings"
)

// LogLevel represents a numeric log severity.
type LogLevel int

const (
	LevelDebug   LogLevel = 0
	LevelInfo    LogLevel = 1
	LevelWarning LogLevel = 2
	LevelError   LogLevel = 3
	LevelFatal   LogLevel = 4
)

// levelNames maps configuration strings to numeric levels.
var levelNames = map[string]LogLevel{
	"debug":   LevelDebug,
	"info":    LevelInfo,
	"warning": LevelWarning,
	"warn":    LevelWarning,
	"error":   LevelError,
	"fatal":   LevelFatal,
}

// ParseLogLevel converts a string level name to LogLevel. Unknown values default to LevelDebug.
func ParseLogLevel(s string) LogLevel {
	if lv, ok := levelNames[strings.ToLower(strings.TrimSpace(s))]; ok {
		return lv
	}
	return LevelDebug
}

// String returns the human-readable name of a LogLevel.
func (l LogLevel) String() string {
	switch l {
	case LevelDebug:
		return "DEBUG"
	case LevelInfo:
		return "INFO"
	case LevelWarning:
		return "WARNING"
	case LevelError:
		return "ERROR"
	case LevelFatal:
		return "FATAL"
	default:
		return "UNKNOWN"
	}
}

// levelWriter is an io.Writer that filters log lines by their [LEVEL] tag.
// Lines without a recognized tag are always printed (safe default).
type levelWriter struct {
	minLevel LogLevel
	out      io.Writer
}

// Write implements io.Writer. It inspects the log line for a [LEVEL] tag
// and drops messages below the configured minimum level.
func (w *levelWriter) Write(p []byte) (n int, err error) {
	line := string(p)
	msgLevel := extractLevel(line)

	// Messages at or above the threshold pass through; unknown-level messages always pass.
	if msgLevel >= w.minLevel {
		return w.out.Write(p)
	}

	// Silently drop the message but report success so the caller doesn't see an error.
	return len(p), nil
}

// extractLevel parses the [LEVEL] tag from a log line.
// Returns LevelDebug (lowest) if no recognized tag is found, ensuring the line is printed.
func extractLevel(line string) LogLevel {
	// Fast path: look for the opening bracket after the standard log date/time prefix.
	idx := strings.Index(line, "[")
	if idx < 0 {
		return LevelDebug
	}
	end := strings.Index(line[idx:], "]")
	if end < 0 {
		return LevelDebug
	}
	tag := strings.ToLower(line[idx+1 : idx+end])

	if lv, ok := levelNames[tag]; ok {
		return lv
	}
	// Unrecognized tag — treat as lowest level so it always prints.
	return LevelDebug
}

// currentLevel holds the active log level after InitLogger is called.
var currentLevel = LevelDebug

// GetLogLevel returns the currently configured global log level.
func GetLogLevel() LogLevel {
	return currentLevel
}

// IsDebug returns true if the current log level is DEBUG.
func IsDebug() bool {
	return currentLevel <= LevelDebug
}

// InitLogger configures the global standard logger to filter by the given level.
// It should be called once at program startup, before any goroutines start logging.
//
// Example:
//
//	common.InitLogger("debug")  // prints everything
//	common.InitLogger("info")   // prints INFO, WARNING, ERROR, FATAL
//	common.InitLogger("error")  // prints ERROR, FATAL only
func InitLogger(level string) {
	currentLevel = ParseLogLevel(level)

	// Replace the standard logger's output with our filtering writer.
	w := &levelWriter{
		minLevel: currentLevel,
		out:      os.Stderr,
	}
	log.SetOutput(w)

	// Use a consistent format: date + time + microseconds (no file/line to keep output clean).
	log.SetFlags(log.Ldate | log.Ltime | log.Lmicroseconds)

	log.Printf("[INFO] logger initialized level=%s", currentLevel)
}
