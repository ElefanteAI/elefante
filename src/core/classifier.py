import re
from typing import Tuple

def classify_memory(content: str) -> Tuple[str, str]:
    """
    Classifies memory content into layer and sublayer based on regex rules.
    Returns (layer, sublayer).
    """
    # Check for INTENT.rule (Uppercase)
    if re.search(r'\b(NEVER|ALWAYS|MUST)\b', content):
        return "intent", "rule"

    content_lower = content.lower()

    # SELF Layer
    # identity: "is" + user entity
    if re.search(r'\bis\b.*\b(jaime|user)\b', content_lower):
        return "self", "identity"
    # preference: prefer|like|hate|love|value
    if re.search(r'prefer|like|hate|love|value', content_lower):
        return "self", "preference"
    # SELF.constraint (lowercase modals)
    if re.search(r'\b(must|never|always)\b', content_lower):
        return "self", "constraint"

    # INTENT Layer (remaining)
    # goal: future tense or want|need|goal|achieve
    if re.search(r'want|need|goal|achieve|will', content_lower):
        return "intent", "goal"
    # anti-pattern: don't|do not|avoid|stop
    if re.search(r"don't|do not|avoid|stop", content_lower):
        return "intent", "anti-pattern"

    # WORLD Layer
    # failure: bug|error|fail|problem|issue|crash|break
    if re.search(r'bug|error|fail|problem|issue|crash|break', content_lower):
        return "world", "failure"
    # method: technique|protocol|method|process|workflow|framework
    if re.search(r'technique|protocol|method|process|workflow|framework', content_lower):
        return "world", "method"
    
    # Default to WORLD.fact
    return "world", "fact"
