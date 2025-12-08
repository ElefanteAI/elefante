"""
LLM Service for Elefante
Handles interactions with Language Models (OpenAI, etc.) for memory consolidation and curation.
"""

import json
import os
from typing import List, Dict, Any, Optional
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # Graceful fallback

from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

class LLMService:
    """
    Service for interacting with LLMs.
    Currently supports OpenAI compatible APIs.
    """
    
    def __init__(self):
        self.config = get_config()
        self.client = None
        self.model = self.config.elefante.llm.model
        self._initialize_client()
        
    def _initialize_client(self):
        """Initialize OpenAI client"""
        if AsyncOpenAI is None:
             logger.warning("OpenAI module not installed. LLM features disabled.")
             return

        api_key = self.config.elefante.llm.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("No LLM API key found. LLM features will be disabled.")
            return
            
        self.client = AsyncOpenAI(api_key=api_key)
        logger.info(f"LLM Service initialized with model: {self.model}")

    async def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a text response from the LLM"""
        if not self.client:
            return "LLM Service not configured."

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.elefante.llm.temperature,
                max_tokens=self.config.elefante.llm.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return f"Error generating response: {e}"

    async def extract_entities(self, content: str) -> List[Dict[str, str]]:
        """
        Extract entities and tags from content using LLM.
        Returns a list of dicts: {"name": "X", "type": "Y"}
        """
        if not self.client:
            return []

        system_prompt = """
        You are an expert knowledge graph engineer. Extract key entities from the user's text.
        Return ONLY a JSON array of objects with 'name' and 'type' fields.
        Types should be one of: person, project, technology, organization, location, event, concept, file, task.
        Example: [{"name": "Elefante", "type": "project"}, {"name": "Python", "type": "technology"}]
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            result = json.loads(response.choices[0].message.content)
            # Handle both {"entities": [...]} and [...] formats
            if "entities" in result:
                return result["entities"]
            elif isinstance(result, list):
                return result
            else:
                # Try to find a list in the values
                for val in result.values():
                    if isinstance(val, list):
                        return val
                return []
                
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []

    async def analyze_memory(self, content: str) -> Dict[str, Any]:
        """
        Analyze memory content to extract deep cognitive structure.
        Returns a dictionary matching the CognitiveAnalysis schema.
        """
        if not self.client:
            # Fallback for no API key
            return {
                "title": content[:50] + "..." if len(content) > 50 else content,
                "summary": content,
                "intent": "statement",
                "emotional_context": {"valence": 0.0, "arousal": 0.0, "mood": "Neutral"},
                "entities": [],
                "relationships": [],
                "strategic_insight": None,
                "action": "ADD"
            }

        system_prompt = """
        You are the Cortex of an advanced AI memory system. 
        Analyze the incoming memory to extract its "Cognitive Delta"—the structural change it imposes on the World Model.
        
        Output JSON ONLY matching this schema:
        {
            "title": "Concise, semantic title (e.g., 'User Language Preference')",
            "summary": "Brief summary of the content",
            "intent": "teaching" | "venting" | "planning" | "reflecting" | "deciding" | "querying" | "statement",
            "emotional_context": {
                "valence": float (-1.0 to 1.0),
                "arousal": float (0.0 to 1.0),
                "mood": "string (e.g., Frustrated, Determined)"
            },
            "entities": [
                {"name": "EntityName", "type": "Type", "description": "Context"}
            ],
            "relationships": [
                {"source": "EntityName", "target": "EntityName", "type": "RELATIONSHIP_TYPE", "reason": "Context"}
            ],
            "strategic_insight": "Actionable takeaway or rule (optional)",
            "action": "ADD" | "UPDATE" | "IGNORE"
        }
        
        RELATIONSHIP GUIDELINES:
        - Use semantic types: LOVES, HATES, BLOCKS, ENABLES, DEPENDS_ON, IS_A, HAS_PART.
        - Connect the 'User' entity to concepts they express opinions about.
        
        Example Input: "I hate Python's GIL, it slows everything down. We should use Rust."
        Example Output:
        {
            "title": "Python GIL vs Rust",
            "summary": "User expresses frustration with Python's GIL performance and suggests Rust as an alternative.",
            "intent": "deciding",
            "emotional_context": {"valence": -0.6, "arousal": 0.7, "mood": "Frustrated"},
            "entities": [
                {"name": "User", "type": "Person"},
                {"name": "Python", "type": "Technology"},
                {"name": "Rust", "type": "Technology"},
                {"name": "GIL", "type": "Concept"}
            ],
            "relationships": [
                {"source": "User", "target": "Python", "type": "DISLIKES", "reason": "GIL performance"},
                {"source": "User", "target": "Rust", "type": "PREFERS", "reason": "Performance"},
                {"source": "Python", "target": "GIL", "type": "HAS_PART"}
            ],
            "strategic_insight": "User prefers Rust over Python for performance-critical tasks due to GIL limitations.",
            "action": "ADD"
        }
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Memory analysis failed: {e}")
            # Fallback
            return {
                "title": content[:50] + "...",
                "summary": content,
                "intent": "statement",
                "emotional_context": {"valence": 0.0, "arousal": 0.0, "mood": "Error"},
                "entities": [],
                "relationships": [],
                "strategic_insight": None,
                "action": "ADD"
            }

    async def classify_memory(self, content: str, tags: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Auto-classify memory content into domain and category.
        Returns: {"domain": "work|personal|learning|project|reference|system", "category": "string"}
        """
        if not self.client:
            # Fallback: Use tags or default
            return {
                "domain": "reference",
                "category": tags[0] if tags else "general"
            }

        system_prompt = """
        You are a memory classification expert. Classify the given memory content.
        
        Return ONLY a JSON object with:
        {
            "domain": "work" | "personal" | "learning" | "project" | "reference" | "system",
            "category": "<string - specific topic like 'elefante', 'python', 'debugging', 'preferences', 'ai-ml'>"
        }
        
        DOMAIN DEFINITIONS:
        - work: Professional tasks, meetings, decisions, architecture
        - personal: Health, relationships, hobbies, personal preferences
        - learning: Tutorials, courses, research, educational content
        - project: Specific project work (identify project name as category)
        - reference: Documentation, APIs, best practices, general knowledge
        - system: System-generated metadata, internal operations
        
        CATEGORY GUIDELINES:
        - Use lowercase, hyphenated names (e.g., "ai-ml", "code-review")
        - Be specific but not too granular
        - If about a named project, use project name as category
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Content: {content}\nTags: {tags or []}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            result = json.loads(response.choices[0].message.content)
            return {
                "domain": result.get("domain", "reference"),
                "category": result.get("category", "general")
            }
            
        except Exception as e:
            logger.error(f"Memory classification failed: {e}")
            return {
                "domain": "reference",
                "category": tags[0] if tags else "general"
            }

    async def generate_semantic_title(
        self, 
        content: str, 
        layer: str = "world", 
        sublayer: str = "fact",
        max_chars: int = 30
    ) -> str:
        """
        Generate a semantic title in Subject-Aspect-Qualifier format.
        Max 30 chars, no truncation ever. Uses LLM for quality.
        
        Format: Subject-Aspect-Qualifier (separated by hyphens)
        Example: "DevEtiquette-CleanEnv-Protocol"
        """
        if not self.client:
            # Fallback: regex-based title generation
            return self._fallback_title(content, layer, sublayer, max_chars)

        system_prompt = f"""You are a semantic title generator for a "Second Brain" memory system.

