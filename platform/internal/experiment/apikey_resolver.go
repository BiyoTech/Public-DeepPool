// APIKeyResolver: reads encrypted API key from the shared api_keys table and decrypts it.
// Used by JudgeService to obtain the actual key value for calling LLM models.
package experiment

import (
	"database/sql"
	"errors"
	"fmt"
	"log"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/experiment/types"
)

type apiKeyResolver struct {
	db            *sql.DB
	encryptionKey []byte // 32-byte AES-256 key
}

// NewAPIKeyResolver creates an APIKeyResolver backed by the shared platform database.
func NewAPIKeyResolver(db *sql.DB, encryptionKey []byte) types.APIKeyResolver {
	return &apiKeyResolver{db: db, encryptionKey: encryptionKey}
}

func (r *apiKeyResolver) Resolve(userID, keyID uint64) (string, error) {
	var encrypted sql.NullString
	err := r.db.QueryRow(
		`SELECT key_encrypted FROM api_keys WHERE id = ? AND user_id = ? AND status = 'active' LIMIT 1`,
		keyID, userID,
	).Scan(&encrypted)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			log.Printf("[ERROR] apikey_resolver: key not found or inactive uid=%d key_id=%d", userID, keyID)
			return "", fmt.Errorf("api key not found or inactive: id=%d", keyID)
		}
		log.Printf("[ERROR] apikey_resolver: query failed uid=%d key_id=%d err=%v", userID, keyID, err)
		return "", fmt.Errorf("query api key: %w", err)
	}
	if !encrypted.Valid || encrypted.String == "" {
		log.Printf("[ERROR] apikey_resolver: encrypted key empty uid=%d key_id=%d", userID, keyID)
		return "", fmt.Errorf("api key has no encrypted value: id=%d", keyID)
	}

	plainKey, err := common.DecryptAESGCM(encrypted.String, r.encryptionKey)
	if err != nil {
		log.Printf("[ERROR] apikey_resolver: decrypt failed uid=%d key_id=%d err=%v", userID, keyID, err)
		return "", fmt.Errorf("decrypt api key: %w", err)
	}
	return plainKey, nil
}
