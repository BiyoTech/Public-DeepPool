package common

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
)

// Response 统一 API 响应结构。
type Response struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data,omitempty"`
}

// WriteJSON 将响应序列化为 JSON 写入 w。
func WriteJSON(w http.ResponseWriter, status int, payload Response) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

// WriteError 返回标准错误 JSON 响应。
func WriteError(w http.ResponseWriter, status int, message string) {
	WriteJSON(w, status, Response{Code: status, Message: message})
}

// HandleBizError 将业务错误统一映射为 HTTP 状态码返回。
func HandleBizError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, ErrDuplicate):
		WriteError(w, http.StatusConflict, "resource already exists")
	case errors.Is(err, ErrNotFound):
		WriteError(w, http.StatusNotFound, "resource not found")
	case errors.Is(err, ErrInvalidRequest):
		message := err.Error()
		if message == "" {
			message = "invalid request"
		}
		WriteError(w, http.StatusBadRequest, message)
	default:
		log.Printf("[ERROR] unhandled biz error: %v", err)
		WriteError(w, http.StatusInternalServerError, "internal server error")
	}
}

// DecodeJSON 从请求体解析 JSON，禁止未知字段。
func DecodeJSON(r *http.Request, dst interface{}) error {
	defer r.Body.Close()
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(dst); err != nil {
		log.Printf("[WARNING] decode json failed path=%s err=%v", r.URL.Path, err)
		return errors.New("invalid request body")
	}
	return nil
}
