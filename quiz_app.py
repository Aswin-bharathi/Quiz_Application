from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response,send_file
import mysql.connector
import pandas as pd
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import random
import xlsxwriter
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.pdfgen import canvas
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import pandas as pd
import io
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
import os
from werkzeug.utils import secure_filename
import os

load_dotenv(dotenv_path=".env")
app = Flask(__name__)   # 🔥 FIRST create app

# Upload folder config
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create folder if not exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



app.secret_key = 'your-secret-key'  # Replace with secure key in production

# MySQL Configuration
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}

# Function to get MySQL connection
def get_db_connection():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        conn.autocommit = False  # Enable manual commit for transactions
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        raise

# Database initialization
def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Enable foreign key support
    c.execute("SET FOREIGN_KEY_CHECKS = 1")

    # 1. students table
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255) NOT NULL,
        roll_no VARCHAR(50) UNIQUE NOT NULL,
        program ENUM('UG', 'PG') NOT NULL,
        year ENUM('I', 'II', 'III') NOT NULL,
        quiz_status VARCHAR(50) DEFAULT 'not_attempted'
    )''')

    # 2. subjects table
    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        subject_code VARCHAR(50) UNIQUE NOT NULL,
        subject_name VARCHAR(255) NOT NULL,
        program ENUM('UG', 'PG') NOT NULL,
        year ENUM('I', 'II', 'III') NOT NULL
    )''')

    # 3. questions table
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        program ENUM('UG', 'PG') NOT NULL,
        year ENUM('I', 'II', 'III') NOT NULL,
        subject VARCHAR(255) NOT NULL,
        subject_code VARCHAR(50) NOT NULL,
        co VARCHAR(50),
        question TEXT NOT NULL,
        option1 TEXT NOT NULL,
        option2 TEXT NOT NULL,
        option3 TEXT NOT NULL,
        option4 TEXT NOT NULL,
        answer TEXT NOT NULL,
        FOREIGN KEY (subject_code) REFERENCES subjects(subject_code) ON DELETE CASCADE
    )''')

    # 4. quiz_entries table
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_entries (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        entry_code VARCHAR(50) UNIQUE NOT NULL
    )''')

    # 5. results table
    c.execute('''CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        student_roll_no VARCHAR(50) NOT NULL,
        subject_code VARCHAR(50) NOT NULL,
        score INTEGER NOT NULL,
        co1_score INT DEFAULT 0,
        co2_score INT DEFAULT 0,
        co3_score INT DEFAULT 0,
        co4_score INT DEFAULT 0,
        co5_score INT DEFAULT 0,
        FOREIGN KEY (student_roll_no) REFERENCES students(roll_no) ON DELETE CASCADE,
        FOREIGN KEY (subject_code) REFERENCES subjects(subject_code) ON DELETE CASCADE
    )''')

    # 6. admins table
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL
    )''')

    # 7. quiz_access table
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_access (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        program ENUM('UG', 'PG') NOT NULL,
        year ENUM('I', 'II', 'III') NOT NULL,
        allowed_subject_code VARCHAR(50) NOT NULL,
        FOREIGN KEY (allowed_subject_code) REFERENCES subjects(subject_code) ON DELETE CASCADE
    )''')

    # 8. student_answers table
    c.execute('''CREATE TABLE IF NOT EXISTS student_answers (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        student_roll_no VARCHAR(50) NOT NULL,
        question_id INTEGER NOT NULL,
        is_correct INTEGER,
        FOREIGN KEY (student_roll_no) REFERENCES students(roll_no) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
    )''')

    # Insert default admin
    default_admin = 'admin'
    default_password = generate_password_hash('admin@123#')  # Change in production
    c.execute('INSERT IGNORE INTO admins (username, password) VALUES (%s, %s)',
              (default_admin, default_password))

    conn.commit()
    conn.close()

# Initialize database
init_db()

# Admin login required decorator
def admin_login_required(f):
    def wrap(*args, **kwargs):
        if 'admin' not in session:
            flash('Please login as admin first!', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap
# @app.route('/')
# def index():
#     return render_template('admin_login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute('SELECT * FROM admins WHERE username = %s', (username,))
        admin = c.fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['password'], password):
            session['admin'] = username
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials!', 'error')
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
@admin_login_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/add_student', methods=['GET', 'POST'])
@admin_login_required
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        roll_no = request.form['roll_no']
        program = request.form['program']
        year = request.form['year']
        dept = request.form['dept']
        mail = request.form['mail']
        
        if not all([name, roll_no, program, year,dept,mail,]):
            flash('All fields are required!', 'error')
            return redirect(url_for('add_student'))
            
        try:
            conn = get_db_connection()
            c = conn.cursor()
            print('hii')
            c.execute('''INSERT INTO students (roll_no, name, program, year, quiz_status,student_dept,student_email) VALUES (%s, %s, %s, %s,%s,%s,%s)''',
                                      (roll_no,name, program, year, 'not_attempted',dept,mail))
            conn.commit()
            flash('Student added successfully!', 'success')
        except mysql.connector.Error as err:
            flash(f'Error: Roll number already exists or invalid data! {str(err)}', 'error')
        finally:
            conn.close()
            
        return redirect(url_for('show_students'))
    return render_template('add_student.html')

@app.route('/update_student/<int:id>', methods=['GET', 'POST'])
@admin_login_required
def update_student(id):
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)  # returns dict instead of tuple

    if request.method == 'POST':
        name = request.form['name']
        roll_no = request.form['roll_no']
        program = request.form['program']
        year = request.form['year']
        quiz_status = request.form['quiz_status']  # New field

        if not all([name, roll_no, program, year, quiz_status]):
            flash('All fields are required!', 'error')
            conn.close()
            return redirect(url_for('update_student', id=id))

        try:
            # ✅ Update student record
            c.execute(
                'UPDATE students SET name = %s, roll_no = %s, program = %s, year = %s, quiz_status = %s WHERE id = %s',
                (name, roll_no, program, year, quiz_status, id)
            )
            conn.commit()

            # ✅ If status is not_attempted → delete results row
            if quiz_status == "not_attempted":
                c.execute("DELETE FROM results WHERE student_roll_no = %s", (roll_no,))
                conn.commit()

            flash('Student updated successfully!', 'success')

        except mysql.connector.Error as err:
            flash(f'Error: Roll number already exists or invalid data! {str(err)}', 'error')
        finally:
            conn.close()

        return redirect(url_for('show_students'))

    # GET request → fetch current student data
    c.execute('SELECT * FROM students WHERE id = %s', (id,))
    student = c.fetchone()
    conn.close()

    if not student:
        flash('Student not found!', 'error')
        return redirect(url_for('show_students'))

    return render_template('update_student.html', student=student)


