from fastapi import Body, FastAPI
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
from matrix.logging_config import setup_logging, log_request, log_response, log_error
from matrix.errors import InvalidInputError, ValidationError, create_error_response
from matrix.llm_client import llm_client
from matrix.openapi_examples import build_msg_example, build_request_body_examples
from matrix.api_models import (
    IngestTableRequest,
    FormulaEvalRequest,
    ModelForecastRequest,
    ExportRequest
)
from matrix.validation import setup_validation_middleware
from pydantic import ValidationError as PydanticValidationError
import time
import json

app = FastAPI(title="Myocyte", version="1.0.0")
setup_instrumentation(app, service_name="myocyte", service_version="1.0.0")
setup_validation_middleware(app)
logger = setup_logging("myocyte")

# Setup comprehensive health and readiness endpoints
from matrix.health import setup_health_endpoints
setup_health_endpoints(app, service_name="myocyte", version="1.0.0")

MYOCYTE_EXAMPLES = {
    "ingest_table": {
        "csv_ingest": build_msg_example(
            target="myocyte",
            intent="ingest_table",
            summary="Parse a pasted CSV extract",
            input_payload={
                "raw_data": "region,revenue,expenses\nNA,120000,45000\nEU,98000,41000",
                "tables": [],
            },
        )
    },
    "formula_eval": {
        "apply_formulas": build_msg_example(
            target="myocyte",
            intent="formula_eval",
            summary="Calculate gross margin and growth",
            input_payload={
                "tables": [
                    {
                        "id": "rev-1",
                        "name": "Monthly Revenue",
                        "headers": ["month", "revenue", "expenses"],
                        "rows": [
                            ["Jan", 120000, 45000],
                            ["Feb", 135000, 47000],
                            ["Mar", 150000, 50000],
                        ],
                    }
                ],
                "formulas": [
                    {"name": "gross_margin", "expression": "revenue - expenses"},
                    {"name": "growth_rate", "expression": "(revenue / lag(revenue)) - 1"},
                ],
            },
        )
    },
    "model_forecast": {
        "forecast_pipeline": build_msg_example(
            target="myocyte",
            intent="model_forecast",
            summary="Generate a revenue forecast",
            input_payload={
                "tables": [
                    {
                        "id": "rev-1",
                        "name": "ARR by month",
                        "headers": ["month", "arr"],
                        "rows": [
                            ["Jan", 220000],
                            ["Feb", 230000],
                            ["Mar", 245000],
                        ],
                    }
                ],
                "forecast_type": "trend",
                "periods": 4,
            },
        )
    },
    "export": {
        "bundle_artifact": build_msg_example(
            target="myocyte",
            intent="export",
            summary="Export calculated tables with metadata",
            input_payload={
                "title": "Revenue Analysis Pack",
                "metadata": {
                    "tables": [{"id": "rev-1", "name": "ARR by month"}],
                    "formulas": ["gross_margin", "growth_rate"],
                    "charts": ["arr_trend", "margin_by_region"],
                },
            },
        )
    },
}
MYOCYTE_REQUEST_BODIES = {
    name: build_request_body_examples(examples) for name, examples in MYOCYTE_EXAMPLES.items()
}

# ============================================================================
# Internal Handler Functions
# ============================================================================

async def _ingest_table_handler(msg: Msg) -> Reply:
    """Analyze and structure table data."""
    start_time = time.time()
    log_request(logger, msg.id, "myocyte", "ingest_table")

    try:
        # Validate input using Pydantic model
        try:
            req = IngestTableRequest(**msg.input)
            req.validate_required_fields()
        except PydanticValidationError as e:
            raise ValidationError(
                "Invalid input for ingest_table request",
                {"validation_errors": e.errors()}
            )

        raw_data = req.raw_data
        tables = req.tables

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

async def _formula_eval_handler(msg: Msg) -> Reply:
    """Evaluate formulas and generate insights from tables."""
    start_time = time.time()
    log_request(logger, msg.id, "myocyte", "formula_eval")

    try:
        # Validate input using Pydantic model
        try:
            req = FormulaEvalRequest(**msg.input)
        except PydanticValidationError as e:
            raise ValidationError(
                "Invalid input for formula_eval request",
                {"validation_errors": e.errors()}
            )

        tables = req.tables
        formulas = req.formulas

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

async def _model_forecast_handler(msg: Msg) -> Reply:
    """Generate forecasts and predictions from data."""
    start_time = time.time()
    log_request(logger, msg.id, "myocyte", "model_forecast")

    try:
        # Validate input using Pydantic model
        try:
            req = ModelForecastRequest(**msg.input)
            req.validate_required_fields()
        except PydanticValidationError as e:
            raise ValidationError(
                "Invalid input for model_forecast request",
                {"validation_errors": e.errors()}
            )

        data = req.data
        tables = req.tables
        forecast_type = req.forecast_type
        periods = req.periods

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

