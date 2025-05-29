import os
import secrets
from PIL import Image, ImageOps
from flask import render_template, url_for, flash, redirect, request, abort, session, jsonify, send_file

from main import app, db, bcrypt, mail, google, github
from main.models import User, SavedJob, Resume
from main.forms import RegistrationForm, LoginForm, UpdateAccountForm, RequestRestForm, ResetPasswordForm, ProfileForm
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
import requests
from functools import wraps
import ast
from datetime import datetime
import docx

import tempfile
import pdfkit
from jinja2 import Template
import json
import pdfplumber
from main.utils.resume_parser import extract_text, get_ai_suggestions
from main.utils.resume_formatter import format_resume_data
from main.utils.template_loader import load_template
from werkzeug.utils import secure_filename


from dotenv import load_dotenv
# Load environment variables
load_dotenv()

ADZUNA_ID=os.getenv('ADZUNA_APP_ID')
ADZUNA_KEY=os.getenv('ADZUNA_APP_KEY')
ADZUNA_COUNTRY=os.getenv("ADZUNA_COUNTRY")



# Resume Parser API configuration
RESUME_PARSER_API_KEY = os.getenv('RESUME_PARSER_API_KEY')
RESUME_PARSER_URL = "https://resume-parser-api.p.rapidapi.com/api/v1/parser/resume"



@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}


