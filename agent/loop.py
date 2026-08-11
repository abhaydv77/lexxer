import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from groq import Groq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dataset import load_dataset, run_query, describe_dataset, TOOLS

MODEL = "llama-3.3-70b-versatile"
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


def run_agent(user_message: str, history: list[dict] | None = None) -> str:
    """Run a single agent turn, invoking dataset tools as needed."""
    messages = history or []
    messages.append({"role": "user", "content": user_message})

    while True:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_OPENAI,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_unset=True))

        tool_calls = msg.tool_calls
        if not tool_calls:
            return msg.content

        for tc in tool_calls:
            fn_name = tc.function.name
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            result = FUNCTIONS[fn_name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })


if __name__ == "__main__":
    history = []
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except EOFError:
            break
        if not user_input:
            continue
        response = run_agent(user_input, history)
        print(f"\nAgent: {response}")