@app.route('/delete_student/<int:id>')
@admin_login_required
def delete_student(id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM students WHERE id = %s', (id,))
        conn.commit()
        flash('Student deleted successfully!', 'success')
    except mysql.connector.Error as err:
        flash(f'Error deleting student: {str(err)}', 'error')
    finally:
        conn.close()
    return redirect(url_for('show_students'))

@app.route('/show_students', methods=['GET'])
@admin_login_required
def show_students():
    search = request.args.get('search', '')
    program = request.args.get('program', '')
    year = request.args.get('year', '')
    department = request.args.get('student_dept', '')
    
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    
    # Fetch distinct departments for dropdown
    c.execute('SELECT DISTINCT student_dept FROM students WHERE student_dept IS NOT NULL AND student_dept != ""')
    departments = [row['student_dept'] for row in c.fetchall()]
    
    # Main query for students
    query = 'SELECT id, roll_no, name, active_status, program, year, quiz_status FROM students'
    params = []
    
    conditions = []
    if search:
        conditions.append('(roll_no LIKE %s OR name LIKE %s)')
        params.extend([f'%{search}%', f'%{search}%'])
    if program:
        conditions.append('program = %s')
        params.append(program)
    if year:
        conditions.append('year = %s')
        params.append(year)
    if department:
        conditions.append('student_dept = %s')
        params.append(department)
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' ORDER BY program ASC, year ASC, CAST(SUBSTR(roll_no, -3) AS SIGNED) ASC'
    
    c.execute(query, params)
    students = c.fetchall()
    conn.close()
    
    return render_template(
        'show_students.html',
        students=students,
        search=search,
        program=program,
        year=year,
        departments=departments,
        department=department
    )

@app.route('/delete_selected_students', methods=['POST'])
@admin_login_required
def delete_selected_students():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()

    # Get form data
    program = request.form.get('program', '')
    year = request.form.get('year', '')
    department = request.form.get('student_dept', '')

    # Build query with filters
    query = 'DELETE FROM students WHERE 1=1'
    params = []
    if program:
        query += ' AND program = %s'
        params.append(program)
    if year:
        query += ' AND year = %s'
        params.append(year)
    if department:
        query += ' AND student_dept = %s'
        params.append(department)

    try:
        c.execute(query, params)
        conn.commit()
        deleted_count = c.rowcount
        return jsonify({'success': True, 'message': f'Deleted {deleted_count} student(s)'})
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/toggle_student_status/<int:id>', methods=['POST'])
@admin_login_required
def toggle_student_status(id):
    try:
        conn = get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute('SELECT active_status FROM students WHERE id = %s', (id,))
        student = c.fetchone()
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        new_status = 'OFF' if student['active_status'] == 'ON' else 'ON'
        c.execute('UPDATE students SET active_status = %s WHERE id = %s', (new_status, id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'new_status': new_status})
    except mysql.connector.Error as err:
        conn.close()
        return jsonify({'error': str(err)}), 500
    

@app.route('/add_question', methods=['GET', 'POST'])
@admin_login_required
def add_question():
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    
    program = request.args.get('program', '')
    year = request.args.get('year', '')
    query = 'SELECT id, subject_name, subject_code, program, year FROM subjects'
    params = []
    if program:
        query += ' WHERE program = %s'
        params.append(program)
    if year:
        query += ' AND year = %s' if 'WHERE' in query else ' WHERE year = %s'
        params.append(year)
    c.execute(query, params)
    subjects = c.fetchall()
    
    if request.method == 'POST':
        program = request.form['program']
        year = request.form['year']
        subject = request.form['subject']
        subject_code = request.form['subject_code']
        co = request.form['co']
        question = request.form['question']
        option1 = request.form['option1']
        option2 = request.form['option2']
        option3 = request.form['option3']
        option4 = request.form['option4']
        answer = request.form['answer']
        
        # ✅ Check all fields filled
        # if not all([program, year, subject, subject_code, co, question, option1, option2, option3, option4, answer]):
        #     flash('All fields are required!', 'error')
        #     conn.close()
        #     return redirect(url_for('add_question', program=program, year=year))
        
        # ✅ Validate subject + code combination from DB
        c.execute("""
            SELECT * FROM subjects 
            WHERE subject_name=%s AND subject_code=%s 
            AND program=%s AND year=%s
        """, (subject, subject_code, program, year))
        subject_row = c.fetchone()
        
        if not subject_row:
            flash("❌ Invalid Subject selection! Please select correct Subject & Code.", "error")
            conn.close()
            return redirect(url_for('add_question', program=program, year=year))
            
        try:
            c.execute("""
                INSERT INTO questions 
                (program, year, subject, subject_code, co, question, option1, option2, option3, option4, answer) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (program, year, subject, subject_code, co, question, option1, option2, option3, option4, answer))
            conn.commit()
            flash('✅ Question added successfully!', 'success')
        except mysql.connector.Error as err:
            flash(f'Error adding question: {str(err)}', 'error')
        finally:
            conn.close()
            
        return redirect(url_for('add_question', program=program, year=year))
    
    conn.close()
    return render_template('add_question.html', subjects=subjects, program=program, year=year)


@app.route('/show_questions', methods=['GET'])
@admin_login_required
def show_questions():
    subject_filter = request.args.get('subject', '')

    conn = get_db_connection()
    c = conn.cursor(dictionary=True)

    # Fetch subjects that have at least one question for the dropdown
    c.execute("""
        SELECT DISTINCT s.subject_code, s.subject_name 
        FROM subjects s
        JOIN questions q ON s.subject_code = q.subject_code
        ORDER BY s.subject_name
    """)
    subjects = c.fetchall()

    # Fetch questions with subject name, filtered by selected subject
    # Replace the query block with this if you want no questions when no subject is selected
    query = '''
        SELECT q.id, q.program, q.year, q.subject_code, q.co, q.question, 
            q.option1, q.option2, q.option3, q.option4, q.answer, 
            s.subject_name AS subject
        FROM questions q
        LEFT JOIN subjects s ON q.subject_code = s.subject_code
        WHERE q.subject_code = %s
    '''
    params = [subject_filter] if subject_filter else ['']  # Default to an invalid subject_code if none selected
    query += " ORDER BY q.subject_code, q.co, q.id"
    c.execute(query, params)
    questions = c.fetchall()

    conn.close()

    return render_template(
        "show_questions.html",
        subjects=subjects,
        questions=questions,
        selected_subject=subject_filter
    )

@app.route('/delete_selected_questions', methods=['POST'])
@admin_login_required
def delete_selected_questions():
    conn = get_db_connection()
    c = conn.cursor()

    # Get the subject code from the query parameter
    subject_code = request.args.get('subject', '')

    if not subject_code:
        conn.close()
        return jsonify({'success': False, 'error': 'No subject selected'})

    try:
        # Delete all questions for the selected subject_code
        c.execute('DELETE FROM questions WHERE subject_code = %s', (subject_code,))
        conn.commit()
        deleted_count = c.rowcount
        conn.close()
        return jsonify({'success': True, 'message': f'Deleted {deleted_count} question(s)'})
    except mysql.connector.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/update_question/<int:question_id>', methods=['GET', 'POST'])
@admin_login_required
def update_question(question_id):

    conn = get_db_connection()
    c = conn.cursor(dictionary=True)

    if request.method == 'POST':

        question_text = request.form['question']
        option1 = request.form['option1']
        option2 = request.form['option2']
        option3 = request.form['option3']
        option4 = request.form['option4']
        answer = request.form['answer']

        image = request.files.get('image')

        # OPTION IMAGES
        option_images = []
        for i in range(1, 5):
            opt_img = request.files.get(f'option{i}_image')
            option_images.append(opt_img)

        image_path = None

        # QUESTION IMAGE
        if image and image.filename != '' and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = filename

        # OPTION IMAGE SAVE
        option_image_paths = []
        for opt_img in option_images:
            if opt_img and opt_img.filename != '' and allowed_file(opt_img.filename):
                filename = secure_filename(opt_img.filename)
                opt_img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                option_image_paths.append(filename)
            else:
                option_image_paths.append(None)

        update_query = """
            UPDATE questions
            SET question=%s,
                option1=%s,
                option2=%s,
                option3=%s,
                option4=%s,
                answer=%s,
                image_path = COALESCE(%s, image_path),
                option1_image = COALESCE(%s, option1_image),
                option2_image = COALESCE(%s, option2_image),
                option3_image = COALESCE(%s, option3_image),
                option4_image = COALESCE(%s, option4_image)
            WHERE id=%s
        """

        values = (
            question_text,
            option1,
            option2,
            option3,
            option4,
            answer,
            image_path,
            option_image_paths[0],
            option_image_paths[1],
            option_image_paths[2],
            option_image_paths[3],
            question_id
        )

        c.execute(update_query, values)
        conn.commit()
        flash("Question updated successfully!", "success")
        conn.close()
        return redirect(url_for('show_questions'))

    # GET METHOD
    c.execute("SELECT * FROM questions WHERE id=%s", (question_id,))
    question = c.fetchone()

    conn.close()

    return render_template('update_questions.html',
                           question=question)

@app.route('/delete_question/<int:question_id>')
@admin_login_required
def delete_question(question_id):
    subject_filter = request.args.get('subject', '')  # Preserve subject filter

    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("DELETE FROM questions WHERE id = %s", (question_id,))
        conn.commit()
        flash("Question deleted successfully!", "success")
    except mysql.connector.Error as e:
        conn.rollback()
        flash(f"Error deleting question: {str(e)}", "error")
    
    conn.close()

    return redirect(url_for('show_questions', subject=subject_filter))

@app.route('/add_subject', methods=['GET', 'POST'])
@admin_login_required
def add_subject():
    if request.method == 'POST':
        subject_name = request.form['subject_name']
        subject_code = request.form['subject_code']
        program = request.form['program']
        year = request.form['year']
        
        if not all([subject_name, subject_code, program, year]):
            flash('All fields are required!', 'error')
            return redirect(url_for('add_subject'))
            
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO subjects (subject_name, subject_code, program, year) VALUES (%s, %s, %s, %s)',
                      (subject_name, subject_code, program, year))
            conn.commit()
            flash('Subject added successfully!', 'success')
        except mysql.connector.Error as err:
            flash(f'Error: Subject code already exists! {str(err)}', 'error')
        finally:
            conn.close()
        return redirect(url_for('show_subjects'))
    return render_template('add_subject.html')


@app.route('/show_subjects', methods=['GET', 'POST'])
@admin_login_required
def show_subjects():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor(dictionary=True)

    program = request.args.get('program', '')
    year = request.args.get('year', '')

    # Build query with optional filters
    query = 'SELECT id, subject_name, subject_code, program, year FROM subjects'
    params = []
    if program or year:
        query += ' WHERE '
        conditions = []
        if program:
            conditions.append('program = %s')
            params.append(program)
        if year:
            conditions.append('year = %s')
            params.append(year)
        query += ' AND '.join(conditions)

    c.execute(query, params)
    subjects = c.fetchall()

    if request.method == 'POST':
        if 'release_subject' in request.form:
            subject_id = request.form['subject_id']
            c.execute('SELECT subject_code, program, year, subject_name FROM subjects WHERE id = %s', (subject_id,))
            subject = c.fetchone()
            if not subject:
                flash('Subject not found!', 'error')
                return redirect(url_for('show_subjects', program=program, year=year))

            subject_code = subject['subject_code']
            subject_program = subject['program']
            subject_year = subject['year']

            # Check if there are questions for this subject
            c.execute('SELECT COUNT(*) as count FROM questions WHERE subject_code = %s', (subject_code,))
            question_count = c.fetchone()['count']
            if question_count == 0:
                flash('No questions available for this subject to release!', 'error')
                return redirect(url_for('show_subjects', program=program, year=year))

            # Check distinct departments for the program and year
            c.execute('SELECT DISTINCT student_dept FROM students WHERE program = %s AND year = %s AND active_status = %s',
                      (subject_program, subject_year, 'ON'))
            departments = [row['student_dept'] for row in c.fetchall()]

            # If more than one department, return departments for dropdown
            if len(departments) > 1 and 'student_dept' not in request.form:
                return render_template('show_subjects.html', subjects=subjects, program=program, year=year,
                                     show_dept_modal=True, departments=departments, subject_id=subject_id)

            # Fetch students based on program, year, and (if provided) selected department
            student_query = 'SELECT roll_no, student_email FROM students WHERE program = %s AND year = %s AND active_status = %s'
            student_params = [subject_program, subject_year, 'ON']
            if 'student_dept' in request.form:
                student_query += ' AND student_dept = %s'
                student_params.append(request.form['student_dept'])

            c.execute(student_query, student_params)
            students = c.fetchall()

            # Fetch questions with options and answers for this subject
            c.execute('SELECT id, co, question, option1, option2, option3, option4, answer FROM questions WHERE subject_code = %s',
                      (subject_code,))
            questions = c.fetchall()

            # Send emails
            sender_email = os.getenv("GMAIL_USER")
            sender_password = os.getenv("GMAIL_APP_PASSWORD")

            subject_line = f"Quiz Results Released for {subject['subject_name']}"

            try:
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.starttls()
                    server.login(sender_email, sender_password)
                    for student in students:
                        recipient_email = student['student_email']  
                        if recipient_email:
                            table_html = '<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">'
                            table_html += '<tr><th>CO</th><th>Question</th><th>A</th><th>B</th><th>C</th><th>D</th><th>Answer</th><th>Your Answer</th></tr>'
                            for q in questions:
                                table_html += '<tr>'
                                table_html += f'<td>{q["co"] if q["co"] else "Not Set"}</td>'
                                table_html += f'<td>{q["question"]}</td>'
                                table_html += f'<td>{q["option1"]}</td>'
                                table_html += f'<td>{q["option2"]}</td>'
                                table_html += f'<td>{q["option3"]}</td>'
                                table_html += f'<td>{q["option4"]}</td>'
                                table_html += f'<td>{q["answer"] if q["answer"] else "Not Set"}</td>'

                                c.execute('SELECT is_correct FROM student_answers WHERE student_roll_no = %s AND question_id = %s',
                                          (student['roll_no'], q['id']))
                                answer = c.fetchone()
                                your_answer = '✅' if answer and answer['is_correct'] == 1 else '❌' if answer else 'Not Attempted'
                                table_html += f'<td>{your_answer}</td>'
                                table_html += '</tr>'
                            table_html += '</table>'

                            c.execute('SELECT score FROM results WHERE student_roll_no = %s AND subject_code = %s',
                                      (student['roll_no'], subject_code))
                            result = c.fetchone()
                            score = result['score'] if result else 'Not Attempted'

                            msg = MIMEMultipart()
                            msg['Subject'] = subject_line
                            msg['From'] = sender_email
                            msg['To'] = recipient_email
                            body = f"""
                            <html>
                            <body>
                                <p>Dear Student,</p>
                                <p>A quiz for <strong>{subject['subject_name']} ({subject_code})</strong> has been released.</p>
                                <p>Below are the questions for your reference:</p>
                                {table_html}
                                <p><strong>Your Quiz Score:</strong> {score}</p>
                                <p>Regards,<br>AAM</p>
                            </body>
                            </html>
                            """
                            msg.attach(MIMEText(body, 'html'))
                            server.sendmail(sender_email, recipient_email, msg.as_string())
                        else:
                            flash(f"No email found for student with roll no {student['roll_no']}. Skipping.", 'warning')
                    flash(f"Quiz released and emails sent to {len(students)} students!", 'success')
            except Exception as e:
                flash(f"Failed to send emails: {str(e)}", 'error')

            return redirect(url_for('show_subjects', program=program, year=year))

        elif 'assign_staff' in request.form:
            staff_name = request.form['staff_name']
            staff_email = request.form['staff_email']
            subject_code = request.form['subject_code']

            if not all([staff_name, staff_email, subject_code]):
                flash('All fields are required!', 'error')
                return redirect(url_for('show_subjects', program=program, year=year))

            try:
                c.execute('INSERT INTO staff (staff_name, email, subject_code) VALUES (%s, %s, %s)',
                          (staff_name, staff_email, subject_code))
                conn.commit()
                flash('Staff assigned successfully!', 'success')
            except mysql.connector.Error as err:
                conn.rollback()
                flash(f'Error assigning staff: {str(err)}', 'error')
            return redirect(url_for('show_subjects', program=program, year=year))

        subject_id = request.form['subject_id']
        subject_name = request.form['subject_name']
        subject_code = request.form['subject_code']
        try:
            c.execute('UPDATE subjects SET subject_name = %s, subject_code = %s WHERE id = %s',
                      (subject_name, subject_code, subject_id))
            conn.commit()
            flash('Subject updated successfully!', 'success')
        except mysql.connector.Error as e:
            conn.rollback()
            flash(f'Error updating subject: {str(e)}', 'error')
        return redirect(url_for('show_subjects', program=program, year=year))

    conn.close()
    return render_template('show_subjects.html', subjects=subjects, program=program, year=year)

@app.route('/get_subjects', methods=['GET'])
@admin_login_required
def get_subjects():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor(dictionary=True)

    program = request.args.get('program', '')
    year = request.args.get('year', '')

    query = 'SELECT subject_name, subject_code FROM subjects'
    params = []
    if program:
        query += ' WHERE program = %s'
        params.append(program)
    if year:
        query += ' AND year = %s' if 'WHERE' in query else ' WHERE year = %s'
        params.append(year)

    print(f"Executing query: {query} with params: {params}")  # Debug print
    c.execute(query, params)
    subjects = c.fetchall()
    print(f"Fetched subjects: {subjects}")  # Debug print
    conn.close()

    return jsonify(subjects)

@app.route('/delete_subject/<int:id>')
@admin_login_required
def delete_subject(id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM subjects WHERE id = %s', (id,))
        conn.commit()
        flash('Subject deleted successfully!', 'success')
    except mysql.connector.Error as err:
        flash(f'Error deleting subject: {str(err)}', 'error')
    finally:
        conn.close()
    return redirect(url_for('show_subjects'))
@app.route('/download_and_reset', methods=['POST'])
def download_and_reset():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Fetch student results
        cursor.execute("SELECT * FROM results")
        data = cursor.fetchall()

        # Create DataFrame
        df = pd.DataFrame(data)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Results')
        output.seek(0)

        # Reset quiz_status column to 'not_attempted'
        cursor.execute("UPDATE students SET quiz_status = %s, active_status = %s", ('not_attempted', 'ON'))
        cursor.execute("truncate table results")
        cursor.execute("truncate table student_answers")
        conn.commit()

        cursor.close()
        conn.close()

        return send_file(
            output,
            as_attachment=True,
            download_name='quiz_results.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print("Error in download_and_reset:", e)
        return jsonify({'error': str(e)}), 500

@app.route('/reset_quiz')
@admin_login_required
def reset_quiz():
    return render_template('reset_quiz.html')

@app.route('/upload_students', methods=['GET', 'POST'])
@admin_login_required
def upload_students():
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    
    program = request.args.get('program', '')
    year = request.args.get('year', '')
    query = 'SELECT id, subject_name, subject_code FROM subjects'
    params = []
    if program:
        query += ' WHERE program = %s'
        params.append(program)
    if year:
        query += ' AND year = %s' if 'WHERE' in query else ' WHERE year = %s'
        params.append(year)
    c.execute(query, params)
    subjects = c.fetchall()
    
    if request.method == 'POST':
        selected_program = request.form.get('program')
        selected_year = request.form.get('year')
        
        if not all([selected_program, selected_year]):
            flash('Program and Year are required!', 'error')
        elif 'file' not in request.files or not request.files['file'].filename:
            flash('No file uploaded!', 'error')
        elif request.files['file'] and request.files['file'].filename.endswith('.xlsx'):
            try:
                df = pd.read_excel(request.files['file'])
                required_columns = ['roll_no','name','student_dept','student_mail']
                if not all(col.lower() in df.columns for col in required_columns):
                    flash('Excel file must contain roll_no, name and student_dept ,student_mail columns!', 'error')
                else:
                    for _, row in df.iterrows():
                        try:
                            c.execute('INSERT INTO students (roll_no, name, program, year, quiz_status,student_dept,student_email) VALUES (%s, %s, %s, %s,%s,%s,%s)',
                                      (row['roll_no'], row['name'], selected_program, selected_year, 'not_attempted',row['student_dept'],row['student_mail']))
                        except mysql.connector.Error:
                            continue  # Skip duplicate roll numbers or invalid emails
                    conn.commit()
                    flash('Students uploaded successfully!', 'success')
            except Exception as e:
                flash(f'Error uploading file: {str(e)}', 'error')
        else:
            flash('Please upload a valid .xlsx file!', 'error')
            
        conn.close()
        return redirect(url_for('upload_students', program=selected_program, year=selected_year))
    
    conn.close()
    return render_template('upload_students.html', subjects=subjects, program=program, year=year)


@app.route('/upload_questions', methods=['GET', 'POST'])
@admin_login_required
def upload_questions():

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor(dictionary=True)

    program = request.args.get('program', '')
    year = request.args.get('year', '')

    query = 'SELECT subject_name, subject_code FROM subjects'
    params = []

    if program:
        query += ' WHERE program = %s'
        params.append(program)

    if year:
        query += ' AND year = %s' if 'WHERE' in query else ' WHERE year = %s'
        params.append(year)

    c.execute(query, params)
    subjects = c.fetchall()

    if request.method == 'POST':

        selected_program = request.form['program']
        selected_year = request.form['year']
        selected_subject = request.form['subject']
        selected_subject_code = request.form['subject_code']
        file = request.files['file']

        if not file or not selected_program or not selected_year or not selected_subject or not selected_subject_code:
            flash('All fields are required!', 'error')
            return redirect(url_for('upload_questions',
                                    program=selected_program,
                                    year=selected_year))

        if not file.filename.endswith('.xlsx'):
            flash('Please upload a valid .xlsx file!', 'error')
            return redirect(url_for('upload_questions',
                                    program=selected_program,
                                    year=selected_year))

        # 🔥 Read Excel
        df = pd.read_excel(file)

        # 🔹 Clean headers
        df.columns = (
            df.columns.astype(str)
            .str.strip()
            .str.lower()
            .str.replace(" ", "")
            .str.replace("_", "")
            .str.replace("-", "")
        )

        # 🔹 Column mapping
        column_mapping = {
            'co': 'co','c.o': 'co','c_o': 'co',
            'courseoutcome': 'co','co_no': 'co','cono': 'co',

            'question': 'question','questions': 'question',
            'questiontext': 'question','ques': 'question','q': 'question',

            'a': 'a','optiona': 'a','option_a': 'a',
            'b': 'b','optionb': 'b','option_b': 'b',
            'c': 'c','optionc': 'c','option_c': 'c',
            'd': 'd','optiond': 'd','option_d': 'd',

            'answer': 'answer','correctanswer': 'answer',
            'correct_answer': 'answer','ans': 'answer','key': 'answer',

            'qimage': 'q_image','q_image': 'q_image',
            'aimage': 'a_image','bimage': 'b_image',
            'cimage': 'c_image','dimage': 'd_image'
        }

        df.columns = [column_mapping.get(col, col) for col in df.columns]
        df = df.dropna(how='all')

        expected_columns = ['co','question','a','b','c','d','answer']
        if not all(col in df.columns for col in expected_columns):
            flash('Excel must contain: co, question, a, b, c, d, answer', 'error')
            return redirect(url_for('upload_questions',
                                    program=selected_program,
                                    year=selected_year))

        # 🔥 Clean Text Function (Supports Numbers)
        def clean_text(value):
            if pd.isna(value):
                return ''
            return str(value).strip()

        # 🔥 Clean Image Function (No "nan")
        def clean_image(value):
            if isinstance(value, str) and value.strip():
                return value.strip()
            return None

        # 🔥 Count Valid Questions
        question_count = 0
        for _, row in df.iterrows():
            question = clean_text(row.get('question'))
            q_image = clean_image(row.get('q_image'))

            if question or q_image:
                question_count += 1

        max_limit = 10 if selected_program == 'UG' else 15

        if question_count != max_limit:
            flash(f'{selected_program} must upload exactly {max_limit} valid questions. You uploaded {question_count}.', 'error')
            return redirect(url_for('upload_questions',
                                    program=selected_program,
                                    year=selected_year))

        # 🔥 Insert Data
        for index, row in df.iterrows():

            co = clean_text(row.get('co'))

            question = clean_text(row.get('question'))
            option1 = clean_text(row.get('a'))
            option2 = clean_text(row.get('b'))
            option3 = clean_text(row.get('c'))
            option4 = clean_text(row.get('d'))
            answer_raw = clean_text(row.get('answer')).lower()

            q_image = clean_image(row.get('q_image'))
            a_image = clean_image(row.get('a_image'))
            b_image = clean_image(row.get('b_image'))
            c_image = clean_image(row.get('c_image'))
            d_image = clean_image(row.get('d_image'))

            if not question and not q_image:
                continue

            options = {'a': option1, 'b': option2, 'c': option3, 'd': option4}
            correct_letter = None

            if answer_raw in options:
                correct_letter = answer_raw
            elif answer_raw in ['1','2','3','4']:
                correct_letter = ['a','b','c','d'][int(answer_raw)-1]
            else:
                for letter, text in options.items():
                    if text and text.lower() in answer_raw:
                        correct_letter = letter
                        break

            if not correct_letter:
                flash(f'Invalid answer "{answer_raw}" in row {index + 2}.', 'error')
                return redirect(url_for('upload_questions',
                                        program=selected_program,
                                        year=selected_year))

            answer_value = f"option{['a','b','c','d'].index(correct_letter)+1}"

            c.execute("""
                INSERT INTO questions
                (program, year, subject, subject_code,
                 co, question, option1, option2, option3, option4, answer,
                 image_path, option1_image, option2_image, option3_image, option4_image)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                selected_program,
                selected_year,
                selected_subject,
                selected_subject_code,
                co,
                question,
                option1,
                option2,
                option3,
                option4,
                answer_value,
                q_image,
                a_image,
                b_image,
                c_image,
                d_image
            ))

        conn.commit()
        flash('Questions uploaded successfully!', 'success')
        return redirect(url_for('upload_questions',
                                program=selected_program,
                                year=selected_year))

    conn.close()

    return render_template('upload_questions.html',
                           subjects=subjects,
                           program=program,
                           year=year)

