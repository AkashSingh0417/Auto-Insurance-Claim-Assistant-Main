# Auto Insurance Claim Assistant

An intelligent web application that helps users file auto insurance claims by processing documents, analyzing videos for license plate detection, and providing AI-powered assistance throughout the claim process.

## 🚀 Features

- **AI-Powered Chat Interface**: Interactive conversation with an AI assistant to guide users through the claim process
- **Document Processing**: Extract text from PDFs, images, and text files using OCR
- **License Plate Detection**: Advanced video analysis to detect and match license plates in uploaded videos
- **Sensitive Data Protection**: Automatic masking of sensitive information (credit cards, SSN, bank accounts)
- **Email Integration**: Send claim summaries with file attachments via email
- **Multi-Format Support**: Handles various file formats including videos (MP4, AVI, MOV, etc.)
- **Real-time Processing**: Fast response times with efficient backend processing

## 🏗️ Architecture

The project consists of two main components:

### Frontend (Flask)
- **File**: `app.py`
- **Purpose**: Web interface, file uploads, email functionality, sensitive data masking
- **Features**: User-friendly chat interface, file management, email sending

### Backend (FastAPI)
- **File**: `main.py`
- **Purpose**: AI processing, document analysis, license plate detection
- **Features**: LLM integration, video processing, text extraction

### Supporting Modules
- **`plate_detection.py`**: License plate detection using OpenCV and EasyOCR
- **`utils.py`**: Utility functions for text processing and LLM communication
- **`email_settings.py`**: Email configuration for sending claim summaries

## 📋 Prerequisites

Before setting up the project, ensure you have:

- **Python 3.8+** installed
- **OpenALPR** (for advanced license plate detection)
- **Git** (for cloning the repository)

### OpenALPR Installation

#### Windows:
1. Download from [OpenALPR releases](https://github.com/openalpr/openalpr/releases)
2. Install the Windows binary
3. Add to system PATH

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install openalpr openalpr-daemon openalpr-utils libopenalpr-dev
```

#### macOS:
```bash
brew install openalpr
```

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd dsw
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Email Settings
Edit `email_settings.py` and update with your email credentials:

```python
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "your-app-password"
}
```

**For Gmail Setup:**
1. Enable 2-factor authentication
2. Generate an app password at [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Use the 16-character app password

### 4. Configure API Keys
Update the following in `utils.py`:
- **Together AI API Key**: Replace the placeholder with your actual API key
- **OCR.space API Key** (optional): For enhanced OCR capabilities

## 🚀 Running the Application

### 1. Start the Backend Server
```bash
# Terminal 1
uvicorn main:app --reload
```
The FastAPI backend will start on `http://localhost:8000`

### 2. Start the Frontend Server
```bash
# Terminal 2
python app.py
```
The Flask frontend will start on `http://localhost:5000`

### 3. Access the Application
Open your browser and navigate to `http://localhost:5000`

## 🌐 Deployment on Render

The Auto Insurance Claim Assistant is deployed and available online through Render, a cloud platform that provides easy deployment and hosting services.

