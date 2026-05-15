# Experiment Guide

The Experiment module provides a complete toolchain for monitoring and evaluating model inference quality. It helps you trace inference logs, perform manual annotations, and use AI to automatically evaluate model output quality.

## Module Overview

The Experiment module consists of three core sub-features:

| Feature | Description |
|---------|-------------|
| **Overview** | At-a-glance summary of Trace status and Judge task results |
| **Trace** | Create trace tasks to capture full inference logs for specific API Keys and models |
| **AI Judge** | Create AI evaluation tasks that use LLM models to automatically assess trace log quality |

After entering the Experiment module, use the left sidebar navigation to switch between sub-features.

## Overview

The Overview page provides data summaries across three dimensions:

### Trace Overview

Displays statistics related to current tracing:

- **API Keys**: Total count / number being traced
- **Models**: Total model count (gateway + custom models) / number being traced
- **Traces**: Total trace tasks / running / stopped

### Judge Overview

Shows a summary table of all evaluation tasks, including:

- Judge name, evaluation model, scorer type
- Evaluation target (all logs / specific Trace / specific model / specific API Key)
- Current status (Pending / Running / Completed / Failed)
- Pass rate from the most recent run

### Evaluation (Coming Soon)

Benchmark-based model evaluation using standard test sets — stay tuned.

---

## Trace

The Trace feature captures complete request and response logs from model inference, serving as the data foundation for subsequent evaluation and analysis.

### Creating a Trace Task

1. Navigate to the **Trace** page and click the **Create Trace** button in the top-right corner
2. Fill in the following information:

| Field | Description |
|-------|-------------|
| **Task Name** | Give the trace task a descriptive name, e.g., "GPT4o Quality Trace" |
| **Select API Keys** | Check the API Keys to trace (at least one required) |
| **Trace Models** | Optional. Leave empty to trace all model requests for the selected API Keys; or search and select specific models |
| **Log Storage** | Choose the log storage method (see below) |

3. Click **Create** to finish

### Log Storage Options

| Storage Type | Description |
|--------------|-------------|
| **Built-in Engine** | Zero configuration, uses the platform-managed database |
| **External Database** | Connect your own database (supports MySQL, PostgreSQL, ClickHouse, etc.) |

When using an external database, you need to provide connection details (host, port, username, password, database name) and can click **Test Connection** to verify connectivity.

### Managing Trace Tasks

Each trace task card provides the following actions:

- **View Logs**: Enter the log list page to view captured inference logs
- **Edit**: Modify trace task configuration (only available when stopped)
- **Start / Stop**: Control the trace task's running state
- **Delete**: Remove the trace task (irreversible)

> **Tip**: Once a trace task is started, all matching inference requests are automatically recorded. Stop it when not needed to avoid excessive log data.

### Viewing Trace Logs

Click the **View Logs** button on a trace task to enter the log list page:

#### Search Filters

Filter logs by the following criteria:

- **Model Name**: Filter by model
- **API Key ID**: Filter by API Key
- **Request ID**: Find a specific request
- **Time Range**: Filter by start and end time

#### Log List

The list displays key information for each log entry:

| Column | Description |
|--------|-------------|
| Request ID | Unique request identifier |
| User Query | User's input question (truncated) |
| Model | Model name used |
| Tokens | Total token consumption |
| Duration | Request duration |
| Status | Success / Failed |
| Feedback | Manual feedback status (Passed / Failed / None) |
| Expectation | Whether expected output is set |

Click any row to open the **Log Detail Dialog**.

### Log Detail

The log detail dialog is divided into three areas:

#### Left — Metadata Panel

Displays basic request information:

- Request ID, model name, API Key ID
- Streaming / non-streaming indicator
- TTFT (Time to First Token)
- Token usage breakdown (Prompt / Completion / Total / Reasoning)
- Request duration
- Request parameters (temperature, top_p, etc.)
- Tools definition list
- Error message (if the request failed)

#### Center — Request / Response Content

Two viewing modes are available:

- **Pretty Mode**: Displays messages as chat bubbles, clearly distinguishing system / user / assistant / tool roles, with structured rendering of Function Calls and Reasoning Content
- **JSON Mode**: Shows raw JSON data for debugging

Switch between **Request** and **Response** using the top tabs.

#### Right — Evaluation Panel

Used for manual annotation of logs, containing two sections:

**1. Feedback**

Add multi-dimensional quality feedback to logs:

- Click **Add Feedback** to create a new feedback item
- Each feedback item includes:
  - **Name**: Feedback dimension name (e.g., "Response Quality", "Format Correctness")
  - **Passed / Failed**: Toggle the evaluation result
  - **Reason**: Optional, provide evaluation rationale
