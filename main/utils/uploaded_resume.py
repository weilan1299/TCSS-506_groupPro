import os
import docx
import pdfplumber
from werkzeug.utils import secure_filename
from datetime import datetime

# Assuming these are available from your main application context or can be passed
# You might need to adjust imports based on your project structure
from main import db
from main.models import Resume
from main.utils.resume_parser import get_ai_suggestions, extract_text # Ensure extract_text is available here
import logging

# Configure logging for this module
logger = logging.getLogger(__name__)

def process_uploaded_resume(uploaded_file, user_id):
    """
    Processes an uploaded resume file, extracts text, generates AI suggestions,
    and saves the data to the database.

    Args:
        uploaded_file: The FileStorage object from Flask's request.files.
        user_id: The ID of the current user.

    Returns:
        A tuple (resume_entry, error_message).
        - resume_entry: The newly created Resume database object if successful, else None.
        - error_message: A string containing an error message if processing fails, else None.
    """
    if not uploaded_file:
        return None, "No file provided for processing."
    if uploaded_file.filename == '':
        return None, "No selected file."

    filename = secure_filename(uploaded_file.filename)
    file_content = ''
    error = None

    try:
        if filename.endswith('.pdf'):
            # pdfplumber needs a file-like object, uploaded_file.stream._file is the underlying BytesIO object
            with pdfplumber.open(uploaded_file.stream._file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        file_content += page_text + '\n'
        elif filename.endswith('.docx'):
            # docx.Document also needs a file-like object
            doc = docx.Document(uploaded_file.stream._file)
            for para in doc.paragraphs:
                file_content += para.text + '\n'
        else:
            error = "Unsupported file type. Please upload a PDF or DOCX."
            # Attempt to read as plain text if it's not a known type
            try:
                # Reset stream position before reading as plain text
                uploaded_file.stream.seek(0)
                file_content = uploaded_file.read().decode('utf-8', errors='ignore')
            except Exception as e:
                logger.error(f"Error reading unsupported file as text: {e}")
                error = f"Error reading file content: {e}"
                file_content = ""

        if error:
            return None, error

        if not file_content.strip():
            return None, "Could not extract any readable text from the uploaded file."

        # Generate AI suggestions
        suggestions = get_ai_suggestions(file_content)

        # Save to database
        resume_entry = Resume(
            title=filename,  # Use filename as title
            content=file_content,  # Store full original content
            ai_suggestions=suggestions,  # Store AI suggestions
            modified_content=None,  # Initially no modifications
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(resume_entry)
        db.session.commit()

        return resume_entry, None # Return the created resume entry and no error

    except Exception as e:
        db.session.rollback() # Rollback in case of database error
        logger.error(f"Error during resume processing: {e}", exc_info=True)
        return None, f"An internal error occurred during file processing: {e}"
