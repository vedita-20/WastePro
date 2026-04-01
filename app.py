from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime
import os
from werkzeug.utils import secure_filename

# Configuration for uploads


app = Flask(__name__)
app.secret_key = "waste_mgmt_2026_final_sync"
# Define the path
UPLOAD_FOLDER = os.path.join('static', 'resolutions')

# SAFETY CHECK: If the folder doesn't exist, create it now
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created missing directory: {UPLOAD_FOLDER}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    return mysql.connector.connect(
        host="localhost", user="root", password="IronmanHulk@7621", database="waste3", raise_on_warnings=True, autocommit=True
    )

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND role=%s", (username, role))
        user = cursor.fetchone()
        
        # We always close the cursor and db as soon as we are done with the query
        cursor.close()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session.clear() 
            session.update({
                'loggedin': True, 
                'id': user['user_id'], 
                'username': user['username'], 
                'role': user['role']
            })
            
            if user['role'] == 'Admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('citizen_dashboard'))
        
        # If credentials are wrong, flash a message
        flash("Invalid Credentials. Please try again.")

    # This handles both the initial GET request AND failed POST requests!
    return render_template('login.html')
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'Citizen')
        # We hash the pin so even DB admins can't see it
        pin = request.form.get('recovery_pin', '1234') 
        
        hashed_pw = generate_password_hash(password)
        hashed_pin = generate_password_hash(pin)

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, email, password, role, recovery_pin) 
                VALUES (%s, %s, %s, %s, %s)
            """, (username, email, hashed_pw, role, hashed_pin))
            db.commit()
            
            return redirect(url_for('login'))
        except Exception as e:
            db.rollback()
            flash(f"Error: {e}. Username or Email might already exist.", "danger")
        finally:
            cursor.close()
            db.close()
            
    return render_template('signup.html')
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # Change 'identity' to 'username' right here:
        identity = request.form.get('username') 
        role = request.form.get('role')
        input_pin = request.form.get('recovery_pin')
        new_password = request.form.get('new_password')
        
        # ... keep the rest of your code the same!

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # 1. Find the user first
        cursor.execute("SELECT * FROM users WHERE (username=%s OR email=%s) AND role=%s", 
                       (identity, identity, role))
        user = cursor.fetchone()
        
        cursor.close()
        db.close()

        # --- DEBUGGING PRINTS (Check your terminal when you submit the form!) ---
        print(f"User found: {user is not None}")
        if user:
            pin_matches = check_password_hash(user['recovery_pin'], input_pin)
            print(f"PIN matches: {pin_matches}")
        # ----------------------------------------------------------------------

        # 2. Check if user exists and verify the hashed PIN
        if user and check_password_hash(user['recovery_pin'], input_pin):
            # 3. Hash the new password and update
            new_hashed_pw = generate_password_hash(new_password)
            
            # Re-open connection to update
            db = get_db()
            cursor = db.cursor()
            cursor.execute("UPDATE users SET password=%s WHERE user_id=%s", 
                           (new_hashed_pw, user['user_id']))
            db.commit()
            cursor.close()
            db.close()
            
            # Success! Flashing a message helps the user know it worked
            flash("Password updated successfully! Please log in.", "success")
            return redirect(url_for('login'))
        else:
            # This is where it goes if the terminal prints say False!
            flash("Invalid Identity, Role, or Recovery PIN.", "danger")
            
    return render_template('forgot_password.html')
@app.route('/admin_dashboard')
def admin_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # KPI 1: Total Waste
    cursor.execute("SELECT IFNULL(SUM(quantity_collected_kg), 0) as q FROM Collection_Record")
    total_waste = cursor.fetchone()['q']

    # KPI 2: Active Vehicles ONLY (Fixed Alias to 'count')
    cursor.execute("SELECT COUNT(*) as count FROM Collection_Vehicle WHERE status = 'Active'")
    v_count = cursor.fetchone()['count']

    # Line Chart Data
    cursor.execute("SELECT collection_date as d, SUM(quantity_collected_kg) as q FROM Collection_Record GROUP BY d ORDER BY d ASC LIMIT 7")
    trend_res = cursor.fetchall()
    days = [row['d'].strftime('%b %d') for row in trend_res] if trend_res else ["No Data"]
    waste_trend = [float(row['q']) for row in trend_res] if trend_res else [0]

    # Doughnut Chart Data
    cursor.execute("SELECT status, COUNT(*) as count FROM Complaint GROUP BY status")
    eff_res = cursor.fetchall()
    eff_labels = [row['status'] for row in eff_res] if eff_res else ["Pending", "Resolved"]
    eff_values = [row['count'] for row in eff_res] if eff_res else [0, 0]

    return render_template('admin_dashboard.html', total_waste=total_waste, v_count=v_count, days=days, waste_trend=waste_trend, eff_labels=eff_labels, eff_values=eff_values)
@app.route('/citizen_dashboard')
def citizen_dashboard():
    # 1. Security Check: Ensure only logged-in Citizens can enter
    if 'loggedin' not in session or session.get('role') != 'Citizen':
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    user_id = session.get('id')

    # 2. Fetch Total Waste Recycled (for the KPI card)
    # IFNULL ensures we get 0 instead of None if the user hasn't recycled yet
    cursor.execute("""
        SELECT IFNULL(SUM(quantity_received_kg), 0) as total 
        FROM Recycling_Record 
        WHERE user_id = %s
    """, (user_id,))
    total_waste = cursor.fetchone()['total']

    # 3. Fetch Count of Pending Complaints (for the badge)
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM Complaint 
        WHERE user_id = %s AND status = 'Pending'
    """, (user_id,))
    status_count = cursor.fetchone()['count']

    # 4. Fetch Chart Data (Last 7 entries for the line graph)
    cursor.execute("""
        SELECT processing_date, SUM(quantity_received_kg) as daily_total
        FROM Recycling_Record
        WHERE user_id = %s
        GROUP BY processing_date
        ORDER BY processing_date ASC
        LIMIT 7
    """, (user_id,))
    chart_data = cursor.fetchall()

    # Format data for Chart.js (JSON ready)
    days = [row['processing_date'].strftime('%b %d') for row in chart_data] if chart_data else []
    values = [float(row['daily_total']) for row in chart_data] if chart_data else []

    cursor.close()
    db.close()

    # 5. Render the page with all necessary variables
    return render_template('citizen_dashboard.html', 
                           username=session.get('username'),
                           total_waste=total_waste,
                           status_count=status_count,
                           days=days,
                           values=values,
                           now=datetime.now().strftime("%A, %B %d"))

