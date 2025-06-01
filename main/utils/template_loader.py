import os

def load_template(theme):
    """Load a resume template by theme name"""
    template_path = f'templates/resume_themes/{theme}.html'
    if not os.path.exists(template_path):
        template_path = 'templates/resume_themes/modern.html'  # Default to modern theme
    with open(template_path, 'r') as f:
        return f.read() 