### Live Application
**🌍 Access the deployed application:** [Auto Insurance Claim Assistant](https://auto-insurance-claim-assistant.onrender.com)

### Deployment Features
- **24/7 Availability**: The application runs continuously on Render's cloud infrastructure
- **Automatic Scaling**: Render automatically handles traffic spikes and scaling
- **SSL Certificate**: Secure HTTPS connection for all communications
- **Global CDN**: Fast loading times from anywhere in the world
- **Automatic Deployments**: Updates are automatically deployed when code is pushed to the repository

### Render Configuration
The application uses the following Render configuration files:

#### `render.yaml`
```yaml
services:
  - type: web
    name: auto-insurance-claim-assistant
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.9.16
```

#### `runtime.txt`
```
python-3.9.16
```

### Environment Variables
The following environment variables are configured in Render:
- **Together AI API Key**: For AI model integration
- **Email Configuration**: SMTP settings for email functionality
- **Security Keys**: For secure data handling

### Deployment Benefits
1. **No Local Setup Required**: Users can access the application directly without installing anything
2. **Cross-Platform Compatibility**: Works on any device with a web browser
3. **Professional Hosting**: Enterprise-grade infrastructure with 99.9% uptime
4. **Cost-Effective**: Free tier available for development and testing
5. **Easy Maintenance**: Automatic updates and monitoring

### Accessing the Deployed Version
1. Visit [https://auto-insurance-claim-assistant-hosted-1.onrender.com/](https://auto-insurance-claim-assistant-hosted-1.onrender.com/)
2. **Important**: If the application appears to be loading slowly or shows an error, please wait 5-10 minutes for the server to restart. This is normal behavior for free-tier deployments on Render.
3. Start using the application immediately once it loads
4. All features are available including:
   - AI-powered chat interface
   - Document upload and processing
   - License plate detection
   - Email functionality
   - Sensitive data protection

### Local vs Deployed
| Feature | Local Development | Deployed Version |
|---------|------------------|------------------|
| Setup Time | 10-15 minutes | Instant |
| Updates | Manual | Automatic |
| Accessibility | Local network only | Global access |
| Maintenance | Manual | Automated |
| Cost | Free | Free tier available |

## 📖 Usage Guide

### 1. Starting a New Claim
1. Open the application in your browser
2. Begin by describing your incident in the chat interface
3. The AI assistant will guide you through the process

### 2. Uploading Documents
- **Supported Formats**: PDF, TXT, Images (JPG, PNG), Videos (MP4, AVI, MOV, MKV, WMV, FLV)
- **File Size Limit**: 50MB per file for email attachments
- **Multiple Files**: Upload multiple files during your conversation

### 3. License Plate Detection
- Upload video files containing license plates
- Provide the plate number you're looking for
- The system will analyze the video and attempt to match the plate

### 4. Getting a Summary
- Click "Summarize & Decide" when you've provided all information
- The AI will generate a comprehensive claim summary
- Download the summary or send it via email

### 5. Email Functionality
- Enter your email address
- The system will send a summary with all uploaded files as attachments
- Files are automatically cleaned up after successful email delivery

## 🔧 Configuration Options

### Email Providers
The system supports multiple email providers:

#### Gmail (Recommended)
```python
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "your-app-password"
}
```

#### Outlook/Hotmail
```python
EMAIL_CONFIG = {
    "smtp_server": "smtp-mail.outlook.com",
    "smtp_port": 587,
    "sender_email": "your-email@outlook.com",
    "sender_password": "your-regular-password"
}
```

#### Yahoo
```python
EMAIL_CONFIG = {
    "smtp_server": "smtp.mail.yahoo.com",
    "smtp_port": 587,
    "sender_email": "your-email@yahoo.com",
    "sender_password": "your-app-password"
}
```

### AI Model Configuration
The system uses Together AI's Mixtral-8x7B-Instruct model. You can modify the model settings in `utils.py`:

```python
response = together.Complete.create(
    prompt=prompt,
    model="mistralai/Mixtral-8x7B-Instruct-v0.1",  # Change model here
    max_tokens=512,  # Adjust response length
    temperature=0.7,  # Adjust creativity
    top_p=0.7,
)
```

## 🔒 Security Features

### Sensitive Data Protection
The system automatically masks sensitive information:
- Credit card numbers
- Social Security Numbers
- Bank account numbers
- IP addresses
- Driver's license numbers
- Passport numbers

### File Security
- Files are stored temporarily in system temp directory
- Automatic cleanup after email delivery
- File size limits prevent abuse
- Secure filename handling

## 🐛 Troubleshooting

### Common Issues

#### 1. OpenALPR Not Found
**Error**: `OpenALPR not found or not properly configured`
**Solution**: Install OpenALPR following the installation guide above

#### 2. Email Sending Fails
**Error**: `SMTP authentication failed`
**Solution**: 
- Check your email credentials in `email_settings.py`
- Ensure 2-factor authentication is enabled for Gmail
- Use app passwords instead of regular passwords

#### 3. Video Processing Errors
**Error**: `Video processing failed`
**Solution**:
- Ensure video format is supported (MP4, AVI, MOV, MKV, WMV, FLV)
- Check video file is not corrupted
- Verify OpenALPR is properly installed

#### 4. API Key Issues
**Error**: `LLM API Error`
**Solution**:
- Verify your Together AI API key is correct
- Check your API quota and billing status
- Ensure internet connectivity

### Debug Mode
Enable debug logging by setting the logging level in `plate_detection.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 📁 Project Structure

```
dsw/
├── app.py                 # Flask frontend application
├── main.py               # FastAPI backend application
├── plate_detection.py    # License plate detection logic
├── utils.py              # Utility functions and LLM integration
├── email_settings.py     # Email configuration
├── requirements.txt      # Python dependencies
├── test_video.mp4        # Sample video for testing
└── README.md            # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


### Planned Features
- Multi-language support
- Advanced document analysis
- Integration with insurance company APIs
- Mobile app version
- Real-time chat support