from flask import render_template, request, redirect, url_for, session, flash

@app.route('/area', methods=['GET', 'POST'])
def area():
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        # Get data from form
        name = request.form.get('area_name')
        zone = request.form.get('zone')
        pop = request.form.get('population')
        
        # Debug: Check terminal to see if this prints
        print(f"DEBUG: Adding Area - {name}, {zone}, {pop}")

        if name and zone:
            try:
                cursor.execute("INSERT INTO Area (area_name, zone, population) VALUES (%s, %s, %s)", 
                               (name, zone, pop))
                db.commit()
                flash("Success: Area Registered!")
            except Exception as e:
                print(f"DB Error: {e}")
                db.rollback()
        
        return redirect(url_for('area'))

    # GET logic for the table and chart
    cursor.execute("SELECT * FROM Area ORDER BY area_id ASC")
    areas = cursor.fetchall()

    cursor.execute("SELECT zone, COUNT(*) as count FROM Area GROUP BY zone")
    chart_stats = cursor.fetchall()
    labels = [row['zone'] for row in chart_stats]
    values = [row['count'] for row in chart_stats]

    return render_template('area.html', areas=areas, labels=labels, values=values)

@app.route('/edit_area/<int:id>', methods=['GET', 'POST'])
def edit_area(id):
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form.get('area_name')
        zone = request.form.get('zone')
        pop = request.form.get('population')
        
        cursor.execute("UPDATE Area SET area_name=%s, zone=%s, population=%s WHERE area_id=%s", 
                       (name, zone, pop, id))
        db.commit()
        return redirect(url_for('area'))

    cursor.execute("SELECT * FROM Area WHERE area_id = %s", (id,))
    area_data = cursor.fetchone()
    return render_template('edit_area.html', area=area_data)

