# LLM Integration Documentation

## Overview

This document describes the integration of real LLM providers (OpenAI and Anthropic Claude) into the BIOwerk system, replacing all mock implementations with actual AI-powered business logic.

## Changes Summary

### 1. Dependencies Added

**requirements.txt:**
- `openai==1.58.1` - OpenAI SDK for GPT models
- `anthropic==0.39.0` - Anthropic SDK for Claude models

### 2. Configuration

**Environment Variables (.env.example):**
```bash
# LLM Provider Configuration
LLM_PROVIDER=openai                          # Primary provider: 'openai' or 'anthropic'

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o
OPENAI_MAX_TOKENS=4096
OPENAI_TEMPERATURE=0.7
OPENAI_TIMEOUT=60

# Anthropic Claude Configuration
ANTHROPIC_API_KEY=your-anthropic-api-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_TOKENS=4096
ANTHROPIC_TEMPERATURE=0.7
ANTHROPIC_TIMEOUT=60
```

**Settings (matrix/config.py):**
- Added LLM provider configuration fields
- Added OpenAI configuration fields
- Added Anthropic configuration fields

### 3. LLM Client Utility (matrix/llm_client.py)

**Features:**
- Unified interface for both OpenAI and Anthropic APIs
- Async support for all LLM calls
- Automatic provider selection based on configuration
- JSON mode support for structured outputs
- Comprehensive error handling and logging
- Token usage tracking

**Key Methods:**
```python
# General chat completion
await llm_client.chat_completion(
    messages=[{"role": "user", "content": "..."}],
    system_prompt="You are an expert...",
    temperature=0.7,
    max_tokens=4096,
    provider="openai",  # Optional override
    json_mode=True      # Enable JSON response
)

# Generate JSON output
await llm_client.generate_json(
    prompt="Create a plan...",
    system_prompt="You are a planner...",
    provider="anthropic"  # Optional override
)
```

## Service Implementations

All 6 services have been upgraded with real LLM implementations:

### 1. Osteon Service (Content Generation)
**Endpoints:** 5 endpoints with LLM integration

| Endpoint | Description | LLM Usage |
|----------|-------------|-----------|
| `/outline` | Generate document outlines | Creates structured outlines with 5-8 sections based on topic/goal |
| `/draft` | Generate draft content | Writes 2-3 paragraphs of high-quality content for sections |
| `/edit` | Edit and improve text | Applies feedback or edit types (improve, shorten, expand, etc.) |
| `/summarize` | Summarize content | Creates summaries in configurable lengths (short/medium/long) |
| `/export` | Export artifacts | Packages sections into complete artifact |

**Example Request:**
```json
POST /osteon/outline
{
  "id": "req-123",
  "input": {
    "topic": "Introduction to Machine Learning",
    "context": "For beginners with programming background"
  }
}
```

### 2. Synapse Service (Presentations)
**Endpoints:** 4 endpoints with LLM integration

| Endpoint | Description | LLM Usage |
|----------|-------------|-----------|
| `/storyboard` | Create presentation outline | Generates diverse slide types with descriptions |
| `/slide_make` | Generate slide content | Creates detailed slides with content and speaker notes |
| `/visualize` | Create data visualizations | Generates chart specifications (bar, line, pie, etc.) |
| `/export` | Export presentation | Packages slides into complete artifact |

**Example Request:**
```json
POST /synapse/storyboard
{
  "id": "req-124",
  "input": {
    "topic": "Q4 Sales Review",
    "audience": "executive team",
    "num_slides": 10
  }
}
```

### 3. Myocyte Service (Data Analysis)
**Endpoints:** 4 endpoints with LLM integration

| Endpoint | Description | LLM Usage |
|----------|-------------|-----------|
| `/ingest_table` | Parse and structure data | Intelligently parses raw data into structured tables |
| `/formula_eval` | Analyze data | Generates insights and suggests useful formulas |
| `/model_forecast` | Generate forecasts | Creates predictions with trend analysis |
| `/export` | Export data artifacts | Packages tables, formulas, and charts |

**Example Request:**
```json
POST /myocyte/formula_eval
{
  "id": "req-125",
  "input": {
    "tables": [
      {
        "id": "t1",
        "headers": ["Product", "Revenue", "Units"],
        "rows": [["A", 1000, 50], ["B", 2000, 100]]
      }
    ]
  }
}
```

### 4. Circadian Service (Project Planning)
**Endpoints:** 4 endpoints with LLM integration

| Endpoint | Description | LLM Usage |
|----------|-------------|-----------|
| `/plan_timeline` | Create project timeline | Generates milestones, identifies risks, suggests actions |
| `/assign` | Make task assignments | Optimally assigns tasks based on skills and workload |
| `/track` | Track progress | Assesses project status with recommendations |
| `/remind` | Generate reminders | Creates contextual, actionable reminders |

**Example Request:**
```json
POST /circadian/plan_timeline
{
  "id": "req-126",
  "input": {
    "project_description": "Build mobile app",
    "duration_weeks": 12,
    "team_size": 5
  }
}
```

