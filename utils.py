import requests
import re
import together
import io
import PyPDF2
import tempfile
import os
from plate_detection import PlateDetector
import json
from datetime import datetime
import base64

# OCR Space API key - replace with your real key if available
OCR_SPACE_API_KEY = 'AIzaSyDI3X7UpI9X9vFIZiw4OMHcP7B3E01qTZk'  # Replace with your real key if available
OCR_SPACE_API_URL = 'https://api.ocr.space/parse/image'

# Together AI API key - use environment variable in production
together.api_key = os.environ.get('TOGETHER_API_KEY', "d8096e400779ee4adf4fb0e7f3bf97ddc4192a797f09ac54c45cd9856cca04d4")

async def extract_text_from_file(file):
    contents = await file.read()
    filename = file.filename.lower()
    if filename.endswith('.txt'):
        try:
            return contents.decode('utf-8', errors='ignore').strip()
        except Exception:
            return '[Error reading text file]'
    elif filename.endswith('.pdf'):
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text() or ''
            return text.strip() if text else '[No text found in PDF]'
        except Exception as e:
            return f'[Error reading PDF: {e}]'
    elif filename.endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')):
        # Handle video files for plate detection
        return await process_video_for_plates(file)
    else:
        # Use OCR for image files
        files = {'file': (file.filename, contents)}
        data = {
            'apikey': OCR_SPACE_API_KEY,
            'language': 'eng',
            'isOverlayRequired': False,
        }
        response = requests.post(OCR_SPACE_API_URL, files=files, data=data)
        if response.ok:
            result = response.json()
            if result.get('IsErroredOnProcessing'):
                return '[OCR Error: ' + result.get('ErrorMessage', ['Unknown error'])[0] + ']'
            parsed_results = result.get('ParsedResults')
            if parsed_results and len(parsed_results) > 0:
                return parsed_results[0].get('ParsedText', '').strip()
            return '[No text found in file]'
        else:
            return '[OCR API request failed]'

async def process_video_for_plates(file):
    """
    Process video file for license plate detection
    
    Args:
        file: Uploaded video file
        
    Returns:
        Text description of detected plates and matching results
    """
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            tmp_file.flush()
            video_path = tmp_file.name
        
        # Initialize plate detector
        detector = PlateDetector()
        
        # Process video for plates
        result = detector.process_video_for_plates(video_path)
        
        # Clean up temporary file
        if os.path.exists(video_path):
            os.unlink(video_path)
        
        if not result['success']:
            return f"[Video Processing Error: {result.get('error', 'Unknown error')}]"
        
        # Format the result as text
        detected_plates = result.get('detected_plates', [])
        total_frames = result.get('total_frames_processed', 0)
        debug_info = result.get('debug_info', {})
        
        # Create detailed report with debugging info
        report = f"[Video Analysis Complete] Processed {total_frames} frames.\n\n"
        
        # Add debugging information
        frames_with_detections = debug_info.get('frames_with_detections', 0)
        total_detections = debug_info.get('total_detections', 0)
        detection_methods = debug_info.get('detection_methods', {})
        
        report += f"📊 Analysis Summary:\n"
        report += f"• Frames with detections: {frames_with_detections}/{total_frames}\n"
        report += f"• Total detections found: {total_detections}\n"
        if detection_methods:
            report += f"• Detection methods used: {', '.join([f'{k}({v})' for k, v in detection_methods.items()])}\n"
        report += "\n"
        
        if not detected_plates:
            report += f"❌ No license plates detected in the video.\n\n"
            report += f"💡 Troubleshooting Tips:\n"
            report += f"• Ensure the video has clear, well-lit license plates\n"
            report += f"• License plates should be clearly visible and not at extreme angles\n"
            report += f"• Try uploading a higher quality video\n"
            report += f"• Make sure the license plate is not blurry or obstructed\n"
            return report
        
        # Create detailed report
        report += f"✅ Detected {len(detected_plates)} unique license plate(s):\n"
        
        for i, plate in enumerate(detected_plates, 1):
            # Safely access plate data
            if isinstance(plate, dict):
                plate_text = plate.get('text', 'Unknown')
                confidence = plate.get('confidence', 0.0)
                frame_number = plate.get('frame_number', 0)
                method = plate.get('method', 'unknown')
                is_valid = plate.get('is_valid_format', False)
            else:
                # If plate is not a dict, treat it as a string
                plate_text = str(plate)
                confidence = 0.5
                frame_number = 0
                method = 'unknown'
                is_valid = False
            
            report += f"{i}. Plate: {plate_text} "
            report += f"(Confidence: {confidence:.2f}) "
            report += f"(Frame: {frame_number}) "
            report += f"(Method: {method}) "
            status = "✅ Valid Format" if is_valid else "⚠️ Invalid Format"
            report += f"({status})\n"
        
        return report
        
    except Exception as e:
        return f"[Video Processing Error: {str(e)}]"