@app.route('/delete_area/<int:id>')
def delete_area(id):
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM Area WHERE area_id = %s", (id,))
    db.commit()
    return redirect(url_for('area'))

@app.route('/vehicle', methods=['GET', 'POST'])
def vehicle():
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        v_num = request.form.get('vehicle_number')
        v_cap = request.form.get('capacity_kg')
        v_driver = request.form.get('driver_name')
        v_status = request.form.get('status')

        try:
            # SQL Optimization: Use an UPSERT or specific error handling
            cursor.execute("""
                INSERT INTO Collection_Vehicle (vehicle_number, capacity_kg, driver_name, status)
                VALUES (%s, %s, %s, %s)
            """, (v_num, v_cap, v_driver, v_status))
            db.commit()
            flash("Vehicle added to fleet successfully!")
        except Exception as e:
            db.rollback()
            # This catches duplicate plate numbers
            flash("System Error: Duplicate vehicle number or database issue.")
        
        return redirect(url_for('vehicle'))

    # Fetching for Table
    cursor.execute("SELECT * FROM Collection_Vehicle ORDER BY vehicle_id ASC")
    vehicles = cursor.fetchall()

    # Prep Chart Data (Only show Active/Maintenance for capacity analysis)
    # This prevents 'Retired' vehicles from cluttering your charts
    v_labels = [v['vehicle_number'] for v in vehicles if v['status'] != 'Retired']
    v_values = [int(v['capacity_kg']) for v in vehicles if v['status'] != 'Retired']

    return render_template('vehicle.html', vehicles=vehicles, v_labels=v_labels, v_values=v_values)

@app.route('/edit_vehicle/<int:id>', methods=['GET', 'POST'])
def edit_vehicle(id):
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        v_num = request.form.get('vehicle_number')
        v_cap = request.form.get('capacity_kg')
        v_driver = request.form.get('driver_name')
        v_status = request.form.get('status')

        cursor.execute("""
            UPDATE Collection_Vehicle 
            SET vehicle_number=%s, capacity_kg=%s, driver_name=%s, status=%s
            WHERE vehicle_id=%s
        """, (v_num, v_cap, v_driver, v_status, id))
        db.commit()
        return redirect(url_for('vehicle'))

    # FETCH CURRENT DATA
    cursor.execute("SELECT * FROM Collection_Vehicle WHERE vehicle_id = %s", (id,))
    
    # THE FIX: Name the variable 'v' so the HTML can see it
    vehicle_to_edit = cursor.fetchone()
    
    if not vehicle_to_edit:
        return "Vehicle not found", 404

    return render_template('edit_vehicle.html', v=vehicle_to_edit) # <-- Changed from 'vehicle' to 'v'

@app.route('/delete_vehicle/<int:id>')
def delete_vehicle(id):
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM Collection_Vehicle WHERE vehicle_id = %s", (id,))
        db.commit()
    except Exception as e:
        db.rollback()
    
    return redirect(url_for('vehicle'))

@app.route('/waste_type', methods=['GET', 'POST'])
def waste_type():
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        type_name = request.form.get('type_name')
        recyclable = 1 if request.form.get('recyclable') else 0
        cursor.execute("INSERT INTO Waste_Type (type_name, recyclable) VALUES (%s, %s)", 
                       (type_name, recyclable))
        db.commit()
        return redirect(url_for('waste_type'))

    # Ensure you are selecting the primary key
    cursor.execute("SELECT * FROM Waste_Type")
    waste_types = cursor.fetchall()
    
    total = len(waste_types)
    rec_count = sum(1 for w in waste_types if w['recyclable'])
    non_rec_count = total - rec_count
    rec_percent = round((rec_count / total * 100), 1) if total > 0 else 0

    return render_template('waste_type.html', 
                           waste_types=waste_types, 
                           total=total, 
                           values=[rec_count, non_rec_count], 
                           labels=['Recyclable', 'Non-Recyclable'],
                           rec_percent=rec_percent)

