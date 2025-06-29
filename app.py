from flask import Flask, render_template_string, request, send_file, flash, redirect, url_for
import requests
import json
import io
import os
import datetime
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from werkzeug.utils import secure_filename
import tempfile
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')  # Use environment variable
backend_url = os.environ.get('BACKEND_URL', 'http://localhost:8000')  # Use environment variable

def mask_sensitive_information(text):
    """
    Mask sensitive information in text with asterisks.
    Handles bank account information, credit card numbers, SSN, and other sensitive data.
    Phone numbers and email addresses are kept visible as requested.
    """
    if not text:
        return text
    
    # Bank account information with bank names and IFSC codes
    # Pattern: Bank Name - Account Number, IFSC: IFSC Code
    text = re.sub(
        r'\b([A-Z]{2,10})\s*-\s*(\d{8,17})\s*,\s*IFSC:\s*([A-Z]{4}0[A-Z0-9]{6})\b',
        lambda m: f"{m.group(1)} - {'*' * len(m.group(2))}, IFSC: {m.group(3)}",
        text,
        flags=re.IGNORECASE
    )
    
    # Bank account information with bank names (without IFSC)
    text = re.sub(
        r'\b([A-Z]{2,10})\s*-\s*(\d{8,17})\b',
        lambda m: f"{m.group(1)} - {'*' * len(m.group(2))}",
        text,
        flags=re.IGNORECASE
    )
    
    # IFSC codes (keep first 4 and last 2 characters, mask the rest)
    text = re.sub(
        r'\bIFSC:\s*([A-Z]{4}0[A-Z0-9]{6})\b',
        lambda m: f"IFSC: {m.group(1)[:4]}{'*' * (len(m.group(1)) - 6)}{m.group(1)[-2:]}",
        text,
        flags=re.IGNORECASE
    )
    
    # Credit card numbers with "Credit Card Number:" prefix
    text = re.sub(
        r'\bCredit\s+Card\s+Number:\s*(\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4})\b',
        lambda m: f"Credit Card Number: {m.group(1)[:4]}{'*' * (len(m.group(1)) - 8)}{m.group(1)[-4:]}",
        text,
        flags=re.IGNORECASE
    )
    
    # Credit card numbers (various formats) - improved pattern
    text = re.sub(
        r'\b(\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4})\b',
        lambda m: m.group(1)[:4] + '*' * (len(m.group(1)) - 8) + m.group(1)[-4:],
        text
    )
    
    # Social Security Numbers
    text = re.sub(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b', '***-**-****', text)
    
    # IP addresses
    text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '***.***.***.***', text)
    
    # Driver's license numbers (various formats)
    text = re.sub(r'\b[A-Z]{1,2}\d{6,8}\b', '**' + '*' * 6, text)
    
    # Passport numbers
    text = re.sub(r'\b[A-Z]{1,2}\d{6,9}\b', '**' + '*' * 6, text)
    
    # Bank account numbers (standalone, but exclude phone numbers)
    # Only mask numbers that are 12+ digits (typical bank account length)
    # and not in phone number format (XXX-XXX-XXXX or similar)
    text = re.sub(
        r'\b(\d{12,17})\b', 
        lambda m: '*' * len(m.group()) 
        if not re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', m.group()) else m.group(), 
        text
    )
    
    return text

