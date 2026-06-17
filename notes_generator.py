"""
AI Notes Generator - Professional Edition
With Signup, Login & Entrance Exam Question Answering
"""

import os
import json
import hashlib
import socket
import re
from datetime import datetime
from pathlib import Path
import PyPDF2
import gradio as gr
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Set OCR paths
tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(tesseract_path):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    print("✅ Tesseract found at:", tesseract_path)
else:
    print("⚠️ Tesseract not found at:", tesseract_path)

# Set poppler path
poppler_path = r'C:\poppler-26.02.0\Library\bin'
if os.path.exists(poppler_path):
    os.environ['PATH'] = poppler_path + os.pathsep + os.environ.get('PATH', '')
    from pdf2image import convert_from_path
    print("✅ Poppler found at:", poppler_path)
    OCR_AVAILABLE = True
else:
    print("⚠️ Poppler not found at:", poppler_path)
    OCR_AVAILABLE = False
    convert_from_path = None

# Create necessary folders
NOTES_FOLDER = Path("notes")
QA_FOLDER = Path("qa_banks")
HISTORY_FOLDER = Path("history")
USERS_FOLDER = Path("users")
UPLOAD_FOLDER = Path("uploads")

for folder in [NOTES_FOLDER, QA_FOLDER, HISTORY_FOLDER, USERS_FOLDER, UPLOAD_FOLDER]:
    folder.mkdir(exist_ok=True)

# Global variables
file_context = {
    "text": "",
    "filename": "",
    "uploaded": False,
    "word_count": 0,
    "pages": 0,
    "is_exam_paper": False
}

current_user = {
    "email": "",
    "logged_in": False
}

# User database
USERS_DB = USERS_FOLDER / "users.json"

def find_free_port(start_port=7860, max_port=8000):
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return 7860

def init_users_db():
    if not USERS_DB.exists():
        with open(USERS_DB, 'w') as f:
            json.dump({}, f)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(email, password):
    init_users_db()
    with open(USERS_DB, 'r') as f:
        users = json.load(f)
    
    if email in users:
        return False, "❌ Email already registered! Please login."
    
    users[email] = {
        "password": hash_password(password),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "history": []
    }
    
    with open(USERS_DB, 'w') as f:
        json.dump(users, f, indent=2)
    
    return True, "✅ Registration successful! Please login."

def login_user(email, password):
    init_users_db()
    with open(USERS_DB, 'r') as f:
        users = json.load(f)
    
    if email not in users:
        return False, "❌ User not found! Please sign up first."
    
    if users[email]["password"] != hash_password(password):
        return False, "❌ Incorrect password!"
    
    current_user["email"] = email
    current_user["logged_in"] = True
    
    return True, f"✅ Welcome back, {email.split('@')[0]}!"

def detect_exam_paper(text):
    text_lower = text.lower()
    exam_keywords = ['pgcet', 'cet', 'kcet', 'jee', 'neet', 'gate', 'entrance exam', 'question paper', 'model paper', 'previous year', 'sample paper', 'mock test', 'question bank', 'marks', 'multiple choice', 'mcq']
    question_patterns = [r'\d+\.\s+', r'Q\.?\s*\d+', r'\(?\d+\s*marks?\)?', r'[A-D]\)\s+']
    
    keyword_count = sum(1 for keyword in exam_keywords if keyword in text_lower)
    pattern_count = sum(1 for pattern in question_patterns if re.search(pattern, text))
    
    return keyword_count >= 2 or pattern_count >= 3

