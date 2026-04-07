package common

import (
	"log"
	"net/http"
	"time"
)

// statusRecorder 记录响应状态码以供日志中间件使用。
// 同时代理 http.Flusher 以支持 SSE 流式推送。
type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

// Flush 代理底层 ResponseWriter 的 Flush 能力（SSE 流式推送必需）。
func (r *statusRecorder) Flush() {
	if f, ok := r.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

// WithRequestLog 请求日志中间件，按状态码分级输出日志。
func WithRequestLog(next http.Handler, debug bool) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		recorder := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(recorder, r)
		cost := time.Since(start)

		switch {
		case recorder.status >= 500:
			log.Printf("[ERROR] %s %s status=%d cost=%s remote=%s", r.Method, r.URL.RequestURI(), recorder.status, cost, r.RemoteAddr)
		case recorder.status >= 400:
			log.Printf("[WARNING] %s %s status=%d cost=%s remote=%s", r.Method, r.URL.RequestURI(), recorder.status, cost, r.RemoteAddr)
		case debug:
			log.Printf("[DEBUG] %s %s status=%d cost=%s remote=%s", r.Method, r.URL.RequestURI(), recorder.status, cost, r.RemoteAddr)
		default:
			log.Printf("[INFO] %s %s status=%d cost=%s", r.Method, r.URL.Path, recorder.status, cost)
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
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
		w.Header().Set("Access-Control-Max-Age", "600")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}
