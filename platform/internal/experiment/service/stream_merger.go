// stream_merger.go: Merge OpenAI SSE streaming chunks into a single non-stream chat.completion JSON.
// This reduces token waste when streaming trace log outputs are fed into judge evaluation prompts.
package service

import (
	"encoding/json"
	"log"
	"strings"
)

// --- Internal types for parsing SSE stream chunks ---

// streamChunk represents a single SSE chunk following the OpenAI chat.completion.chunk format.
type streamChunk struct {
	ID      string              `json:"id"`
	Object  string              `json:"object"`
	Created int64               `json:"created"`
	Model   string              `json:"model"`
	Choices []streamChunkChoice `json:"choices"`
}

// streamChunkChoice represents one choice element inside a streaming chunk.
type streamChunkChoice struct {
	Index        int              `json:"index"`
	Delta        streamChunkDelta `json:"delta"`
	FinishReason *string          `json:"finish_reason"`
}

// streamChunkDelta represents the delta object carrying incremental content.
type streamChunkDelta struct {
	Role             string          `json:"role,omitempty"`
	Content          *string         `json:"content"`
	ReasoningContent *string         `json:"reasoning_content"`
	ToolCalls        []toolCallDelta `json:"tool_calls,omitempty"`
}

// toolCallDelta represents a partial tool_call delivered incrementally across chunks.
type toolCallDelta struct {
	Index    int    `json:"index"`
	ID       string `json:"id,omitempty"`
	Type     string `json:"type,omitempty"`
	Function struct {
		Name      string `json:"name,omitempty"`
		Arguments string `json:"arguments,omitempty"`
	} `json:"function"`
}

// --- Output types for merged non-stream response ---

// mergedResponse is the final merged chat.completion JSON structure.
type mergedResponse struct {
	ID      string         `json:"id"`
	Object  string         `json:"object"`
	Created int64          `json:"created"`
	Model   string         `json:"model"`
	Choices []mergedChoice `json:"choices"`
}

// mergedChoice represents a fully assembled choice with a complete message.
type mergedChoice struct {
	Index        int           `json:"index"`
	Message      mergedMessage `json:"message"`
	FinishReason string        `json:"finish_reason,omitempty"`
}

// mergedMessage is the assembled message combining all delta fragments.
type mergedMessage struct {
	Role             string           `json:"role"`
	Content          string           `json:"content,omitempty"`
	ReasoningContent string           `json:"reasoning_content,omitempty"`
	ToolCalls        []mergedToolCall `json:"tool_calls,omitempty"`
}

// mergedToolCall is a fully assembled tool_call entry.
type mergedToolCall struct {
	ID       string `json:"id"`
	Type     string `json:"type"`
	Function struct {
		Name      string `json:"name"`
		Arguments string `json:"arguments"`
	} `json:"function"`
}

// --- Accumulator for incremental assembly ---

// choiceAccumulator holds state while merging deltas for a single choice index.
type choiceAccumulator struct {
	role             string
	content          strings.Builder
	reasoningContent strings.Builder
	finishReason     string
	// toolCalls keyed by tool_call index for incremental assembly
	toolCalls map[int]*toolCallAccumulator
}

// toolCallAccumulator holds state while merging a single tool_call across chunks.
type toolCallAccumulator struct {
	id       string
	callType string
	name     strings.Builder
	args     strings.Builder
}