- Multiple feedback items can be added to cover different evaluation dimensions
- Click the × on a feedback item to remove it

**2. Expectation**

Set standard answers or expected outputs for logs:

- Click **Add Expectation** to create an expected output
- Includes the following fields:
  - **Name**: Expectation item name (e.g., "Standard Answer")
  - **Data Type**: Text / Number / Boolean / JSON
  - **Content**: The expected output content
  - **Reason**: Optional, explain why this is the expected output

> **Tip**: Set expectations can be referenced in AI Judge evaluations as the `{{expectations}}` variable, allowing the AI to consider standard answers during evaluation.

Click the **Save** button at the bottom to submit annotations.

---

## AI Judge

The Judge feature uses LLM models to automatically evaluate trace log output quality, supporting batch evaluation and multiple scoring strategies.

### Creating a Judge Task

1. Navigate to the **AI Judge** page and click the **Create Judge** button in the top-right corner
2. Fill in the following information in the right-side drawer:

#### Basic Information

| Field | Description |
|-------|-------------|
| **Judge Name** | Give the evaluation task a descriptive name |

#### Evaluation Target

The evaluation target determines which logs will be evaluated, supporting progressive filtering:

**Step 1: Select Trace Task (Optional)**
- Select "All Traces" to not restrict to a specific trace task
- After selecting a specific Trace, you can further filter by model and API Key

**Step 2: Filter by Model / API Key (Optional)**
- When a specific Trace is selected, its associated models and API Keys are displayed
- Click tags to toggle selection, multiple selections supported

**Step 3: Select Specific Logs (Optional)**
- Click **Pick specific logs** to open the log selection dialog
- Check specific log entries to evaluate in the dialog
- Supports select all / deselect all

The bottom displays a summary of the current evaluation target, such as "Target: All logs from Trace #1" or "Target: 3 specific log(s)".

#### Evaluation Model & API Key

| Field | Description |
|-------|-------------|
| **Judge Model** | Select the LLM model to perform evaluation (searchable dropdown) |
| **Judge API Key** | Select the API Key to use when calling the evaluation model |

#### Scorer Configuration

**Scorer Type**:

| Type | Description |
|------|-------------|
| **Built-in** | Platform-preset scoring strategies; selecting one auto-fills the evaluation prompt |
| **Custom** | Fully customizable evaluation prompt |

**Evaluation Prompt**:

Regardless of scorer type, you can edit the evaluation prompt. The following variables are supported:

| Variable | Description |
|----------|-------------|
| `{{inputs}}` | User's input content |
| `{{outputs}}` | Model's output content |
| `{{conversations}}` | Full conversation context |
| `{{expectations}}` | Manually annotated expected output (if available) |

3. Click **Create** to finish

### Managing Judge Tasks

Each judge task card provides the following actions:

- **Run**: Start evaluation, executing AI evaluation on all matching logs
- **Edit**: Modify judge task configuration
- **View Runs**: View historical run records and evaluation results
- **Delete**: Remove the judge task

### Running an Evaluation

After clicking **Run**, the system will:

1. Filter matching trace logs based on the evaluation target
2. For each log, populate the evaluation prompt variables with its content
3. Call the evaluation model to perform assessment
4. Record each log's evaluation result (Passed / Failed + Reason)

### Viewing Run Records

Click **View Runs** to open the right-side drawer:

#### Run List

Displays all historical run records, each containing:

- Run number (Run #ID)
- Status (Pending / Running / Completed / Failed)
- Progress bar (completed / total)
- Pass rate (shown only for completed runs)
- Creation time

Pass rate color coding:
- 🟢 ≥ 80%: Green
- 🟡 ≥ 50%: Orange
- 🔴 < 50%: Red

#### Evaluation Results

Click a run record to view detailed per-log evaluation results:

| Column | Description |
|--------|-------------|
| Log ID | ID of the evaluated log |
| Passed | Passed / Failed |
| Reason | AI-provided evaluation rationale (click to expand full text) |
| Duration | Single evaluation duration |
| Status | Evaluation execution status (Success / Failed) |

---

## Best Practices

### Recommended Workflow

```
Create API Key → Create Trace → Use API to generate inference logs
    → View logs & manual annotation → Create Judge → Run evaluation → Analyze results
```

### Tips

1. **Start with small-scope tracing**: Trace specific models and API Keys first to avoid excessive log volume
2. **Leverage manual annotations**: Add Feedback and Expectation to key logs to provide reference standards for AI evaluation
3. **Iterate on prompts**: Adjust evaluation prompts based on results to improve evaluation accuracy
4. **Run evaluations regularly**: Re-run evaluations after model or prompt changes to compare quality before and after
5. **Focus on low pass rates**: Prioritize analyzing evaluation tasks with pass rates below 50% to identify quality issues