Generate a title in format: Subject-Aspect-Qualifier
- Subject: The core topic (e.g., Python, MCP, DevEtiquette, Self)
- Aspect: The type/category (e.g., Preference, Method, Rule, Identity)
- Qualifier: The specific detail (e.g., TypeHints, Export, Clean)

CRITICAL RULES:
1. Maximum {max_chars} characters TOTAL including hyphens
2. NO SPACES - use CamelCase within each part
3. Separator is hyphen "-"
4. Capture the ESSENCE of the memory, not just keywords
5. If layer is 'self', Subject can be 'Self' or the specific identity aspect
6. If layer is 'intent', Aspect should be Rule/Goal/Protocol
7. If too long, drop Qualifier first, then shorten Aspect

8. DETERMINISM: Identical concepts MUST have identical titles.
9. QUALIFIER RULE: Use the OBJECT noun, NOT an adjective. 
   - BAD: "Self-Pref-Favorite" (Favorite what?)
   - BAD: "Self-Pref-Really" (Vague)
   - GOOD: "Self-Pref-Color" (Specific)
   - GOOD: "Self-Pref-ElectricBlue" (Specific)

EXAMPLES:
"I am a senior software architect" → "Self-Identity-Architect"
"I prefer Python type hints" → "Python-Pref-TypeHints"
"Always verify MCP actions before claiming done" → "MCP-Rule-Verification"
"I like my environment clean and non-redundant" → "DevEtiquette-CleanEnv"
"The project uses Kuzu for graph database" → "Project-Tech-Kuzu"
"I speak Spanish, French and English" → "Self-Languages-Trilingual"

