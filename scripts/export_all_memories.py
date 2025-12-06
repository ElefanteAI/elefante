"""Direct ChromaDB export - no async, no orchestrator"""
import csv
import os
from pathlib import Path
import chromadb

# Connect directly to ChromaDB
data_path = Path.home() / '.elefante' / 'data' / 'chroma'
client = chromadb.PersistentClient(path=str(data_path))

# Get collection
collection = client.get_collection('memories')

# Get ALL memories (no filtering)
results = collection.get(include=['metadatas', 'documents'])

total = len(results['ids'])
print(f'Total memories retrieved: {total}')

# Define all possible metadata fields
fields = [
    'id', 'content', 'created_at', 'created_by', 'domain', 'category', 
    'memory_type', 'subcategory', 'intent', 'importance', 'urgency', 
    'confidence', 'tags', 'keywords', 'entities', 'status', 
    'relationship_type', 'parent_id', 'related_memory_ids', 'conflict_ids',
    'supersedes_id', 'superseded_by_id', 'source', 'source_detail',
    'source_reliability', 'verified', 'verified_by', 'verified_at',
    'session_id', 'author', 'project', 'workspace', 'file_path',
    'line_number', 'url', 'location', 'last_accessed', 'last_modified',
    'access_count', 'decay_rate', 'reinforcement_factor', 'version',
    'deprecated', 'archived', 'summary', 'sentiment', 'quality_score',
    'custom_metadata', 'system_metadata'
]

# Write CSV
output_path = 'data/memories_complete_export_91.csv'
os.makedirs('data', exist_ok=True)

with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    
    for i, doc_id in enumerate(results['ids']):
        row = {'id': doc_id}
        row['content'] = results['documents'][i] if results['documents'] else ''
        metadata = results['metadatas'][i] if results['metadatas'] else {}
        
        for field in fields[2:]:  # Skip id and content
            value = metadata.get(field, '')
            if isinstance(value, (list, dict)):
                row[field] = str(value)
            else:
                row[field] = value if value is not None else ''
        
        writer.writerow(row)

print(f'CSV exported to: {output_path}')
print(f'Rows written: {total}')