async def _export__handler(msg: Msg) -> Reply:
    """Export the complete data artifact."""
    start_time = time.time()
    log_request(logger, msg.id, "myocyte", "export")

    try:
        # Validate input using Pydantic model
        try:
            req = ExportRequest(**msg.input)
        except PydanticValidationError as e:
            raise ValidationError(
                "Invalid input for export request",
                {"validation_errors": e.errors()}
            )

        title = req.title
        sections = req.sections
        metadata = req.metadata

        # For myocyte, we expect tables/formulas/charts in sections or metadata
        tables = metadata.get("tables", []) if isinstance(metadata, dict) else []
        formulas = metadata.get("formulas", []) if isinstance(metadata, dict) else []
        charts = metadata.get("charts", []) if isinstance(metadata, dict) else []

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


# ============================================================================
# API v1 Endpoints
# ============================================================================

@app.post("/v1/ingest_table", response_model=Reply, openapi_extra=MYOCYTE_REQUEST_BODIES["ingest_table"])
async def ingest_table_v1(msg: Msg = Body(..., examples=MYOCYTE_EXAMPLES["ingest_table"])):
    """Ingest Table endpoint (API v1)."""
    return await _ingest_table_handler(msg)

@app.post("/v1/formula_eval", response_model=Reply, openapi_extra=MYOCYTE_REQUEST_BODIES["formula_eval"])
async def formula_eval_v1(msg: Msg = Body(..., examples=MYOCYTE_EXAMPLES["formula_eval"])):
    """Formula Eval endpoint (API v1)."""
    return await _formula_eval_handler(msg)

@app.post("/v1/model_forecast", response_model=Reply, openapi_extra=MYOCYTE_REQUEST_BODIES["model_forecast"])
async def model_forecast_v1(msg: Msg = Body(..., examples=MYOCYTE_EXAMPLES["model_forecast"])):
    """Model Forecast endpoint (API v1)."""
    return await _model_forecast_handler(msg)

@app.post("/v1/export", response_model=Reply, openapi_extra=MYOCYTE_REQUEST_BODIES["export"])
async def export__v1(msg: Msg = Body(..., examples=MYOCYTE_EXAMPLES["export"])):
    """Export  endpoint (API v1)."""
    return await _export__handler(msg)
# ============================================================================
# Legacy Endpoints (Backward Compatibility)
# ============================================================================

@app.post("/ingest_table", response_model=Reply, deprecated=True, openapi_extra=MYOCYTE_REQUEST_BODIES["ingest_table"])
async def ingest_table_legacy(msg: Msg = Body(..., examples=MYOCYTE_EXAMPLES["ingest_table"])):
    """
    DEPRECATED: Use /v1/ingest_table instead.
    Ingest Table endpoint.
    """
    logger.warning("Deprecated endpoint /ingest_table used. Please migrate to /v1/ingest_table")
    return await _ingest_table_handler(msg)

@app.post("/formula_eval", response_model=Reply, deprecated=True, openapi_extra=MYOCYTE_REQUEST_BODIES["formula_eval"])
async def formula_eval_legacy(msg: Msg = Body(..., examples=MYOCYTE_EXAMPLES["formula_eval"])):
    """
    DEPRECATED: Use /v1/formula_eval instead.
    Formula Eval endpoint.
    """
    logger.warning("Deprecated endpoint /formula_eval used. Please migrate to /v1/formula_eval")
    return await _formula_eval_handler(msg)

@app.post("/model_forecast", response_model=Reply, deprecated=True, openapi_extra=MYOCYTE_REQUEST_BODIES["model_forecast"])
async def model_forecast_legacy(msg: Msg = Body(..., examples=MYOCYTE_EXAMPLES["model_forecast"])):
    """
    DEPRECATED: Use /v1/model_forecast instead.
    Model Forecast endpoint.
    """
    logger.warning("Deprecated endpoint /model_forecast used. Please migrate to /v1/model_forecast")
    return await _model_forecast_handler(msg)

@app.post("/export", response_model=Reply, deprecated=True, openapi_extra=MYOCYTE_REQUEST_BODIES["export"])
async def export__legacy(msg: Msg = Body(..., examples=MYOCYTE_EXAMPLES["export"])):
    """
    DEPRECATED: Use /v1/export instead.
    Export  endpoint.
    """
    logger.warning("Deprecated endpoint /export used. Please migrate to /v1/export")
    return await _export__handler(msg)
