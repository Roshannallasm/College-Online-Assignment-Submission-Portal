from flask import send_file, abort
from flask import session
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import request, flash, redirect, url_for, render_template
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from docx2pdf import convert
from datetime import datetime
from flask import jsonify, request
from flask import render_template
from werkzeug.utils import secure_filename
import sqlite3
import os

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

def allowed_file(filename):
     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secure secret key
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROFILE_UPLOAD_FOLDER'] = 'static/profilephotos'

# SQLite database initialization
conn = sqlite3.connect('assignments.db')
c = conn.cursor()

# Assuming you have a global list to store notifications
notifications = []
# Ensure that the 'name' column exists in the 'users' table
try:
     c.execute('ALTER TABLE users ADD COLUMN name TEXT')
except sqlite3.OperationalError as e:
     pass  # Column already exists, ignore the error

# Ensure that the 'submitted_by' column exists in the 'assignments' table
try:
     c.execute('ALTER TABLE assignments ADD COLUMN submitted_by TEXT')
except sqlite3.OperationalError as e:
     pass  # Column already exists, ignore the error

# Ensure that the 'status', 'marks', and 'comments' columns exist in the 'assignments' table
try:
     c.execute('SELECT status, marks, comments FROM assignments LIMIT 1')
except sqlite3.OperationalError:
     c.execute('ALTER TABLE assignments ADD COLUMN status TEXT')
     c.execute('ALTER TABLE assignments ADD COLUMN marks INTEGER')
     c.execute('ALTER TABLE assignments ADD COLUMN comments TEXT')
     conn.commit()

conn.commit()
conn.close()

conn = sqlite3.connect('notification.db')
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS notification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        date TEXT NOT NULL
    )