def send_email(to_email, subject, body, attachment_content=None, attachment_name=None):
    """Send email with summary attachment only (no file attachments)"""
    
    try:
        # Import email settings
        try:
            from email_settings import EMAIL_CONFIG
            smtp_server = EMAIL_CONFIG["smtp_server"]
            smtp_port = EMAIL_CONFIG["smtp_port"]
            sender_email = EMAIL_CONFIG["sender_email"]
            sender_password = EMAIL_CONFIG["sender_password"]
        except ImportError:
            # Fallback to default settings if email_settings.py doesn't exist
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            sender_email = "your-email@gmail.com"
            sender_password = "your-app-password"
        
        # Check if settings are still default
        if sender_email == "your-email@gmail.com" or sender_password == "your-app-password":
            return False, "Please configure your email settings in email_settings.py"
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(body, 'plain'))
        
        # Add summary attachment if provided
        if attachment_content and attachment_name:
            attachment = MIMEText(attachment_content)
            attachment.add_header('Content-Disposition', 'attachment', filename=attachment_name)
            msg.attach(attachment)
        
        # Create SMTP session
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        
        # Login
        server.login(sender_email, sender_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        
        print(f"📧 EMAIL SENT:")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"From: {sender_email}")
        
        return True, "Email sent successfully!"
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False, f"Error sending email: {str(e)}"

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auto Insurance Claim Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .main-content {
            display: flex;
            min-height: 600px;
        }
        
        .input-section {
            flex: 1;
            padding: 30px;
            background: #f8f9fa;
            border-right: 1px solid #e9ecef;
        }
        
        .chat-section {
            flex: 2;
            padding: 30px;
            display: flex;
            flex-direction: column;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .form-group input, .form-group textarea, .form-group select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .file-upload {
            position: relative;
            display: inline-block;
            width: 100%;
        }
        
        .file-upload input[type=file] {
            position: absolute;
            opacity: 0;
            width: 100%;
            height: 100%;
            cursor: pointer;
        }
        
        .file-upload-label {
            display: block;
            padding: 15px;
            background: #e9ecef;
            border: 2px dashed #adb5bd;
            border-radius: 8px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .file-upload-label:hover {
            background: #dee2e6;
            border-color: #667eea;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            text-align: center;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(40, 167, 69, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #5a6268;
        }
        
        .chat-container {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 20px;
            padding: 20px;
            background: white;
            border-radius: 10px;
            border: 1px solid #e9ecef;
        }
        
        .chat-message {
            margin-bottom: 15px;
            padding: 15px;
            border-radius: 10px;
            max-width: 80%;
        }
        
        .user-message {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin-left: auto;
            text-align: right;
        }
        
        .assistant-message {
            background: #f8f9fa;
            color: #2c3e50;
            border: 1px solid #e9ecef;
        }
        
        .summary-report {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .summary-report h3 {
            color: #2c3e50;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .summary-report pre {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            white-space: pre-wrap;
            font-family: inherit;
            line-height: 1.6;
        }
        
        .flash-message {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: 600;
        }
        
        .flash-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .flash-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .flash-warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
            color: #6c757d;
        }
        
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .file-info {
            background: #e9ecef;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
        }
        
        .file-info h4 {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        
        .file-info p {
            color: #6c757d;
            margin-bottom: 10px;
        }
        
        .file-info ul {
            list-style: none;
            padding: 0;
        }
        
        .file-info li {
            background: white;
            padding: 10px;
            margin-bottom: 5px;
            border-radius: 5px;
            border: 1px solid #dee2e6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .btn-remove {
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 5px 10px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .btn-remove:hover {
            background: #c82333;
        }
        
        .email-btn {
            background: #28a745;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            margin-left: 10px;
        }
        
        .email-btn:hover {
            background: #218838;
        }
        
        .email-form {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            margin-top: 15px;
        }
        
        .email-form input[type="email"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        
        .btn-cancel {
            background: #6c757d;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
            margin-left: 10px;
        }
        
        .btn-cancel:hover {
            background: #5a6268;
        }
        
        @media (max-width: 768px) {
            .main-content {
                flex-direction: column;
            }
            
            .input-section {
                border-right: none;
                border-bottom: 1px solid #e9ecef;
            }
            
            .header h1 {
                font-size: 2em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚗 Auto Insurance Claim Assistant</h1>
            <p>Upload documents, videos, and chat with AI to process your insurance claim</p>
        </div>
        
        <div class="main-content">
            <div class="input-section">
                <form method="POST" enctype="multipart/form-data" id="chatForm">
                    <input type="hidden" name="user_id" value="{{ user_id }}">
                    <input type="hidden" name="conversation_history" value="{{ conversation_history }}">
                    
                    <div class="form-group">
                        <label for="message">💬 Your Message:</label>
                        <textarea name="message" id="message" rows="4" placeholder="Describe your insurance claim, ask questions, or provide additional context...">{{ message }}</textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="file">📎 Upload File:</label>
                        <div class="file-upload">
                            <input type="file" name="file" id="file" accept=".pdf,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.mp4,.avi,.mov,.mkv,.wmv,.flv">
                            <label for="file" class="file-upload-label">
                                📁 Click to select a file (PDF, Image, or Video)
                            </label>
                        </div>
                        <small style="color: #6c757d; margin-top: 5px; display: block;">
                            Supported: PDF documents, images (JPG, PNG, GIF, BMP, TIFF), videos (MP4, AVI, MOV, MKV, WMV, FLV)
                        </small>
                    </div>
                    
                    <div class="form-group">
                        <label for="plate_number">🚗 License Plate Number (for video processing):</label>
                        <input type="text" name="plate_number" id="plate_number" placeholder="Enter license plate number (optional)" value="{{ plate_number }}">
                        <small style="color: #6c757d; margin-top: 5px; display: block;">
                            Required for video license plate detection and matching
                        </small>
                    </div>
                    
                    <button type="submit" class="btn btn-primary" style="width: 100%; margin-bottom: 10px;">
                        🚀 Send Message & Process File
                    </button>
                    
                    <button type="submit" name="summarize" value="1" class="btn btn-success" style="width: 100%;">
                        📋 Summarize & Generate Report
                    </button>
                </form>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>Processing your request...</p>
                </div>
            </div>
            
            <div class="chat-section">
                <div class="chat-container">
                    {% for role, content in chat_history %}
                        {% if role == 'user' %}
                            <div class="chat-message user-message">{{ content }}</div>
                        {% else %}
                            <div class="chat-message assistant-message">{{ content }}</div>
                        {% endif %}
                    {% endfor %}
                </div>
                {% if summary %}
                <div class="summary-report">
                    <h3>
                        📋 Summary Report
                        <button type="button" class="email-btn" onclick="toggleEmailForm()">📧 Send Email</button>
                    </h3>
                    <pre>{{ summary }}</pre>
                    
                    <!-- Email Form (hidden by default) -->
                    <div id="emailForm" class="email-form" style="display: none;">
                        <h4 style="margin-bottom: 15px; color: #333;">Send Summary Report via Email</h4>
                        <form method="POST" action="/send_email">
                            <input type="hidden" name="summary" value='{{ summary|tojson|safe }}'>
                            <input type="hidden" name="user_id" value="{{ user_id }}">
                            <input type="email" name="email" placeholder="Enter recipient email address" required>
                            <button type="submit" class="btn btn-success">Send Email</button>
                            <button type="button" class="btn btn-cancel" onclick="toggleEmailForm()">Cancel</button>
                        </form>
                    </div>
                    
                    <form method="POST" action="/download_summary">
                        <input type="hidden" name="summary" value='{{ summary|tojson|safe }}'>
                        <button type="submit" class="btn btn-primary">Download Report</button>
                    </form>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <!-- Flash Messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="flash-message flash-{{ category }}" style="position: fixed; top: 20px; right: 20px; z-index: 1000; max-width: 300px;">
                    {{ message }}
                </div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <script>
        function toggleEmailForm() {
            const emailForm = document.getElementById('emailForm');
            if (emailForm.style.display === 'none') {
                emailForm.style.display = 'block';
            } else {
                emailForm.style.display = 'none';
            }
        }
        
        // Show loading spinner when form is submitted
        document.getElementById('chatForm').addEventListener('submit', function() {
            document.getElementById('loading').style.display = 'block';
        });
        
        // Auto-hide flash messages after 5 seconds
        setTimeout(function() {
            const flashMessages = document.querySelectorAll('.flash-message');
            flashMessages.forEach(function(message) {
                message.style.display = 'none';
            });
        }, 5000);
        
        // Update file upload label with selected filename
        document.getElementById('file').addEventListener('change', function() {
            const label = document.querySelector('.file-upload-label');
            if (this.files.length > 0) {
                label.textContent = '📁 ' + this.files[0].name;
            } else {
                label.textContent = '📁 Click to select a file (PDF, Image, or Video)';
            }
        });
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    # Main route handling chat interface and file uploads
    user_id = request.form.get('user_id', 'user1')
    message = request.form.get('message', '')
    plate_number = request.form.get('plate_number', '')
    conversation_history = request.form.get('conversation_history', '[]')
    summary = request.form.get('summary', '')
    
    # Parse conversation history from frontend
    if conversation_history:
        try:
            conversation = json.loads(conversation_history)
            if not isinstance(conversation, list):
                conversation = []
        except Exception:
            conversation = []
    else:
        conversation = []
    
    # Handle file upload and message processing
    if request.method == 'POST' and 'summarize' not in request.form and 'download_summary' not in request.form:
        files = None
        file = request.files.get('file')
        print(f"🔍 DEBUG: File upload detected: {file.filename if file else 'None'}")
        
        if file and file.filename:
            files = {'file': (file.filename, file.stream, file.mimetype)}
            print(f"✅ File prepared for processing: {file.filename}")
        
        # Mask sensitive info before sending to backend
        masked_message = mask_sensitive_information(message)
        
        data = {
            'user_id': user_id,
            'message': masked_message,  # Send masked message to backend
            'api_key': '',
            'conversation_history': json.dumps(conversation)
        }
        # Add plate number if provided for video processing
        if plate_number:
            data['plate_number'] = plate_number
        try:
            resp = requests.post(f'{backend_url}/interact', data=data, files=files)
            if resp.ok:
                history = resp.json()['history']
                # Mask sensitive info in conversation history
                masked_history = []
                for role, content in history:
                    if role == 'user':
                        # Mask user messages only
                        masked_content = mask_sensitive_information(content)
                        masked_history.append((role, masked_content))
                    else:
                        # Keep assistant messages as is
                        masked_history.append((role, content))
                conversation = masked_history
            else:
                conversation.append(('assistant', 'Error communicating with backend.'))
        except Exception as e:
            conversation.append(('assistant', f'Error: {e}'))
        conversation_history = json.dumps(conversation)
    
    # Handle summary generation request
    elif request.method == 'POST' and 'summarize' in request.form:
        # Generate summary only when Summarize & Decide is clicked
        try:
            summary_resp = requests.post(f'{backend_url}/generate_summary', json={'conversation_history': conversation_history})
            if summary_resp.ok:
                summary = summary_resp.json().get('summary', '')
                # Mask sensitive information in the summary
                summary = mask_sensitive_information(summary)
        except Exception:
            summary = ''
    
    return render_template_string(HTML_TEMPLATE, chat_history=conversation, user_id=user_id, conversation_history=conversation_history, summary=summary, plate_number=plate_number)

@app.route('/download_summary', methods=['POST'])
def download_summary():
    # Download summary as text file with sensitive data masked
    summary = request.form.get('summary', '')
    if summary:
        summary_text = json.loads(summary) if summary.startswith('"') else summary
        # Mask sensitive information in the summary before downloading
        masked_summary = mask_sensitive_information(summary_text)
        return send_file(
            io.BytesIO(masked_summary.encode('utf-8')),
            mimetype='text/plain',
            as_attachment=True,
            download_name='insurance_claim_summary.txt'
        )
    return "No summary to download.", 400

@app.route('/send_email', methods=['POST'])
def send_email_route():
    """Handle email sending request with masked sensitive data"""
    try:
        email = request.form.get('email')
        summary = request.form.get('summary', '')
        user_id = request.form.get('user_id', 'user1')
        
        if not email:
            flash('Please provide a valid email address.', 'error')
            return redirect('/')
        
        if not summary:
            flash('No summary content to send.', 'error')
            return redirect('/')
        
        # Parse summary content
        summary_text = json.loads(summary) if summary.startswith('"') else summary
        
        # Mask sensitive information
        masked_summary = mask_sensitive_information(summary_text)
        
        # Create email body
        email_body = f"""Dear User,

Please find attached the summary report for your auto insurance claim.

Best regards,
Auto Insurance Claim Assistant

---
This is an automated message from the Auto Insurance Claim Assistant system.
"""
        
        # Send email with summary attachment only
        success, message = send_email(
            to_email=email,
            subject="Auto Insurance Claim Summary Report",
            body=email_body,
            attachment_content=masked_summary,
            attachment_name='insurance_claim_summary.txt'
        )
        
        if success:
            flash('Email sent successfully!', 'success')
        else:
            flash(message, 'error')
            
    except Exception as e:
        flash(f'Error sending email: {str(e)}', 'error')
    
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 