@app.route('/edit_waste/<int:id>', methods=['GET', 'POST'])
def edit_waste(id):
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        type_name = request.form.get('type_name')
        recyclable = 1 if request.form.get('recyclable') else 0
        
        # Check: Is your column named waste_type_id or waste_id?
        cursor.execute("UPDATE Waste_Type SET type_name=%s, recyclable=%s WHERE waste_id=%s", 
                       (type_name, recyclable, id))
        db.commit()
        return redirect(url_for('waste_type'))

    cursor.execute("SELECT * FROM Waste_Type WHERE waste_id = %s", (id,))
    waste = cursor.fetchone()
    
    # PEER TIP: If 'waste' is None, the ID doesn't exist in the DB
    if not waste:
        return "Waste Type not found", 404
        
    return render_template('edit_waste.html', w=waste)

@app.route('/delete_waste/<int:id>')
def delete_waste(id):
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM Waste_Type WHERE waste_id = %s", (id,))
    db.commit()
    return redirect(url_for('waste_type'))

@app.route('/collectionrecord', methods=['GET', 'POST'])
def collectionrecord():
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        a_id = request.form.get('area_id')
        v_id = request.form.get('vehicle_id')
        w_id = request.form.get('waste_id')
        c_date = request.form.get('collection_date')
        qty = request.form.get('quantity_collected_kg')

        cursor.execute("""
            INSERT INTO Collection_Record (area_id, vehicle_id, waste_id, collection_date, quantity_collected_kg)
            VALUES (%s, %s, %s, %s, %s)
        """, (a_id, v_id, w_id, c_date, qty))
        db.commit()
        return redirect(url_for('collectionrecord'))

    # Dropdowns for Form
    cursor.execute("SELECT area_id, area_name FROM Area")
    areas = cursor.fetchall()
    cursor.execute("SELECT vehicle_id, vehicle_number FROM Collection_Vehicle")
    vehicles = cursor.fetchall()
    cursor.execute("SELECT waste_id, type_name FROM Waste_Type")
    waste_types = cursor.fetchall()

    # FIFO Table Data
    cursor.execute("""
        SELECT cr.*, a.area_name, v.vehicle_number, w.type_name 
        FROM Collection_Record cr
        JOIN Area a ON cr.area_id = a.area_id
        JOIN Collection_Vehicle v ON cr.vehicle_id = v.vehicle_id
        JOIN Waste_Type w ON cr.waste_id = w.waste_id
        ORDER BY cr.collection_date ASC
    """)
    history = cursor.fetchall()

    return render_template('collectionrecord.html', areas=areas, vehicles=vehicles, waste_types=waste_types, records=history)

@app.route('/editcr/<int:id>', methods=['GET', 'POST'])
def editcr(id):
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        a_id = request.form.get('area_id')
        v_id = request.form.get('vehicle_id')
        w_id = request.form.get('waste_id')
        c_date = request.form.get('collection_date')
        qty = request.form.get('quantity_collected_kg')

        cursor.execute("""
            UPDATE Collection_Record 
            SET area_id=%s, vehicle_id=%s, waste_id=%s, collection_date=%s, quantity_collected_kg=%s
            WHERE record_id=%s
        """, (a_id, v_id, w_id, c_date, qty, id))
        db.commit()
        return redirect(url_for('collectionrecord'))

    cursor.execute("SELECT * FROM Collection_Record WHERE record_id = %s", (id,))
    record = cursor.fetchone()
    
    # Re-fetch dropdowns for the edit page
    cursor.execute("SELECT area_id, area_name FROM Area")
    areas = cursor.fetchall()
    cursor.execute("SELECT vehicle_id, vehicle_number FROM Collection_Vehicle")
    vehicles = cursor.fetchall()
    cursor.execute("SELECT waste_id, type_name FROM Waste_Type")
    waste_types = cursor.fetchall()

    return render_template('editcr.html', r=record, areas=areas, vehicles=vehicles, waste_types=waste_types)

