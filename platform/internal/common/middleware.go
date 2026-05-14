package common

import (
	"bytes"
	"log"
	"net/http"
	"time"
)

// statusRecorder captures response status code and error response body for logging.
// Also proxies http.Flusher to support SSE streaming.
type statusRecorder struct {
	http.ResponseWriter
	status int
	buf    bytes.Buffer // captures response body when status >= 400
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

func (r *statusRecorder) Write(b []byte) (int, error) {
	// Capture error response body for detailed logging
	if r.status >= 400 {
		r.buf.Write(b)
	}
	return r.ResponseWriter.Write(b)
}

// Flush proxies the underlying ResponseWriter's Flush (required for SSE streaming).
func (r *statusRecorder) Flush() {
	if f, ok := r.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

// WithRequestLog is a request logging middleware that outputs detailed error info for 4xx/5xx responses.
func WithRequestLog(next http.Handler, debug bool) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		recorder := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(recorder, r)
		cost := time.Since(start)

		// Truncate error body for logging (max 512 bytes to avoid log flooding)
		errBody := recorder.buf.String()
		if len(errBody) > 512 {
			errBody = errBody[:512] + "...(truncated)"
		}

		switch {
		case recorder.status >= 500:
			log.Printf("[ERROR] %s %s status=%d cost=%s remote=%s body=%s",
				r.Method, r.URL.RequestURI(), recorder.status, cost, r.RemoteAddr, errBody)
		case recorder.status >= 400:
			log.Printf("[WARN] %s %s status=%d cost=%s remote=%s body=%s",
				r.Method, r.URL.RequestURI(), recorder.status, cost, r.RemoteAddr, errBody)
		case debug:
			log.Printf("[DEBUG] %s %s status=%d cost=%s remote=%s",
				r.Method, r.URL.RequestURI(), recorder.status, cost, r.RemoteAddr)
		default:
			log.Printf("[INFO] %s %s status=%d cost=%s",
				r.Method, r.URL.Path, recorder.status, cost)
		}
	})
}

// WithCORS 跨域中间件，允许所有 Origin。
func WithCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if origin := r.Header.Get("Origin"); origin != "" {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
		}
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
		w.Header().Set("Access-Control-Max-Age", "600")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}
