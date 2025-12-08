import re
from typing import Tuple

def classify_memory(content: str) -> Tuple[str, str]:
    """
    Classifies memory content into layer and sublayer based on regex rules.
    Returns (layer, sublayer).
    
    V3 Schema:
    - SELF: Who the user IS (identity, preference, constraint)
    - WORLD: What the user KNOWS (fact, failure, method)
    - INTENT: What the user DOES (rule, goal, anti-pattern)
    """
    # Check for INTENT.rule (Uppercase imperatives)
    if re.search(r'\b(NEVER|ALWAYS|MUST|CRITICAL|LAW|RULE|PROTOCOL)\b', content):
        return "intent", "rule"

    content_lower = content.lower()
    
    # =========================================================================
    # SELF Layer: Who the user IS
    # =========================================================================
    
    # SELF.identity: First-person statements about who the user is
    if re.search(r'^i (am|live|speak|work|have|was|studied|grew|come from|specialize)\b', content_lower):
        return "self", "identity"
    if re.search(r'\bmy (name|profession|job|role|background|expertise|experience|skill)\b', content_lower):
        return "self", "identity"
    if re.search(r'\bi am (a|an|the|from|based|located|specializing)\b', content_lower):
        return "self", "identity"
    if re.search(r'\buser (is|prefers|lives|works|speaks)\b', content_lower):
        return "self", "identity"
    if re.search(r'\b(jaime|jay)\b.*\b(is|prefers|lives)\b', content_lower):
        return "self", "identity"
    # Additional identity patterns
    if re.search(r'\b(senior|junior|lead|principal|staff)\s+(developer|engineer|architect|designer)\b', content_lower):
        return "self", "identity"
    if re.search(r'\bspecializ(e|ing|es)\s+in\b', content_lower):
        return "self", "identity"
        
    # SELF.preference: What the user likes/dislikes/values
    if re.search(r'\bi (like|prefer|hate|love|value|enjoy|dislike|appreciate|want)\b', content_lower):
        return "self", "preference"
    if re.search(r'\b(straightforward|concise|efficient|minimal|clean|simple)\b', content_lower):
        return "self", "preference"
    if re.search(r'\bprefer(s|ence|red)?\b', content_lower):
        return "self", "preference"
    if re.search(r'\b(favorite|best|ideal|perfect)\b', content_lower):
        return "self", "preference"
    if re.search(r'\bno (apologies|waste|fluff|bs)\b', content_lower):
        return "self", "preference"
        
    # SELF.constraint: Personal limits/rules
    if re.search(r'\b(must not|never|always)\b', content_lower):
        return "self", "constraint"
    if re.search(r'\bdo not\b.*\b(waste|use|spend)\b', content_lower):
        return "self", "constraint"
    if re.search(r'\b(limit|restrict|constraint|boundary)\b', content_lower):
        return "self", "constraint"
    
    # =========================================================================
    # INTENT Layer: What the user DOES/WANTS
    # =========================================================================
    
    # INTENT.goal: Future intentions  
    if re.search(r'\b(want to|need to|goal|objective|plan to|aiming|achieve|intend)\b', content_lower):
        return "intent", "goal"
    if re.search(r'\bwill (be|have|create|build|implement)\b', content_lower):
        return "intent", "goal"
    if re.search(r'\b(todo|task|next step|upcoming|roadmap)\b', content_lower):
        return "intent", "goal"
        
    # INTENT.anti-pattern: Things to avoid
    if re.search(r"\b(don't|do not|avoid|stop|refrain|prevent)\b", content_lower):
        return "intent", "anti-pattern"
    if re.search(r'\b(bad practice|anti-pattern|mistake|pitfall|warning)\b', content_lower):
        return "intent", "anti-pattern"
    
    # =========================================================================
    # WORLD Layer: What the user KNOWS
    # =========================================================================
    
    # WORLD.failure: Problems and errors
    if re.search(r'\b(bug|error|fail|problem|issue|crash|break|exception|traceback)\b', content_lower):
        return "world", "failure"
    if re.search(r'\b(fix|debug|resolve|solved)\b.*\b(error|bug|issue|problem)\b', content_lower):
        return "world", "failure"
    if re.search(r'\b(root cause|debugging|troubleshoot)\b', content_lower):
        return "world", "failure"
        
    # WORLD.method: Techniques and processes
    if re.search(r'\b(technique|protocol|method|process|workflow|framework|pattern|architecture)\b', content_lower):
        return "world", "method"
    if re.search(r'\b(project|system|service|api|database|server)\b.*\b(uses|requires|implements)\b', content_lower):
        return "world", "method"
    if re.search(r'\busing\b.*\b(kafka|docker|kubernetes|python|react|kuzu|chroma|chromadb)\b', content_lower):
        return "world", "method"
    if re.search(r'\b(microservices|distributed|architecture|infrastructure|pipeline)\b', content_lower):
        return "world", "method"
    if re.search(r'\b(step \d|first|then|finally|after that)\b', content_lower):
        return "world", "method"
    if re.search(r'\b(how to|guide|tutorial|instructions)\b', content_lower):
        return "world", "method"
    
    # Default to WORLD.fact
    return "world", "fact"