''')

conn.commit()
conn.close()

# Function to authenticate user
def authenticate_user(username, password):
     conn = sqlite3.connect('assignments.db')
     c = conn.cursor()
     c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
     user = c.fetchone()
     conn.close()
     return user

# Function to get user type
def get_user_type(username):
     conn = sqlite3.connect('assignments.db')
     c = conn.cursor()
     c.execute('SELECT role FROM users WHERE username=?', (username,))
     user_type = c.fetchone()[0]
     conn.close()
     return user_type

# Function to get user name
def get_user_name(username):
     conn = sqlite3.connect('assignments.db')
     c = conn.cursor()
     c.execute('SELECT name FROM users WHERE username=?', (username,))
     user_name = c.fetchone()[0]
     conn.close()
     return user_name

# Function to get assignments for a specific user
def get_user_assignments(username):
     conn = sqlite3.connect('assignments.db')
     c = conn.cursor()
     c.execute('SELECT * FROM assignments WHERE submitted_by=?', (username,))
     assignments = c.fetchall()
     conn.close()
     return assignments

def get_student_names_from_database(query):
     # Assuming you have a 'users' table with 'name' and 'username' columns
     conn = sqlite3.connect('assignments.db')
     c = conn.cursor()
     c.execute('SELECT name, username FROM users WHERE LOWER(name) LIKE ? LIMIT 5', ('%' + query + '%',))
     student_names = [{'name': name, 'username': username} for name, username in c.fetchall()]
     conn.close()
     return student_names

def get_assignments_for_user(username):
     # Assuming you have an 'assignments' table with relevant columns
     conn = sqlite3.connect('assignments.db')
     c = conn.cursor()
     c.execute('SELECT name, status, marks FROM assignments WHERE submitted_by=?', (username,))
     assignments = [{'name': name, 'status': status, 'marks': marks} for name, status, marks in c.fetchall()]
     conn.close()
     return assignments

@app.route('/')
def index():
     if 'username' in session:
         user_type = get_user_type(session['username'])
         if user_type == 'student':
             return redirect(url_for('student_dashboard'))
         elif user_type == 'faculty':
             return redirect(url_for('faculty_dashboard'))
     return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
     if request.method == 'POST':
         username = request.form['username']
         password = request.form['password']
         user = authenticate_user(username, password)

         if user:
             session['username'] = username
             flash('Login successful!', 'success')
             return redirect(url_for('index'))
         else:
             flash('Invalid username or password', 'error')

     return render_template('login.html')

@app.route('/logout')
def logout():
     session.pop('username', None)
     return redirect(url_for('login'))

@app.route('/student_dashboard', methods=['GET', 'POST'])
def student_dashboard():
     if 'username' in session and get_user_type(session['username']) == 'student':
         if request.method == 'POST':
             file = request.files['file']

             if file.filename == '':
                 flash('No selected file', 'error')
                 return redirect(request.url)

             file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
             file.save(file_path)

             name = request.form['name']

             conn = sqlite3.connect('assignments.db')
             c = conn.cursor()
             c.execute('INSERT INTO assignments (name, file_path, submitted_by) VALUES (?, ?, ?)', (name, file_path, session['username']))
             conn.commit()

             # Fetch the updated assignments after submission
             c.execute('SELECT * FROM assignments WHERE submitted_by=?', (session['username'],))
             assignments = c.fetchall()

             conn.close()

             flash('Assignment submitted successfully!', 'success')
             return redirect(url_for('student_dashboard'))
       
         # Retrieve all notifications from the database
         conn = sqlite3.connect('notification.db')
         c = conn.cursor()

         # Fetch notifications from the database
         c.execute('SELECT * FROM notification ORDER BY date DESC')
         notificationss = c.fetchall()

          # Print all notifications for debugging
         print("All Notifications:", notificationss)

         conn.close()

         # Fetch assignments for the student
         assignments = get_user_assignments(session['username'])
         return render_template('student_dashboard.html', username=session['username'], assignments=assignments, notificationss=notificationss)
     else:
         flash('Please log in as a student to access the dashboard', 'error')
         return redirect(url_for('login'))

@app.route('/upload_profile_photo', methods=['POST'])
def upload_profile_photo():
    if 'username' in session:  # Check if user is logged in
        # Assuming you have a 'users' table with columns 'username', 'name', 'email', etc.
        username = session['username']  # Get the username from the session
        try:
            if 'photo' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['photo']

            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400

            # Construct the upload path
            upload_path = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], file.filename)

            # Save the file to the specified upload path
            file.save(upload_path)

            # Update the database with the file path
            conn = sqlite3.connect('assignments.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET photo_path = ? WHERE username = ?", (file.filename, username))
            conn.commit()
            conn.close()

            return jsonify({'message': 'Profile photo uploaded successfully', 'upload_path': upload_path}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'User not logged in'}), 401  # Return 401 if user is not logged in

@app.route('/get_profile_photo', methods=['GET'])
def get_profile_photo():
    if 'username' in session:
        username = session['username']
        conn = sqlite3.connect('assignments.db')
        c = conn.cursor()
        c.execute('SELECT photo_path FROM users WHERE username=?', (username,))
        photo_path = c.fetchone()
        conn.close()
        # Print photo_path for debugging
        if photo_path:
            # Print the photo path being returned
            return send_from_directory(app.config['PROFILE_UPLOAD_FOLDER'], photo_path[0])
        else:
            default_image_path = 'default_logo.jpg'
            return send_from_directory(app.config['PROFILE_UPLOAD_FOLDER'],default_image_path )
    else:
        print("User not logged in.")  # Print if user is not logged in
        return jsonify({'error': 'User not logged in'}), 401
    
@app.route('/faculty_dashboard')
def faculty_dashboard():
    if 'username' in session and get_user_type(session['username']) == 'faculty':
        conn = sqlite3.connect('assignments.db')
        c = conn.cursor()

        # Retrieve all assignments from the database
        c.execute('SELECT * FROM assignments')
        assignments = c.fetchall()

        # Retrieve all notifications from the database
        conn = sqlite3.connect('notification.db')
        c = conn.cursor()

        # Fetch notifications from the database
        c.execute('SELECT * FROM notification ORDER BY date DESC')
        notifications = c.fetchall()

        # Print all assignments for debugging
        print("All Assignments:", assignments)

        # Filter assignments that are accepted (including 'Approved') and evaluated
        accepted_assignments = [assignment for assignment in assignments if assignment[4] in ('Accepted', 'Approved') and assignment[5] is not None]

        # Reverse the order of accepted_assignments
        accepted_assignments = accepted_assignments[::-1]

        # Filter assignments that are rejected
        rejected_assignments = [assignment for assignment in assignments if assignment[4] == 'Rejected']

        # Reverse the order of rejected_assignments
        rejected_assignments = rejected_assignments[::-1]

        # Print rejected_assignments for debugging
        print("Rejected Assignments:", rejected_assignments)

        # Filter assignments that are not evaluated
        new_assignments = [assignment for assignment in assignments if not assignment[4]]

        # Reverse the order of new_assignments
        new_assignments = new_assignments[::-1]

        # Print all notifications for debugging
        print("All Notifications:", notifications)

        conn.close()

        return render_template('faculty_dashboard.html', username=session['username'], new_assignments=new_assignments, accepted_assignments=accepted_assignments, rejected_assignments=rejected_assignments, notifications=notifications)
    else:
        flash('Please log in as faculty to access the dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
     if request.method == 'POST':
         # Retrieve form data
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        role = request.form['role']
        id_rollno = request.form['id']
        gender = request.form['gender']
        contact_number = request.form['contact']
        email = request.form['email']
        secret_code = request.form['secretCode']  # Assuming the name of the input field is 'secretCode'

        # Insert the user data into the database
        try:
            conn = sqlite3.connect('assignments.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, name, role, id_rollno, gender, contact_number, email, secret_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (username, password, name, role, id_rollno, gender, contact_number, email, secret_code))
            conn.commit()
            conn.close()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))  # Redirect to the login page after successful registration
        except sqlite3.Error as e:
            print("SQLite error:", e)
           # Handle the error, possibly by displaying an error message to the user
            return render_template('error.html')  # Render a template for displaying the error
     # If the request method is GET, render the registration form template
     return render_template('register.html')

@app.route('/submit_assignment', methods=['POST'])
def submit_assignment():
    if 'username' in session and get_user_type(session['username']) == 'student':
        if request.method == 'POST':
            # Handle the form submission logic here
            name = request.form['name']
            file = request.files['file']
            if file and allowed_file(file.filename):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)

                # Convert .doc to .pdf if necessary
                if file.filename.lower().endswith('.doc'):
                    pdf_path = os.path.splitext(file_path)[0] + '.pdf'
                    convert(file_path, pdf_path)
                    os.remove(file_path)  # Remove the original .doc file
                    file_path = pdf_path

                conn = sqlite3.connect('assignments.db')
                c = conn.cursor()
                c.execute('INSERT INTO assignments (name, file_path, submitted_by) VALUES (?, ?, ?)',
                          (name, file_path, session['username']))
                conn.commit()

                # Fetch the updated assignments after submission
                c.execute('SELECT * FROM assignments WHERE submitted_by=?', (session['username'],))
                assignments = c.fetchall()
                 # Print all notifications for debugging
                print("All Notifications:", notifications)

                conn.close()

                flash('Assignment submitted successfully!', 'success')
                return redirect(url_for('student_dashboard'))
            else:
                flash('Invalid file format. Please upload a .pdf, .doc, or .docx file.', 'error')
                return redirect(request.url)

    flash('Please log in as a student to submit assignments', 'error')
    return redirect(url_for('login'))

@app.route('/evaluate_assignment/<int:assignment_id>', methods=['GET', 'POST'])
def evaluate_assignment(assignment_id):
    if 'username' in session and get_user_type(session['username']) == 'faculty':
        conn = sqlite3.connect('assignments.db')
        c = conn.cursor()
        c.execute('SELECT * FROM assignments WHERE id=?', (assignment_id,))
        assignment = c.fetchone()

        if assignment:
            if request.method == 'POST':
                status = request.form['status']
                marks = request.form['marks']
                comments = request.form['comments']

                c.execute('UPDATE assignments SET status=?, marks=?, comments=? WHERE id=?', (status, marks, comments, assignment_id))
                conn.commit()
                conn.close()

                flash('Evaluation saved successfully!', 'success')
                return redirect(url_for('faculty_dashboard'))

            return render_template('evaluate_assignment.html', username=session['username'], assignment=assignment)
        else:
            flash('Assignment not found', 'error')
            return redirect(url_for('faculty_dashboard'))
    else:
        flash('Please log in as faculty to access the evaluation page', 'error')
        return redirect(url_for('login'))

@app.route('/user_details', methods=['GET'])
def user_details():
    if 'username' in session:  # Check if user is logged in
        # Assuming you have a 'users' table with columns 'username', 'name', 'email', etc.
        username = session['username']  # Get the username from the session
        conn = sqlite3.connect('assignments.db')
        c = conn.cursor()
        c.execute('SELECT name, email, role, id_rollno, gender, contact_number FROM users WHERE username=?', (username,))
        user_details = c.fetchone()  # Fetch user details from the database
        conn.close()

        if user_details:
            # Prepare the user details in a dictionary format
            user_data = {
                'name': user_details[0],
                'email': user_details[1],
                'role': user_details[2],
                'id_rollno': user_details[3],
                'gender': user_details[4],
                'contact_number': user_details[5],
                'username': username
            }
            return jsonify(user_data)  # Return user details in JSON format
        else:
            return jsonify({'error': 'User details not found'}), 404  # Return 404 if user details are not found
    else:
        return jsonify({'error': 'User not logged in'}), 401  # Return 401 if user is not logged in
@app.route('/approve_assignment/<int:assignment_id>')
def approve_assignment(assignment_id):
    if 'username' in session and get_user_type(session['username']) == 'faculty':
        conn = sqlite3.connect('assignments.db')
        c = conn.cursor()
        c.execute('UPDATE assignments SET status="Approved" WHERE id=?', (assignment_id,))
        conn.commit()
        conn.close()

        flash('Assignment approved successfully!', 'success')
        return redirect(url_for('faculty_dashboard'))
    else:
        flash('Please log in as faculty to perform this action', 'error')
        return redirect(url_for('login'))

@app.route('/reject_assignment/<int:assignment_id>')
def reject_assignment(assignment_id):
    if 'username' in session and get_user_type(session['username']) == 'faculty':
        conn = sqlite3.connect('assignments.db')
        c = conn.cursor()
        c.execute('UPDATE assignments SET status="Rejected" WHERE id=?', (assignment_id,))
        conn.commit()
        conn.close()

        flash('Assignment rejected successfully!', 'success')
        return redirect(url_for('faculty_dashboard'))
    else:
        flash('Please log in as faculty to perform this action', 'error')
        return redirect(url_for('login'))

@app.route('/download_assignment/<filename>')
def download_assignment(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Check if the file exists before attempting to send it
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, attachment_filename=filename)
    else:
        # If the file doesn't exist, return a 404 Not Found error
        return abort(404)

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

@app.route('/get_student_names', methods=['GET'])
def get_student_names():
    query = request.args.get('query', '').lower()

    print(f"Received request for student names with query: {query}")

    student_names = get_student_names_from_database(query)

    return jsonify(student_names)

@app.route('/get_assignments', methods=['GET'])
def get_assignments():
    username = request.args.get('username', '')

    print(f"Received request for assignments with username: {username}")

    assignments = get_assignments_for_user(username)

    # Reverse the order of assignments
    assignments = assignments[::-1]
    return jsonify(assignments)

@app.route('/evaluate_assignment/<username>', methods=['GET', 'POST'])
def evaluate_assignment_for_user(username):
    if 'username' in session and get_user_type(session['username']) == 'faculty':
        # Fetch the assignment details based on the username and status
        conn = sqlite3.connect('assignments.db')
        c = conn.cursor()

        # Fetch the assignment based on the assignment name
        assignment_name = request.args.get('assignment_name', '')
        c.execute('SELECT * FROM assignments WHERE submitted_by=? AND name=? AND status IS NULL', (username, assignment_name))
        assignment = c.fetchone()

        if assignment:
            if request.method == 'POST':
                # Handle the evaluation form submission logic here
                status = request.form['status']
                marks = request.form['marks']
                comments = request.form['comments']

                # Validate the input data (add more validation as needed)
                if not status or not marks:
                    flash('Please provide both status and marks for evaluation', 'error')
                    return redirect(request.url)

                # Check if the assignment has already been evaluated
                if assignment[4] is not None:
                    flash('This assignment has already been evaluated', 'error')
                    return redirect(request.url)

                # Update the assignment details in the database
                c.execute('UPDATE assignments SET status=?, marks=?, comments=? WHERE id=?', (status, marks, comments, assignment[0]))
                conn.commit()

                flash('Evaluation saved successfully!', 'success')
                return redirect(url_for('faculty_dashboard'))

            return render_template('evaluate_assignment.html', username=session['username'], assignment=assignment)
        else:
            flash('Assignment not found', 'error')
            return redirect(url_for('faculty_dashboard'))
    else:
        flash('Please log in as faculty to access the evaluation page', 'error')
        return redirect(url_for('login'))

@app.route('/notification', methods=['GET', 'POST'])
def notification():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        date = datetime.now().strftime('%d-%m-%Y %H:%M')

        conn = sqlite3.connect('notification.db')
        c = conn.cursor()

        # Insert the notification into the database
        c.execute('INSERT INTO notification (title, content, date) VALUES (?, ?, ?)', (title, content, date))
        conn.commit()
        conn.close()
        flash('Notification created successfully!', 'success')

        return redirect(url_for('faculty_dashboard'))  # Redirect to the same route to refresh and show the updated list

    return render_template('notification.html')

@app.route('/delete_notification/<int:notification_id>', methods=['GET'])
def delete_notification(notification_id):
    # Handle the notification deletion logic here
    conn = sqlite3.connect('notification.db')
    c = conn.cursor()

    # Delete the notification from the database based on the notification_id
    c.execute('DELETE FROM notification WHERE id=?', (notification_id,))
    conn.commit()
    conn.close()

    flash('Notification deleted successfully!', 'success')

    return redirect(url_for('faculty_dashboard'))

@app.route('/edit_notification/<int:notification_id>', methods=['GET', 'POST'])
def edit_notification(notification_id):
    if request.method == 'GET':
        # Handle the notification retrieval logic here
        conn = sqlite3.connect('notification.db')
        c = conn.cursor()
        # Fetch the notification from the database based on the notification_id
        c.execute('SELECT * FROM notification WHERE id=?', (notification_id,))
        notification = c.fetchone()

        # Check if notification exists
        if notification:
            # Assuming 'title' is one of the columns in the notification table
            notification_title = notification[1]
            notification_content = notification[2]
            conn.close()

            # Render the template and pass the notification_title and notification_content
            # Also, pass the notification_id to the template
            return render_template('edit_notification.html', notification_title=notification_title, notification_content=notification_content, notification_id=notification_id)
        else:
            # Handle the case when the notification is not found
            return render_template('notification_not_found.html')

    elif request.method == 'POST':
        # Handle the notification update logic here
        conn = sqlite3.connect('notification.db')
        c = conn.cursor()

        try:
            # Update notification details based on the form submission
            title = request.form['title']
            content = request.form['content']
            date = datetime.now().strftime('%d-%m-%Y %H:%M')

            # Update the notification in the database
            c.execute('UPDATE notification SET title=?, content=?, date=? WHERE id=?', (title, content, date, notification_id))
            conn.commit()

            flash('Notification updated successfully!', 'success')

            # Redirect to the faculty dashboard or notifications tab
            return redirect(url_for('faculty_dashboard'))

        except Exception as e:
            print("Error during update:", str(e))
            flash('Error updating notification!', 'error')

        finally:
            conn.close()
            return redirect(url_for('faculty_dashboard'))

if __name__ == "__main__":
     app.run(debug=True)