// mergeStreamChunks parses SSE-formatted streaming response body and merges all
// chat.completion.chunk entries into a single chat.completion JSON string.
// On any parse failure, it returns the original body with a warning log (graceful fallback).
func mergeStreamChunks(responseBody string) string {
	lines := strings.Split(responseBody, "\n")

	var (
		topID      string
		topModel   string
		topCreated int64
		choices    = make(map[int]*choiceAccumulator) // keyed by choice index
		parsed     int
	)

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		// Strip SSE "data: " prefix
		if !strings.HasPrefix(line, "data: ") && !strings.HasPrefix(line, "data:") {
			continue
		}
		payload := strings.TrimPrefix(line, "data: ")
		payload = strings.TrimPrefix(payload, "data:")
		payload = strings.TrimSpace(payload)

		// Skip SSE terminal marker
		if payload == "[DONE]" {
			continue
		}

		var chunk streamChunk
		if err := json.Unmarshal([]byte(payload), &chunk); err != nil {
			log.Printf("[WARN] stream_merger: failed to parse chunk json, falling back to raw body err=%v", err)
			return responseBody
		}

		// Capture top-level metadata from the first successfully parsed chunk
		if parsed == 0 {
			topID = chunk.ID
			topModel = chunk.Model
			topCreated = chunk.Created
		}
		parsed++

		// Accumulate each choice's delta
		for _, c := range chunk.Choices {
			acc, ok := choices[c.Index]
			if !ok {
				acc = &choiceAccumulator{
					toolCalls: make(map[int]*toolCallAccumulator),
				}
				choices[c.Index] = acc
			}

			// Role: take the first non-empty value
			if c.Delta.Role != "" && acc.role == "" {
				acc.role = c.Delta.Role
			}

			// Content: append incremental text
			if c.Delta.Content != nil && *c.Delta.Content != "" {
				acc.content.WriteString(*c.Delta.Content)
			}

			// Reasoning content: append incremental text
			if c.Delta.ReasoningContent != nil && *c.Delta.ReasoningContent != "" {
				acc.reasoningContent.WriteString(*c.Delta.ReasoningContent)
			}

			// Tool calls: merge by tool_call index
			for _, tc := range c.Delta.ToolCalls {
				tcAcc, exists := acc.toolCalls[tc.Index]
				if !exists {
					tcAcc = &toolCallAccumulator{}
					acc.toolCalls[tc.Index] = tcAcc
				}
				// ID and type appear only in the first chunk for each tool_call
				if tc.ID != "" && tcAcc.id == "" {
					tcAcc.id = tc.ID
				}
				if tc.Type != "" && tcAcc.callType == "" {
					tcAcc.callType = tc.Type
				}
				if tc.Function.Name != "" {
					tcAcc.name.WriteString(tc.Function.Name)
				}
				if tc.Function.Arguments != "" {
					tcAcc.args.WriteString(tc.Function.Arguments)
				}
			}

			// Finish reason: take the last non-empty value
			if c.FinishReason != nil && *c.FinishReason != "" {
				acc.finishReason = *c.FinishReason
			}
		}
	}

	// If no chunks were parsed, fall back to raw body
	if parsed == 0 {
		log.Printf("[WARN] stream_merger: no valid SSE chunks found, falling back to raw body")
		return responseBody
	}

	// Assemble merged response
	resp := mergedResponse{
		ID:      topID,
		Object:  "chat.completion",
		Created: topCreated,
		Model:   topModel,
	}

	// Build choices ordered by index (find max index first)
	maxIdx := 0
	for idx := range choices {
		if idx > maxIdx {
			maxIdx = idx
		}
	}
	for i := 0; i <= maxIdx; i++ {
		acc, ok := choices[i]
		if !ok {
			continue
		}

		msg := mergedMessage{
			Role:             acc.role,
			Content:          acc.content.String(),
			ReasoningContent: acc.reasoningContent.String(),
		}

		// Assemble tool_calls ordered by index
		if len(acc.toolCalls) > 0 {
			maxTCIdx := 0
			for idx := range acc.toolCalls {
				if idx > maxTCIdx {
					maxTCIdx = idx
				}
			}
			for j := 0; j <= maxTCIdx; j++ {
				tcAcc, exists := acc.toolCalls[j]
				if !exists {
					continue
				}
				tc := mergedToolCall{
					ID:   tcAcc.id,
					Type: tcAcc.callType,
				}
				if tc.Type == "" {
					tc.Type = "function" // default per OpenAI spec
				}
				tc.Function.Name = tcAcc.name.String()
				tc.Function.Arguments = tcAcc.args.String()
				msg.ToolCalls = append(msg.ToolCalls, tc)
			}
		}

		choice := mergedChoice{
			Index:        i,
			Message:      msg,
			FinishReason: acc.finishReason,
		}
		resp.Choices = append(resp.Choices, choice)
	}

	out, err := json.Marshal(resp)
	if err != nil {
		log.Printf("[WARN] stream_merger: failed to marshal merged response, falling back to raw body err=%v", err)
		return responseBody
	}

	log.Printf("[INFO] stream_merger: merged %d SSE chunks into non-stream response (raw_len=%d merged_len=%d)",
		parsed, len(responseBody), len(out))
	return string(out)
}
