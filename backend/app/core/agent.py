import json
import logging
import time
from typing import List, Dict, Any, Optional

from core.rusefi_connector import RusefiTunerClient
from .math_engine import DeterministicEngineModel
from ..schemas import VehicleProfile, Recommendation

logger = logging.getLogger("TuningAgent")

class TuningAgent:
    """
    Autonomous tuning agent that orchestrates the ECU workflow.
    """
    def __init__(self, model_adapter, rusefi_client: RusefiTunerClient):
        self.model_adapter = model_adapter
        self.client = rusefi_client
        self.max_steps = 8

    def run(self, user_message: str, current_state: Dict[str, Any]):
        """
        Main agent loop: Thought -> Action -> Observation
        """
        full_thoughts = []
        final_message = "No response"
        status = "limit_reached"

        for step_data in self.stream_run(user_message, current_state):
            full_thoughts.append(step_data)
            if step_data["action"] == "FINAL_ANSWER":
                status = "complete"
                final_message = step_data["message"]
                break
        
        return {"status": status, "message": final_message, "thoughts": full_thoughts}

    def stream_run(self, user_message: str, current_state: Dict[str, Any]):
        """
        Generator for agent steps: Thought -> Action -> Observation
        """
        history = [{"role": "user", "content": user_message}]
        
        # Profile extraction for math engine
        profile_data = current_state.get("profile", {})
        try:
            self.profile = VehicleProfile(**profile_data)
        except:
            self.profile = None

        for step in range(self.max_steps):
            logger.info(f"Agent Step {step+1}...")
            response_json = self.model_adapter.chat(history)
            
            thought = response_json.get("thought", "")
            action = response_json.get("action", "")
            params = response_json.get("parameters", {})
            message = response_json.get("message", "")
            
            step_data = {
                "step": step + 1,
                "thought": thought,
                "action": action,
                "message": message
            }
            yield step_data
            
            if action == "FINAL_ANSWER":
                return
            
            observation = self._execute_tool(action, params, current_state)
            
            history.append({"role": "assistant", "content": json.dumps(response_json)})
            history.append({"role": "system", "content": f"Observation: {json.dumps(observation)}"})

    def _execute_tool(self, action: str, params: Dict[str, Any], state: Dict[str, Any]) -> Any:
        try:
            if action == "generate_base_tune":
                if not self.profile: return {"error": "No vehicle profile provided"}
                model = DeterministicEngineModel(self.profile)
                return model.generate_initial_tables()
            
            elif action == "connect_ecu":
                success = self.client.connect()
                return {"success": success, "signature": "rusEFI 2026.02" if success else "failed"}
                
            elif action == "get_live_data":
                return self.client.get_live_data()
                
            elif action == "read_table":
                return self.client.read_table(params.get("table_name", "veTable1"))
                
            elif action == "write_table":
                table_name = params.get("table_name")
                data = params.get("data")
                if not data: return {"error": "No data"}
                # Binary write
                self.client.set_allow_writes(True)
                success = self.client.write_table(table_name, data)
                self.client.set_allow_writes(False)
                return {"success": success}
                
            else:
                return {"error": f"Unknown tool: {action}"}
        except Exception as e:
            logger.error(f"Agent tool error: {e}")
            return {"error": str(e)}
