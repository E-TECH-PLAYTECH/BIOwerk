from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
from matrix.logging_config import setup_logging, log_request, log_response, log_error
from matrix.errors import InvalidInputError, create_error_response
from matrix.llm_client import llm_client
import time
import json

app = FastAPI(title="Synapse")
setup_instrumentation(app, service_name="synapse", service_version="1.0.0")
logger = setup_logging("synapse")

# Setup comprehensive health and readiness endpoints
from matrix.health import setup_health_endpoints
setup_health_endpoints(app, service_name="synapse", version="1.0.0")

@app.post("/storyboard", response_model=Reply)
async def storyboard(msg: Msg):
    """Generate a storyboard (slide outline) for a presentation."""
    start_time = time.time()
    log_request(logger, msg.id, "synapse", "storyboard")

    try:
        inp = msg.input or {}
        topic = inp.get("topic", "")
        goal = inp.get("goal", "")
        audience = inp.get("audience", "general")
        num_slides = inp.get("num_slides", 10)

        if not topic and not goal:
            raise InvalidInputError("Topic or goal is required")

        # Generate storyboard using LLM
        system_prompt = """You are an expert presentation designer. Create a compelling storyboard for a presentation.
Return your response as a JSON object with a 'storyboard' array containing slide objects.
Each slide should have: title, description, and slide_type (title, content, image, data, conclusion).
Example: {"storyboard": [{"title": "Introduction", "description": "Hook audience with key problem", "slide_type": "title"}]}"""

        prompt = f"""Create a storyboard for a {num_slides}-slide presentation:

Topic: {topic or goal}
Audience: {audience}
{f"Goal: {goal}" if goal and topic else ""}

Generate a compelling storyboard with diverse slide types."""

        response_text = await llm_client.generate_json(
            prompt=prompt,
            system_prompt=system_prompt
        )

        output = json.loads(response_text)

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "synapse", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        # Fallback output
        output = {"storyboard": [{"title": "Introduction", "description": topic or goal, "slide_type": "title"}]}
        return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "synapse", e))

@app.post("/slide_make", response_model=Reply)
async def slide_make(msg: Msg):
    """Generate actual slide content from storyboard."""
    start_time = time.time()
    log_request(logger, msg.id, "synapse", "slide_make")

    try:
        inp = msg.input or {}
        storyboard = inp.get("storyboard", [])
        topic = inp.get("topic", "")

        if not storyboard:
            raise InvalidInputError("Storyboard is required")

        # Generate slides using LLM
        system_prompt = """You are an expert presentation content writer. Create detailed slide content based on the storyboard.
Return your response as a JSON object with 'slides' array containing slide objects.
Each slide should have: id, title, content (array of bullet points or paragraphs), and slide_type.
Also include 'speaker_notes' array with notes for each slide.
Example: {
  "slides": [{"id": "slide-1", "title": "Introduction", "content": ["Point 1", "Point 2"], "slide_type": "content"}],
  "speaker_notes": ["Introduce yourself and the topic..."]
}"""

        storyboard_text = json.dumps(storyboard, indent=2)

        prompt = f"""Create detailed slide content for this storyboard:

Topic: {topic}

Storyboard:
{storyboard_text}

Generate complete slides with content and speaker notes."""

        response_text = await llm_client.generate_json(
            prompt=prompt,
            system_prompt=system_prompt
        )

        output = json.loads(response_text)

        # Add layout graph (simple sequential layout)
        num_slides = len(output.get("slides", []))
        layout_graph = {
            "nodes": [{"id": f"slide-{i}", "position": i} for i in range(num_slides)],
            "edges": [{"from": f"slide-{i}", "to": f"slide-{i+1}"} for i in range(num_slides - 1)]
        }
        output["layout_graph"] = layout_graph

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "synapse", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        # Fallback output
        output = {
            "slides": [{"id": "slide-1", "title": storyboard[0].get("title", "Slide 1"), "content": ["Content here"], "slide_type": "content"}],
            "layout_graph": {},
            "speaker_notes": ["Notes here"]
        }
        return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "synapse", e))

@app.post("/visualize", response_model=Reply)
async def visualize(msg: Msg):
    """Generate data visualization specifications."""
    start_time = time.time()
    log_request(logger, msg.id, "synapse", "visualize")

    try:
        inp = msg.input or {}
        data = inp.get("data", [])
        description = inp.get("description", "")
        viz_type = inp.get("viz_type", "auto")

        if not data and not description:
            raise InvalidInputError("Data or description is required")

        # Generate visualization spec using LLM
        system_prompt = """You are a data visualization expert. Create appropriate visualization specifications.
Return your response as a JSON object with 'viz' containing: type (bar, line, pie, scatter, etc.), data, labels, and config.
Example: {
  "viz": {
    "type": "bar",
    "data": [10, 20, 30],
    "labels": ["A", "B", "C"],
    "config": {"title": "Chart Title", "xLabel": "X Axis", "yLabel": "Y Axis"}
  }
}"""

        if data:
            prompt = f"""Create a visualization specification for this data:

Data: {json.dumps(data)}
{f"Description: {description}" if description else ""}
{f"Preferred type: {viz_type}" if viz_type != "auto" else ""}

Choose the best visualization type and generate the complete spec."""
        else:
            prompt = f"""Create a visualization specification based on this description:

Description: {description}
{f"Preferred type: {viz_type}" if viz_type != "auto" else ""}

Generate sample data and visualization spec."""

        response_text = await llm_client.generate_json(
            prompt=prompt,
            system_prompt=system_prompt
        )

        output = json.loads(response_text)

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "synapse", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        # Fallback output
        output = {"viz": {"type": "bar", "data": data or [1, 2, 3], "labels": ["A", "B", "C"]}}
        return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "synapse", e))

@app.post("/export", response_model=Reply)
async def export_(msg: Msg):
    """Export the complete presentation artifact."""
    start_time = time.time()
    log_request(logger, msg.id, "synapse", "export")

    try:
        inp = msg.input or {}
        title = inp.get("title", "Untitled Presentation")
        slides = inp.get("slides", [])
        layout_graph = inp.get("layout_graph", {})
        notes = inp.get("notes", [])
        metadata = inp.get("metadata", {})

        output = {
            "artifact": {
                "kind": "synslide",
                "meta": {
                    "title": title,
                    "created_at": time.time(),
                    **metadata
                },
                "body": {
                    "slides": slides,
                    "layout_graph": layout_graph,
                    "notes": notes
                }
            }
        }

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "synapse", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "synapse", e))
