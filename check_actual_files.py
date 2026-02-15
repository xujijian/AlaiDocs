import sqlite3
from pathlib import Path

base_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf")
kb = Path(r"D:\E-BOOK\axis-SQLite\kb.sqlite")

conn = sqlite3.connect(str(kb))
cursor = conn.cursor()

cursor.execute('SELECT path FROM documents LIMIT 10')
print("检查前10个文档是否存在:")
for row in cursor.fetchall():
    rel_path = row[0]
    full_path = base_dir / rel_path
    exists = "✅" if full_path.exists() else "❌"
    print(f"{exists} {rel_path}")

conn.close()