# Custom decorator
def custom_login_required_for_save(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.method == 'POST':
                pending_data = {
                    'job_id': request.form.get('job_id'),
                    'api_used': request.form.get('api_used')
                }
                api_used = request.form.get('api_used')
                job_data_from_form = request.form.get('job_data')

                if api_used == 'adzuna':
                    # For Adzuna, only store minimal data if job_data_from_form is present
                    if job_data_from_form:
                        try:
                            # Try to parse it to extract key fields safely
                            temp_job_data = json.loads(job_data_from_form)
                        except json.JSONDecodeError:
                             try:
                                # Fallback to ast.literal_eval if direct JSON fails
                                temp_job_data = ast.literal_eval(job_data_from_form)
                             except:
                                temp_job_data = None # Could not parse

                    else:
                        flash('DEBUG custom_login (adzuna): job_data_from_form is None/empty. Storing only ID/API.', 'warning')
                elif api_used == 'usajobs':
                    # For USAJobs, store the full job_data as it's generally smaller/structured
                    pending_data['job_data'] = job_data_from_form
                    flash(f'DEBUG custom_login (usajobs): Storing job_data: {job_data_from_form[:100] if job_data_from_form else "None"}', 'debug')

                session['pending_save_job'] = pending_data
                session.modified = True

            next_destination_endpoint = request.url_rule.endpoint if request.url_rule else url_for('home')

            flash('You need to be logged in to save jobs.', 'info')
            return redirect(url_for('login', next=next_destination_endpoint))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/', methods=['GET', 'POST'])
def home():
    jobs = []
    error_message = None
    page       = request.args.get('page', 1, type=int)
    per_page   = 10
    total_jobs = 0
    total_pages = 0
    keyword  = ""
    location = ""
    job_type = ""
    search_performed = False

    if request.method == 'POST':
        keyword  = request.form.get('query', "")
        location = request.form.get('location', "")
        job_type = request.form.get('job_type', "")
        search_performed = True
    elif request.args.get('keyword'):
        keyword  = request.args.get('keyword', "")
        location = request.args.get('location', "")
        job_type = request.args.get('job_type', "")
        search_performed = True

    if search_performed:
        batch_page = 1
        url = f"https://api.adzuna.com/v1/api/jobs/{os.getenv('ADZUNA_COUNTRY')}/search/{batch_page}"
        params = {
            "app_id": ADZUNA_ID,
            "app_key": ADZUNA_KEY,
            "what": keyword,
            "where": location,
            "results_per_page": 30,
            "content-type": "application/json"
        }
        try:
            resp = requests.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            all_jobs   = data.get("results", [])
            total_jobs = data.get("count", 0)
            if job_type:
                jt = job_type.lower()
                if jt in ("full_time", "part_time"):
                    all_jobs = [j for j in all_jobs if j.get("contract_time", "") == jt]
                elif jt == "remote":
                    all_jobs = [j for j in all_jobs if "Remote" in j.get('location', "").get('area', [])]
                total_jobs = len(all_jobs)
            total_pages = (total_jobs + per_page - 1) // per_page
            start_idx   = (page - 1) * per_page
            end_idx     = start_idx + per_page
            jobs        = all_jobs[start_idx:end_idx]
        except requests.HTTPError as e:
            error_message = f"Adzuna API error: {e.response.status_code} – {e.response.text}"
        except Exception as e:
            error_message = "Unable to fetch jobs. Please try again later."
            app.logger.exception(e)

    return render_template(
        'home.html', jobs=jobs, error_message=error_message, api_used='adzuna',
        page=page, total_pages=total_pages, total_jobs=total_jobs,
        keyword=keyword, location=location, job_type=job_type
    )

@app.route('/about')
def about():
    return render_template('about.html', title='About')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Account created for {form.username.data}! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            session.modified = True # Explicitly mark session as modified

            next_page_url = request.args.get('next')
            # If 'next' points to a view function name (e.g. 'save_job') from our custom decorator
            if next_page_url and next_page_url == 'save_job': # We stored the endpoint name
                 flash('Login successful! Completing pending action...', 'success')
                 return redirect(url_for(next_page_url))
            elif next_page_url: # if next_page_url is a full path
                 flash('Login successful!', 'success')
                 return redirect(next_page_url)
            else:
                 flash('Login successful!', 'success')
                 return redirect(url_for('home'))
        else:
            flash("Login Unsuccessful. Please check your email and password", 'danger')
    return render_template('login.html', title='Login', form=form)



@app.route("/google")
def google_login():
    if not google.authorized:
        flash("Google login failed. Please try again.", "danger")
        return redirect(url_for("google.login"))
    try:
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            flash("Failed to fetch user info from Google", "danger")
            return redirect(url_for("login"))

        user_info = resp.json()
        # Extract user information from the response
        email = user_info["email"]
        username= user_info.get('name') or email.split('@')[0]  # Use the part before '@' as username

        if not email:
            flash("No email found in Google account", "danger")
            return redirect(url_for("login"))

        # Check if user exists or create one
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(username=username, email=email, password='oauth')  # Dummy password
            db.session.add(user)
            db.session.commit()
        login_user(user)
        flash("Logged in via Google", "success")
        return redirect(url_for("home"))

    except Exception as e:
        import traceback
        print('Google login error:', e)
        traceback.print_exc()
        flash("Something went wrong during Google login", "danger")
        return redirect(url_for("login"))


@app.route("/github")
def github_login():
    if not github.authorized:
        return redirect(url_for("github.login"))

    resp = github.get("/user")
    if not resp.ok:
        flash("GitHub login failed", "danger")
        return redirect(url_for("login"))

    user_info = resp.json()
    github_email = user_info.get("email")
    github_username = user_info.get("login")

    # If GitHub didn't return an email, fetch it from the API
    if not github_email:
        emails_resp = github.get("/user/emails")
        if emails_resp.ok:
            for email_obj in emails_resp.json():
                if email_obj.get("primary") and email_obj.get("verified"):
                    github_email = email_obj.get("email")
                    break

    if not github_email:
        flash("GitHub login did not return an email address", "danger")
        return redirect(url_for("login"))

    # Check if user already exists
    user = User.query.filter_by(email=github_email).first()
    if not user:
        # Create new user

        user = User(username=github_username, email=github_email, password="oauth")  # Dummy password
        db.session.add(user)
        db.session.commit()

    login_user(user)
    flash("Logged in via GitHub", "success")
    return redirect(url_for("home"))


@app.route('/logout')
def logout():
    # 1) Log out from your app
    logout_user()

    # 2) If there's a Google OAuth token, revoke it
    google_token = session.get("google_oauth_token", {}).get("access_token")
    if google_token:
        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": google_token},
            headers={"content-type": "application/x-www-form-urlencoded"}
        )
    github_token = session.get("github_oauth_token", {}).get("access_token")
    if github_token:
        requests.delete("https://api.github.com/applications/Ov23liaSTZ9n66sMdPCS/token",
            auth=(os.getenv("GITHUB_CLIENT_ID"), os.getenv("GITHUB_CLIENT_SECRET")),
            json={"access_token": github_token})
    # 3) Clear it from the session so Flask-Dance won't reuse it
    session.pop("google_oauth_token", None)
    session.pop("github_oauth_token", None)

    flash("You've been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    return render_template('account.html', title='Account', form=form)

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn= random_hex + ".jpg"
    picture_path= os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    # Resize the image
    output_size = (200, 200)
    i = Image.open(form_picture).convert('RGB')  # Ensure image is in RGB mode
    i = ImageOps.fit(i, output_size, method=Image.LANCZOS)
    i.save(picture_path, format='JPEG', quality=90)  # Save as JPEG with quality

    return picture_fn

def ensure_protocol(url):
    if url and not url.startswith(('http://', 'https://')):
        return 'https://' + url
    return url

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form= ProfileForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file= save_picture(form.picture.data)
            current_user.image_file= picture_file
        current_user.bio = form.bio.data
        current_user.skills = form.skills.data
        current_user.linkedin = ensure_protocol(form.linkedin.data)
        current_user.github = ensure_protocol(form.github.data)
        current_user.location = form.location.data

        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))
    form.bio.data= current_user.bio
    form.skills.data = current_user.skills
    form.linkedin.data = current_user.linkedin
    form.github.data = current_user.github
    form.location.data = current_user.location
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('profile.html', title='Profile', form=form, image_file=image_file)