@app.route('/delete_collection/<int:id>')
def delete_collection(id):
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute("DELETE FROM Collection_Record WHERE record_id = %s", (id,))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        
    # FIX: Matches the function name 'collection_record'
    return redirect(url_for('collectionrecord'))

@app.route('/complaintres', methods=['GET', 'POST'])
def complaintres():
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        complaint_id = request.form.get('complaint_id')
        resolution_notes = request.form.get('resolution_notes')
        file = request.files.get('proof_image')

        if file and complaint_id:
            filename = secure_filename(f"res_{complaint_id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # FIXED: Using 'resolved_by_admin_id' to match your schema
            cursor.execute("""
                INSERT INTO Complaint_Resolution 
                (complaint_id, resolution_notes, resolution_image, resolved_by_admin_id, resolution_date) 
                VALUES (%s, %s, %s, %s, CURDATE())
            """, (complaint_id, resolution_notes, filename, session.get('id')))
            
            cursor.execute("UPDATE Complaint SET status = 'Resolved' WHERE complaint_id = %s", (complaint_id,))
            db.commit()
            return redirect(url_for('complaintres'))

    # FIXED: Using 'r.resolved_by_admin_id' in the ON clause
    cursor.execute("""
        SELECT 
            r.resolution_id, 
            r.resolution_date, 
            r.resolution_notes, 
            r.resolution_image,
            c.issue_description, 
            c.complaint_date, 
            a.area_name, 
            u.username AS resolved_by
        FROM Complaint_Resolution r
        JOIN Complaint c ON r.complaint_id = c.complaint_id
        JOIN Area a ON c.area_id = a.area_id
        JOIN Users u ON r.resolved_by_admin_id = u.user_id
        ORDER BY r.resolution_date DESC
    """)
    resolutions = cursor.fetchall()

    cursor.execute("SELECT complaint_id, issue_description FROM Complaint WHERE status = 'Pending'")
    pending = cursor.fetchall()

    return render_template('complaintres.html', resolutions=resolutions, pending=pending)
# --- CITIZEN ROUTES (Matches your Navbar) ---

@app.route('/complaint', methods=['GET', 'POST'])
def complaint():
    if 'loggedin' not in session or session.get('role') != 'Citizen':
        return redirect(url_for('login'))

    user_id = session.get('id')
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # 1. HANDLE FORM SUBMISSION (POST)
    if request.method == 'POST':
        area_id = request.form.get('area_id')
        complaint_date = request.form.get('complaint_date')
        description = request.form.get('issue_description')

        try:
            cursor.execute("""
                INSERT INTO Complaint (area_id, user_id, complaint_date, issue_description, status) 
                VALUES (%s, %s, %s, %s, 'Pending')
            """, (area_id, user_id, complaint_date, description))
            db.commit()
        except Exception as e:
            db.rollback()
            flash("Error submitting complaint: " + str(e))
        return redirect(url_for('complaint'))

    # 2. FETCH AREAS
    cursor.execute("SELECT * FROM Area")
    areas_list = cursor.fetchall()

    # 3. THE FIX: JOIN with Complaint_Resolution to get the photo
    cursor.execute("""
        SELECT 
            c.*, 
            a.area_name, 
            r.resolution_notes, 
            r.resolution_image 
        FROM Complaint c 
        JOIN Area a ON c.area_id = a.area_id 
        LEFT JOIN Complaint_Resolution r ON c.complaint_id = r.complaint_id 
        WHERE c.user_id = %s 
        ORDER BY c.complaint_date ASC
    """, (user_id,))
    my_complaints = cursor.fetchall()

    # 4. STATS
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM Complaint 
        WHERE user_id = %s 
        GROUP BY status
    """, (user_id,))
    user_stats = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('complaint.html', 
                           areas=areas_list, 
                           complaints=my_complaints, 
                           stats=user_stats)
@app.route('/delete_complaint/<int:id>')
def delete_complaint(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    try:
        # We ensure the user can only delete their own if they aren't an Admin
        if session['role'] == 'Admin':
            cursor.execute("DELETE FROM Complaint WHERE complaint_id = %s", (id,))
        else:
            cursor.execute("DELETE FROM Complaint WHERE complaint_id = %s AND user_id = %s", (id, session['id']))
            
        db.commit()
        flash("Complaint removed successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error: {e}", "danger")
    finally:
        cursor.close()
        db.close()
        
    return redirect(url_for('complaint'))
@app.route('/edit_complaint/<int:id>', methods=['GET', 'POST'])
def edit_complaint(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        new_desc = request.form.get('issue_description')
        if session['role'] == 'Admin':
            new_status = request.form.get('status')
            cursor.execute("UPDATE Complaint SET issue_description=%s, status=%s WHERE complaint_id=%s", (new_desc, new_status, id))
        else:
            cursor.execute("UPDATE Complaint SET issue_description=%s WHERE complaint_id=%s AND user_id=%s AND status='Pending'", (new_desc, id, session['id']))
        
        db.commit()
        return redirect(url_for('complaint' if session['role'] == 'Citizen' else 'complaintres'))

    cursor.execute("SELECT * FROM Complaint WHERE complaint_id = %s", (id,))
    complaint_data = cursor.fetchone()
    cursor.close()
    db.close()
    
    return render_template('edit_complaint.html', complaint=complaint_data)

@app.route('/recycle_centre') # Removed 'POST' methods
def recycle_centre():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Now we only handle the search and the display
    search_query = request.args.get('search', '')
    if search_query:
        cursor.execute("""
            SELECT * FROM Recycling_Center 
            WHERE center_name LIKE %s OR location LIKE %s
        """, (f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT * FROM Recycling_Center ORDER BY center_name ASC")
    
    centers = cursor.fetchall()

    cursor.close()
    db.close()
    return render_template('recycle_centre.html', centers=centers)

@app.route('/recycle_record', methods=['GET', 'POST'])
def recycle_record():
    if 'loggedin' not in session or session.get('role') != 'Citizen':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    user_id = session.get('id')

    # --- PART 1: SAVE NEW ENTRY ---
    if request.method == 'POST':
        c_id = request.form.get('center_id')
        w_id = request.form.get('waste_id')
        qty = request.form.get('quantity_received_kg')
        p_date = request.form.get('processing_date')

        cursor.execute("""
            INSERT INTO Recycling_Record (user_id, center_id, waste_id, quantity_received_kg, processing_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, c_id, w_id, qty, p_date))
        db.commit()
        flash("Impact Logged! 🌿")
        return redirect(url_for('recycle_record'))

    # --- PART 2: FETCH DATA FOR UI ---
    cursor.execute("SELECT * FROM Recycling_Center")
    centers = cursor.fetchall()

    cursor.execute("SELECT * FROM Waste_Type WHERE recyclable = 1")
    waste_types = cursor.fetchall()

    cursor.execute("""
        SELECT r.*, c.center_name, w.type_name 
        FROM Recycling_Record r
        JOIN Recycling_Center c ON r.center_id = c.center_id
        JOIN Waste_Type w ON r.waste_id = w.waste_id
        WHERE r.user_id = %s
        ORDER BY r.processing_date asc
    """, (user_id,))
    history = cursor.fetchall()

    return render_template('recycle_record.html', centers=centers, waste_types=waste_types, records=history)