@app.route('/set_entry_code', methods=['GET', 'POST'])
@admin_login_required
def set_entry_code():
    if request.method == 'POST':
        entry_code = request.form['entry_code']
        if not entry_code:
            flash('Entry code is required!', 'error')
            return redirect(url_for('set_entry_code'))
            
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO quiz_entries (entry_code) VALUES (%s)', (entry_code,))
            conn.commit()
            flash('Entry code set successfully!', 'success')
        except mysql.connector.Error as err:
            flash(f'Error setting entry code: {str(err)}', 'error')
        finally:
            conn.close()
        return redirect(url_for('admin_dashboard'))
    return render_template('set_entry_code.html')

@app.route('/view_results')
@admin_login_required
def view_results():

    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    search = request.args.get('search', '')
    program = request.args.get('program', '')
    year = request.args.get('year', '')
    department = request.args.get('student_dept', '')
    c.execute('SELECT DISTINCT student_dept FROM students WHERE student_dept IS NOT NULL AND student_dept != ""')
    departments = [row['student_dept'] for row in c.fetchall()]

    # Determine the subject_code based on results for filtered students
    subject_code = "N/A"
    subject_name = "N/A"
    max_marks = "N/A"
    co_counts = {}
    department_name = department if department else "N/A"
    class_name = "N/A"
    if year:
        class_name = f"{year} {department_name if department_name != 'N/A' else 'All'} A"

    # Build conditions and params for filtering students
    params = []
    conditions = []
    if search:
        conditions.append('(s.name LIKE %s OR s.roll_no LIKE %s)')
        params.extend([f'%{search}%', f'%{search}%'])
    if program:
        conditions.append('s.program = %s')
        params.append(program)
    if year:
        conditions.append('s.year = %s')
        params.append(year)
    if department:
        conditions.append('s.student_dept = %s')
        params.append(department)

    if conditions:
        # Find the subject_code with the most results for the filtered students
        query_subject = '''
            SELECT r.subject_code, COUNT(*) AS cnt
            FROM results r
            JOIN students s ON s.roll_no = r.student_roll_no
            WHERE ''' + ' AND '.join(conditions) + '''
            GROUP BY r.subject_code
            ORDER BY cnt DESC
            LIMIT 1
        '''
        c.execute(query_subject, params)
        sub_res = c.fetchone()
        if sub_res:
            subject_code = sub_res['subject_code']

    if subject_code == "N/A" and program and year:
        # Fallback to any subject for the program/year if no results
        c.execute("SELECT subject_code FROM subjects WHERE program = %s AND year = %s LIMIT 1", (program, year))
        fallback_sub = c.fetchone()
        if fallback_sub:
            subject_code = fallback_sub['subject_code']

    if subject_code != "N/A":
        # Fetch subject_name
        c.execute("SELECT subject_name FROM subjects WHERE subject_code = %s LIMIT 1", (subject_code,))
        sub_name = c.fetchone()
        subject_name = sub_name['subject_name'] if sub_name else "N/A"

        # Fetch max_marks (total questions)
        c.execute("SELECT COUNT(*) AS total_qns FROM questions WHERE subject_code = %s", (subject_code,))
        q_res = c.fetchone()
        max_marks = q_res['total_qns'] if q_res else "N/A"

        # Fetch CO-wise counts
        c.execute("""
            SELECT co, COUNT(*) AS count
            FROM questions
            WHERE subject_code = %s
            GROUP BY co
            ORDER BY co
        """, (subject_code,))
        co_results = c.fetchall()
        co_counts = {row['co']: row['count'] for row in co_results}

    # Now build the main query, filtering results by the determined subject_code
    query = '''
        SELECT
            s.roll_no AS student_roll_no,
            s.name,
            COALESCE(MAX(s.quiz_status), 'not_attempted') AS quiz_status,
            s.program,
            s.year,
            s.student_dept,
            %s AS subject_code,
            %s AS subject_name,
            COALESCE(r.co1_score, 0) AS co1_score,
            COALESCE(r.co2_score, 0) AS co2_score,
            COALESCE(r.co3_score, 0) AS co3_score,
            COALESCE(r.co4_score, 0) AS co4_score,
            COALESCE(r.co5_score, 0) AS co5_score,
            COALESCE(r.score, 0) AS total_mark
        FROM students s
        LEFT JOIN results r ON s.roll_no = r.student_roll_no AND r.subject_code = %s
    '''
    params_main = [subject_code, subject_name, subject_code] + params  # Add subject params first
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' GROUP BY s.roll_no, s.name, s.program, s.year, s.student_dept, r.co1_score, r.co2_score, r.co3_score, r.co4_score, r.co5_score, r.score ORDER BY s.roll_no ASC'
    c.execute(query, params_main)
    results = c.fetchall()

    # Update department_name if needed
    if results and department_name == "N/A":
        department_name = results[0]['student_dept'] or "N/A"

    from flask import jsonify

