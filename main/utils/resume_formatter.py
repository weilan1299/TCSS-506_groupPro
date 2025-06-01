def format_resume_data(data):
    """Format resume data according to JSON Resume schema"""
    try:
        # Handle skills whether they come as a string or list
        skills = data.get('skills', [])
        if isinstance(skills, str):
            skills = [{"name": skill.strip()} for skill in skills.split(',') if skill.strip()]
        elif isinstance(skills, list):
            skills = [{"name": skill.strip()} for skill in skills if skill.strip()]
        else:
            skills = []

        # Format the resume data according to JSON Resume schema
        formatted_data = {
            "basics": {
                "name": data.get('personal_info', {}).get('name', '') or data.get('name', ''),
                "email": data.get('personal_info', {}).get('email', '') or data.get('email', ''),
                "phone": data.get('personal_info', {}).get('phone', '') or data.get('phone', ''),
                "location": {
                    "address": data.get('personal_info', {}).get('location', '') or data.get('location', '')
                },
                "summary": data.get('personal_info', {}).get('summary', '') or data.get('summary', '')
            },
            "work": [],
            "education": [],
            "skills": skills,
            "projects": [],
            "awards": []
        }

        # Process work experience
        experience = data.get('experience', [])
        if isinstance(experience, list):
            for exp in experience:
                if isinstance(exp, dict):
                    formatted_data["work"].append({
                        "company": exp.get('company', ''),
                        "position": exp.get('title', ''),
                        "startDate": exp.get('start_date', '') or exp.get('start', ''),
                        "endDate": exp.get('end_date', '') or exp.get('end', ''),
                        "summary": exp.get('description', '')
                    })

        # Process education
        education = data.get('education', [])
        if isinstance(education, list):
            for edu in education:
                if isinstance(edu, dict):
                    formatted_data["education"].append({
                        "institution": edu.get('school', ''),
                        "area": edu.get('degree', ''),
                        "startDate": edu.get('start_date', '') or edu.get('start', ''),
                        "endDate": edu.get('end_date', '') or edu.get('end', '')
                    })

        # Process projects
        projects = data.get('projects', [])
        if isinstance(projects, list):
            for proj in projects:
                if isinstance(proj, dict):
                    formatted_data["projects"].append({
                        "name": proj.get('title', ''),
                        "description": proj.get('description', '')
                    })

        # Process awards
        awards = data.get('awards', [])
        if isinstance(awards, list):
            for award in awards:
                if isinstance(award, dict):
                    formatted_data["awards"].append({
                        "title": award.get('title', ''),
                        "date": award.get('date', '')
                    })

        return formatted_data
    except Exception as e:
        # Return a minimal valid structure if formatting fails
        return {
            "basics": {
                "name": "Error in Resume Data",
                "email": "",
                "phone": "",
                "location": {"address": ""},
                "summary": ""
            },
            "work": [],
            "education": [],
            "skills": [],
            "projects": [],
            "awards": []
        } 