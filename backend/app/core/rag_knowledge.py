import json
import os
from typing import List

PROJECT_ROOT = r"C:\Users\Rezi\.gemini\antigravity\scratch\basetune_architect"
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


class RagKnowledgeBase:
    """
    Enhanced RAG knowledge base that loads structured JSON datasets
    from data/ directories (injectors, sensors, turbos, historical tuning, etc.)
    and serves them as context for the LLM adapter.
    """
    
    def __init__(self):
        self.documents = []
        self._load_static_documents()
        self._load_json_datasets()

    def _load_static_documents(self):
        """Load hardcoded tuning knowledge documents."""
        self.documents.extend([
            {
                "topic": "B-series optimal ignition",
                "content": "For Honda B18C engines on 93 octane, optimal MBT starts around 28-30 degrees at WOT near 6000 RPM. Avoid exceeding 32 degrees under load to prevent knock. Retard timing by 1 degree per 10 kPa of boost."
            },
            {
                "topic": "E85 Fuel Behavior",
                "content": "E85 allows for much leaner safe cruise but requires approximately 30-35% more fuel volume overall. Target AFR under boost on E85 can safely be 11.5 to 11.8."
            },
            {
                "topic": "K-series timing",
                "content": "Honda K-series engines respond well to timing but are knock limited on pump gas. VTC advance should be reduced at high boost."
            },
            {
                "topic": "Idle stability",
                "content": "For stable idle on large injectors (1000cc+), ensure deadtime curves are accurate. Target idle AFR of 13.5-14.2 on gas, or 14.5 on E85. Lower ignition timing (10-15 degrees) helps stabilize idle by retaining torque reserve."
            }
        ])

    def _load_json_datasets(self):
        """Scan data/ directory for JSON files and ingest them as RAG documents."""
        if not os.path.exists(DATA_DIR):
            return

        for root, _, files in os.walk(DATA_DIR):
            for f in files:
                if f.endswith(".json"):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r") as fh:
                            data = json.load(fh)
                        
                        # Use either the "description" field or derive topic from filename
                        topic = data.get("description", f.replace(".json", "").replace("_", " ").title()) if isinstance(data, dict) else f.replace(".json", "").replace("_", " ").title()
                        
                        # Serialize the entire JSON as the content (compact)
                        content = json.dumps(data, indent=None)
                        
                        # Determine the category from the path
                        rel_path = os.path.relpath(root, DATA_DIR)
                        
                        self.documents.append({
                            "topic": f"{topic} ({rel_path})",
                            "content": content[:2000],  # Limit to 2000 chars per document for prompt budget
                            "source_file": filepath
                        })
                    except Exception as e:
                        print(f"Warning: could not load {filepath}: {e}")

    def retrieve_context(self, profile_make: str, profile_family: str, fuel_type: str) -> str:
        """
        Keyword-based retrieval. Returns formatted string of the most relevant documents.
        """
        relevant_docs = []
        query_terms = [
            profile_make.lower(), 
            profile_family.lower(), 
            fuel_type.lower(), 
            "optimal", "timing", "base", "knock", "injector", "ve"
        ]

        for doc in self.documents:
            topic_lower = doc["topic"].lower()
            content_lower = doc["content"].lower()
            
            # Weighted scoring
            score = 0
            for term in query_terms:
                # Topic match is higher weight
                if term in topic_lower:
                    score += 5
                # Exact engine/fuel matches are high weight
                if term in [profile_make.lower(), profile_family.lower(), fuel_type.lower()]:
                    if term in content_lower:
                        score += 10
                elif term in content_lower:
                    score += 1
            
            if score > 0:
                relevant_docs.append((score, doc))

        # Sort by relevance, take top 10
        relevant_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = [d for _, d in relevant_docs[:10]]

        if not top_docs:
            return "No specific knowledge documents found for this profile."

        context = ""
        for d in top_docs:
            context += f"--- Document: {d['topic']} ---\n{d['content']}\n\n"

        return context


if __name__ == "__main__":
    kb = RagKnowledgeBase()
    print(f"Loaded {len(kb.documents)} documents into RAG knowledge base.")
    print("\nTest retrieval for Honda B18C 93 Octane:")
    ctx = kb.retrieve_context("Honda", "B18C", "93 Octane")
    print(ctx[:1000] + "...")
