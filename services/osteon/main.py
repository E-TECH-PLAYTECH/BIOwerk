from fastapi import FastAPI, HTTPException
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
from matrix.logging_config import setup_logging, log_request, log_response, log_error
from matrix.errors import InvalidInputError, create_error_response
from matrix.llm_client import llm_client
import time
import json

app = FastAPI(title="Osteon")
setup_instrumentation(app)
logger = setup_logging("osteon")

# State to track sections across requests
session_state = {}

@app.post("/outline", response_model=Reply)
async def outline(msg: Msg):
    """Generate a structured outline for a document based on the goal/topic."""
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "outline")

    try:
        inp = msg.input or {}
        goal = inp.get("goal", "")
        topic = inp.get("topic", goal)
        context = inp.get("context", "")

        if not topic:
            raise InvalidInputError("Topic or goal is required")

        # Generate outline using LLM
        system_prompt = """You are an expert content strategist. Generate a detailed, well-structured outline for the given topic.
Return your response as a JSON object with an 'outline' array containing section titles.
Each section should be a string representing a major section or chapter title.
Example: {"outline": ["Introduction", "Background", "Main Analysis", "Case Studies", "Conclusions"]}"""

        prompt = f"""Create a detailed outline for the following topic:

Topic: {topic}
{f"Context: {context}" if context else ""}

Generate a comprehensive outline with 5-8 main sections that would make for a well-structured document."""

        response_text = await llm_client.generate_json(
            prompt=prompt,
            system_prompt=system_prompt
        )

        output = json.loads(response_text)

        # Store outline in session state
        session_state[msg.id] = {"outline": output.get("outline", [])}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        # Fallback output
        output = {"outline": ["Introduction", "Main Content", "Conclusion"]}
        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))

@app.post("/draft", response_model=Reply)
async def draft(msg: Msg):
    """Generate draft content for sections."""
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "draft")

    try:
        inp = msg.input or {}
        goal = inp.get("goal", "")
        section_title = inp.get("section_title", "")
        outline = inp.get("outline", [])
        context = inp.get("context", "")

        if not goal and not section_title:
            raise InvalidInputError("Goal or section_title is required")

        # Generate content using LLM
        system_prompt = """You are an expert writer. Generate high-quality, detailed content for the given section.
Your writing should be clear, informative, and well-structured."""

        if section_title:
            prompt = f"""Write detailed content for the following section:

Section Title: {section_title}
{f"Overall Goal: {goal}" if goal else ""}
{f"Document Outline: {', '.join(outline)}" if outline else ""}
{f"Context: {context}" if context else ""}

Write 2-3 paragraphs of high-quality content for this section."""
        else:
            prompt = f"""Write an introductory section for a document with the following goal:

Goal: {goal}
{f"Outline: {', '.join(outline)}" if outline else ""}
{f"Context: {context}" if context else ""}

Write 2-3 paragraphs introducing the topic and setting the stage."""

        content_text = await llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt
        )

        sections = [{
            "id": f"s_{int(time.time())}",
            "title": section_title or "Introduction",
            "text": content_text.strip()
        }]

        output = {
            "sections": sections,
            "toc": [s["title"] for s in sections],
            "citations": []
        }

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))

@app.post("/edit", response_model=Reply)
async def edit(msg: Msg):
    """Edit and improve content based on feedback."""
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "edit")

    try:
        inp = msg.input or {}
        original_text = inp.get("text", "")
        feedback = inp.get("feedback", "")
        edit_type = inp.get("edit_type", "improve")

        if not original_text:
            raise InvalidInputError("Text is required for editing")

        # Generate edited content using LLM
        system_prompt = """You are an expert editor. Review and improve the given text based on the feedback provided.
Return the edited version of the text."""

        if feedback:
            prompt = f"""Edit the following text based on this feedback:

Feedback: {feedback}

Original Text:
{original_text}

Provide the improved version of the text."""
        else:
            edit_instructions = {
                "improve": "Improve the clarity, flow, and quality of the text.",
                "shorten": "Make the text more concise while preserving key information.",
                "expand": "Expand the text with more detail and examples.",
                "formalize": "Make the tone more formal and professional.",
                "simplify": "Simplify the language to make it more accessible."
            }

            instruction = edit_instructions.get(edit_type, edit_instructions["improve"])

            prompt = f"""{instruction}

Original Text:
{original_text}

Provide the edited version."""

        edited_text = await llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt
        )

        output = {
            "edited_text": edited_text.strip(),
            "original_text": original_text,
            "diff": "text_replaced"
        }

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))

@app.post("/summarize", response_model=Reply)
async def summarize(msg: Msg):
    """Summarize content."""
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "summarize")

    try:
        inp = msg.input or {}
        text = inp.get("text", "")
        sections = inp.get("sections", [])
        max_length = inp.get("max_length", "medium")

        if not text and not sections:
            raise InvalidInputError("Text or sections are required for summarization")

        # Combine sections if provided
        if sections:
            text = "\n\n".join([f"{s.get('title', '')}\n{s.get('text', '')}" for s in sections])

        # Generate summary using LLM
        system_prompt = """You are an expert at creating concise, informative summaries.
Extract the key points and present them clearly."""

        length_guidance = {
            "short": "in 2-3 sentences",
            "medium": "in 1-2 paragraphs",
            "long": "in 3-4 paragraphs"
        }

        guidance = length_guidance.get(max_length, length_guidance["medium"])

        prompt = f"""Summarize the following text {guidance}:

{text}

Provide a clear, comprehensive summary."""

        summary_text = await llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt
        )

        output = {
            "summary": summary_text.strip(),
            "length": max_length,
            "original_length": len(text)
        }

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))

@app.post("/export", response_model=Reply)
async def export_(msg: Msg):
    """Export the complete artifact with all sections."""
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "export")

    try:
        inp = msg.input or {}
        title = inp.get("title", "Untitled Document")
        sections = inp.get("sections", [])
        metadata = inp.get("metadata", {})

        output = {
            "artifact": {
                "kind": "osteon",
                "meta": {
                    "title": title,
                    "created_at": time.time(),
                    **metadata
                },
                "body": {
                    "sections": sections,
                    "toc": [s.get("title", "") for s in sections]
                }
            }
        }

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))