# 🔥 AJAX request – return JSON only
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        ajax_data = []
        for r in results:
            is_not_attempted = r['quiz_status'].lower() == 'not_attempted' or subject_code == 'N/A'
            ajax_data.append({
                "roll_no": r['student_roll_no'],
                "name": r['name'],
                "co1": "-" if is_not_attempted else r['co1_score'],
                "co2": "-" if is_not_attempted else r['co2_score'],
                "co3": "-" if is_not_attempted else r['co3_score'],
                "co4": "-" if is_not_attempted else r['co4_score'],
                "co5": "-" if is_not_attempted else r['co5_score'],
                "total": "-" if is_not_attempted else r['total_mark'],
            })

        return jsonify(ajax_data)

    if request.args.get('format') == 'excel':
        df = pd.DataFrame([
            {
                'Roll Number': r['student_roll_no'],
                'Student Name': r['name'],
                'CO1': 'A' if r['quiz_status'].lower() == 'not_attempted' or subject_code == 'N/A' else r['co1_score'],
                'CO2': 'A' if r['quiz_status'].lower() == 'not_attempted' or subject_code == 'N/A' else r['co2_score'],
                'CO3': 'A' if r['quiz_status'].lower() == 'not_attempted' or subject_code == 'N/A' else r['co3_score'],
                'CO4': 'A' if r['quiz_status'].lower() == 'not_attempted' or subject_code == 'N/A' else r['co4_score'],
                'CO5': 'A' if r['quiz_status'].lower() == 'not_attempted' or subject_code == 'N/A' else r['co5_score'],
                'Total': 'A' if r['quiz_status'].lower() == 'not_attempted' or subject_code == 'N/A' else r['total_mark']
            } for r in results
        ])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Results')
        output.seek(0)
        base_dir = "results"
        os.makedirs(base_dir, exist_ok=True)
        subfolder = f"{program}-{year}" if program and year else "default"
        filename = f"{subject_name.replace(' ', '_')}.xlsx" if subject_name != "N/A" else f"results_{department_name}_{year}.xlsx"
        file_path = os.path.join(base_dir, subfolder, filename)
        with open(file_path, 'wb') as f:
            f.write(output.getvalue())
        with open(file_path, 'rb') as f:
            response = make_response(f.read())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return response

    # PDF download and email to staff
    if request.args.get('format') == 'pdf':
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        try:
            logo = Image("static/logo.png", width=450, height=80)
            elements.append(logo)
        except:
            pass
        elements.append(Paragraph(f"<b>DEPARTMENT OF {department_name.upper()}</b>", styles['Title']))
        elements.append(Paragraph("Quiz Results", styles['Title']))
        elements.append(Spacer(1, 12))
        # Test details with CO counts
        details = [
            ["Subject Code:", subject_code, "Subject Name:", subject_name],
            ["Max Marks:", str(max_marks), "Class:", class_name],
            ["Date of Test:", datetime.now().strftime("%d-%m-%Y %H:%M"), "Date of Submission:", ""]
        ]
        # Add CO-wise question count
        co_count_str = ", ".join([f"CO{k}: {v}" for k, v in sorted(co_counts.items())]) or "N/A"
        details.append(["CO-Count : ", co_count_str, "", ""])
        details_table = Table(details, colWidths=[80, 150, 80, 150])
        elements.append(details_table)
        elements.append(Spacer(1, 12))
        # Results table
        table_data = [["Roll Number", "Student Name", "CO1", "CO2", "CO3", "CO4", "CO5", "Total"]]
        for r in results:
            is_not_attempted = r['quiz_status'].lower() == 'not_attempted' or subject_code == 'N/A'
            table_data.append([
                r['student_roll_no'],
                r['name'],
                "A" if is_not_attempted else str(r['co1_score']),
                "A" if is_not_attempted else str(r['co2_score']),
                "A" if is_not_attempted else str(r['co3_score']),
                "A" if is_not_attempted else str(r['co4_score']),
                "A" if is_not_attempted else str(r['co5_score']),
                "A" if is_not_attempted else str(r['total_mark'])
            ])
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')
        ]))
        elements.append(table)
        elements.append(Spacer(1, 24))
        # Signatures
        sigs = [["", "Staff in-charge", "", "Head", "", "Principal", ""]]
        sig_table = Table(sigs, colWidths=[100, 100, 100, 100, 100, 100, 100])
        elements.append(sig_table)
        doc.build(elements)
        buffer.seek(0)
        # Define base directory and subfolder
        base_dir = "results"
        os.makedirs(base_dir, exist_ok=True)
        subfolder = f"{program}-{year}" if program and year else "default"
        os.makedirs(os.path.join(base_dir, subfolder), exist_ok=True)
        filename = f"{subject_name.replace(' ', '_')}.pdf" if subject_name != "N/A" else f"results_{department_name}_{year}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        file_path = os.path.join(base_dir, subfolder, filename)
        with open(file_path, 'wb') as f:
            f.write(buffer.getvalue())
        # Send PDF to staff email
        sender_email = os.getenv("GMAIL_USER")
        sender_password = os.getenv("GMAIL_APP_PASSWORD")
        print(os.getenv("GMAIL_USER"))
        print(os.getenv("GMAIL_APP_PASSWORD"))
        if subject_code != "N/A":
            c.execute('SELECT email FROM staff WHERE subject_code = %s', (subject_code,))
            staff = c.fetchone()
            if staff and staff['email']:
                with open(file_path, 'rb') as f:
                    attachment = MIMEApplication(f.read(), _subtype="pdf")
                    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg = MIMEMultipart()
                    msg['Subject'] = f"Quiz Results for {subject_name}"
                    msg['From'] = sender_email
                    msg['To'] = staff['email']
                    msg.attach(attachment)
                    with smtplib.SMTP('smtp.gmail.com',587) as server:
                        server.starttls()
                        server.login(sender_email,sender_password)
                        server.sendmail(sender_email, staff['email'], msg.as_string())
                flash(f"PDF sent to staff email: {staff['email']}", 'success')
            else:
                flash(f"No staff email found for subject {subject_code}.", 'warning')
        else:
            flash("No subject code available to send email.", 'warning')
        # Serve the file as a response for download
        with open(file_path, 'rb') as f:
            response = make_response(f.read())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-type'] = 'application/pdf'
        return response
    conn.close()
    return render_template(
        'view_results.html',
        results=results,
        search=search,
        program=program,
        year=year,
        departments=departments,
        department=department
    )