### 5. Nucleus Service (Orchestration)
**Endpoints:** 4 endpoints with LLM integration

| Endpoint | Description | LLM Usage |
|----------|-------------|-----------|
| `/plan` | Create execution plans | Generates multi-step workflow plans with dependencies |
| `/route` | Intelligent routing | Routes requests to appropriate services |
| `/review` | Quality review | Reviews content against quality criteria |
| `/finalize` | Finalize workflows | Summarizes workflow results |

**Example Request:**
```json
POST /nucleus/plan
{
  "id": "req-127",
  "input": {
    "goal": "Create a product launch presentation with data analysis",
    "requirements": ["Include sales forecasts", "Professional design"]
  }
}
```

### 6. Chaperone Service (Format Conversion)
**Endpoints:** 2 endpoints with LLM integration

| Endpoint | Description | LLM Usage |
|----------|-------------|-----------|
| `/import_artifact` | Import external content | Intelligently parses and structures imported content |
| `/export_artifact` | Export to formats | Prepares content for PDF/DOCX/XLSX/PPTX export |

**Example Request:**
```json
POST /chaperone/export_artifact
{
  "id": "req-128",
  "input": {
    "artifact": {...},
    "format": "pdf"
  }
}
```

## Error Handling

All services implement comprehensive error handling:

1. **JSON Parse Errors:** Fallback to reasonable defaults when LLM returns invalid JSON
2. **API Errors:** Logged with full context and returned as proper error responses
3. **Invalid Input:** Validated and returns clear error messages
4. **Timeouts:** Configurable per provider (default 60 seconds)

## Logging and Observability

All LLM calls are instrumented with:
- Request/response logging
- Token usage tracking
- Duration metrics
- Error tracking
- Prometheus metrics via existing instrumentation

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 3. Set API Keys
```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 4. Choose Provider
```bash
# In .env file
LLM_PROVIDER=openai  # or 'anthropic'
```

### 5. Start Services
```bash
docker compose up --build
```

## Testing

### Test Individual Services

**Osteon (Content Generation):**
```bash
curl -X POST http://localhost:8080/osteon/outline \
  -H "Content-Type: application/json" \
  -d '{"id":"test-1","input":{"topic":"AI Ethics"}}'
```

**Synapse (Presentations):**
```bash
curl -X POST http://localhost:8080/synapse/storyboard \
  -H "Content-Type: application/json" \
  -d '{"id":"test-2","input":{"topic":"Product Demo","num_slides":5}}'
```

**Myocyte (Data Analysis):**
```bash
curl -X POST http://localhost:8080/myocyte/model_forecast \
  -H "Content-Type: application/json" \
  -d '{"id":"test-3","input":{"data":[100,110,120,130],"periods":3}}'
```

**Circadian (Planning):**
```bash
curl -X POST http://localhost:8080/circadian/plan_timeline \
  -H "Content-Type: application/json" \
  -d '{"id":"test-4","input":{"project_description":"Website redesign","duration_weeks":8}}'
```

**Nucleus (Orchestration):**
```bash
curl -X POST http://localhost:8080/nucleus/plan \
  -H "Content-Type: application/json" \
  -d '{"id":"test-5","input":{"goal":"Create quarterly report"}}'
```

## Performance Considerations

1. **Token Limits:** Configured per provider (default 4096)
2. **Timeouts:** 60 seconds per request (configurable)
3. **Rate Limits:** Respect provider rate limits
4. **Caching:** Consider implementing response caching for repeated requests
5. **Async Operations:** All LLM calls are async for better performance

## Cost Management

- Monitor token usage via logs
- Adjust `max_tokens` and `temperature` per use case
- Consider using different models for different complexity levels
- Implement caching strategies for common requests

## Future Enhancements

1. **Response Caching:** Cache LLM responses for identical inputs
2. **Model Selection:** Auto-select model based on task complexity
3. **Streaming:** Implement streaming for long-form content
4. **Batch Processing:** Batch multiple requests for efficiency
5. **Fine-tuning:** Fine-tune models for specific use cases
6. **Fallback Chains:** Automatic fallback to alternative providers

## Troubleshooting

### API Key Issues
```
Error: OpenAI client not configured
Solution: Ensure OPENAI_API_KEY is set in .env
```

### JSON Parse Errors
```
Warning: Failed to parse LLM JSON response
Solution: Services automatically fall back to default responses
```

### Timeout Errors
```
Error: Request timeout
Solution: Increase OPENAI_TIMEOUT or ANTHROPIC_TIMEOUT in .env
```

### Rate Limiting
```
Error: Rate limit exceeded
Solution: Implement exponential backoff or reduce request frequency
```

## Summary

**Total Integration:**
- ✅ 6 services updated
- ✅ 23 endpoints with real LLM calls
- ✅ Support for OpenAI and Anthropic
- ✅ Comprehensive error handling
- ✅ Full logging and observability
- ✅ Production-ready configuration

All mock implementations have been replaced with intelligent, LLM-powered business logic that provides real value to users.