async def process_video_with_plate_matching(file, user_plate_number):
    """
    Process video file and match detected plates with user-provided plate number
    
    Args:
        file: Uploaded video file
        user_plate_number: User-provided plate number to match against
        
    Returns:
        Text description of matching results
    """
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            tmp_file.flush()
            video_path = tmp_file.name
        
        # Initialize plate detector
        detector = PlateDetector()
        
        # Process video for plates with matching
        result = detector.process_video_for_plates(video_path, user_plate_number)
        
        # Clean up temporary file
        if os.path.exists(video_path):
            os.unlink(video_path)
        
        if not result['success']:
            return f"[Video Processing Error: {result.get('error', 'Unknown error')}]"
        
        # Format the matching result
        debug_info = result.get('debug_info', {})
        total_frames = result.get('total_frames_processed', 0)
        frames_with_detections = debug_info.get('frames_with_detections', 0)
        detected_plates = result.get('detected_plates', [])
        
        if result.get('match_found', False):
            if result.get('exact_match', False):
                report = f"✅ EXACT MATCH FOUND!\n"
                report += f"User Plate: {result['user_plate']}\n"
                detected_plate = result.get('detected_plate', {})
                if isinstance(detected_plate, dict):
                    detected_text = detected_plate.get('text', 'Unknown')
                else:
                    detected_text = str(detected_plate)
                report += f"Detected Plate: {detected_text}\n"
                report += f"Confidence: {result.get('confidence', 0):.2f}\n"
            else:
                report = f"✅ PARTIAL MATCH FOUND!\n"
                report += f"User Plate: {result['user_plate']}\n"
                detected_plate = result.get('detected_plate', {})
                if isinstance(detected_plate, dict):
                    detected_text = detected_plate.get('text', 'Unknown')
                else:
                    detected_text = str(detected_plate)
                report += f"Detected Plate: {detected_text}\n"
                report += f"Similarity: {result.get('confidence', 0):.2f}\n"
        else:
            report = f"❌ NO MATCH FOUND\n"
            report += f"User Plate: {result['user_plate']}\n"
            
            # Safely extract plate texts
            plate_texts = []
            for plate in detected_plates:
                if isinstance(plate, dict):
                    plate_texts.append(plate.get('text', 'Unknown'))
                else:
                    plate_texts.append(str(plate))
            
            if plate_texts:
                report += f"Detected Plates: {', '.join(plate_texts)}\n"
            else:
                report += f"Detected Plates: None\n"
        
        report += f"\n📊 Analysis Summary:\n"
        report += f"• Total frames processed: {total_frames}\n"
        report += f"• Frames with detections: {frames_with_detections}\n"
        report += f"• Unique plates found: {result.get('unique_plate_count', 0)}\n"
        
        if not detected_plates:
            report += f"\n💡 No plates detected. Possible reasons:\n"
            report += f"• Video quality is too low\n"
            report += f"• License plates are not clearly visible\n"
            report += f"• Lighting conditions are poor\n"
            report += f"• License plates are at extreme angles\n"
            report += f"• Video resolution is too low\n"
        
        return report
        
    except Exception as e:
        return f"[Video Processing Error: {str(e)}]"

