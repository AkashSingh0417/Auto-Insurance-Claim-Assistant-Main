from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import JSONResponse
from utils import extract_text_from_file, llm_respond, generate_summary, get_chat_history, process_video_with_plate_matching, process_video_with_multiple_plates, extract_vehicle_numbers_from_message
from typing import Optional
import json

app = FastAPI()

@app.post('/interact')
async def interact(
    user_id: str = Form(...),
    message: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    api_key: str = Form(...),
    conversation_history: Optional[str] = Form(None),
    plate_number: Optional[str] = Form(None)
):
    extracted_text = ''
    if file:
        # Check if this is a plate matching request
        if plate_number and file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')):
            # Check if plate_number contains multiple vehicle numbers (looks like a message)
            if ' ' in plate_number or len(plate_number) > 15:
                # Treat as message with multiple vehicle numbers
                extracted_text = await process_video_with_multiple_plates(file, plate_number)
            else:
                # Single plate number
                extracted_text = await process_video_with_plate_matching(file, plate_number)
        else:
            extracted_text = await extract_text_from_file(file)
    
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
    
    # Convert conversation from tuple format to dictionary format for processing
    conversation_dict = []
    for entry in conversation:
        if isinstance(entry, tuple) and len(entry) == 2:
            role, content = entry
            if role == 'user':
                conversation_dict.append({'message': content, 'file_text': '', 'assistant': ''})
            elif role == 'assistant':
                # Add assistant response to the last entry or create new entry
                if conversation_dict:
                    conversation_dict[-1]['assistant'] = content
                else:
                    conversation_dict.append({'message': '', 'file_text': '', 'assistant': content})
        elif isinstance(entry, dict):
            conversation_dict.append(entry)
    
    # Add current message and file
    entry = {'message': message, 'file_text': extracted_text, 'assistant': ''}
    conversation_dict.append(entry)
    
    # Generate LLM response
    response = llm_respond(message, extracted_text, conversation_dict, api_key)
    entry['assistant'] = response
    
    # Return full chat history in tuple format
    history = get_chat_history(conversation_dict)
    return JSONResponse({'history': history})

@app.post('/plate_matching')
async def plate_matching(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    plate_number: str = Form(...),
    api_key: str = Form(...)
):
    """
    Dedicated endpoint for license plate matching
    """
    try:
        # Validate video file format
        if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')):
            return JSONResponse({
                'success': False,
                'error': 'File must be a video format (mp4, avi, mov, mkv, wmv, flv)'
            })
        
        # Check if plate_number contains multiple vehicle numbers
        if ' ' in plate_number or len(plate_number) > 15:
            # Process as message with multiple vehicle numbers
            result = await process_video_with_multiple_plates(file, plate_number)
            vehicle_info = extract_vehicle_numbers_from_message(plate_number)
            
            return JSONResponse({
                'success': True,
                'result': result,
                'message': plate_number,
                'vehicle_info': vehicle_info,
                'filename': file.filename,
                'type': 'multiple_plates'
            })
        else:
            # Process as single plate number
            result = await process_video_with_plate_matching(file, plate_number)
            
            return JSONResponse({
                'success': True,
                'result': result,
                'user_plate': plate_number,
                'filename': file.filename,
                'type': 'single_plate'
            })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        })

@app.post('/multi_plate_matching')
async def multi_plate_matching(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    message: str = Form(...),
    api_key: str = Form(...)
):
    """
    Dedicated endpoint for multiple license plate matching from a message
    """
    try:
        # Validate video file format
        if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')):
            return JSONResponse({
                'success': False,
                'error': 'File must be a video format (mp4, avi, mov, mkv, wmv, flv)'
            })
        
        # Extract vehicle numbers from message
        vehicle_info = extract_vehicle_numbers_from_message(message)
        
        if not vehicle_info['all_plates']:
            return JSONResponse({
                'success': False,
                'error': f'No vehicle numbers found in message: "{message}"'
            })
        
        # Process video with multiple plates
        result = await process_video_with_multiple_plates(file, message)
        
        return JSONResponse({
            'success': True,
            'result': result,
            'message': message,
            'vehicle_info': vehicle_info,
            'filename': file.filename
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        })

@app.post('/extract_vehicle_numbers')
async def extract_vehicle_numbers(
    message: str = Form(...)
):
    """
    Extract vehicle numbers from a message without processing video
    """
    try:
        vehicle_info = extract_vehicle_numbers_from_message(message)
        
        return JSONResponse({
            'success': True,
            'message': message,
            'vehicle_info': vehicle_info
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        })

@app.post('/generate_summary')
async def generate_summary_api(request: Request):
    data = await request.json()
    conversation_history = data.get('conversation_history', [])
    if isinstance(conversation_history, str):
        try:
            conversation_history = json.loads(conversation_history)
        except Exception:
            conversation_history = []
    
    # Convert conversation from tuple format to dictionary format for processing
    conversation_dict = []
    for entry in conversation_history:
        if isinstance(entry, tuple) and len(entry) == 2:
            role, content = entry
            if role == 'user':
                conversation_dict.append({'message': content, 'file_text': '', 'assistant': ''})
            elif role == 'assistant':
                # Add assistant response to the last entry or create new entry
                if conversation_dict:
                    conversation_dict[-1]['assistant'] = content
                else:
                    conversation_dict.append({'message': '', 'file_text': '', 'assistant': content})
        elif isinstance(entry, dict):
            conversation_dict.append(entry)
    
    # Generate summary from conversation
    summary = generate_summary(conversation_dict)
    return JSONResponse({'summary': summary})

@app.get('/summary')
async def summary(user_id: str):
    # For stateless, just return a placeholder
    return JSONResponse({'summary': 'Summary report is only available in stateful mode.'}) 