import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Listar cidadãos
cursor.execute('SELECT nome, id FROM cidadaos_cidadao ORDER BY nome')
cidadaos = cursor.fetchall()

print(f"Total de cidadãos: {len(cidadaos)}")
print("\nCidadãos cadastrados:")
for nome, id_cidadao in cidadaos:
    print(f"- {nome} (ID: {id_cidadao})")

conn.close()