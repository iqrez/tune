import json
import logging
from typing import List, Dict, Optional, Any
from openai import OpenAI
from ..schemas import AnalysisRequest, Recommendation
from .prompts import TUNER_SYSTEM_PROMPT

logger = logging.getLogger("ModelAdapter")

class LocalModelAdapter:
    """
    Enhanced LLM adapter for Ollama/Local Inference.
    Uses the expert TUNER_SYSTEM_PROMPT and enforces structured JSON output.
    """
    def __init__(self, base_url: str = "http://localhost:11434/v1", api_key: str = "ollama", model_name: str = "llama3"):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name

    def chat(self, messages: List[Dict[str, str]], system_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Base chat method that takes full message history.
        """
        sys_msg = [{"role": "system", "content": system_override or TUNER_SYSTEM_PROMPT}]
        full_messages = sys_msg + messages

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=full_messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return {"thought": str(e), "action": "FINAL_ANSWER", "message": "Connection error."}

    def analyze_datalog(self, request: AnalysisRequest, rag_context: str) -> List[Recommendation]:
        """
        Specialized method for tuning analysis.
        """
        user_content = f"Analyze: {request.datalog_summary.model_dump_json()} Context: {rag_context}"
        result = self.chat([{"role": "user", "content": user_content}])
        
        recs_data = result.get("parameters", {}).get("recommendations", [])
        try:
            return [Recommendation(**r) for r in recs_data]
        except Exception as e:
            logger.error(f"Conversion Error: {e}")
            return []