async def process_video_with_multiple_plates(file, message):
    """
    Process video file and match detected plates with multiple vehicle numbers from a message
    
    Args:
        file: Uploaded video file
        message: Message containing vehicle numbers
        
    Returns:
        Text description of matching results for all vehicle numbers
    """
    try:
        # Extract vehicle numbers from message
        vehicle_info = extract_vehicle_numbers_from_message(message)
        
        if not vehicle_info['all_plates']:
            return f"[No vehicle numbers found in message: '{message}']"
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            tmp_file.flush()
            video_path = tmp_file.name
        
        # Initialize plate detector
        detector = PlateDetector()
        
        # Process video with multiple plates
        result = detector.process_video_with_multiple_plates(video_path, vehicle_info)
        
        # Clean up temporary file
        if os.path.exists(video_path):
            os.unlink(video_path)
        
        if not result['success']:
            return f"[Video Processing Error: {result.get('error', 'Unknown error')}]"
        
        # Format the multi-plate result
        report = f"🚗 MULTIPLE VEHICLE PLATE ANALYSIS\n"
        report += f"Message: {message}\n"
        report += f"Extracted vehicle numbers: {', '.join(vehicle_info['all_plates'])}\n\n"
        
        # Summary statistics
        summary = result['summary']
        report += f"📊 Analysis Summary:\n"
        report += f"• Total frames processed: {result.get('total_frames_processed', 'N/A')}\n"
        report += f"• Plates in message: {summary['total_plates_in_message']}\n"
        report += f"• Plates found in video: {summary['plates_found_in_video']}\n"
        report += f"• Exact matches: {summary['exact_matches']}\n"
        report += f"• Partial matches: {summary['partial_matches']}\n\n"
        
        # Individual plate results
        report += f"🔍 Individual Plate Results:\n"
        for plate, match_result in result['matches'].items():
            status = "✅" if match_result['match_found'] else "❌"
            vehicle_type = match_result.get('vehicle_type', 'unknown')
            
            if vehicle_type == 'user_vehicle':
                vehicle_desc = "User's Vehicle"
            elif vehicle_type == 'other_vehicle':
                vehicle_desc = "Other Vehicle Involved"
            else:
                vehicle_desc = "Unknown"
            
            report += f"{status} {plate} ({vehicle_desc})\n"
            report += f"   Result: {match_result['message']}\n"
            if match_result.get('context'):
                report += f"   Context: {match_result['context']}\n"
            report += "\n"
        
        # Show all detected plates in video
        if result.get('all_detected_plates'):
            report += f"📋 All Plates Detected in Video:\n"
            for i, plate in enumerate(result['all_detected_plates'], 1):
                if isinstance(plate, dict):
                    text = plate.get('text', 'Unknown')
                    conf = plate.get('confidence', 0.0)
                    frame_num = plate.get('frame_number', 'Unknown')
                else:
                    text = str(plate)
                    conf = 0.0
                    frame_num = 'Unknown'
                report += f"  {i}. '{text}' (conf: {conf:.2f}, frame: {frame_num})\n"
        
        # Provide recommendations
        if summary['plates_found_in_video'] == 0:
            report += f"\n💡 No plates from the message were found in the video.\n"
            report += f"Possible reasons:\n"
            report += f"• Video quality is too low\n"
            report += f"• License plates are not clearly visible\n"
            report += f"• Lighting conditions are poor\n"
            report += f"• License plates are at extreme angles\n"
        elif summary['exact_matches'] > 0:
            report += f"\n✅ Successfully found exact matches for {summary['exact_matches']} vehicle(s)!\n"
        elif summary['partial_matches'] > 0:
            report += f"\n⚠️ Found partial matches for {summary['partial_matches']} vehicle(s).\n"
            report += f"Please verify the detected plates manually.\n"
        
        return report
        
    except Exception as e:
        return f"[Video Processing Error: {str(e)}]"

def llm_respond(message, extracted_text, conversation, api_key=None):
    # Check if user is done providing information
    if message and user_is_done(message):
        return "Thank you for providing all the information. Let me know if you want a summary report of your claim."
    
    system_prompt = (
        "You are an auto insurance claim assistant. Let the user tell their story about the incident in detail. Your responses must be very short (1-2 sentences) and only ask for missing or unclear information. Do not summarize, give advice, or make decisions until the user asks for a summary. Do not interrupt the user or ask for documents unless they indicate they are ready. When the user is finished and requests a summary, generate a concise summary report of the whole incident, clearly stating whether the insurance claim should be approved or not, and why. The summary should be useful for both the insurance company and the user."
    )
    # Build the prompt from the conversation
    prompt = system_prompt + "\n"
    
    # Handle conversation format - it can be either list of tuples (role, content) or list of dicts
    for entry in conversation:
        if isinstance(entry, tuple) and len(entry) == 2:
            # New format: (role, content)
            role, content = entry
            if role == 'user':
                prompt += f"User: {content}\n"
            elif role == 'assistant':
                prompt += f"Assistant: {content}\n"
        elif isinstance(entry, dict):
            # Old format: dict with 'message', 'file_text', 'assistant' keys
            if entry.get('message'):
                prompt += f"User: {entry['message']}\n"
            if entry.get('file_text'):
                prompt += f"User: {entry['file_text']}\n"
            if entry.get('assistant'):
                prompt += f"Assistant: {entry['assistant']}\n"
    
    if message:
        prompt += f"User: {message}\n"
    if extracted_text:
        prompt += f"User: {extracted_text}\n"
    prompt += "Assistant:"

    try:
        response = together.Complete.create(
            prompt=prompt,
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            max_tokens=512,
            temperature=0.7,
            top_p=0.7,
        )
        print("[DEBUG] Raw LLM response:", response)  # Debug print
        # Correctly parse the response
        if isinstance(response, dict):
            if 'choices' in response and len(response['choices']) > 0:
                text = response['choices'][0].get('text', '').strip()
                if text:
                    # Only return the first 2 sentences for shortness
                    sentences = re.split(r'(?<=[.!?])\s+', text)
                    useful = [s for s in sentences
                              if not s.lower().startswith("only follow")]
                    short_text = " ".join(useful[:2]).strip()
                    return short_text if short_text else "Could you please clarify or provide more details about your claim?"
                else:
                    return "[LLM returned empty text]"
            elif 'error' in response:
                return f"[LLM API Error: {response['error']}]"
            else:
                return f"[LLM API Error: Unexpected response format: {response}]"
        else:
            return f"[LLM API Error: Non-dict response: {response}]"
    except Exception as e:
        return f"Sorry, I couldn't process your request. Exception: {e}"

