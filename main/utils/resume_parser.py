import pdfplumber
import docx
import os
import cohere
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Cohere client
co = cohere.Client(os.getenv("COHERE_API_KEY"))

def extract_text(file_path):
    """Extract text from PDF or DOCX files"""
    if file_path.endswith('.pdf'):
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text
    elif file_path.endswith('.docx'):
        doc = docx.Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    else:
        return ""

def get_ai_suggestions(resume_text):
    """Get AI suggestions for resume improvements"""
    prompt = f"""As a professional resume reviewer, analyze this resume and provide specific suggestions for improvement in the following areas:
1. Content and achievements
2. Skills and keywords
3. Format and structure
4. Professional summary
5. Action verbs and language

Resume text:
{resume_text}

Please provide detailed, actionable suggestions for each area."""

    response = co.generate(
        model='command-r-plus',
        prompt=prompt,
        max_tokens=500,
        temperature=0.7,
    )
    return response.generations[0].text.strip() 