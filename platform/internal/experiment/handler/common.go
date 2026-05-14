// Shared utilities for experiment HTTP handlers.
package handler

import (
	"net/http"
	"strconv"
)

// intQuery extracts an integer query parameter, returning defaultVal if absent or invalid.
func intQuery(r *http.Request, key string, defaultVal int) int {
	v := r.URL.Query().Get(key)
	if v == "" {
		return defaultVal
	}
	n, err := strconv.Atoi(v)
	if err != nil || n < 0 {
		return defaultVal
	}
	return n
}