Return ONLY the title string, nothing else."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Layer: {layer}, Sublayer: {sublayer}\nContent: {content}"}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            title = response.choices[0].message.content.strip()
            
            # Validation: ensure no truncation
            if len(title) > max_chars:
                # LLM failed constraint - try to fix
                parts = title.split('-')
                if len(parts) >= 3:
                    # Drop qualifier
                    title = f"{parts[0]}-{parts[1]}"
                if len(title) > max_chars and len(parts) >= 2:
                    # Shorten
                    title = parts[0][:max_chars]
            
            # Ensure no spaces
            title = title.replace(' ', '')
            
            return title[:max_chars]  # Final safety
            
        except Exception as e:
            logger.error(f"Title generation failed: {e}")
            return self._fallback_title(content, layer, sublayer, max_chars)

    def _fallback_title(self, content: str, layer: str, sublayer: str, max_chars: int = 30) -> str:
        """Regex-based fallback title generation when LLM unavailable."""
        import re
        
        # Extract key nouns/verbs
        content_lower = content.lower()
        
        # Subject mapping based on layer
        if layer == 'self':
            subject = 'Self'
        elif layer == 'intent':
            subject = 'Rule'
        else:
            # Try to extract a topic
            tech_match = re.search(r'\b(python|kuzu|chromadb|mcp|react|typescript|elefante)\b', content_lower)
            if tech_match:
                subject = tech_match.group(1).capitalize()
            else:
                subject = 'Memory'
        
        # Aspect from sublayer
        aspect_map = {
            'identity': 'Identity',
            'preference': 'Pref',
            'constraint': 'Limit',
            'fact': 'Fact',
            'failure': 'Debug',
            'method': 'Method',
            'rule': 'Rule',
            'goal': 'Goal',
            'anti-pattern': 'Avoid'
        }
        aspect = aspect_map.get(sublayer, 'Info')
        
        # Qualifier: first significant noun (skip stop words)
        words = re.findall(r'\b[A-Za-z]{4,}\b', content)
        skip_words = {
            'really', 'actually', 'favorite', 'definitely', 'probably', 
            'however', 'because', 'should', 'would', 'could', 'about',
            'think', 'guess', 'maybe', 'having', 'making', 'doing'
        }
        
        qualifier = 'Gen'
        for w in words:
            if w.lower() not in skip_words:
                qualifier = w[:8].capitalize()
                break
        
        # Build title respecting max_chars
        title = f"{subject}-{aspect}-{qualifier}"
        if len(title) > max_chars:
            title = f"{subject}-{aspect}"
        if len(title) > max_chars:
            title = subject[:max_chars]
        
        return title


# Global singleton
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
