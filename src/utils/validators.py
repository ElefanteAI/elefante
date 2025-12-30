"""
Input validation utilities for Elefante memory system
"""

import re
from typing import Any, List, Optional
from uuid import UUID
from datetime import datetime


class ValidationError(Exception):
    """Custom validation error"""
    pass


def validate_memory_content(content: str, min_length: int = 1, max_length: int = 100000) -> str:
    """
    Validate memory content
    
    Args:
        content: Memory content to validate
        min_length: Minimum content length
        max_length: Maximum content length
        
    Returns:
        Validated content (stripped)
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(content, str):
        raise ValidationError("Content must be a string")
    
    content = content.strip()
    
    if len(content) < min_length:
        raise ValidationError(f"Content must be at least {min_length} characters")
    
    if len(content) > max_length:
        raise ValidationError(f"Content must not exceed {max_length} characters")
    
    return content


def validate_importance(importance: int) -> int:
    """
    Validate importance level
    
    Args:
        importance: Importance level (1-10)
        
    Returns:
        Validated importance
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(importance, int):
        raise ValidationError("Importance must be an integer")
    
    if importance < 1 or importance > 10:
        raise ValidationError("Importance must be between 1 and 10")
    
    return importance


def validate_tags(tags: List[str], max_tags: int = 20, max_tag_length: int = 50) -> List[str]:
    """
    Validate tags list
    
    Args:
        tags: List of tags
        max_tags: Maximum number of tags
        max_tag_length: Maximum length of each tag
        
    Returns:
        Validated and normalized tags
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(tags, list):
        raise ValidationError("Tags must be a list")
    
    if len(tags) > max_tags:
        raise ValidationError(f"Maximum {max_tags} tags allowed")
    
    validated_tags = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValidationError("Each tag must be a string")
        
        tag = tag.strip().lower()
        
        if not tag:
            continue  # Skip empty tags
        
        if len(tag) > max_tag_length:
            raise ValidationError(f"Tag '{tag}' exceeds maximum length of {max_tag_length}")
        
        # Validate tag format (alphanumeric, hyphens, underscores)
        if not re.match(r'^[a-z0-9_-]+$', tag):
            raise ValidationError(f"Tag '{tag}' contains invalid characters. Use only letters, numbers, hyphens, and underscores")
        
        validated_tags.append(tag)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in validated_tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    return unique_tags


def validate_uuid(uuid_str: Any) -> UUID:
    """
    Validate and convert UUID string
    
    Args:
        uuid_str: UUID string or UUID object
        
    Returns:
        UUID object
        
    Raises:
        ValidationError: If validation fails
    """
    if isinstance(uuid_str, UUID):
        return uuid_str
    
    if not isinstance(uuid_str, str):
        raise ValidationError("UUID must be a string or UUID object")
    
    try:
        return UUID(uuid_str)
    except ValueError as e:
        raise ValidationError(f"Invalid UUID format: {e}")


def validate_entity_name(name: str, min_length: int = 1, max_length: int = 200) -> str:
    """
    Validate entity name
    
    Args:
        name: Entity name
        min_length: Minimum name length
        max_length: Maximum name length
        
    Returns:
        Validated name (stripped)
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(name, str):
        raise ValidationError("Entity name must be a string")
    
    name = name.strip()
    
    if len(name) < min_length:
        raise ValidationError(f"Entity name must be at least {min_length} characters")
    
    if len(name) > max_length:
        raise ValidationError(f"Entity name must not exceed {max_length} characters")
    
    return name


def validate_query(query: str, min_length: int = 1, max_length: int = 1000) -> str:
    """
    Validate search query
    
    Args:
        query: Search query
        min_length: Minimum query length
        max_length: Maximum query length
        
    Returns:
        Validated query (stripped)
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(query, str):
        raise ValidationError("Query must be a string")
    
    query = query.strip()
    
    if len(query) < min_length:
        raise ValidationError(f"Query must be at least {min_length} characters")
    
    if len(query) > max_length:
        raise ValidationError(f"Query must not exceed {max_length} characters")
    
    return query


def validate_limit(limit: int, min_limit: int = 1, max_limit: int = 100) -> int:
    """
    Validate result limit
    
    Args:
        limit: Result limit
        min_limit: Minimum limit
        max_limit: Maximum limit
        
    Returns:
        Validated limit
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(limit, int):
        raise ValidationError("Limit must be an integer")
    
    if limit < min_limit:
        raise ValidationError(f"Limit must be at least {min_limit}")
    
    if limit > max_limit:
        raise ValidationError(f"Limit must not exceed {max_limit}")
    
    return limit


def validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> tuple:
    """
    Validate date range
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Tuple of (start_date, end_date)
        
    Raises:
        ValidationError: If validation fails
    """
    if start_date and not isinstance(start_date, datetime):
        raise ValidationError("Start date must be a datetime object")
    
    if end_date and not isinstance(end_date, datetime):
        raise ValidationError("End date must be a datetime object")
    
    if start_date and end_date and start_date > end_date:
        raise ValidationError("Start date must be before end date")
    
    return start_date, end_date


def validate_cypher_query(query: str) -> str:
    """
    Basic validation for Cypher queries
    
    Args:
        query: Cypher query string
        
    Returns:
        Validated query
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(query, str):
        raise ValidationError("Cypher query must be a string")
    
    query = query.strip()
    
    if not query:
        raise ValidationError("Cypher query cannot be empty")
    
    # Basic safety checks (prevent destructive operations in production)
    dangerous_keywords = ['DELETE', 'DROP', 'REMOVE']
    query_upper = query.upper()
    
    for keyword in dangerous_keywords:
        if keyword in query_upper:
            raise ValidationError(f"Dangerous operation '{keyword}' not allowed in queries")
    
    return query


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file system operations
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')
    
    return filename or 'unnamed'