@app.route('/logout')
@admin_login_required
def admin_logout():
    session.pop('admin', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('admin_login'))

@app.route('/set_quiz_subject', methods=['GET', 'POST'])
@admin_login_required
def set_quiz_subject():
    if request.method == 'POST':
        program = request.form['program']
        year = request.form['year']
        subject_code = request.form['subject_code']
        action = request.form['action']

        conn = get_db_connection()
        c = conn.cursor()

        try:
            if action == "off":
                c.execute('DELETE FROM quiz_access WHERE program = %s AND year = %s AND allowed_subject_code = %s',
                          (program, year, subject_code))
                conn.commit()
                flash(f'{subject_code} access removed!', 'success')

            elif action == "on":
                # Only insert if not already present
                c.execute('SELECT 1 FROM quiz_access WHERE program = %s AND year = %s AND allowed_subject_code = %s',
                          (program, year, subject_code))
                if not c.fetchone():
                    c.execute('INSERT INTO quiz_access (program, year, allowed_subject_code) VALUES (%s, %s, %s)',
                              (program, year, subject_code))
                    conn.commit()
                    flash(f'{subject_code} access granted!', 'success')

        except mysql.connector.Error as err:
            flash(f'Error updating quiz subject: {str(err)}', 'error')
        finally:
            conn.close()

        return redirect(url_for('set_quiz_subject'))

    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    c.execute('SELECT program, year, subject_code FROM subjects')
    subject_options = c.fetchall()

    # Get all allowed subjects
    c.execute('SELECT allowed_subject_code FROM quiz_access')
    current_allowed_subjects = {row['allowed_subject_code'] for row in c.fetchall()}

    conn.close()
    return render_template('set_quiz_subject.html',
                           subject_options=subject_options,
                           current_allowed_subjects=current_allowed_subjects)


