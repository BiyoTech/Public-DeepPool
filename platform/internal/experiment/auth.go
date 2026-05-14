// Lightweight session-based authentication for experiment server.
// Reads the shared user_sessions table (same MySQL database as Manager)
// to validate Bearer tokens without depending on the manager process.
package experiment

import (
	"database/sql"
	"errors"
	"log"
	"strings"

	"deeppool/platform/internal/experiment/types"
)

// ErrInvalidToken is returned when a session token is invalid or expired.
var ErrInvalidToken = errors.New("invalid or expired token")

type authService struct {
	db *sql.DB
}

// NewAuthService creates an AuthService backed by the shared MySQL database.
func NewAuthService(db *sql.DB) types.AuthService {
	return &authService{db: db}
}

func (a *authService) AuthUserID(authHeader string) (uint64, error) {
	auth := strings.TrimSpace(authHeader)
	if !strings.HasPrefix(auth, "Bearer ") {
		return 0, ErrInvalidToken
	}
	token := strings.TrimSpace(strings.TrimPrefix(auth, "Bearer "))
	if token == "" {
		return 0, ErrInvalidToken
	}

	var uid uint64
	err := a.db.QueryRow(`
		SELECT user_id FROM user_sessions
		WHERE token = ? AND (expires_at IS NULL OR expires_at > UTC_TIMESTAMP())
		LIMIT 1
	`, token).Scan(&uid)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, ErrInvalidToken
		}
		log.Printf("[ERROR] experiment auth: query token err=%v", err)
		return 0, err
	}
	return uid, nil
}
