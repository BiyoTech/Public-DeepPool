// Package common 定义全局公共错误码、响应结构和 HTTP 中间件。
package common

import "errors"

// 业务错误哨兵值，各组件统一使用。
var (
	ErrDuplicate      = errors.New("duplicate resource")
	ErrNotFound       = errors.New("resource not found")
	ErrInvalidToken   = errors.New("invalid token")
	ErrInvalidRequest = errors.New("invalid request")
)
