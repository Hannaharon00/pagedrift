"""
Validation/typing layer for the LLM config dict stored at
    datastore.data['settings']['application']['llm']

Storage stays a plain dict (orjson-serialized). This model is hydrated on read
(model_validate) and dumped on write (model_dump). WTForms field names match
the storage field names exactly — no aliases needed.
"""
from typing import ClassVar, Tuple

from pydantic import BaseModel, ConfigDict