def calculate_importance(content: str, layer: str, sublayer: str) -> int:
    """
    Calculate importance score (1-10) based on content analysis.
    
    Importance scale:
    - 10: Critical laws, persona definitions, system rules
    - 8-9: Strong preferences, key decisions, important failures
    - 6-7: Notable methods, specific knowledge
    - 4-5: General facts, routine information
    - 1-3: Low-value, redundant, or ephemeral content
    """
    score = 5  # Default baseline
    
    content_lower = content.lower()
    
    # === CRITICAL MARKERS (boost to 9-10) ===
    if re.search(r'\b(CRITICAL|NEVER|ALWAYS|MUST|LAW|RULE)\b', content):
        score = 10
    elif re.search(r'\b(important|essential|crucial|key|vital|fundamental)\b', content_lower):
        score = max(score, 8)
    
    # === LAYER-BASED SCORING ===
    if layer == "self":
        if sublayer == "identity":
            score = max(score, 8)  # Identity is always important
        elif sublayer == "preference":
            score = max(score, 7)
        elif sublayer == "constraint":
            score = max(score, 9)  # Constraints are critical
    
    elif layer == "intent":
        if sublayer == "rule":
            score = max(score, 9)
        elif sublayer == "goal":
            score = max(score, 7)
        elif sublayer == "anti-pattern":
            score = max(score, 8)  # Anti-patterns prevent mistakes
    
    elif layer == "world":
        if sublayer == "failure":
            # Failures with solutions are more valuable
            if re.search(r'\b(fix|solution|resolve|solved)\b', content_lower):
                score = max(score, 8)
            else:
                score = max(score, 6)
        elif sublayer == "method":
            score = max(score, 6)
        # fact stays at default (5)
    
    # === CONTENT QUALITY MODIFIERS ===
    
    # Length bonus (detailed content is often more valuable)
    word_count = len(content.split())
    if word_count > 50:
        score = min(10, score + 1)
    elif word_count < 10:
        score = max(1, score - 1)
    
    # Technical depth bonus
    if re.search(r'\b(implementation|architecture|algorithm|optimization)\b', content_lower):
        score = min(10, score + 1)
    
    # Decision markers
    if re.search(r'\b(decided|decision|chose|selected)\b', content_lower):
        score = max(score, 7)
    
    # API/Config markers (operational knowledge)
    if re.search(r'\b(api key|password|secret|config|credential)\b', content_lower):
        score = max(score, 8)
    
    return min(10, max(1, score))


def classify_memory_full(content: str) -> Tuple[str, str, int]:
    """
    Full classification returning (layer, sublayer, importance).
    """
    layer, sublayer = classify_memory(content)
    importance = calculate_importance(content, layer, sublayer)
    return layer, sublayer, importance
