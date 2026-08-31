import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from groq import Groq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dataset import load_dataset, run_query, describe_dataset, TOOLS
from memory.working import WorkingMemory
from harness.context import ContextBuilder
from harness.runtime import ToolRuntime
from harness.validator import Validator, ValidationContext
from tracing.tracer import Tracer, TraceRun
import tools.dataset as dataset_module

MODEL = "openai/gpt-oss-20b"
client = Groq(api_key=os.environ["GROQ_API_KEY"])

FUNCTIONS = {
    "load_dataset": load_dataset,
    "run_query": run_query,
    "describe_dataset": describe_dataset,
}

tool_runtime = ToolRuntime()
tool_runtime.register_all(FUNCTIONS, TOOLS)

validator = Validator()
tracer = Tracer()

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": {
                "type": "object",
                "properties": t["input_schema"]["properties"],
                "required": t["input_schema"].get("required", []),
            },
        },
    }
    for t in TOOLS
]

SYSTEM_PROMPT = "You are a data analysis agent. Use the available tools to inspect and query datasets."

context_builder = ContextBuilder(system_instructions=SYSTEM_PROMPT)


def run_agent(
    user_message: str,
    memory: WorkingMemory | None = None,
    trace: Tracer | None = None,
    run_id: str | None = None,
    max_iterations: int = 5,
) -> str:
    """Run the agent loop with a bounded number of LLM iterations.

    Each iteration consists of one LLM call followed by processing its
    response (executing tool calls, validating results). The loop stops
    when the LLM returns no tool calls, or when ``max_iterations`` is
    reached.

    Args:
        user_message: The user's input message.
        memory: Optional working memory to persist state across calls.
        trace: Optional tracer for observability.
        run_id: Optional run identifier for tracing.
        max_iterations: Maximum number of LLM iterations (default: 5).
            Must be a positive integer.

    Returns:
        The final response content from the LLM, or a graceful message
        if the iteration limit was reached.

    Raises:
        ValueError: If ``max_iterations`` is not a positive integer.
    """
    if not isinstance(max_iterations, int) or max_iterations <= 0:
        raise ValueError("max_iterations must be a positive integer")

    if memory is None:
        memory = WorkingMemory()

    if trace is None:
        trace = Tracer()

    trace.start_run(run_id=run_id)

    # Seed memory with current user input
    memory.set_task(user_message)
    memory.add_message("user", user_message)

    if not any(m.get("role") == "system" for m in memory.messages):
        memory.messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    try:
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            # Build context for this turn
            context = context_builder.build(memory, tools=TOOLS)
            trace.log(
                "context_built",
                metadata={
                    "message_count": len(context.to_messages()),
                    "tool_count": len(TOOLS),
                    "dataset_available": memory.dataset is not None,
                },
            )

            llm_start = time.perf_counter()
            resp = client.chat.completions.create(
                model=MODEL,
                messages=context.to_messages(),
                tools=TOOLS_OPENAI,
                tool_choice="auto",
            )
            llm_duration_ms = round((time.perf_counter() - llm_start) * 1000, 2)
            trace.log(
                "llm_call",
                metadata={"provider": "groq", "model": MODEL},
                duration_ms=llm_duration_ms,
                status="success",
            )

            msg = resp.choices[0].message
            memory.add_assistant_message(msg.model_dump(exclude_unset=True))

            tool_calls = msg.tool_calls
            if not tool_calls:
                trace.log("response_generated", metadata={"length": len(msg.content or "")})
                trace.end_run(status="success")
                return msg.content

            for tc in tool_calls:
                fn_name = tc.function.name
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                if args is None:
                    args = {}

                trace.log("tool_call", metadata={"tool": fn_name, "arguments": args})

                # Execute the tool through the runtime (execution boundary)
                exec_result = tool_runtime.execute(fn_name, args)
                result = exec_result.as_dict()

                # Validate the result before trusting it
                ctx = ValidationContext(dataset=dataset_module._df)
                validation = validator.validate(exec_result, context=ctx)

                # Record tool outcome in working memory
                memory.add_tool_result(fn_name, args, result)

                # Attach validation result to the most recent tool result
                if memory.tool_results:
                    memory.tool_results[-1].validation = validation
                memory.add_validation_result(validation)

                trace.log(
                    "tool_completed",
                    metadata={
                        "tool": fn_name,
                        "success": exec_result.success,
                        "error_type": exec_result.error_type,
                    },
                    duration_ms=exec_result.duration_ms,
                    status="success" if exec_result.success else "error",
                )

                trace.log(
                    "validation",
                    metadata={
                        "validator": validation.validator_name,
                        "valid": validation.valid,
                        "expected": validation.expected,
                        "actual": validation.actual,
                    },
                    status="passed" if validation.valid else "failed",
                )

                # If this was a dataset load, extract and store metadata
                if fn_name == "load_dataset" and result.get("success"):
                    data = result.get("data", {})
                    ds_info = {
                        "name": args.get("name") or args.get("path"),
                        "sources": args.get("path"),
                        "row_count": data.get("row_count"),
                        "columns": data.get("columns", []),
                        "preview": data.get("preview", []),
                    }
                    memory.set_dataset(ds_info)

                # If validation failed, surface the failure to the agent so it
                # can retry / correct, without silently replacing the result.
                if not validation.valid:
                    memory.add_message(
                        "user",
                        f"VALIDATION FAILED for '{fn_name}'.\n"
                        f"Validator: {validation.validator_name}\n"
                        f"Expected: {validation.expected}\n"
                        f"Actual:   {validation.actual}\n"
                        f"Error: {validation.error or 'N/A'}\n"
                        f"Please recalculate or correct the result.",
                    )

                # Update messages for the next LLM call
                memory.add_tool_message(tc.id, str(result))

            # Check if we've reached the iteration limit after processing tool calls
            if iteration >= max_iterations:
                trace.log(
                    "max_iterations_reached",
                    metadata={"max_iterations": max_iterations, "final_iteration": iteration},
                )
                trace.end_run(status="stopped")
                return (
                    f"Agent stopped after reaching the maximum number of iterations ({max_iterations}). "
                    "The task may be incomplete. Please refine your request or try again."
                )

    except Exception as exc:
        trace.log(
            "error",
            metadata={
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        )
        trace.end_run(status="failed")
        raise


if __name__ == "__main__":
    memory = WorkingMemory()
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except EOFError:
            break
        if not user_input:
            continue
        response = run_agent(user_input, memory)
        print(f"\nAgent: {response}")