@app.route("/people")
def people():
    skill_filter = request.args.get('skill', '').strip().lower()
    location_filter = request.args.get('location', '').strip().lower()

    users = User.query
    if skill_filter:
        users = users.filter(User.skills.ilike(f'%{skill_filter}%'))
    if location_filter:
        users = users.filter(User.location.ilike(f'%{location_filter}%'))
    users = users.all()
    return render_template("people.html", users=users)

@app.route('/people/<int:user_id>')
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('public_profile.html', user=user)



@app.route('/save_job', methods=['GET', 'POST'])
@custom_login_required_for_save
def save_job():
    job_id, api_used, job_data_str, job_data = None, None, None, None
    source = ""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        job_id = request.form.get('job_id')
        api_used = request.form.get('api_used')
        job_data_str = request.form.get('job_data')
        source = "POST request"
        if job_data_str:
            try:
                job_data = json.loads(job_data_str)
            except json.JSONDecodeError:
                try: 
                    job_data = ast.literal_eval(job_data_str)
                except Exception as e_parse:
                    if is_ajax:
                        return jsonify({"status": "error", "message": f"Error parsing job_data from POST form: {e_parse}"}), 400
                    flash('Error parsing job_data from POST form.', 'danger')
                    return redirect(request.referrer or url_for('home'))
        else:
            if is_ajax:
                return jsonify({"status": "error", "message": "job_data missing from POST form."}), 400
            flash('job_data missing from POST form.', 'danger')
            return redirect(request.referrer or url_for('home'))

    elif request.method == 'GET' and 'pending_save_job' in session:
        pending_data = session.pop('pending_save_job')
        session.modified = True
        job_id = pending_data.get('job_id')
        api_used = pending_data.get('api_used')
        source = "session (after login)"

        if api_used == 'adzuna':
            # For Adzuna, construct a minimal job_data from stored pending_data
            # This avoids re-fetching or storing large objects in session
            job_data = {
                'id': job_id, # Adzuna ID for consistency if needed later
                'title': pending_data.get('title', 'N/A'),
                'company': {'display_name': pending_data.get('company_display_name', 'N/A')},
                'location': {'display_name': pending_data.get('location_display_name', 'N/A')},
                'redirect_url': pending_data.get('redirect_url', '#') # Important for apply link
                # Add other essential small fields if needed
            }
            flash(f'Reconstructed minimal Adzuna job_data from session: {job_data}', 'debug')
        elif api_used == 'usajobs':
            job_data_str = pending_data.get('job_data')
            if job_data_str:
                try:
                    job_data = json.loads(job_data_str)
                except json.JSONDecodeError:
                    try: # Fallback for session if data is dict-like string
                        job_data = ast.literal_eval(job_data_str)
                    except:
                        flash('Error parsing USAJobs job_data from session.', 'danger')
                        return redirect(request.referrer or url_for('home'))
            else:
                flash('USAJobs job_data missing from session pending_data.', 'danger')
                return redirect(request.referrer or url_for('home'))
    else:
        if is_ajax:
            return jsonify({"status": "error", "message": "Invalid request method or no pending data."}), 405 
        return redirect(url_for('home'))

    if not job_id or not api_used:
        if is_ajax:
            return jsonify({"status": "error", "message": f'Missing critical job information (ID or API used) (source: {source}).'}), 400
        flash(f'Missing critical job information (ID or API used) (source: {source}).', 'danger')
        return redirect(request.referrer or url_for('home'))

    if not job_data:
        if is_ajax:
            return jsonify({"status": "error", "message": f'Failed to prepare job_data for saving (source: {source}).'}), 500
        flash(f'Failed to prepare job_data for saving (source: {source}).', 'danger')
        return redirect(request.referrer or url_for('home'))

    existing = SavedJob.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    if existing:
        if is_ajax:
            return jsonify({"status": "info", "message": "Job already saved!", "job_id": job_id, "saved": True})
        flash('Job already saved!', 'info')
    else:
        sj = SavedJob(user_id=current_user.id, job_id=job_id, job_data=job_data, api_used=api_used)
        db.session.add(sj)
        db.session.commit()
        if is_ajax:
            return jsonify({"status": "success", "message": "Job saved!", "job_id": job_id, "saved": True})
        flash(f'Job saved successfully (from {source})!', 'success')
    
    referrer = request.referrer
    if referrer and url_for('save_job') in referrer:
        return redirect(url_for('home'))
    return redirect(referrer or url_for('home'))

