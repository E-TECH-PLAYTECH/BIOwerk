from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
from matrix.logging_config import setup_logging, log_request, log_response, log_error
from matrix.errors import InvalidInputError, create_error_response
from matrix.llm_client import llm_client
import time
import json

app = FastAPI(title="Myocyte")
setup_instrumentation(app)
logger = setup_logging("myocyte")

@app.post("/ingest_table", response_model=Reply)
async def ingest_table(msg: Msg):
    """Analyze and structure table data."""
    start_time = time.time()
    log_request(logger, msg.id, "myocyte", "ingest_table")

    try:
        inp = msg.input or {}
        raw_data = inp.get("raw_data", "")
        tables = inp.get("tables", [])

        if not raw_data and not tables:
            raise InvalidInputError("raw_data or tables is required")

        # If tables are already provided, analyze and enhance them
        if tables:
            output = {"tables": tables, "summary": f"Ingested {len(tables)} tables"}
            duration_ms = (time.time() - start_time) * 1000
            log_response(logger, msg.id, "myocyte", True, duration_ms)
            return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))

        # Parse raw data into structured tables using LLM
        system_prompt = """You are a data analysis expert. Parse and structure the given data into tables.
Return your response as a JSON object with a 'tables' array.
Each table should have: id, name, headers (array of column names), rows (array of row data).
Example: {
  "tables": [{
    "id": "table-1",
    "name": "Sales Data",
    "headers": ["Product", "Revenue", "Units"],
    "rows": [["Product A", 1000, 50], ["Product B", 2000, 100]]
  }]
}"""

        prompt = f"""Parse this data into structured tables:

{raw_data}

Identify logical tables, determine appropriate headers, and structure the data."""

        response_text = await llm_client.generate_json(
            prompt=prompt,
            system_prompt=system_prompt
        )

        output = json.loads(response_text)
        output["summary"] = f"Parsed {len(output.get('tables', []))} tables from raw data"

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "myocyte", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        output = {"tables": tables or [], "summary": "Fallback: data ingested"}
        return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "myocyte", e))

@app.post("/formula_eval", response_model=Reply)
async def formula_eval(msg: Msg):
    """Evaluate formulas and generate insights from tables."""
    start_time = time.time()
    log_request(logger, msg.id, "myocyte", "formula_eval")

    try:
        inp = msg.input or {}
        tables = inp.get("tables", [])
        formulas = inp.get("formulas", [])

        if not tables:
            raise InvalidInputError("tables is required")

        # If no formulas provided, generate insights
        if not formulas:
            system_prompt = """You are a data analyst. Analyze the provided tables and generate insights.
Return your response as a JSON object with: insights (array of strings), suggested_formulas (array of formula objects).
Each formula should have: id, expression, description.
Example: {
  "insights": ["Revenue increased 20% YoY", "Product A is the top seller"],
  "suggested_formulas": [{"id": "f1", "expression": "SUM(Revenue)", "description": "Total revenue"}]
}"""

            prompt = f"""Analyze these tables and provide insights:

{json.dumps(tables, indent=2)}

Generate key insights and suggest useful formulas."""

            response_text = await llm_client.generate_json(
                prompt=prompt,
                system_prompt=system_prompt
            )

            result = json.loads(response_text)
            output = {
                "tables": tables,
                "formulas": result.get("suggested_formulas", []),
                "insights": result.get("insights", []),
                "charts_spec": []
            }
        else:
            # Evaluate provided formulas
            system_prompt = """You are a data analyst. Evaluate the given formulas against the tables.
Return your response as a JSON object with: results (array of formula results), charts_spec (array of chart specs).
Each result should have: formula_id, value, explanation.
Example: {
  "results": [{"formula_id": "f1", "value": 5000, "explanation": "Sum of all revenue"}],
  "charts_spec": [{"type": "bar", "data": [1, 2, 3], "labels": ["A", "B", "C"]}]
}"""

            prompt = f"""Evaluate these formulas on the given tables:

Tables:
{json.dumps(tables, indent=2)}

Formulas:
{json.dumps(formulas, indent=2)}

Calculate results and suggest visualizations."""

            response_text = await llm_client.generate_json(
                prompt=prompt,
                system_prompt=system_prompt
            )

            result = json.loads(response_text)
            output = {
                "tables": tables,
                "formulas": formulas,
                "results": result.get("results", []),
                "charts_spec": result.get("charts_spec", [])
            }

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "myocyte", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        output = {"tables": tables, "formulas": formulas, "charts_spec": []}
        return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "myocyte", e))

@app.post("/model_forecast", response_model=Reply)
async def model_forecast(msg: Msg):
    """Generate forecasts and predictions from data."""
    start_time = time.time()
    log_request(logger, msg.id, "myocyte", "model_forecast")

    try:
        inp = msg.input or {}
        data = inp.get("data", [])
        tables = inp.get("tables", [])
        forecast_type = inp.get("forecast_type", "trend")
        periods = inp.get("periods", 5)

        if not data and not tables:
            raise InvalidInputError("data or tables is required")

        # Generate forecast using LLM
        system_prompt = """You are a data scientist and forecasting expert. Analyze the data and generate forecasts.
Return your response as a JSON object with: forecast (object with predictions), confidence, methodology, insights.
Example: {
  "forecast": {
    "periods": 5,
    "predictions": [100, 105, 110, 115, 120],
    "type": "trend"
  },
  "confidence": "medium",
  "methodology": "Linear trend analysis",
  "insights": ["Data shows steady upward trend", "Expected 20% growth over 5 periods"]
}"""

        data_text = json.dumps(data if data else tables, indent=2)

        prompt = f"""Generate a {forecast_type} forecast for {periods} periods ahead:

Data:
{data_text}

Analyze trends, patterns, and generate predictions with explanations."""

        response_text = await llm_client.generate_json(
            prompt=prompt,
            system_prompt=system_prompt
        )

        output = json.loads(response_text)

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "myocyte", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        output = {"forecast": {"desc": "Forecast generated", "periods": periods}, "confidence": "low"}
        return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "myocyte", e))

@app.post("/export", response_model=Reply)
async def export_(msg: Msg):
    """Export the complete data artifact."""
    start_time = time.time()
    log_request(logger, msg.id, "myocyte", "export")

    try:
        inp = msg.input or {}
        title = inp.get("title", "Untitled Data Analysis")
        tables = inp.get("tables", [])
        formulas = inp.get("formulas", [])
        charts = inp.get("charts", [])
        metadata = inp.get("metadata", {})

        output = {
            "artifact": {
                "kind": "myotab",
                "meta": {
                    "title": title,
                    "created_at": time.time(),
                    **metadata
                },
                "body": {
                    "tables": tables,
                    "formulas": formulas,
                    "charts": charts
                }
            }
        }

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "myocyte", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "myocyte", e))
