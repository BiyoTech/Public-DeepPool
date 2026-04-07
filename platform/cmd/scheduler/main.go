// scheduler 服务入口：token 流量调度。
package main

import (
	"log"
	"os"
	"strings"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/config"
	"deeppool/platform/internal/scheduler"
)

func main() {
	cfgPath := os.Getenv("DEEPPOOL_CONFIG")
	if cfgPath == "" {
		cfgPath = "config/scheduler.yaml"
	}
	log.Printf("[INFO] loading config from %s", cfgPath)

	cfg, err := config.Load(cfgPath)
	if err != nil {
		log.Fatalf("[ERROR] load config: %v", err)
	}
	logLevel := strings.ToLower(cfg.Log.Level)
	common.InitLogger(logLevel)

	// TODO: scheduler 后续需要 DB 时在此初始化

	srv := scheduler.NewServer(cfg.Server.Addr, logLevel, cfg.Server.TLS)
	if err = srv.Start(); err != nil {
		log.Fatalf("[ERROR] server stopped: %v", err)
	}
}