def generate_summary(convo):
    summary_prompt = (
        "Given the following conversation between a user and an auto insurance claim assistant, "
        "write a concise summary of the incident, and clearly state whether the insurance claim should be approved or not, and why. "
        "Be professional and brief. Conversation:\n"
    )
    
    # Handle conversation format - it can be either list of tuples (role, content) or list of dicts
    for entry in convo:
        if isinstance(entry, tuple) and len(entry) == 2:
            # New format: (role, content)
            role, content = entry
            if role == 'user':
                summary_prompt += f"User: {content}\n"
            elif role == 'assistant':
                summary_prompt += f"Assistant: {content}\n"
        elif isinstance(entry, dict):
            # Old format: dict with 'message', 'file_text', 'assistant' keys
            if entry.get('message'):
                summary_prompt += f"User: {entry['message']}\n"
            if entry.get('file_text'):
                summary_prompt += f"User (file): {entry['file_text']}\n"
            if entry.get('assistant'):
                summary_prompt += f"Assistant: {entry['assistant']}\n"
        else:
            summary_prompt += f"{entry}\n"
    
    summary_prompt += "\nSummary and Decision:"

    # Use the same LLM as before
    try:
        response = together.Complete.create(
            prompt=summary_prompt,
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            max_tokens=512,
            temperature=0.7,
            top_p=0.7,
        )
        print("[DEBUG] Raw LLM summary response:", response)  # Debug print
        # Correctly parse the response
        if isinstance(response, dict):
            if 'choices' in response and len(response['choices']) > 0:
                text = response['choices'][0].get('text', '').strip()
                return text if text else '[LLM returned empty summary]'
            elif 'error' in response:
                return f"[LLM API Error: {response['error']}]"
            else:
                return f"[LLM API Error: Unexpected response format: {response}]"
        else:
            return f"[LLM API Error: Non-dict response: {response}]"
    except Exception as e:
        return f"[LLM API Exception: {e}]"

def get_chat_history(convo):
    # If conversation is already in the correct format (list of tuples), return it
    if convo and isinstance(convo[0], tuple) and len(convo[0]) == 2:
        return convo
    
    # Handle old format (list of dicts)
    history = []
    for entry in convo:
        if isinstance(entry, dict):
            if entry.get('message'):
                history.append(("user", entry['message']))
            if entry.get('assistant'):
                history.append(("assistant", entry['assistant']))
            if entry.get('file_text'):
                history.append(("user", entry['file_text']))
        elif isinstance(entry, tuple) and len(entry) == 2:
            # Already in correct format
            history.append(entry)
    return history

def user_is_done(message):
    # Check if user indicates they're finished providing information
    done_phrases = [
        "that's all", "no more", "i have only this", "i don't have more", "that's it",
        "please summarize", "generate summary", "nothing else", "no further", "done", "finished"
    ]
    msg = message.lower()
    return any(phrase in msg for phrase in done_phrases)

def extract_vehicle_numbers_from_message(message):
    """
    Extract vehicle numbers from a message that might contain multiple plates
    
    Args:
        message: String containing vehicle numbers
        
    Returns:
        Dictionary with 'user_vehicle' and 'other_vehicle' plates
    """
    # Clean the message and extract alphanumeric sequences
    # Common Indian plate patterns
    plate_patterns = [
        r'[A-Z]{2}[0-9]{1,2}[A-Z]{1,2}[0-9]{4}',  # KA01AB1234
        r'[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}',      # KA01AB1234
        r'[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}',  # KA01ABC1234
        r'[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}',    # KA01ABC1234
        r'[A-Z0-9]{6,12}',  # Any alphanumeric 6-12 chars
    ]
    
    # Find all potential plate numbers
    found_plates = []
    for pattern in plate_patterns:
        matches = re.findall(pattern, message.upper())
        found_plates.extend(matches)
    
    # Remove duplicates while preserving order
    unique_plates = []
    seen = set()
    for plate in found_plates:
        if plate not in seen:
            unique_plates.append(plate)
            seen.add(plate)
    
    result = {
        'user_vehicle': None,
        'other_vehicle': None,
        'all_plates': unique_plates
    }
    
    # Assign plates to user and other vehicle
    if len(unique_plates) >= 1:
        result['user_vehicle'] = unique_plates[0]
    if len(unique_plates) >= 2:
        result['other_vehicle'] = unique_plates[1]
    
    return result 