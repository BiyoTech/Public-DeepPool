// Package config 提供统一的配置加载能力，各组件共用。
package config

import (
	"errors"
	"fmt"
	"os"
	"strings"

	"gopkg.in/yaml.v3"
)

// Config 顶层配置，server/mysql/log 为通用字段，各组件可扩展。
type Config struct {
	Server ServerConfig `yaml:"server"`
	MySQL  MySQLConfig  `yaml:"mysql"`
	Log    LogConfig    `yaml:"log"`
	Admin  AdminConfig  `yaml:"admin"`
}

// TLSConfig TLS/HTTPS 配置，嵌入 ServerConfig 中。
// Enabled=false 时保持原有明文 HTTP/gRPC 行为，无需任何证书文件。
type TLSConfig struct {
	Enabled    bool   `yaml:"enabled"`     // 是否启用 TLS，默认 false
	CertFile   string `yaml:"cert_file"`   // 证书文件路径（PEM 格式）
	KeyFile    string `yaml:"key_file"`    // 私钥文件路径（PEM 格式）
	SkipVerify bool   `yaml:"skip_verify"` // 客户端是否跳过证书验证（自签名场景）
}

type ServerConfig struct {
	Addr     string    `yaml:"addr"`
	GRPCAddr string    `yaml:"grpc_addr"`
	TLS      TLSConfig `yaml:"tls"`
}

// NodeManagerConfig NodeManager 节点配置信息
type NodeManagerConfig struct {
	Name string `yaml:"name"`
	Addr string `yaml:"addr"`
}

// Admin 管控平台相关配置
type AdminConfig struct {
	NodeManagers            []NodeManagerConfig `yaml:"node_managers"`
	SuperAdmin              SuperAdminConfig    `yaml:"super_admin"`
	InternalToken           string              `yaml:"internal_token"`             // Gateway ↔ NodeManager internal token
	DefaultHybridPolicyPath string              `yaml:"default_hybrid_policy_path"` // path to default hybrid routing policy YAML
	APIKeyEncryptionKey     string              `yaml:"api_key_encryption_key"`     // 32-byte hex key for AES-256-GCM encryption of API keys
}

// SuperAdminConfig 默认超级管理员账号配置
type SuperAdminConfig struct {
	Username string `yaml:"username"`
	Password string `yaml:"password"`
	Phone    string `yaml:"phone"`
	Email    string `yaml:"email"`
}

type MySQLConfig struct {
	Host            string `yaml:"host"`
	Port            int    `yaml:"port"`
	User            string `yaml:"user"`
	Password        string `yaml:"password"`
	Database        string `yaml:"database"`
	MaxOpenConns    int    `yaml:"max_open_conns"`
	MaxIdleConns    int    `yaml:"max_idle_conns"`
	ConnMaxLifetime int    `yaml:"conn_max_lifetime_minutes"`
}

type LogConfig struct {
	Level string `yaml:"level"`
}

// Load 从指定路径加载配置文件，校验必填项并填充默认值。
func Load(path string) (*Config, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	cfg := &Config{}
	if err = yaml.Unmarshal(content, cfg); err != nil {
		return nil, err
	}
	if err = cfg.validate(); err != nil {
		return nil, err
	}
	cfg.applyDefaults()
	return cfg, nil
}

func (c *Config) applyDefaults() {
	if c.Server.Addr == "" {
		c.Server.Addr = ":8080"
	}
	if c.Server.GRPCAddr == "" {
		c.Server.GRPCAddr = ":9090"
	}
	if c.MySQL.Port == 0 {
		c.MySQL.Port = 3306
	}
	if c.MySQL.MaxOpenConns <= 0 {
		c.MySQL.MaxOpenConns = 20
	}
	if c.MySQL.MaxIdleConns <= 0 {
		c.MySQL.MaxIdleConns = 10
	}
	if c.MySQL.ConnMaxLifetime <= 0 {
		c.MySQL.ConnMaxLifetime = 30
	}
	if c.Log.Level == "" {
		c.Log.Level = "debug"
	}
	// 环境变量可覆盖日志级别
	if envLevel := strings.TrimSpace(os.Getenv("DEEPPOOL_LOG_LEVEL")); envLevel != "" {
		c.Log.Level = strings.ToLower(envLevel)
	}
}

func (c *Config) validate() error {
	if c.MySQL.Host == "" {
		return errors.New("mysql.host is required")
	}
	if c.MySQL.User == "" {
		return errors.New("mysql.user is required")
	}
	if c.MySQL.Database == "" {
		return errors.New("mysql.database is required")
	}

	// TLS 启用时，证书和私钥必须指定且文件存在
	if c.Server.TLS.Enabled {
		if c.Server.TLS.CertFile == "" || c.Server.TLS.KeyFile == "" {
			return errors.New("server.tls: cert_file and key_file are required when tls is enabled")
		}
		if _, err := os.Stat(c.Server.TLS.CertFile); err != nil {
			return fmt.Errorf("server.tls.cert_file: %w", err)
		}
		if _, err := os.Stat(c.Server.TLS.KeyFile); err != nil {
			return fmt.Errorf("server.tls.key_file: %w", err)
		}
	}
	return nil
}
