import os
import sqlite3

def run_migrations():
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(migrations_dir)
    db_path = os.path.join(backend_dir, 'softlend.db')
    sql_path = os.path.join(migrations_dir, '001_init.sql')

    print(f"Running migrations from {sql_path} on database {db_path}...")
    
    if not os.path.exists(sql_path):
        print(f"Error: migration file {sql_path} does not exist!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        with open(sql_path, 'r') as f:
            sql_script = f.read()
            
        cursor.executescript(sql_script)
        conn.commit()
        print("Migrations successfully applied!")
    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    run_migrations()
