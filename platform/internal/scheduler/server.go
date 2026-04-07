// Package scheduler 提供 scheduler 组件的 HTTP 服务器。
// scheduler 负责 token 流量调度，将推理请求分发到合适的 NodeManager。
package scheduler

import (
	"crypto/tls"
	"encoding/json"
	"log"
	"net/http"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/config"
)

// Server scheduler HTTP 服务器。
type Server struct {
	addr   string
	server *http.Server
	tlsCfg *tls.Config // 非 nil 时启用 HTTPS
}

// NewServer 创建 scheduler 服务器。tlsCfg 非 nil 时启用 HTTPS。
func NewServer(addr string, logLevel string, tlsCfg config.TLSConfig) *Server {
	mux := http.NewServeMux()

	// 健康检查
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok", "service": "scheduler"})
	})

	// TODO: 注册 token 流量调度相关路由
	// mux.HandleFunc("/api/v1/inference/dispatch", ...)

	var wrapped http.Handler = common.WithRequestLog(common.WithCORS(mux), common.IsDebug())

	// 加载 TLS 配置
	tc, err := common.LoadTLSConfig(tlsCfg)
	if err != nil {
		log.Fatalf("[FATAL] scheduler: load TLS config: %v", err)
	}

	return &Server{
		addr:   addr,
		server: &http.Server{Addr: addr, Handler: wrapped},
		tlsCfg: tc,
	}
}

// Start 启动 HTTP(S) 服务，根据 TLS 配置决定协议。
func (s *Server) Start() error {
	if s.tlsCfg != nil {
		s.server.TLSConfig = s.tlsCfg
		log.Printf("[INFO] scheduler HTTPS listening on %s", s.addr)
		// cert/key 已通过 TLSConfig.Certificates 加载，传空字符串即可
		return s.server.ListenAndServeTLS("", "")
	}
	log.Printf("[INFO] scheduler HTTP listening on %s (TLS disabled)", s.addr)
	return s.server.ListenAndServe()
}

func (s *Server) Addr() string { return s.addr }
