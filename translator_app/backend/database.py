import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "translator.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS translation_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_text TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target_text TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS terminology (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chinese_term TEXT NOT NULL,
            french_term TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_word TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target_word TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            context TEXT,
            example_sentence TEXT,
            frequency INTEGER DEFAULT 1,
            mastered INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 兼容旧数据库：如果 example_sentence 列不存在则添加
    try:
        cursor.execute('SELECT example_sentence FROM vocabulary LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE vocabulary ADD COLUMN example_sentence TEXT')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_source_text ON translation_memory(source_text)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_vocab_source ON vocabulary(source_word, source_lang)
    ''')
    
    conn.commit()
    conn.close()

def get_memory_by_text(text, source_lang, similarity_threshold=0.9):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT target_text, target_lang, source_text FROM translation_memory 
        WHERE source_lang = ?
    ''', (source_lang,))
    results = cursor.fetchall()
    conn.close()
    
    text = text.strip()
    text_len = len(text)
    
    for target_text, target_lang, source_text in results:
        source_text = source_text.strip()
        source_len = len(source_text)
        
        if text == source_text:
            return (target_text, target_lang, 1.0)
        
        if text_len > 0 and source_len > 0:
            common = sum(1 for c in text if c in source_text)
            similarity = common / max(text_len, source_len)
            if similarity >= similarity_threshold:
                return (target_text, target_lang, similarity)
    
    return None

def add_memory(source_text, source_lang, target_text, target_lang):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO translation_memory (source_text, source_lang, target_text, target_lang)
        VALUES (?, ?, ?, ?)
    ''', (source_text, source_lang, target_text, target_lang))
    conn.commit()
    conn.close()

def get_all_memories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, source_text, source_lang, target_text, target_lang, created_at
        FROM translation_memory ORDER BY created_at DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return [{
        "id": row[0],
        "source_text": row[1],
        "source_lang": row[2],
        "target_text": row[3],
        "target_lang": row[4],
        "created_at": row[5]
    } for row in results]

def delete_memory(memory_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM translation_memory WHERE id = ?', (memory_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

def clear_all_memories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM translation_memory')
    conn.commit()
    conn.close()

def get_all_terminology():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, chinese_term, french_term, created_at
        FROM terminology ORDER BY created_at DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return [{
        "id": row[0],
        "chinese_term": row[1],
        "french_term": row[2],
        "created_at": row[3]
    } for row in results]

def add_terminology(chinese_term, french_term):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO terminology (chinese_term, french_term)
        VALUES (?, ?)
    ''', (chinese_term, french_term))
    conn.commit()
    conn.close()

def delete_terminology(term_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM terminology WHERE id = ?', (term_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

def clear_all_terminology():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM terminology')
    conn.commit()
    conn.close()

def find_matching_terms(text, source_lang):
    all_terms = get_all_terminology()
    matching_terms = []
    if source_lang == 'zh':
        for term in all_terms:
            if term['chinese_term'] in text:
                matching_terms.append(f"{term['chinese_term']}={term['french_term']}")
    else:
        for term in all_terms:
            if term['french_term'] in text:
                matching_terms.append(f"{term['french_term']}={term['chinese_term']}")
    return matching_terms

def add_vocabulary(source_word, source_lang, target_word, target_lang, context="", example_sentence=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, frequency FROM vocabulary 
        WHERE source_word = ? AND source_lang = ? AND target_word = ?
    ''', (source_word, source_lang, target_word))
    
    result = cursor.fetchone()
    if result:
        vocab_id, frequency = result
        cursor.execute('''
            UPDATE vocabulary 
            SET frequency = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (frequency + 1, vocab_id))
    else:
        cursor.execute('''
            INSERT INTO vocabulary (source_word, source_lang, target_word, target_lang, context, example_sentence)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (source_word, source_lang, target_word, target_lang, context, example_sentence))
    
    conn.commit()
    conn.close()

def update_vocabulary(vocab_id, source_word=None, target_word=None, example_sentence=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    updates = []
    params = []
    if source_word is not None:
        updates.append("source_word = ?")
        params.append(source_word)
    if target_word is not None:
        updates.append("target_word = ?")
        params.append(target_word)
    if example_sentence is not None:
        updates.append("example_sentence = ?")
        params.append(example_sentence)
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(vocab_id)
    cursor.execute(f'''
        UPDATE vocabulary SET {', '.join(updates)} WHERE id = ?
    ''', params)
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

def add_vocabulary_meaning(vocab_id, new_meaning):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT target_word FROM vocabulary WHERE id = ?', (vocab_id,))
    result = cursor.fetchone()
    if result:
        current_meaning = result[0]
        if new_meaning not in current_meaning:
            updated_meaning = f"{current_meaning}；{new_meaning}"
            cursor.execute('''
                UPDATE vocabulary SET target_word = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (updated_meaning, vocab_id))
            conn.commit()
    conn.close()
    return cursor.rowcount > 0

def get_all_vocabulary():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, source_word, source_lang, target_word, target_lang, context, example_sentence, frequency, mastered, created_at
        FROM vocabulary ORDER BY frequency DESC, created_at DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return [{
        "id": row[0],
        "source_word": row[1],
        "source_lang": row[2],
        "target_word": row[3],
        "target_lang": row[4],
        "context": row[5],
        "example_sentence": row[6],
        "frequency": row[7],
        "mastered": row[8],
        "created_at": row[9]
    } for row in results]

def get_unmastered_vocabulary():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, source_word, source_lang, target_word, target_lang, context, example_sentence, frequency, mastered, created_at
        FROM vocabulary WHERE mastered = 0 ORDER BY frequency DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return [{
        "id": row[0],
        "source_word": row[1],
        "source_lang": row[2],
        "target_word": row[3],
        "target_lang": row[4],
        "context": row[5],
        "example_sentence": row[6],
        "frequency": row[7],
        "mastered": row[8],
        "created_at": row[9]
    } for row in results]

def update_vocabulary_mastered(vocab_id, mastered):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE vocabulary SET mastered = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    ''', (mastered, vocab_id))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

def delete_vocabulary(vocab_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM vocabulary WHERE id = ?', (vocab_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

def clear_all_vocabulary():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM vocabulary')
    conn.commit()
    conn.close()

init_db()