def save_to_history(item_type, item_name, content_preview):
    if not current_user["logged_in"]:
        return
    
    history_file = HISTORY_FOLDER / f"{current_user['email'].replace('@', '_').replace('.', '_')}_history.json"
    
    if history_file.exists():
        with open(history_file, 'r') as f:
            history = json.load(f)
    else:
        history = []
    
    history.append({
        "type": item_type,
        "name": item_name,
        "preview": content_preview[:200],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)

def get_user_history():
    if not current_user["logged_in"]:
        return []
    
    history_file = HISTORY_FOLDER / f"{current_user['email'].replace('@', '_').replace('.', '_')}_history.json"
    
    if history_file.exists():
        with open(history_file, 'r') as f:
            return json.load(f)
    return []

def delete_user_history():
    if not current_user["logged_in"]:
        return False, "Not logged in"
    
    history_file = HISTORY_FOLDER / f"{current_user['email'].replace('@', '_').replace('.', '_')}_history.json"
    if history_file.exists():
        history_file.unlink()
        return True, "✅ History deleted successfully!"
    return False, "No history found"

def extract_text_from_pdf(pdf_path):
    try:
        full_text = ""
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            total_pages = len(reader.pages)
            
            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    full_text += page_text + "\n\n"
        
        if full_text.strip():
            return full_text, f"Extracted from {total_pages} pages", total_pages, "text"
        
        if OCR_AVAILABLE and convert_from_path is not None:
            images = convert_from_path(pdf_path, dpi=200)
            total_pages = len(images)
            
            for page_num, image in enumerate(images, 1):
                page_text = pytesseract.image_to_string(image)
                if page_text.strip():
                    full_text += f"\n[Page {page_num} - OCR]\n"
                    full_text += page_text + "\n\n"
            
            if full_text.strip():
                return full_text, f"Extracted from {total_pages} pages using OCR", total_pages, "scanned"
            else:
                return None, "No text could be extracted", total_pages, "failed"
        else:
            return None, "Text couldn't be extracted", total_pages, "error"
    except Exception as e:
        return None, f"Error: {str(e)}", 0, "error"


class NotesGenerator:
    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY')
        self.client = None
        
        if self.api_key and self.api_key != "your-api-key-here":
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                print("✅ Groq API connected!")
            except Exception as e:
                print(f"⚠️ API Error: {e}")
    
    def extract_and_store_file(self, file_path):
        global file_context
        
        text, status, pages, extraction_type = extract_text_from_pdf(file_path)
        
        if not text:
            return False, status, 0, 0, "error", False
        
        is_exam = detect_exam_paper(text)
        
        file_context = {
            "text": text,
            "filename": os.path.basename(file_path),
            "uploaded": True,
            "word_count": len(text.split()),
            "pages": pages,
            "extraction_type": extraction_type,
            "is_exam_paper": is_exam
        }
        
        save_to_history("FILE_UPLOAD", os.path.basename(file_path), f"Uploaded PDF, {len(text.split())} words")
        return True, status, len(text.split()), pages, extraction_type, is_exam
    
    def generate_topic_wise_summary(self):
        global file_context
        
        if not file_context["uploaded"]:
            return "❌ Please upload a PDF file first."
        
        if not self.client:
            return self.get_fallback_summary()
        
        if file_context.get("is_exam_paper"):
            prompt = f"""You are an expert educator. This is an EXAM PAPER. Provide SOLUTIONS/ANSWERS to each question.

FILE: {file_context['filename']}
PAGES: {file_context['pages']}
WORDS: {file_context['word_count']}

CONTENT:
{file_context['text'][:8000]}

IMPORTANT FORMATTING RULES:
- Use <br><br><br> (THREE blank lines) between each question
- Use **bold** for question numbers
- Use • for bullet points, each on a new line with <br>
- Leave proper spacing between answer points

FORMAT EXACTLY LIKE THIS:

<br><br><br>

**📌 QUESTION 1:** [Question text]
<br><br>
**Answer:**
<br>
• First key point with explanation
<br>
• Second key point with explanation
<br>
• Third key point with explanation
<br><br>
💡 **Example:** [Example if available]
<br><br><br>

**📌 QUESTION 2:** [Question text]
<br><br>
**Answer:**
<br>
• Point 1
<br>
• Point 2
<br><br>

Provide complete answers for ALL questions."""
        else:
            prompt = f"""You are an expert educator. Create a DETAILED topic-wise summary.

FILE: {file_context['filename']}
PAGES: {file_context['pages']}
WORDS: {file_context['word_count']}

CONTENT:
{file_context['text'][:8000]}

IMPORTANT FORMATTING RULES:
- Use <br><br><br> (THREE blank lines) between each topic
- Use **bold** for topic headings
- Use • for bullet points, each on a new line with <br>
- Leave proper spacing between points

FORMAT EXACTLY LIKE THIS:

<br><br><br>

**📌 TOPIC 1:** [Topic Name]
<br><br>
[Detailed explanation in 2-3 sentences]
<br>
• Key point 1 with explanation
<br>
• Key point 2 with explanation
<br>
• Key point 3 with explanation
<br><br>
💡 **Example:** [Example if available]
<br><br><br>

**📌 TOPIC 2:** [Topic Name]
<br><br>
[Detailed explanation]
<br>
• Key point 1
<br>
• Key point 2
<br><br><br>

**📌 KEY TAKEAWAYS**
<br><br>
✅ Takeaway 1
<br>
✅ Takeaway 2
<br>
✅ Takeaway 3

Cover EVERY important topic from the document."""
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=4000
            )
            summary = response.choices[0].message.content
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = NOTES_FOLDER / f"summary_{timestamp}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            save_to_history("SUMMARY_GENERATED", file_context['filename'], "Summary generated")
            
            exam_note = ""
            if file_context.get("is_exam_paper"):
                exam_note = '<div style="background: #fef3c7; padding: 12px; border-radius: 10px; margin-bottom: 20px;">📝 <strong>Exam Paper Detected!</strong> Solutions provided for all questions.</div>'
            
            return f"""
<div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 20px; border-radius: 16px; margin-bottom: 20px;">
📄 <strong>PDF Analysis Complete</strong><br>
• File: {file_context['filename']}<br>
• Pages: {file_context['pages']}<br>
• Words: {file_context['word_count']:,}<br>
• Type: {"📋 Exam Paper (Solutions Below)" if file_context.get("is_exam_paper") else "📚 Study Material"}
</div>
{exam_note}
<div style="background: white; padding: 30px; border-radius: 16px; max-height: 600px; overflow-y: auto; line-height: 1.9;">
{summary}
</div>
<div style="background: #f1f5f9; padding: 15px; border-radius: 12px; text-align: center; margin-top: 20px;">
💾 Saved to notes/ folder
</div>
"""
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def generate_qa_bank(self):
        global file_context
        
        if not file_context["uploaded"]:
            return "❌ Please upload a PDF file first."
        
        if not self.client:
            return self.get_fallback_qa()
        
        if file_context.get("is_exam_paper"):
            prompt = f"""Based on this EXAM PAPER, provide COMPLETE SOLUTIONS.

FILE: {file_context['filename']}
CONTENT: {file_context['text'][:8000]}

IMPORTANT FORMATTING RULES:
- Use <br><br><br> (THREE blank lines) between each question
- Use **bold** for question numbers
- Use • for bullet points, each on a new line with <br>

FORMAT EXACTLY LIKE THIS:

<br><br><br>

**Q1.** [Question text]
<br><br>
**Answer:**
<br>
• Point 1
<br>
• Point 2
<br>
• Point 3
<br><br>
📌 **Key Point:** Important note
<br><br><br>

**Q2.** [Question text]
<br><br>
**Answer:**
<br>
• Point 1
<br>
• Point 2

Cover ALL questions from the exam paper."""
        else:
            prompt = f"""Based on this PDF content, create a QUESTION AND ANSWER BANK.

FILE: {file_context['filename']}
CONTENT: {file_context['text'][:8000]}

Create questions covering ALL major topics with marks:
- 5 questions of 2 marks (short answers)
- 5 questions of 5 marks (medium answers)
- 5 questions of 8 marks (detailed answers)

IMPORTANT FORMATTING RULES:
- Use <br><br><br> (THREE blank lines) between each question
- Use **bold** for question numbers and marks
- Use • for bullet points, each on a new line with <br>

FORMAT EXACTLY LIKE THIS:

<br><br><br>

**Q1.** [Question text] **(2 Marks)**
<br><br>
**Answer:**
<br>
• Point 1
<br>
• Point 2
<br><br><br>

**Q2.** [Question text] **(5 Marks)**
<br><br>
**Answer:**
<br>
• Main point 1
<br>
• Main point 2
<br>
• Main point 3"""
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=4000
            )
            qa_content = response.choices[0].message.content
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = QA_FOLDER / f"qa_bank_{timestamp}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(qa_content)
            
            save_to_history("QA_GENERATED", file_context['filename'], "Q&A Bank generated")
            
            exam_note = ""
            if file_context.get("is_exam_paper"):
                exam_note = '<div style="background: #fef3c7; padding: 12px; border-radius: 10px; margin-bottom: 20px;">📝 <strong>Exam Paper Detected!</strong> Solutions provided below.</div>'
            
            return f"""
<div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 20px; border-radius: 16px; margin-bottom: 20px;">
📋 <strong>Question & Answer Bank</strong><br>
• Based on: {file_context['filename']}<br>
• Pages: {file_context['pages']}<br>
• Words: {file_context['word_count']:,}
</div>
{exam_note}
<div style="background: white; padding: 30px; border-radius: 16px; max-height: 600px; overflow-y: auto; line-height: 1.9;">
{qa_content}
</div>
<div style="background: #f1f5f9; padding: 15px; border-radius: 12px; text-align: center; margin-top: 20px;">
💾 Saved to qa_banks/ folder
</div>
"""
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def ask_question(self, question):
        global file_context
        
        if not file_context["uploaded"]:
            return "❌ Please upload a PDF file first."
        
        if not question or not question.strip():
            return "❌ Please enter a question."
        
        if not self.client:
            return self.get_fallback_answer(question)
        
        save_to_history("QUESTION_ASKED", question[:100], question[:200])
        
        prompt = f"""Answer this question based ONLY on the uploaded PDF.

FILE: {file_context['filename']}
CONTENT: {file_context['text'][:8000]}

QUESTION: {question}

IMPORTANT FORMATTING RULES:
- Start with a direct answer
- Use • for bullet points, each on a new line with <br>
- Leave <br><br> between sections
- Use <br><br> before conclusion

FORMAT YOUR ANSWER LIKE THIS:
[Direct answer in 1-2 sentences]
<br><br>
• First supporting point
<br>
• Second supporting point
<br>
• Third supporting point
<br><br>
📌 **Example:** [Example from content]
<br><br>
✅ **Key Takeaway:** [Summary]"""
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=2500
            )
            answer = response.choices[0].message.content
            
            exam_note = ""
            if file_context.get("is_exam_paper"):
                exam_note = '<div style="background: #fef3c7; padding: 8px; border-radius: 8px; margin-bottom: 15px;">📝 <strong>Exam Question</strong></div>'
            
            return f"""
<div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 20px; border-radius: 16px; margin-bottom: 20px;">
📄 <strong>Based on:</strong> {file_context['filename']}
</div>
{exam_note}
<div style="background: white; padding: 25px; border-radius: 16px; max-height: 500px; overflow-y: auto; line-height: 1.9;">
<strong>❓ Question:</strong><br>
{question}
<br><br><br>
<strong>✅ Answer:</strong><br><br>
{answer}
</div>
"""
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def get_fallback_summary(self):
        return f"""
<div style="background: #fef3c7; padding: 20px; border-radius: 16px;">
<h3>📝 PDF Ready for Analysis</h3>
<p><strong>File:</strong> {file_context['filename']}<br>
<strong>Words:</strong> {file_context['word_count']:,}</p>
<p>Add Groq API key to .env file for AI analysis.</p>
</div>
"""
    
    def get_fallback_qa(self):
        return f"""
<div style="background: #fef3c7; padding: 20px; border-radius: 16px;">
<h3>📝 Ready for Q&A Generation</h3>
<p><strong>File:</strong> {file_context['filename']}<br>
<strong>Words:</strong> {file_context['word_count']:,}</p>
<p>Add Groq API key to .env file for AI generation.</p>
</div>
"""
    
    def get_fallback_answer(self, question):
        return f"""
<div style="background: #fef3c7; padding: 20px; border-radius: 16px;">
<h3>❓ Question Received</h3>
<p><strong>Your Question:</strong> {question}</p>
<p><strong>Current PDF:</strong> {file_context['filename']}</p>
<p>Add Groq API key to .env file for AI answers.</p>
</div>
"""


