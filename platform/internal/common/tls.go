// TLS 工具函数：为 HTTP 和 gRPC 提供统一的证书加载与 TLS 配置能力。
//
// 设计思路：
//   - 所有组件共用同一套 TLS 加载逻辑，避免重复实现
//   - TLS 未启用时返回 nil，调用方通过 nil 判断走明文模式
//   - gRPC Server 和 Client 分别提供独立函数，职责清晰
package common

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"

	"deeppool/platform/internal/config"
)

// LoadTLSConfig 从配置加载 TLS 证书，返回 *tls.Config。
// TLS 未启用时返回 (nil, nil)，调用方据此判断是否启用 HTTPS。
func LoadTLSConfig(cfg config.TLSConfig) (*tls.Config, error) {
	if !cfg.Enabled {
		return nil, nil
	}

	cert, err := tls.LoadX509KeyPair(cfg.CertFile, cfg.KeyFile)
	if err != nil {
		return nil, fmt.Errorf("load TLS keypair: %w", err)
	}

	tlsCfg := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS12,
	}

	log.Printf("[INFO] TLS config loaded cert=%s key=%s", cfg.CertFile, cfg.KeyFile)
	return tlsCfg, nil
}

// NewGRPCServerOption 返回 gRPC Server 的 TLS ServerOption。
// TLS 未启用时返回 nil，调用方应跳过该 option。
func NewGRPCServerOption(cfg config.TLSConfig) (grpc.ServerOption, error) {
	if !cfg.Enabled {
		return nil, nil
	}

	cert, err := tls.LoadX509KeyPair(cfg.CertFile, cfg.KeyFile)
	if err != nil {
		return nil, fmt.Errorf("load gRPC server TLS keypair: %w", err)
	}

	tlsCfg := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS12,
	}

	creds := credentials.NewTLS(tlsCfg)
	log.Printf("[INFO] gRPC server TLS credentials loaded cert=%s", cfg.CertFile)
	return grpc.Creds(creds), nil
}

// NewGRPCClientCredentials 返回 gRPC Client 的 TransportCredentials。
// TLS 未启用时返回 insecure credentials；启用时根据 SkipVerify 决定是否验证服务端证书。
func NewGRPCClientCredentials(cfg config.TLSConfig) (credentials.TransportCredentials, error) {
	if !cfg.Enabled {
		return insecure.NewCredentials(), nil
	}

	tlsCfg := &tls.Config{
		MinVersion: tls.VersionTLS12,
	}

	// 自签名证书场景：跳过服务端证书验证
	if cfg.SkipVerify {
		tlsCfg.InsecureSkipVerify = true
		log.Printf("[WARNING] gRPC client TLS: skip_verify=true (insecure, use only for self-signed certs)")
	} else {
		// 使用系统根证书池验证服务端
		rootCAs, err := x509.SystemCertPool()
		if err != nil {
			return nil, fmt.Errorf("load system cert pool: %w", err)
		}
		tlsCfg.RootCAs = rootCAs
	}

	creds := credentials.NewTLS(tlsCfg)
	log.Printf("[INFO] gRPC client TLS credentials loaded skip_verify=%v", cfg.SkipVerify)
	return creds, nil
}