@app.route('/', methods=['GET', 'POST'])
def quiz_login():
    if request.method == 'POST':
        roll_no = request.form['roll_no'].upper()
        entry_code = request.form['entry_code']

        conn = get_db_connection()
        c = conn.cursor(dictionary=True)

        c.execute('SELECT * FROM students WHERE roll_no = %s', (roll_no,))
        student = c.fetchone()

        if student:
            program = student['program']
            year = student['year']
            quiz_status = student['quiz_status']

            c.execute('''
                UPDATE students 
                SET quiz_status = %s 
                WHERE roll_no = %s AND quiz_status = %s
            ''', ('attempted', roll_no, 'not_attempted'))

            conn.commit()

            if c.rowcount == 0:
                flash('You have already attempted the quiz!', 'error')
                conn.close()
                return render_template('quiz_login.html')

            c.execute('SELECT allowed_subject_code FROM quiz_access WHERE program = %s AND year = %s', (program, year))
            allowed_subject = c.fetchone()

            c.execute('SELECT * FROM quiz_entries WHERE entry_code = %s', (entry_code,))
            valid_code = c.fetchone()

            if allowed_subject and valid_code:
                subject_code = allowed_subject['allowed_subject_code']
                c.execute('SELECT subject_name FROM subjects WHERE subject_code = %s', (subject_code,))
                sub = c.fetchone()
                
                # Update status
                c.execute('UPDATE students SET quiz_status = %s WHERE roll_no = %s', ('attempted', roll_no))
                conn.commit()

                # Store in session — CORRECT KEYS!
                session['student'] = {
                    'roll_no': roll_no,
                    'name': student['name'],
                    'program': student['program'],
                    'year': student['year'],
                    'subject_code': subject_code,
                    'subject_name': sub['subject_name']
                }
                conn.close()
                return redirect(url_for('quiz_start'))  # Welcome page first
            else:
                flash('Invalid entry code or quiz not available for your class!', 'error')
        else:
            flash('Invalid roll number!', 'error')

        conn.close()

    return render_template('quiz_login.html')