# Professional CSS
PROFESSIONAL_CSS = """
.gradio-container {
    background: #f0f2f5 !important;
}
.main-container {
    max-width: 1400px !important;
    margin: auto !important;
    padding: 20px !important;
}
.output-container {
    max-height: 600px !important;
    overflow-y: auto !important;
    background: transparent !important;
    padding: 20px !important;
}
.output-container div {
    line-height: 1.9 !important;
}
.gr-button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    padding: 12px 32px !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    transition: all 0.3s !important;
    border: none !important;
}
.gr-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(102,126,234,0.3);
}
.app-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 40px;
    border-radius: 20px;
    text-align: center;
    margin-bottom: 30px;
}
.app-header h1 {
    margin: 0;
    font-size: 2.5em;
}
.app-header p {
    margin: 10px 0 0;
    opacity: 0.9;
}
.file-info {
    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    padding: 20px;
    border-radius: 16px;
    border-left: 4px solid #10b981;
}
.login-card {
    background: white;
    border-radius: 28px;
    padding: 50px;
    max-width: 450px;
    margin: auto;
    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
}
.login-header {
    text-align: center;
    margin-bottom: 40px;
}
.login-header .icon {
    font-size: 56px;
    margin-bottom: 16px;
}
.login-header h2 {
    color: #1e293b;
    font-size: 32px;
}
.input-group {
    margin-bottom: 24px;
}
.input-group label {
    display: block;
    margin-bottom: 8px;
    color: #334155;
    font-weight: 500;
}
.input-group input {
    width: 100%;
    padding: 14px 16px;
    border: 2px solid #e2e8f0;
    border-radius: 14px;
    font-size: 15px;
}
.input-group input:focus {
    outline: none;
    border-color: #667eea;
}
.login-btn, .signup-btn {
    width: 100%;
    padding: 14px;
    margin-top: 8px;
    border-radius: 14px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
}
.login-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
}
.signup-btn {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
    color: white !important;
}
.toggle-btn {
    background: transparent !important;
    color: #667eea !important;
    border: 1px solid #667eea !important;
    margin-top: 15px !important;
    width: 100% !important;
}
.toggle-btn:hover {
    background: #667eea !important;
    color: white !important;
}
.message {
    margin-top: 20px;
    padding: 12px;
    border-radius: 12px;
    text-align: center;
}
.message.success {
    background: #dcfce7;
    color: #166534;
}
.message.error {
    background: #fee2e2;
    color: #dc2626;
}
.history-item {
    background: white;
    padding: 15px;
    border-radius: 12px;
    margin: 10px 0;
    border-left: 4px solid #667eea;
}
"""


