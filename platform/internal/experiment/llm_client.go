// LLM client for calling models via Manager Gateway's OpenAI-compatible endpoint.
// Used by Judge and Evaluate services to invoke LLM models for evaluation.
package experiment

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"deeppool/platform/internal/experiment/types"
)

type llmClient struct {
	gatewayURL string // base URL ending with /v1, e.g. "https://api.deeppool.tech/v1"
	httpClient *http.Client
}

// NewLLMClient creates an LLM client targeting the Manager Gateway.
func NewLLMClient(gatewayURL string) types.LLMClient {
	return &llmClient{
		gatewayURL: strings.TrimRight(gatewayURL, "/"),
		httpClient: &http.Client{
			Timeout: 120 * time.Second, // LLM calls can be slow
		},
	}
}

func (c *llmClient) ChatCompletion(ctx context.Context, apiKey string, req types.ChatCompletionRequest) (*types.ChatCompletionResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	url := c.gatewayURL + "/chat/completions"
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+apiKey)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("http call: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("gateway returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result types.ChatCompletionResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}
	return &result, nil
}
