# Guardrails Guide

Guardrails are content safety rules that you attach to an API Key. Every request (input) or response (output) passing through that key is automatically evaluated by an LLM judge. Depending on the rule configuration, flagged content can be **blocked** (request rejected with HTTP 400) or **logged** (recorded for audit without blocking).

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Phase** | When the evaluation runs: **Input** (before the request reaches the model) or **Output** (after the model responds) |
| **Action** | What happens when content is flagged: **Block** (reject the request/response) or **Log** (record only, don't block) |
| **Evaluator Model** | The LLM model used to evaluate content (e.g., GPT-4o, Qwen) |
| **Evaluator API Key** | The API Key used to authenticate the evaluator LLM call |
| **Storage** | Where evaluation results are stored: **Builtin** (platform-managed database) or **External** (user-provided database) |

### Input vs Output Guardrails

- **Input Guardrails** inspect the user's message *before* it is forwarded to the target model. Ideal for blocking PII leakage, jailbreak attempts, or unsafe prompts.
- **Output Guardrails** inspect the model's response *after* generation. Ideal for detecting hallucinations, unsafe generated content, or PII in responses.

> **Note:** When an Output Guardrail is enabled, streaming responses are automatically downgraded to non-streaming. The response header `X-DP-Stream-Downgraded: output-guardrail` will be set to inform the client.

### Block vs Log

| Action | Behavior |
|--------|----------|
| **Block** | Flagged content is rejected. Input → returns HTTP 400 with `content_policy_violation`. Output → response is replaced with an error. If the evaluator itself fails, the request is blocked (fail-closed). |
| **Log** | Flagged content is recorded in the evaluation results table but the request proceeds normally. If the evaluator fails, the request is allowed (fail-open). |

---

## Built-in Templates

DeepPool provides 5 ready-to-use guardrail templates. Select a template when creating a rule to auto-fill the name, phase, and evaluation prompt.

| Template | Phase | Description |
|----------|-------|-------------|
| **PII Redaction** | Input & Output | Detects PII (names, emails, phones, SSN, credit cards, addresses) and provides a redacted version with placeholders |
| **PII Blocking** | Input | Zero-tolerance PII policy — blocks any content containing personal information |
| **Unsafe Content** | Input & Output | Detects hate speech, harassment, violence, self-harm, sexual content, extremism, and dangerous instructions |
| **Jailbreak Detection** | Input | Detects prompt injection, instruction override, encoding tricks, role-play exploitation, and system prompt extraction attempts |
| **Hallucination Detection** | Output | Detects fabricated facts, fake citations, false claims about real entities, and unverifiable confident assertions |

You can also write fully custom evaluation prompts. Use the `{{content}}` placeholder in your prompt — it will be replaced with the actual text being evaluated at runtime.

---

## Creating a Guardrail Rule

1. Navigate to **API Key** tab → click an API Key to open its detail view
2. Switch to the **Guardrails** tab
3. Click the **+ Add** button in the top-right corner
4. Fill in the form:

| Field | Description |
|-------|-------------|
| **Template** | Optional. Select a built-in template to auto-fill fields, or choose "Custom" to write from scratch |
| **Name** | A descriptive name for this rule (e.g., "Block PII in requests") |
| **Phase** | Choose **Input** or **Output** |
| **Action** | Choose **Block** (reject flagged content) or **Log** (record only) |
| **Evaluator Model** | Select the LLM model that will evaluate content |
| **Evaluator API Key** | Select the API Key for authenticating evaluator calls |
| **Evaluation Prompt** | The prompt sent to the evaluator LLM. Use `{{content}}` as a placeholder for the text to be evaluated |
| **Result Storage** | **Builtin** (platform database) or **External** (your own database — fill in connection details) |

5. Click **Save** to create the rule

The rule is **enabled by default**. You can toggle it on/off from the rules list without deleting it.

---

## Managing Rules

From the Guardrails tab of an API Key detail view:

- **Toggle** — Click the Enabled/Disabled badge to quickly enable or disable a rule without deleting it
- **Edit** — Hover over a rule and click the edit icon to modify any field
- **Delete** — Hover over a rule and click the delete icon (requires confirmation)

Multiple rules can be attached to a single API Key. All enabled rules for the matching phase are evaluated **in parallel** for every request.

---

## Viewing Evaluation Results

Switch to the **Evaluation Results** sub-tab within the Guardrails tab to see a log of all evaluations:

| Column | Description |
|--------|-------------|
| **Time** | When the evaluation was performed (UTC) |
| **Request ID** | The unique request identifier (click to copy) |
| **Phase** | Input or Output |
| **Flagged** | Whether the evaluator flagged the content |
| **Confidence** | The evaluator's confidence score (0–100%) |
| **Blocked** | Whether the request/response was actually blocked |
| **Duration** | How long the evaluation took (ms) |
| **Reason** | The evaluator's explanation for its decision |

### Filtering

Use the **date range picker** at the top to filter results by time period, then click **Search**.

The results list uses **infinite scroll** — simply scroll down to load more records.

---

## Best Practices

1. **Use Block for input, Log for output first** — Start with logging on output guardrails to understand your traffic patterns before enabling blocking.
2. **Choose a fast evaluator model** — Guardrail evaluation adds latency to every request. Use a small, fast model (e.g., GPT-4o-mini) for lower overhead.
3. **Avoid evaluator recursion** — The evaluator API Key's own requests are automatically excluded from guardrail evaluation (via the `X-DP-Guardrail-Eval` header) to prevent infinite loops.
4. **Layer your guardrails** — Combine PII blocking on input with hallucination detection on output for comprehensive coverage.
5. **Monitor evaluation results** — Regularly review logged results to tune your prompts and reduce false positives.
