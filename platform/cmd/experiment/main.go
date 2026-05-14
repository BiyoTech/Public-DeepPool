// Experiment gRPC server entry point: Judge (AI-based trace evaluation) and
// Evaluate (dataset-based model evaluation).
//
// This server exposes only gRPC. All web-facing HTTP requests are proxied
// by the Manager server via gRPC client calls.
package main

import (
	"log"
	"os"
	"strings"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/config"
	"deeppool/platform/internal/experiment"
	mysqlstore "deeppool/platform/internal/storage/mysql"
)

func main() {
	cfgPath := os.Getenv("DEEPPOOL_CONFIG")
	if cfgPath == "" {
		cfgPath = "config/experiment.yaml"
	}
	log.Printf("[INFO] loading config from %s", cfgPath)

	cfg, err := config.Load(cfgPath)
	if err != nil {
		log.Fatalf("[ERROR] load config: %v", err)
	}
	logLevel := strings.ToLower(cfg.Log.Level)
	common.InitLogger(logLevel)

	db, err := mysqlstore.NewDB(cfg.MySQL)
	if err != nil {
		log.Fatalf("[ERROR] init mysql: %v", err)
	}
	defer db.Close()

	// Initialize experiment-specific schema (idempotent DDL)
	if err = mysqlstore.EnsureSchema(db, experiment.SchemaDDL); err != nil {
		log.Fatalf("[ERROR] ensure schema failed: %v", err)
	}

	// Idempotent column migrations for existing tables
	if err = experiment.MigrateSchema(db, cfg.MySQL.Database); err != nil {
		log.Fatalf("[ERROR] migrate schema failed: %v", err)
	}

	grpcAddr := cfg.Server.GRPCAddr
	if grpcAddr == "" {
		grpcAddr = ":9093"
	}

	srv := experiment.NewServer(grpcAddr, db, cfg.Experiment, cfg.Server.TLS)
	if err = srv.Start(); err != nil {
		log.Fatalf("[ERROR] server stopped: %v", err)
	}
}