@app.route('/editrr/<int:id>', methods=['GET', 'POST'])
def editrr(id):
    if 'loggedin' not in session or session.get('role') != 'Citizen':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    user_id = session.get('id')

    # --- 1. HANDLE FORM SUBMISSION (POST) ---
    if request.method == 'POST':
        c_id = request.form.get('center_id')
        w_id = request.form.get('waste_id')
        qty = request.form.get('quantity_received_kg')
        p_date = request.form.get('processing_date')

        cursor.execute("""
            UPDATE Recycling_Record 
            SET center_id=%s, waste_id=%s, quantity_received_kg=%s, processing_date=%s
            WHERE recycle_id=%s AND user_id=%s
        """, (c_id, w_id, qty, p_date, id, user_id))
        
        db.commit()
        flash("Record updated successfully!")
        return redirect(url_for('recycle_record'))

    # --- 2. FETCH CURRENT DATA (GET) ---
    # We fetch the record AND the lists for the dropdowns
    cursor.execute("SELECT * FROM Recycling_Record WHERE recycle_id = %s AND user_id = %s", (id, user_id))
    record = cursor.fetchone()

    if not record:
       
        return redirect(url_for('recycle_record'))

    cursor.execute("SELECT * FROM Recycling_Center")
    centers = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Waste_Type WHERE recyclable = 1")
    waste_types = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('editrr.html', r=record, centers=centers, waste_types=waste_types)
