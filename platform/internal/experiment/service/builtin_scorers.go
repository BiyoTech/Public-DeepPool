// Builtin scorers: pre-defined evaluation prompt templates for AI judge.
// Scorer definitions are loaded from YAML template files at startup, supporting i18n (en/zh).
//
// Loading priority:
//   1. External filesystem path (templateDir config) — allows runtime override
//   2. Embedded templates (go:embed via template package) — always available in binary
//
// Template files: platform/internal/experiment/template/judge_template_{lang}.yaml
//
// Supported template variables in prompts:
//   - {{inputs}}        — model input (request_body)
//   - {{outputs}}       — model output (response_body)
//   - {{conversations}} — full conversation (messages extracted from request_body)
//   - {{expectations}}  — human-annotated expected output (from annotation)
package service

import (
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"deeppool/platform/internal/experiment/template"

	"gopkg.in/yaml.v3"
)

// BuiltinScorer represents a pre-defined evaluation scorer template.
// ResponseFormat is system-controlled and appended automatically during judge execution.
// It is NOT exposed to the frontend or editable by users.
type BuiltinScorer struct {
	Name           string `json:"name" yaml:"name"`
	DisplayName    string `json:"display_name" yaml:"display_name"`
	Description    string `json:"description" yaml:"description"`
	PromptTemplate string `json:"prompt_template" yaml:"prompt_template"`
	ResponseFormat string `json:"-" yaml:"response_format"` // internal only, not serialized to JSON/gRPC
}

// scorerTemplateFile defines the YAML structure for scorer template files.
type scorerTemplateFile struct {
	Scorers []BuiltinScorer `yaml:"scorers"`
}

// TemplateVariables lists all supported placeholder variables in scorer prompts.
var TemplateVariables = []string{
	"{{inputs}}",
	"{{outputs}}",
	"{{conversations}}",
	"{{expectations}}",
}

// scorerRegistry holds loaded scorers keyed by language code.
var (
	scorerRegistry     map[string][]BuiltinScorer // lang -> scorers
	scorerRegistryOnce sync.Once
	templateDir        string // set by InitScorerTemplates
)

// defaultLang is the fallback language when requested lang is not available.
const defaultLang = "en"

// supportedLangs defines the language codes to load at startup.
var supportedLangs = []string{"en", "zh"}

// InitScorerTemplates loads scorer templates from the given directory.
// Must be called once at server startup before any ListBuiltinScorers call.
//
// Loading strategy per language:
//  1. Try external file: {templateBaseDir}/judge_template_{lang}.yaml
//  2. Fallback to embedded template compiled into the binary
func InitScorerTemplates(templateBaseDir string) {
	templateDir = templateBaseDir
	scorerRegistryOnce.Do(func() {
		scorerRegistry = make(map[string][]BuiltinScorer)
		for _, lang := range supportedLangs {
			filename := "judge_template_" + lang + ".yaml"
			externalPath := filepath.Join(templateBaseDir, filename)

			// Priority 1: load from external filesystem
			if scorers, err := loadScorerFileFromDisk(externalPath); err == nil {
				scorerRegistry[lang] = scorers
				log.Printf("[INFO] builtin_scorers: loaded %d scorers for lang=%s from external file %s", len(scorers), lang, externalPath)
				continue
			}

			// Priority 2: fallback to embedded template
			if scorers, err := loadScorerFileFromEmbed(filename); err == nil {
				scorerRegistry[lang] = scorers
				log.Printf("[INFO] builtin_scorers: loaded %d scorers for lang=%s from embedded template", len(scorers), lang)
				continue
			}

			log.Printf("[WARN] builtin_scorers: no template available for lang=%s (tried external=%s and embedded)", lang, externalPath)
		}

		if len(scorerRegistry[defaultLang]) == 0 {
			log.Printf("[ERROR] builtin_scorers: no English templates loaded from external or embedded sources, scorer list will be empty")
			scorerRegistry[defaultLang] = []BuiltinScorer{}
		}
	})
}

// loadScorerFileFromDisk reads and parses a scorer YAML file from the filesystem.
func loadScorerFileFromDisk(path string) ([]BuiltinScorer, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseScorerYAML(data)
}

// loadScorerFileFromEmbed reads and parses a scorer YAML file from the embedded FS.
func loadScorerFileFromEmbed(filename string) ([]BuiltinScorer, error) {
	data, err := template.FS.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	return parseScorerYAML(data)
}

// parseScorerYAML unmarshals raw YAML bytes into a scorer list.
func parseScorerYAML(data []byte) ([]BuiltinScorer, error) {
	var f scorerTemplateFile
	if err := yaml.Unmarshal(data, &f); err != nil {
		return nil, err
	}
	// Trim trailing whitespace from prompt templates and response format (YAML block scalars may add newlines)
	for i := range f.Scorers {
		f.Scorers[i].PromptTemplate = strings.TrimRight(f.Scorers[i].PromptTemplate, "\n\r ")
		f.Scorers[i].ResponseFormat = strings.TrimRight(f.Scorers[i].ResponseFormat, "\n\r ")
	}
	return f.Scorers, nil
}

// BuiltinScorers returns all scorers for the default language (backward compatible).
var BuiltinScorers []BuiltinScorer // kept for backward compat with GetBuiltinScorer

// GetBuiltinScorersForLang returns the scorer list for the requested language.
// Falls back to English if the language is not available.
func GetBuiltinScorersForLang(lang string) []BuiltinScorer {
	// Normalize: "zh-CN" -> "zh", "en-US" -> "en"
	lang = normalizeLang(lang)
	if scorers, ok := scorerRegistry[lang]; ok {
		return scorers
	}
	return scorerRegistry[defaultLang]
}

// GetBuiltinScorer returns a builtin scorer by name (uses default language).
func GetBuiltinScorer(name string) *BuiltinScorer {
	scorers := scorerRegistry[defaultLang]
	for i := range scorers {
		if scorers[i].Name == name {
			return &scorers[i]
		}
	}
	return nil
}

// normalizeLang converts locale codes like "zh-CN" to base language "zh".
func normalizeLang(lang string) string {
	lang = strings.TrimSpace(strings.ToLower(lang))
	if lang == "" {
		return defaultLang
	}
	// "zh-cn" -> "zh", "en-us" -> "en"
	if idx := strings.IndexAny(lang, "-_"); idx > 0 {
		lang = lang[:idx]
	}
	return lang
}