def create_interface():
    generator = NotesGenerator()
    
    with gr.Blocks(title="AI Notes Generator", theme=gr.themes.Soft()) as demo:
        
        # Login Page
        with gr.Column(visible=True, elem_id="auth_container") as auth_container:
            gr.HTML("""
            <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px;">
                <div class="login-card">
                    <div class="login-header">
                        <div class="icon">📚</div>
                        <h2>AI Notes Generator</h2>
                        <p>Login or Sign up to access study materials</p>
                    </div>
            """)
            
            # Login Form
            login_email = gr.Textbox(label="Email Address", placeholder="student@example.com", type="email")
            login_password = gr.Textbox(label="Password", placeholder="Enter your password", type="password")
            login_btn = gr.Button("Login", variant="primary", elem_classes="login-btn")
            login_status = gr.HTML('')
            show_signup_btn = gr.Button("🆕 New user? Create an account", elem_classes="toggle-btn")
            
            # Signup Form
            signup_email = gr.Textbox(label="Email Address", placeholder="student@example.com", type="email", visible=False)
            signup_password = gr.Textbox(label="Password (min 6 characters)", placeholder="Choose a password", type="password", visible=False)
            signup_confirm = gr.Textbox(label="Confirm Password", placeholder="Confirm your password", type="password", visible=False)
            signup_btn = gr.Button("Sign Up", variant="primary", elem_classes="signup-btn", visible=False)
            signup_status = gr.HTML('', visible=False)
            show_login_btn = gr.Button("🔐 Already have an account? Login here", elem_classes="toggle-btn", visible=False)
            
            gr.HTML("</div></div>")
        
        # Main Dashboard
        with gr.Column(visible=False) as dashboard_container:
            gr.HTML("""
            <div class="main-container">
                <div class="app-header">
                    <h1>📚 AI Notes Generator</h1>
                    <p>Upload PDF - Get Topic-wise Summary, Q&A Bank, and Ask Questions</p>
                </div>
            """)
            
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📄 Upload PDF Document")
                    pdf_input = gr.File(label="Choose PDF File", file_types=[".pdf"], type="filepath")
                    upload_btn = gr.Button("📤 Upload & Analyze PDF", variant="primary", size="lg")
                    upload_status = gr.HTML('')
                
                with gr.Column(scale=2):
                    file_info_display = gr.HTML(elem_classes="file-info", visible=False)
            
            gr.Markdown("---")
            
            with gr.Tabs():
                with gr.TabItem("📝 Topic-wise Summary"):
                    summary_btn = gr.Button("🔍 Generate Summary", variant="primary", size="lg")
                    summary_output = gr.HTML(elem_classes="output-container")
                
                with gr.TabItem("📋 Question & Answer Bank"):
                    qa_btn = gr.Button("🎯 Generate Q&A Bank", variant="primary", size="lg")
                    qa_output = gr.HTML(elem_classes="output-container")
                
                with gr.TabItem("💬 Ask Questions"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            question_input = gr.Textbox(
                                label="Your Question",
                                lines=3,
                                placeholder="Example: What is the answer to question 5?"
                            )
                            ask_btn = gr.Button("🤔 Ask Question", variant="primary", size="lg")
                        with gr.Column(scale=2):
                            answer_output = gr.HTML(elem_classes="output-container")
                
                with gr.TabItem("📜 History"):
                    refresh_btn = gr.Button("🔄 Refresh", variant="secondary")
                    history_output = gr.HTML(elem_classes="output-container")
                
                with gr.TabItem("⚙️ Settings"):
                    gr.Markdown("### Settings")
                    gr.Markdown(f"**Current User:** {current_user['email'] if current_user['logged_in'] else 'Not logged in'}")
                    gr.Markdown("---")
                    delete_history_btn = gr.Button("🗑️ Delete My History", variant="secondary")
                    delete_status = gr.HTML('')
                    gr.Markdown("---")
                    logout_btn = gr.Button("🚪 Logout", variant="stop")
            
            gr.HTML("</div>")
        
        # Toggle functions
        def show_signup():
            return [
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=True), gr.update(visible=True), gr.update(visible=True), gr.update(visible=True),
                gr.update(visible=True), gr.update(visible=True)
            ]
        
        def show_login():
            return [
                gr.update(visible=True), gr.update(visible=True), gr.update(visible=True), gr.update(visible=True),
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=False)
            ]
        
        # Login/Signup handlers
        def do_login(email, pwd):
            if not email or not pwd:
                return '<div class="message error">❌ Please enter email and password</div>', gr.update(visible=True), gr.update(visible=False)
            
            success, msg = login_user(email, pwd)
            
            if success:
                return f'<div class="message success">{msg}</div>', gr.update(visible=False), gr.update(visible=True)
            return f'<div class="message error">{msg}</div>', gr.update(visible=True), gr.update(visible=False)
        
        def do_signup(email, pwd, confirm):
            if not email or not pwd:
                return '<div class="message error">❌ Please enter email and password</div>'
            if pwd != confirm:
                return '<div class="message error">❌ Passwords do not match</div>'
            if len(pwd) < 6:
                return '<div class="message error">❌ Password must be at least 6 characters</div>'
            
            success, msg = register_user(email, pwd)
            if success:
                return f'<div class="message success">{msg} Please login.</div>'
            return f'<div class="message error">{msg}</div>'
        
        def logout():
            global current_user
            current_user["email"] = ""
            current_user["logged_in"] = False
            return gr.update(visible=True), gr.update(visible=False)
        
        def delete_history():
            success, msg = delete_user_history()
            return f'<div class="message {"success" if success else "error"}">{msg}</div>'
        
        def show_history():
            history = get_user_history()
            if not history:
                return "<div class='history-item'>No history yet.</div>"
            
            html = "<div style='max-height: 500px; overflow-y: auto;'>"
            for item in reversed(history[-15:]):
                html += f"""
                <div class='history-item'>
                    <strong>📌 {item['type']}</strong><br>
                    <strong>Name:</strong> {item['name']}<br>
                    <strong>Time:</strong> {item['timestamp']}<br>
                    <strong>Preview:</strong> {item['preview']}<br>
                </div>
                """
            html += "</div>"
            return html
        
        def upload_pdf(file):
            if not file:
                return '<div class="message error">❌ Please select a PDF file</div>', gr.update(visible=False), ""
            
            success, status, word_count, pages, extract_type, is_exam = generator.extract_and_store_file(file)
            
            if success:
                exam_note = ""
                if is_exam:
                    exam_note = '<br>📝 <strong>Exam Paper Detected!</strong> Solutions will be provided.'
                
                info_html = f"""
<div class="file-info">
<strong>✅ PDF Uploaded Successfully!</strong><br><br>
📄 <strong>File:</strong> {file_context['filename']}<br>
📊 <strong>Words:</strong> {word_count:,}<br>
📑 <strong>Pages:</strong> {pages}<br>
✅ <strong>Status:</strong> Ready for analysis{exam_note}
</div>
"""
                return f'<div class="message success">✅ {status}</div>', gr.update(visible=True), info_html
            else:
                return f'<div class="message error">❌ {status}</div>', gr.update(visible=False), ""
        
        def generate_summary():
            return generator.generate_topic_wise_summary()
        
        def generate_qa():
            return generator.generate_qa_bank()
        
        def ask_question(question):
            return generator.ask_question(question)
        
        # Connect handlers
        login_btn.click(do_login, [login_email, login_password], [login_status, auth_container, dashboard_container])
        signup_btn.click(do_signup, [signup_email, signup_password, signup_confirm], [signup_status])
        logout_btn.click(logout, [], [auth_container, dashboard_container])
        delete_history_btn.click(delete_history, [], [delete_status])
        refresh_btn.click(show_history, [], [history_output])
        
        upload_btn.click(upload_pdf, [pdf_input], [upload_status, file_info_display, file_info_display])
        summary_btn.click(generate_summary, [], [summary_output])
        qa_btn.click(generate_qa, [], [qa_output])
        ask_btn.click(ask_question, [question_input], [answer_output])
        
        # Toggle between Login and Signup
        show_signup_btn.click(show_signup, [], [login_email, login_password, login_btn, show_signup_btn, signup_email, signup_password, signup_confirm, signup_btn, signup_status, show_login_btn])
        show_login_btn.click(show_login, [], [login_email, login_password, login_btn, show_signup_btn, signup_email, signup_password, signup_confirm, signup_btn, signup_status, show_login_btn])
    
    return demo


