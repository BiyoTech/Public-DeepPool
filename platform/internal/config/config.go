// Package config 提供统一的配置加载能力，各组件共用。
package config

import (
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// Config 顶层配置，server/mysql/log 为通用字段，各组件可扩展。
type Config struct {
	Server         ServerConfig         `yaml:"server"`
	MySQL          MySQLConfig          `yaml:"mysql"`
	Log            LogConfig            `yaml:"log"`
	Admin          AdminConfig          `yaml:"admin"`
	StreamTimeouts StreamTimeoutsConfig `yaml:"stream_timeouts"`
	Experiment     ExperimentConfig     `yaml:"experiment"`
}

// ExperimentConfig holds experiment server specific settings.
type ExperimentConfig struct {
	ManagerGatewayURL   string `yaml:"manager_gateway_url"`    // Manager gateway URL for LLM calls
	APIKeyEncryptionKey string `yaml:"api_key_encryption_key"` // 32-byte hex key for decrypting trace DSN
	WorkerPoolSize      int    `yaml:"worker_pool_size"`       // concurrent judge/eval workers, default 5
	TemplateDir         string `yaml:"template_dir"`           // path to scorer template YAML files directory
}

// StreamTimeoutsConfig holds global stream-level liveness timeouts shared by
// both the Gateway (Provider SSE + gRPC stream to NodeManager) and the
// NodeManager (DeepNode chunk channel). Keeping these as a top-level config
// block — rather than hiding them inside hybrid routing policy — lets
// non-hybrid models (pure Provider / pure DeepNode) benefit from the same
// safety net, and makes the knob easy to tune per deployment.
//
// Semantics:
//   - FirstTokenTimeoutSeconds: max wait from dispatch until the FIRST chunk
//     arrives (TTFT guard). 0 means "use built-in default" (10s).
//   - InterChunkIdleTimeoutSeconds: max idle gap allowed between two
//     consecutive chunks (liveness guard). 0 means "use built-in default"
//     (20s). Long-running reasoning/generation is allowed as long as chunks
//     keep flowing within this window.
type StreamTimeoutsConfig struct {
	FirstTokenTimeoutSeconds     int `yaml:"first_token_timeout_seconds"`
	InterChunkIdleTimeoutSeconds int `yaml:"inter_chunk_idle_timeout_seconds"`
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

// ExperimentServerConfig holds connection info for a remote Experiment gRPC server.
type ExperimentServerConfig struct {
	Name string `yaml:"name"` // logical name for the experiment server instance
	Addr string `yaml:"addr"` // gRPC dial address, e.g. "127.0.0.1:9093"
}

// AdminConfig holds management platform configuration.
type AdminConfig struct {
	NodeManagers            []NodeManagerConfig      `yaml:"node_managers"`
	ExperimentServers       []ExperimentServerConfig `yaml:"experiment_servers"`
	SuperAdmin              SuperAdminConfig    `yaml:"super_admin"`
	InternalToken           string              `yaml:"internal_token"`             // Gateway ↔ NodeManager internal token
	DefaultHybridPolicyPath string              `yaml:"default_hybrid_policy_path"` // path to default hybrid routing policy YAML
	APIKeyEncryptionKey     string              `yaml:"api_key_encryption_key"`     // 32-byte hex key for AES-256-GCM encryption of API keys
	SMTP                    SMTPConfig          `yaml:"smtp"`                       // SMTP mail server for verification codes
	Payment                 PaymentConfig       `yaml:"payment"`                    // third-party payment gateway configuration
	DefaultTraceDB          DefaultTraceDBConfig `yaml:"default_trace_db"`          // built-in trace log storage engine
}

// DefaultTraceDBConfig defines the platform-managed database for built-in trace log storage.
// When a user selects "builtin" storage_type, these DB credentials are used automatically.
type DefaultTraceDBConfig struct {
	DBType   string `yaml:"db_type"`   // mysql / postgresql / clickhouse
	DBHost   string `yaml:"db_host"`
	DBPort   int    `yaml:"db_port"`
	DBUser   string `yaml:"db_user"`
	DBPass   string `yaml:"db_pass"`
	DBName   string `yaml:"db_name"`
}

// PaymentConfig holds third-party payment gateway credentials.
type PaymentConfig struct {
	NotifyBaseURL   string          `yaml:"notify_base_url"`   // public base URL for async callbacks, e.g. "https://api.deeppool.tech"
	FrontendBaseURL string          `yaml:"frontend_base_url"` // frontend site URL for payment return redirects, e.g. "https://deeppool.tech"
	Wechat          WechatPayConfig `yaml:"wechat"`
	Alipay          AlipayConfig    `yaml:"alipay"`
}

// WechatPayConfig holds WeChat Pay V3 API credentials.
type WechatPayConfig struct {
	MchID             string `yaml:"mch_id"`               // merchant ID
	MchSerialNo       string `yaml:"mch_serial_no"`        // merchant API certificate serial number
	MchAPIKeyV3       string `yaml:"mch_api_key_v3"`       // API v3 secret key (for callback decryption)
	MchPrivateKeyPath string `yaml:"mch_private_key_path"` // path to apiclient_key.pem
	WxPubKeyID        string `yaml:"wx_pub_key_id"`        // WeChat Pay public key ID (e.g. PUB_KEY_ID_xxxx)
	WxPubKeyPath      string `yaml:"wx_pub_key_path"`      // path to WeChat Pay public key PEM file
	AppID             string `yaml:"app_id"`               // WeChat app ID (optional, for JSAPI)
}

// AlipayConfig holds Alipay API credentials.
type AlipayConfig struct {
	AppID             string `yaml:"app_id"`               // Alipay application ID
	PrivateKeyPath    string `yaml:"private_key_path"`     // path to app private key PEM file
	AlipayPublicKeyPath string `yaml:"alipay_public_key_path"` // path to Alipay public key PEM file
	IsSandbox         bool   `yaml:"is_sandbox"`           // true to use sandbox environment
}

// SMTPConfig SMTP mail server configuration for sending verification codes.
type SMTPConfig struct {
	Host               string `yaml:"host"`                 // SMTP server host, e.g. "smtp.exmail.qq.com"
	Port               int    `yaml:"port"`                 // SMTP server port, e.g. 465
	User               string `yaml:"user"`                 // sender email address
	Password           string `yaml:"password"`             // SMTP password or app-specific token
	From               string `yaml:"from"`                 // display name, e.g. "DeepPool <noreply@deeppool.io>"
	UseTLS             bool   `yaml:"use_tls"`              // true for implicit TLS (port 465), false for STARTTLS (port 587)
	InsecureSkipVerify bool   `yaml:"insecure_skip_verify"` // skip TLS certificate verification (use only when server cert doesn't match hostname)
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

// Default stream-level timeouts, shared by Gateway and NodeManager. Kept in
// the config package so all consumers reach the same defaults without a
// cross-package dependency.
const (
	// DefaultFirstTokenTimeout bounds how long to wait for the FIRST streaming
	// chunk after dispatching a task. Guards against upstream stalls / cold
	// start hangs while tolerating reasonable model warm-up latency.
	DefaultFirstTokenTimeout = 10 * time.Second

	// DefaultInterChunkIdleTimeout bounds the gap between two consecutive
	// chunks in a streaming response. Long-running reasoning / generation is
	// allowed as long as chunks keep flowing within this window.
	DefaultInterChunkIdleTimeout = 20 * time.Second
)

// FirstTokenTimeout returns the configured TTFT budget or the built-in
// default when unset / non-positive.
func (s StreamTimeoutsConfig) FirstTokenTimeout() time.Duration {
	if s.FirstTokenTimeoutSeconds > 0 {
		return time.Duration(s.FirstTokenTimeoutSeconds) * time.Second
	}
	return DefaultFirstTokenTimeout
}

// InterChunkIdleTimeout returns the configured inter-chunk idle budget or
// the built-in default when unset / non-positive.
func (s StreamTimeoutsConfig) InterChunkIdleTimeout() time.Duration {
	if s.InterChunkIdleTimeoutSeconds > 0 {
		return time.Duration(s.InterChunkIdleTimeoutSeconds) * time.Second
	}
	return DefaultInterChunkIdleTimeout
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
