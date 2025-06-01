from flask import jsonify, request
from main import db
from main.models import Resume
import json
from main.utils.resume_formatter import format_resume_data
from main.utils.resume_parser import get_ai_suggestions

def process_form_data(form_data):
    """
    Process form data and convert it to a structured format
    
    Args:
        form_data: Raw form data from request
        
    Returns:
        dict: Processed form data with structured arrays
    """
    processed_data = form_data.to_dict()
    
    # Initialize arrays
    processed_data['experience'] = []
    processed_data['education'] = []
    
    # Process experience entries
    titles = form_data.getlist('exp_title[]')
    companies = form_data.getlist('exp_company[]')
    starts = form_data.getlist('exp_start[]')
    ends = form_data.getlist('exp_end[]')
    descriptions = form_data.getlist('exp_description[]')
    
    for i in range(len(titles)):
        if titles[i].strip():
            processed_data['experience'].append({
                'title': titles[i],
                'company': companies[i],
                'start': starts[i],
                'end': ends[i],
                'description': descriptions[i]
            })
    
    # Process education entries
    schools = form_data.getlist('edu_school[]')
    degrees = form_data.getlist('edu_degree[]')
    edu_starts = form_data.getlist('edu_start[]')
    edu_ends = form_data.getlist('edu_end[]')
    
    for i in range(len(schools)):
        if schools[i].strip():
            processed_data['education'].append({
                'school': schools[i],
                'degree': degrees[i],
                'start': edu_starts[i],
                'end': edu_ends[i]
            })
    
    # Process skills
    skills_text = processed_data.get('skills', '')
    if skills_text:
        processed_data['skills'] = [skill.strip() for skill in skills_text.split(',') if skill.strip()]
    
    return processed_data

def save_resume(form_data, user_id, title):
    """
    Save resume data to the database
    
    Args:
        form_data: Form data containing resume information
        user_id: ID of the user saving the resume
        title: Title of the resume
        
    Returns:
        dict: Response containing success status and resume ID
    """
    try:
        # Process form data
        processed_data = process_form_data(form_data)
        
        # Format resume data according to JSON Resume schema
        resume_data = format_resume_data(processed_data)
        
        # Get AI suggestions
        resume_text = f"""
Name: {processed_data.get('name', '')}
Email: {processed_data.get('email', '')}
Phone: {processed_data.get('phone', '')}
Location: {processed_data.get('location', '')}

Summary:
{processed_data.get('summary', '')}

Experience:
{chr(10).join([f"- {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('start', '')} - {exp.get('end', '')}): {exp.get('description', '')}" for exp in processed_data.get('experience', [])])}

Education:
{chr(10).join([f"- {edu.get('degree', '')} from {edu.get('school', '')} ({edu.get('start', '')} - {edu.get('end', '')})" for edu in processed_data.get('education', [])])}

Skills:
{processed_data.get('skills', '')}
"""
        suggestions = get_ai_suggestions(resume_text)
        
        # Create new resume entry
        resume = Resume(
            title=title,
            content=json.dumps(resume_data),
            user_id=user_id,
            theme=processed_data.get('theme', 'modern')
        )
        
        # Save to database
        db.session.add(resume)
        db.session.commit()
        
        return {
            'success': True,
            'resume_id': resume.id,
            'suggestions': suggestions
        }
        
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'error': str(e)
        } 