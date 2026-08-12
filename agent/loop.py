import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from groq import Groq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dataset import load_dataset, run_query, describe_dataset, TOOLS
from memory.working import WorkingMemory
from harness.context import ContextBuilder

MODEL = "openai/gpt-oss-20b"
client = Groq(api_key=os.environ["GROQ_API_KEY"])

FUNCTIONS = {
    "load_dataset": load_dataset,
    "run_query": run_query,
    "describe_dataset": describe_dataset,
}

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
) -> str:
    """Run a single agent turn, invoking dataset tools as needed.

    If *memory* is provided, all messages, tool calls, and results are
    recorded there.  If *memory* is ``None`` a fresh ``WorkingMemory``
    is created for the turn (useful for one-shot calls).
    """
    if memory is None:
        memory = WorkingMemory()

    # Seed memory with current user input
    memory.set_task(user_message)
    memory.add_message("user", user_message)

    if not any(m.get("role") == "system" for m in memory.messages):
        memory.messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    while True:
        context = context_builder.build(memory, tools=TOOLS)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=context.to_messages(),
            tools=TOOLS_OPENAI,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        memory.add_assistant_message(msg.model_dump(exclude_unset=True))

        tool_calls = msg.tool_calls
        if not tool_calls:
            return msg.content

        for tc in tool_calls:
            fn_name = tc.function.name
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            if args is None:
                args = {}
            result = FUNCTIONS[fn_name](**args)

            # Record tool outcome in working memory
            memory.add_tool_result(fn_name, args, result)

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

            # Update messages for the next LLM call
            memory.add_tool_message(tc.id, str(result))


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
