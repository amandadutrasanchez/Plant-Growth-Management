import sqlite3

conn = sqlite3.connect('venv/capacidade_estufa.db')
cursor = conn.cursor()

# Check current columns
cursor.execute('PRAGMA table_info(rotas)')
cols = [r[1] for r in cursor.fetchall()]
print('Current columns:', cols)

if 'concomitante' not in cols:
    cursor.execute('ALTER TABLE rotas ADD COLUMN concomitante INTEGER DEFAULT 0')
    conn.commit()
    print('concomitante column added!')
else:
    print('concomitante column already exists')

# Verify
cursor.execute('PRAGMA table_info(rotas)')
cols = [r[1] for r in cursor.fetchall()]
print('Final columns:', cols)

conn.close()
