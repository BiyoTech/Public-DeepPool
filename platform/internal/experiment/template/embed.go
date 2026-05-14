// Package template embeds builtin scorer YAML templates into the binary.
// This ensures templates are available even when deployed as a standalone binary
// without the source directory structure.
package template

import "embed"

//go:embed judge_template_en.yaml judge_template_zh.yaml
var FS embed.FS