def main():
    port = find_free_port(7860, 8000)
    
    print("="*60)
    print("     AI Notes Generator - Professional Edition")
    print("="*60)
    print("\n✅ Features:")
    print("  • Sign up / Login system")
    print("  • Exam Paper Detection (PGCET, CET, etc.)")
    print("  • Automatic Solutions for Exam Papers")
    print("  • Topic-wise Summary with proper spacing")
    print("  • Question & Answer Bank")
    print("  • Interactive Q&A with formatted answers")
    
    if OCR_AVAILABLE:
        print("\n✅ OCR ENABLED - Scanned PDFs supported!")
    
    init_users_db()
    with open(USERS_DB, 'r') as f:
        users = json.load(f)
    
    if not users:
        default_user = {
            "admin@example.com": {
                "password": hash_password("admin123"),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "history": []
            }
        }
        with open(USERS_DB, 'w') as f:
            json.dump(default_user, f, indent=2)
        print("\n📝 Default admin user:")
        print("   Email: admin@example.com")
        print("   Password: admin123")
    
    api_key = os.getenv('GROQ_API_KEY')
    if api_key and api_key != "your-api-key-here":
        print("\n✅ API key detected! Full AI features enabled.")
    else:
        print("\n⚠️ No API key found. Add to .env file.")
    
    print(f"\n🚀 Starting on port {port}...")
    print(f"📍 http://127.0.0.1:{port}\n")
    
    demo = create_interface()
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        share=False,
        inbrowser=True,
        css=PROFESSIONAL_CSS
    )


if __name__ == "__main__":
    main()