@app.route('/quiz_questions')
def quiz_questions():
    if 'student' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('quiz_login'))

    # Same logic as your current quiz_start but without the card
    # Fetch questions, shuffle, etc.
    # Render your existing quiz_start.html but rename it to quiz_questions.html
    # Remove the start card — only show questions + submit button

    return render_template('quiz_questions.html', 
                          questions=session.get('questions', []),
                          student_name=session['student']['name'],
                          roll_no=session['student']['roll_no'])

@app.route('/quiz_start')
def quiz_start():
    if 'student' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('quiz_login'))

    conn = get_db_connection()
    c = conn.cursor(dictionary=True)

    try:
        roll_no = session['student']['roll_no']

        # 🔹 Check active student
        c.execute(
            'SELECT * FROM students WHERE roll_no = %s AND active_status = %s',
            (roll_no, 'ON')
        )
        student = c.fetchone()

        if not student:
            flash('The Student is Absent Today', 'error')
            return redirect(url_for('quiz_login'))

        # 🔹 Check quiz access
        c.execute("""
            SELECT allowed_subject_code FROM quiz_access
            WHERE program = %s AND year = %s
        """, (student['program'], student['year']))

        access = c.fetchone()

        if not access or access['allowed_subject_code'] != session['student']['subject_code']:
            flash('Quiz is not currently available for your class.', 'error')
            return redirect(url_for('quiz_login'))

        # 🔹 Fetch questions
        c.execute(
            'SELECT * FROM questions WHERE subject_code = %s',
            (session['student']['subject_code'],)
        )
        questions = c.fetchall()

        if not questions:
            flash('No questions found for this subject!', 'error')
            return redirect(url_for('quiz_login'))

        # 🔥 CLEAN IMAGE FIELDS PROPERLY
        for q in questions:

            # Clean question image
            if not q.get('image_path') or str(q['image_path']).lower() in ['none', 'nan', '']:
                q['image_path'] = None

            # Clean option images
            for i in range(1, 5):
                key = f'option{i}_image'
                if not q.get(key) or str(q[key]).lower() in ['none', 'nan', '']:
                    q[key] = None

        # Shuffle after cleaning
        random.shuffle(questions)

        # Store in session
        session['questions'] = questions

        if 'start_time' not in session:
            session['start_time'] = datetime.now().isoformat()

        session['tab_switches'] = 0

    except Exception as err:
        flash(f'Database error: {str(err)}', 'error')
        return redirect(url_for('quiz_login'))

    finally:
        conn.close()

    return render_template(
        'quiz_start.html',
        questions=session['questions'],
        student_name=session['student']['name'],
        roll_no=session['student']['roll_no']
    )
    