@app.route('/deleterr/<int:id>')
def deleterr(id):
    if 'loggedin' not in session or session.get('role') != 'Citizen':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    user_id = session.get('id')

    # Security check: only delete if the record belongs to the logged-in user
    try:
        cursor.execute("DELETE FROM Recycling_Record WHERE recycle_id = %s AND user_id = %s", (id, user_id))
        db.commit()
            
    except Exception as e:
        db.rollback()
        
    
    finally:
        cursor.close()
        db.close()

    return redirect(url_for('recycle_record'))
@app.route('/awareness')
def awareness():
    # Ensure user is logged in
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    # We DON'T add a role check here so both Admins and Citizens can see it.
    # This prevents the "kick-back" to the dashboard.
    return render_template('awareness.html', username=session.get('username'))

# --- SHARED ---
@app.route('/profile')
def profile():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Use the ID stored in the session during login
    user_id = session.get('id') 

    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    userdata = cursor.fetchone()
    
    cursor.close()
    db.close()

    if userdata:
        # 🟢 CRITICAL: The variable name here MUST match the template
        return render_template('profile.html', user=userdata)
    else:
        flash("User not found.")
        return redirect(url_for('login'))
@app.route('/edit_user/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if 'loggedin' not in session or session.get('id') != id:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('password')

        # Security: Only update password if user actually typed a new one
        if new_password and new_password.strip() != "":
            cursor.execute("UPDATE users SET username=%s, email=%s, password=%s WHERE user_id=%s", 
                           (username, email, new_password, id))
        else:
            cursor.execute("UPDATE users SET username=%s, email=%s WHERE user_id=%s", 
                           (username, email, id))
            
        db.commit()
        session['username'] = username
        flash('Security settings updated!')
        return redirect(url_for('profile'))

    cursor.execute('SELECT user_id, username, email FROM users WHERE user_id = %s', (id,))
    userdata = cursor.fetchone()
    return render_template('edit_user.html', user=userdata)
@app.route('/admin_recycle')
def admin_recycle():
    # Security Check: Ensure only Admins can see this
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # --- ANALYSIS 1: Leaderboard (Top Recycling Citizens) ---
    cursor.execute("""
        SELECT u.username, SUM(r.quantity_received_kg) as total_kg
        FROM Recycling_Record r
        JOIN users u ON r.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY total_kg DESC
        LIMIT 5
    """)
    leaderboard_data = cursor.fetchall()
    
    # Prep data for Chart.js
    l_labels = [row['username'] for row in leaderboard_data]
    l_values = [float(row['total_kg']) for row in leaderboard_data]

    # --- ANALYSIS 2: Waste Type Distribution ---
    cursor.execute("""
        SELECT w.type_name, SUM(r.quantity_received_kg) as total
        FROM Recycling_Record r
        JOIN Waste_Type w ON r.waste_id = w.waste_id
        GROUP BY w.type_name
    """)
    waste_stats = cursor.fetchall()
    w_labels = [row['type_name'] for row in waste_stats]
    w_values = [float(row['total']) for row in waste_stats]

    # --- ANALYSIS 3: Full Audit Table (FIFO) ---
    cursor.execute("""
        SELECT r.*, u.username, c.center_name, w.type_name 
        FROM Recycling_Record r
        JOIN users u ON r.user_id = u.user_id
        JOIN Recycling_Center c ON r.center_id = c.center_id
        JOIN Waste_Type w ON r.waste_id = w.waste_id
        ORDER BY r.processing_date ASC
    """)
    all_history = cursor.fetchall()

    return render_template('admin_recycle.html', 
                           l_labels=l_labels, l_values=l_values,
                           w_labels=w_labels, w_values=w_values,
                           records=all_history)
@app.route('/logout')
def logout():
    # Remove session data, this will log the user out
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('role', None)
    
    # Redirect to login page
  
    return redirect(url_for('login'))
# CHECK IF YOU HAVE THIS IN YOUR APP.PY:
@app.route('/admin_recycle_centre', methods=['GET', 'POST'])
def admin_recycle_centre():
    if 'loggedin' not in session or session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # CREATE: Handling the Registration Form
    if request.method == 'POST':
        name = request.form.get('center_name')
        loc = request.form.get('location')
        contact = request.form.get('contact_number')
        
        cursor.execute("""
            INSERT INTO Recycling_Center (center_name, location, contact_number) 
            VALUES (%s, %s, %s)
        """, (name, loc, contact))
        db.commit()
        return redirect(url_for('admin_recycle_centre'))
    # READ: Fetching all centers for the table
    cursor.execute("SELECT * FROM Recycling_Center ORDER BY center_id ASC")
    centers = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('admin_recycle_centre.html', centers=centers)
@app.route('/editarc/<int:id>', methods=['GET', 'POST'])
def editarc(id):
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # UPDATE: Saving the new details
    if request.method == 'POST':
        name = request.form.get('center_name')
        loc = request.form.get('location')
        contact = request.form.get('contact_number')

        cursor.execute("""
            UPDATE Recycling_Center 
            SET center_name=%s, location=%s, contact_number=%s 
            WHERE center_id=%s
        """, (name, loc, contact, id))
        db.commit()
        flash("Centre updated!")
        return redirect(url_for('admin_recycle_centre'))

    # FETCH: Getting current data to show in the Edit HTML
    cursor.execute("SELECT * FROM Recycling_Center WHERE center_id = %s", (id,))
    center = cursor.fetchone()
    
    cursor.close()
    db.close()
    return render_template('editarc.html', center=center)
@app.route('/delete_recycle_centre/<int:id>')
def delete_recycle_centre(id):
    # 1. Security Check: Only Admins can delete
    if session.get('role') != 'Admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 2. Execute Deletion
        cursor.execute("DELETE FROM Recycling_Center WHERE center_id = %s", (id,))
        db.commit()
        flash("Recycling Centre deleted successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error deleting record: {e}", "danger")
    finally:
        cursor.close()
        db.close()
        
    return redirect(url_for('recycle_centre'))
        
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute("DELETE FROM Recycling_Center WHERE center_id = %s", (id,))
        db.commit()
        flash("Centre removed.")
    except Exception as e:
        db.rollback()
        flash("Error: Could not delete centre.")
        
    cursor.close()
    db.close()
    return redirect(url_for('admin_recycle_centre'))
@app.before_request
def restrict_access():
    allowed_routes = ['login', 'signup', 'static', 'awareness','forgot_password'] # <--- ADD 'awareness' HERE
    if 'loggedin' not in session and request.endpoint not in allowed_routes:
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(port=8000, debug=True)