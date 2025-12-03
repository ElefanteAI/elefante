#!/usr/bin/env python3
"""Check embeddings table structure"""

import sqlite3

conn = sqlite3.connect('C:/Users/JaimeSubiabreCistern/.elefante/data/chroma/chroma.sqlite3')
cursor = conn.cursor()

print("Embeddings table schema:")
cursor.execute('PRAGMA table_info(embeddings)')
for row in cursor.fetchall():
    print(f'  {row}')

print("\nTotal embeddings:", cursor.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0])

print("\nSample embedding IDs:")
cursor.execute('SELECT id, segment_id FROM embeddings ORDER BY id DESC LIMIT 5')
for row in cursor.fetchall():
    print(f'  ID: {row[0]}, Segment: {row[1]}')

conn.close()

# Made with Bob