@app.route('/quiz_submit', methods=['POST'])
def quiz_submit():
    if 'student' not in session or 'questions' not in session:
        flash('Session expired!', 'error')
        return redirect(url_for('quiz_login'))

    student = session['student']
    answers = request.form
    correct = 0
    co_marks = {'CO1': 0, 'CO2': 0, 'CO3': 0, 'CO4': 0, 'CO5': 0}

    conn = get_db_connection()
    c = conn.cursor()

    try:
        for q in session['questions']:
            qid = str(q['id'])
            is_correct = 0

            c.execute("SELECT co FROM questions WHERE id = %s", (q['id'],))
            result = c.fetchone()
            co_key = f"CO{result[0]}" if result else None

            if qid in answers and answers[qid].strip().lower() == q['answer'].strip().lower():
                correct += 1
                is_correct = 1
                if co_key and co_key in co_marks:
                    co_marks[co_key] += 1

            c.execute('INSERT INTO student_answers (student_roll_no, question_id, is_correct) VALUES (%s, %s, %s)',
                      (student['roll_no'], q['id'], is_correct))

        # FIX: Use 'subject_code' not 'subject'
        c.execute('''
            INSERT INTO results 
            (student_roll_no, subject_code, score, co1_score, co2_score, co3_score, co4_score, co5_score) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            student['roll_no'], 
            student['subject_code'],  # ← Correct key
            correct,
            co_marks['CO1'], co_marks['CO2'], co_marks['CO3'],
            co_marks['CO4'], co_marks['CO5']
        ))

        conn.commit()

    except Exception as err:
        conn.rollback()
        flash(f'Error saving results: {str(err)}', 'error')
    finally:
        conn.close()

    session['score'] = correct
    session['total_questions'] = len(session['questions'])
    
    # Clear quiz data
    session.pop('questions', None)
    session.pop('start_time', None)

    return redirect(url_for('quiz_result'))

@app.route('/quiz_result')
def quiz_result():
    if 'student' not in session or 'score' not in session:
        flash('Please complete the quiz first!', 'error')
        return redirect(url_for('quiz_login'))
        
    score = session['score']
    total_questions = session['total_questions']
    
    session.pop('questions', None)
    session.pop('start_time', None)
    session.pop('tab_switches', None)
    session.pop('score', None)
    session.pop('total_questions', None)
    session.pop('student', None)
    
    return render_template('quiz_result.html', score=score, total_questions=total_questions)

@app.route('/quiz/track_tab_switch', methods=['POST'])
def track_tab_switch():
    if 'student' in session:
        session['tab_switches'] = session.get('tab_switches', 0) + 1
        if session['tab_switches'] >3:
            return jsonify({'auto_submit': True})
    return jsonify({'auto_submit': False})

@app.route('/alter_student_year', methods=['POST'])
@admin_login_required
def alter_student_year():
    conn = get_db_connection()
    c = conn.cursor()

    program = request.form.get('program', '')
    year = request.form.get('year', '')
    department = request.form.get('student_dept', '')
    new_year = request.form.get('new_year')

    if not new_year or not year:
        return jsonify({'success': False, 'error': 'Invalid year'})

    query = 'UPDATE students SET year = %s WHERE year = %s'
    params = [new_year, year]

    if program:
        query += ' AND program = %s'
        params.append(program)
    if department:
        query += ' AND student_dept = %s'
        params.append(department)

    try:
        c.execute(query, params)
        conn.commit()
        updated = c.rowcount
        return jsonify({'success': True, 'updated_count': updated})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000)