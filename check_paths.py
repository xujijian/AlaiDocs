import sqlite3
conn = sqlite3.connect(r'D:\E-BOOK\axis-SQLite\kb.sqlite')
cursor = conn.cursor()
cursor.execute('SELECT path FROM documents WHERE vendor="TI" LIMIT 3')
print('TI 文档路径示例:')
for row in cursor.fetchall():
    print(f'  {row[0]}')
    
cursor.execute('SELECT path FROM documents WHERE vendor="ADI" LIMIT 3')
print('\nADI 文档路径示例:')
for row in cursor.fetchall():
    print(f'  {row[0]}')
conn.close()
