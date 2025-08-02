import sqlite3

def migrate_db():
    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    
    # Backup existing tables
    c.execute('''CREATE TABLE IF NOT EXISTS students_backup AS SELECT * FROM students''')
    c.execute('''CREATE TABLE IF NOT EXISTS results_backup AS SELECT * FROM results''')
    c.execute('''CREATE TABLE IF NOT EXISTS questions_backup AS SELECT * FROM questions''')
    
    # Drop old tables
    c.execute('DROP TABLE IF EXISTS students')
    c.execute('DROP TABLE IF EXISTS results')
    c.execute('DROP TABLE IF EXISTS questions')
    
    # Create new tables with correct schema
    c.execute('''CREATE TABLE students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lotname TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        quiz_status_tech TEXT DEFAULT 'not_attempted',
        quiz_status_software TEXT DEFAULT 'not_attempted'
    )''')
    
    c.execute('''CREATE TABLE results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lotname TEXT NOT NULL,
        score INTEGER NOT NULL,
        duration INTEGER NOT NULL,
        quiz_type TEXT NOT NULL
    )''')
    
    c.execute('''CREATE TABLE questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_type TEXT NOT NULL,
        question TEXT NOT NULL,
        option1 TEXT NOT NULL,
        option2 TEXT NOT NULL,
        option3 TEXT NOT NULL,
        option4 TEXT NOT NULL,
        answer TEXT NOT NULL
    )''')
    
    # Recreate other tables (unchanged)
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_code TEXT NOT NULL,
        quiz_type TEXT NOT NULL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    
    # Migrate students data
    c.execute('SELECT lotname, password, quiz_status_tech, quiz_status_software FROM students_backup')
    existing_lotnames = set()
    for row in c.fetchall():
        lotname, password, quiz_status_tech, quiz_status_software = row
        if lotname not in existing_lotnames:
            password = password or (lotname + '@2k25')
            quiz_status_tech = quiz_status_tech or 'not_attempted'
            quiz_status_software = quiz_status_software or 'not_attempted'
            c.execute('INSERT INTO students (lotname, password, quiz_status_tech, quiz_status_software) VALUES (?, ?, ?, ?)',
                     (lotname, password, quiz_status_tech, quiz_status_software))
            existing_lotnames.add(lotname)
    
    # Migrate results data
    c.execute('SELECT lotname, score, duration, quiz_type FROM results_backup')
    for row in c.fetchall():
        lotname, score, duration, quiz_type = row
        duration = duration or 0
        quiz_type = quiz_type or 'Tech'  # Default to Tech for existing data
        c.execute('INSERT INTO results (lotname, score, duration, quiz_type) VALUES (?, ?, ?, ?)',
                 (lotname, score, duration, quiz_type))
    
    # Migrate questions data
    c.execute('SELECT question, option1, option2, option3, option4, answer FROM questions_backup')
    for row in c.fetchall():
        question, option1, option2, option3, option4, answer = row
        c.execute('INSERT INTO questions (quiz_type, question, option1, option2, option3, option4, answer) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 ('Tech', question, option1, option2, option3, option4, answer))  # Default to Tech for existing questions
    
    # Clean up backups
    c.execute('DROP TABLE IF EXISTS students_backup')
    c.execute('DROP TABLE IF EXISTS results_backup')
    c.execute('DROP TABLE IF EXISTS questions_backup')
    
    conn.commit()
    conn.close()
    print("Database migration completed successfully!")

if __name__ == '__main__':
    migrate_db()