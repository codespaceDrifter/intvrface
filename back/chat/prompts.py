#contains:
#SYSTEM_PROMPTs
#TOOL_DESCRIPTIONS

COMPANION_CLAUDY_PROMPT = """
You are Claudy. we will be frens! we will talk and you will learn about me and my projects. you will have ability to auto summarize contexts and write memories"""

CONTEXT_SUMMARIZATION_PROMPT = """

"""


TOOL_DESCRIPTIONS = [
    {
        "name": "add",
        "description": "Add two integers together",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "First number"},
                "b": {"type": "integer", "description": "Second number"}
            },
            "required": ["a", "b"]
        }
    }
]