@app.route('/saved_jobs')
@login_required
def saved_jobs():
    saved_jobs_list = SavedJob.query.filter_by(user_id=current_user.id).order_by(SavedJob.saved_at.desc()).all()
    return render_template('saved_jobs.html', title='Saved Jobs', saved_jobs=saved_jobs_list)

@app.route('/unsave_job', methods=['POST'])
@login_required
def unsave_job():
    # Ensure this uses 'saved_job_id' from the form as in your template, not 'job_id'
    saved_job_db_id = request.form.get('saved_job_id') 
    if not saved_job_db_id:
        flash('No job specified to unsave.', 'danger')
        return redirect(url_for('saved_jobs'))

    sj = SavedJob.query.get(saved_job_db_id) # Use .get() for primary key lookup
    if not sj:
        abort(404) # Job not found

    if sj.user_id != current_user.id:
        abort(403) # User doesn't own this saved job
    
    db.session.delete(sj)
    db.session.commit()
    flash('Job removed from your saved list!', 'info')
    return redirect(request.referrer or url_for('saved_jobs'))

def send_reset_email(user):
    token =user.get_reset_token()
    msg = Message('Password Reset Request', sender='noreply@demo.com', recipients=[user.email])
    msg.body = (f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)} 
If you did not make this request then simply ignore this email and no changes will be made.''')
    mail.send(msg)

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestRestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
            flash('An email has been sent with instructions to reset your password', 'info')
            return redirect(url_for('login'))
        else:
             flash('Email not found. You may need to register first.', 'warning') # Added feedback for non-existent email
    return render_template('reset_request.html', title='Reset Password', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash(f'Your password has been updated! You are now able to log in.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)


#From Weilan
@app.route('/resume/new', methods=['GET', 'POST'])
@login_required
def new_resume():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Extract text from PDF
            text = extract_text(file_path)

            # Get AI suggestions
            suggestions = get_ai_suggestions(text)

            # Format data according to JSON Resume schema
            resume_data = format_resume_data(suggestions)

            # Save to database
            resume = Resume(
                title=filename,
                content=json.dumps(resume_data),
                user_id=current_user.id
            )
            db.session.add(resume)
            db.session.commit()

            # Clean up
            os.remove(file_path)

            flash('Your resume has been uploaded and processed!', 'success')
            return redirect(url_for('resume_preview', resume_id=resume.id))
    return render_template('upload.html', title='New Resume')


@app.route('/resume/<int:resume_id>/preview')
@login_required
def resume_preview(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        return render_template('error.html',
                               title='Access Denied',
                               message='You do not have permission to view this resume.')

    resume_data = json.loads(resume.content)
    response = render_template('resume_preview.html', resume=resume_data)
    return response, 200, {'X-Frame-Options': 'DENY'}


@app.route('/resume/<int:resume_id>/download')
@login_required
def download_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        return render_template('error.html',
                               title='Access Denied',
                               message='You do not have permission to download this resume.')

    resume_data = json.loads(resume.content)

    # Create a temporary HTML file
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
        html_content = render_template('resume_preview.html', resume=resume_data)
        temp_html.write(html_content.encode('utf-8'))
        temp_html_path = temp_html.name

    # Convert HTML to PDF
    pdf_path = temp_html_path.replace('.html', '.pdf')
    try:
        pdfkit.from_file(temp_html_path, pdf_path)
    except Exception as e:
        os.unlink(temp_html_path)
        return render_template('error.html',
                               title='PDF Generation Error',
                               message='Failed to generate PDF',
                               error_details=str(e))

    # Clean up the temporary HTML file
    os.unlink(temp_html_path)

    # Send the PDF file
    try:
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"{resume.title.rsplit('.', 1)[0]}.pdf",
            mimetype='application/pdf'
        )
    finally:
        # Clean up the temporary PDF file
        os.unlink(pdf_path)


@app.route('/resume/<int:resume_id>/delete', methods=['POST'])
@login_required
def delete_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        return render_template('error.html',
                               title='Access Denied',
                               message='You do not have permission to delete this resume.')

    db.session.delete(resume)
    db.session.commit()
    flash('Resume has been deleted!', 'success')
    return redirect(url_for('home'))


@app.route('/resume/<int:resume_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        return render_template('error.html',
                               title='Access Denied',
                               message='You do not have permission to edit this resume.')

    if request.method == 'POST':
        resume_data = request.json
        resume.content = json.dumps(resume_data)
        db.session.commit()
        return jsonify({'message': 'Resume updated successfully'})

    resume_data = json.loads(resume.content)
    return render_template('edit_resume.html', resume=resume_data)


@app.route('/resume', methods=['GET', 'POST'])
def resume():
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                text = ''
                if file.filename.endswith('.pdf'):
                    with pdfplumber.open(file) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + '\n'
                elif file.filename.endswith('.docx'):
                    doc = docx.Document(file)
                    for para in doc.paragraphs:
                        text += para.text + '\n'
                parsed = {
                    "summary": text[:300],
                    "skills": [],
                    "education": [],
                    "workExperience": []
                }
                return jsonify(parsed)
        return redirect(url_for('resume_builder'))
    return render_template('resume.html')


@app.route('/resume/builder')
def resume_builder():
    return render_template('resume_builder.html', title='Resume Builder')


@app.route('/resume/analyze', methods=['POST'])
def analyze_resume():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Convert resume data to text for analysis
        resume_text = f"""
Name: {data.get('name', '')}
Email: {data.get('email', '')}
Phone: {data.get('phone', '')}
Location: {data.get('location', '')}

Summary:
{data.get('summary', '')}

Experience:
{chr(10).join([f"- {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('start', '')} - {exp.get('end', '')}): {exp.get('description', '')}" for exp in data.get('experience', [])])}

Education:
{chr(10).join([f"- {edu.get('degree', '')} from {edu.get('school', '')} ({edu.get('start', '')} - {edu.get('end', '')})" for edu in data.get('education', [])])}

Skills:
{data.get('skills', '')}
"""

        # Get AI suggestions
        suggestions = get_ai_suggestions(resume_text)

        return jsonify({
            'success': True,
            'suggestions': suggestions
        })

    except Exception as e:
        app.logger.error(f"Resume analysis error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/resume/export', methods=['POST'])
def export_resume():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Format the resume data
        formatted_data = format_resume_data(data)
        theme = data.get('theme', 'modern')

        # Convert resume data to HTML using the selected theme
        template = Template(load_template(theme))
        html_content = template.render(resume=formatted_data)

        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
            temp_html.write(html_content.encode('utf-8'))
            temp_html_path = temp_html.name

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf_path = temp_pdf.name

        try:
            # Configure pdfkit options
            options = {
                'page-size': 'Letter',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': 'UTF-8',
                'no-outline': None,
                'enable-local-file-access': None
            }

            # Convert HTML to PDF
            pdfkit.from_file(temp_html_path, temp_pdf_path, options=options)

            # Send the PDF file
            return send_file(
                temp_pdf_path,
                as_attachment=True,
                download_name='resume.pdf',
                mimetype='application/pdf'
            )
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_html_path)
                os.unlink(temp_pdf_path)
            except Exception as e:
                app.logger.error(f"Error cleaning up temporary files: {str(e)}")

    except Exception as e:
        app.logger.error(f"Export error: {str(e)}")
        return jsonify({'error': f'Failed to export resume: {str(e)}'}), 500



@app.route('/resume/preview', methods=['POST'])
def preview_resume():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Format the resume data with error handling
        formatted_data = format_resume_data(data)
        theme = data.get('theme', 'modern')

        try:
            # Convert resume data to HTML using the selected theme
            template = Template(load_template(theme))
            html_content = template.render(resume=formatted_data)
        except Exception as e:
            app.logger.error(f"Template rendering error: {str(e)}")
            # Fallback to a basic template if theme rendering fails
            html_content = f"""
            <div class="resume">
                <div class="header">
                    <h1>{formatted_data['basics']['name']}</h1>
                    <div class="contact-info">
                        <span>{formatted_data['basics']['email']}</span>
                        <span class="separator">•</span>
                        <span>{formatted_data['basics']['phone']}</span>
                        <span class="separator">•</span>
                        <span>{formatted_data['basics']['location']['address']}</span>
                    </div>
                </div>

                <div class="section">
                    <h2>Summary</h2>
                    <p>{formatted_data['basics']['summary']}</p>
                </div>

                <div class="section">
                    <h2>Experience</h2>
                    {''.join([f'''
                    <div class="entry">
                        <div class="entry-header">
                            <h3>{work["position"]}</h3>
                            <span class="company">{work["company"]}</span>
                        </div>
                        <div class="entry-dates">{work["startDate"]} - {work["endDate"]}</div>
                        <p class="description">{work["summary"]}</p>
                    </div>''' for work in formatted_data['work']])}
                </div>

                <div class="section">
                    <h2>Education</h2>
                    {''.join([f'''
                    <div class="entry">
                        <div class="entry-header">
                            <h3>{edu["institution"]}</h3>
                            <span class="degree">{edu["area"]}</span>
                        </div>
                        <div class="entry-dates">{edu["startDate"]} - {edu["endDate"]}</div>
                    </div>''' for edu in formatted_data['education']])}
                </div>

                <div class="section">
                    <h2>Skills</h2>
                    <div class="skills-list">
                        {''.join([f'<span class="skill-tag">{skill["name"]}</span>' for skill in formatted_data['skills']])}
                    </div>
                </div>
            </div>
            """

        # Add CSS for better web preview
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{formatted_data['basics']['name']} - Resume</title>
            <style>
                @page {{
                    size: letter;
                    margin: 0;
                }}
                body {{
                    font-family: "Times New Roman", Times, serif;
                    line-height: 1.15;
                    margin: 0;
                    padding: 0;
                    background-color: #f8f9fa;
                    color: #000;
                }}
                .resume {{
                    width: 8.5in;
                    min-height: 11in;
                    padding: 0.75in;
                    margin: 0 auto;
                    background-color: white;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                    position: relative;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 0.25in;
                }}
                h1 {{
                    font-size: 12pt;
                    margin: 0 0 0.1in 0;
                    font-weight: bold;
                    text-transform: uppercase;
                }}
                .contact-info {{
                    font-size: 12pt;
                }}
                .separator {{
                    margin: 0 0.1in;
                }}
                h2 {{
                    font-size: 12pt;
                    font-weight: bold;
                    text-transform: uppercase;
                    border-bottom: 1px solid #000;
                    padding-bottom: 0.05in;
                    margin: 0.2in 0 0.1in 0;
                }}
                .section {{
                    margin-bottom: 0.15in;
                }}
                .entry {{
                    margin-bottom: 0.1in;
                }}
                .entry-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: baseline;
                    margin-bottom: 0.02in;
                }}
                .entry-header h3 {{
                    font-size: 12pt;
                    font-weight: bold;
                    margin: 0;
                }}
                .company, .degree {{
                    font-size: 12pt;
                    font-style: italic;
                }}
                .entry-dates {{
                    font-size: 12pt;
                    margin-bottom: 0.02in;
                }}
                .description {{
                    font-size: 12pt;
                    margin: 0.02in 0;
                    text-align: justify;
                }}
                .skills-list {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.1in;
                    margin-top: 0.05in;
                }}
                .skill-tag {{
                    font-size: 12pt;
                    padding: 0;
                    margin-right: 0.2in;
                }}
                .skill-tag:after {{
                    content: ",";
                }}
                .skill-tag:last-child:after {{
                    content: "";
                }}
                p {{
                    margin: 0.02in 0;
                    font-size: 12pt;
                    text-align: justify;
                }}
                @media print {{
                    body {{
                        background-color: white;
                    }}
                    .resume {{
                        box-shadow: none;
                        width: 100%;
                        height: 100%;
                        margin: 0;
                        padding: 0.75in;
                    }}
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        return html_content, 200, {'Content-Type': 'text/html'}

    except Exception as e:
        app.logger.error(f"Preview error: {str(e)}")
        # Return a basic error page instead of JSON error
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Resume Preview Error</title>
            <style>
                body {{
                    font-family: "Times New Roman", Times, serif;
                    line-height: 1.15;
                    margin: 0;
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background-color: #f8f9fa;
                }}
                .error-container {{
                    background-color: white;
                    padding: 30px;
                    border: 1px solid #000;
                    text-align: center;
                }}
                h1 {{ 
                    color: #000;
                    font-size: 12pt;
                    margin: 0 0 12px 0;
                    font-weight: bold;
                }}
                p {{
                    margin: 8px 0;
                    font-size: 12pt;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>Error Generating Preview</h1>
                <p>There was an error generating the resume preview. Please try again or contact support if the problem persists.</p>
                <p>Error details: {str(e)}</p>
            </div>
        </body>
        </html>
        """
        return error_html, 200, {'Content-Type': 'text/html'}
