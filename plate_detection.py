import cv2
import numpy as np
import re
import os
import tempfile
import subprocess
import json
from typing import List, Tuple, Optional, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlateDetector:
    """
    Vehicle number plate detection and matching using OpenALPR and OpenCV
    """
    
    def __init__(self, openalpr_config_path: str = None):
        """
        Initialize the plate detector
        
        Args:
            openalpr_config_path: Path to OpenALPR config file (optional)
        """
        self.openalpr_config_path = openalpr_config_path
        self.plate_patterns = [
            # Common Indian plate patterns
            r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,2}[0-9]{4}$',  # KA01AB1234
            r'^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$',      # KA01AB1234
            r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$',  # KA01ABC1234
            r'^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$',    # KA01ABC1234
            # Add more patterns as needed
        ]
        
        # Initialize EasyOCR reader once (lazy loading)
        self._ocr_reader = None
        
    @property
    def ocr_reader(self):
        """Lazy load EasyOCR reader"""
        if self._ocr_reader is None:
            try:
                import easyocr
                self._ocr_reader = easyocr.Reader(['en'], gpu=False)  # Force CPU to avoid GPU issues
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                self._ocr_reader = None
        return self._ocr_reader
    
    def extract_frames_from_video(self, video_path: str, max_frames: int = 8) -> List[np.ndarray]:
        """
        Extract frames from video for processing
        
        Args:
            video_path: Path to video file
            max_frames: Maximum number of frames to extract
            
        Returns:
            List of frames as numpy arrays
        """
        frames = []
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            logger.error(f"Could not open video file: {video_path}")
            return frames
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        # Calculate frame interval to extract evenly distributed frames
        if total_frames > max_frames:
            interval = total_frames // max_frames
        else:
            interval = 1
            
        frame_count = 0
        extracted_count = 0
        
        # Extract frames at regular intervals
        while extracted_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % interval == 0:
                frames.append(frame)
                extracted_count += 1
                
            frame_count += 1
            
        cap.release()
        logger.info(f"Extracted {len(frames)} frames from video")
        return frames
    
    def simple_text_detection(self, plate_region: np.ndarray) -> Optional[str]:
        """
        Simple text detection without OCR for basic testing
        
        Args:
            plate_region: Cropped plate region image
            
        Returns:
            Detected text or None
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
            
            # Apply threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Find contours that might be text
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Simple heuristic: look for rectangular contours that might be characters
            potential_chars = []
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if 50 < area < 2000:  # Reasonable size for characters
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / float(h)
                    if 0.2 < aspect_ratio < 2.0:  # Character-like aspect ratio
                        potential_chars.append((x, y, w, h))
            
            # Sort characters by x position (left to right)
            potential_chars.sort(key=lambda x: x[0])
            
            # Simple text reconstruction (just for debugging)
            if len(potential_chars) >= 3:  # At least 3 characters
                # Create a simple text representation
                text = f"PLATE_{len(potential_chars)}CHARS"
                return text
            
            return None
            
        except Exception as e:
            logger.error(f"Error in simple text detection: {e}")
            return None

    def detect_plates_opencv(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect license plates using OpenCV image processing
        
        Args:
            frame: Input frame as numpy array
            
        Returns:
            List of detected plates with coordinates and confidence
        """
        plates = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply multiple preprocessing techniques
        # Method 1: Gaussian blur + morphological operations
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
        morph = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel)
        
        # Method 2: Edge detection
        edges = cv2.Canny(gray, 50, 150)
        
        # Method 3: Adaptive threshold
        adaptive_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        # Try different methods for plate detection
        methods = [
            ('morphological', morph),
            ('edges', edges),
            ('adaptive_thresh', adaptive_thresh)
        ]
        
        for method_name, processed_img in methods:
            # Find contours
            contours, _ = cv2.findContours(processed_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 500:  # Reduced minimum area for better detection
                    continue
                    
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check aspect ratio (license plates are typically rectangular)
                aspect_ratio = w / float(h)
                if 1.5 <= aspect_ratio <= 6.0:  # Wider range for better detection
                    # Extract the region
                    plate_region = frame[y:y+h, x:x+w]
                    
                    # Try OCR first, then fallback to simple detection
                    plate_text = None
                    
                    # Try EasyOCR if available
                    if self.ocr_reader is not None:
                        plate_text = self.ocr_plate_text(plate_region)
                    
                    # Fallback to simple detection if OCR fails
                    if not plate_text:
                        plate_text = self.simple_text_detection(plate_region)
                    
                    if plate_text:
                        # Even if format doesn't match, include it for debugging
                        is_valid = self.is_valid_plate_format(plate_text)
                        confidence = 0.8 if is_valid else 0.3
                        
                        plates.append({
                            'text': plate_text,
                            'confidence': confidence,
                            'bbox': (x, y, w, h),
                            'region': plate_region,
                            'method': method_name,
                            'is_valid_format': is_valid
                        })
        
        return plates
    
    def detect_plates_openalpr(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect license plates using OpenALPR
        
        Args:
            frame: Input frame as numpy array
            
        Returns:
            List of detected plates with text and confidence
        """
        plates = []
        
        # Save frame to temporary file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            cv2.imwrite(tmp_file.name, frame)
            temp_path = tmp_file.name
        
        try:
            # Run OpenALPR command
            cmd = ['alpr', '-j', temp_path]
            if self.openalpr_config_path:
                cmd.extend(['-c', self.openalpr_config_path])
                
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                try:
                    alpr_result = json.loads(result.stdout)
                    for plate in alpr_result.get('results', []):
                        plate_text = plate.get('plate', '').strip()
                        confidence = plate.get('confidence', 0)
                        
                        if plate_text and self.is_valid_plate_format(plate_text):
                            plates.append({
                                'text': plate_text,
                                'confidence': confidence,
                                'bbox': None,  # OpenALPR doesn't provide bbox in JSON mode
                                'region': None
                            })
                except json.JSONDecodeError:
                    logger.warning("Failed to parse OpenALPR JSON output")
                    
        except subprocess.TimeoutExpired:
            logger.warning("OpenALPR command timed out")
        except FileNotFoundError:
            logger.warning("OpenALPR not found. Please install OpenALPR.")
        except Exception as e:
            logger.error(f"Error running OpenALPR: {e}")
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        
        return plates
    
    def ocr_plate_text(self, plate_region: np.ndarray) -> Optional[str]:
        """
        Extract text from plate region using OCR
        
        Args:
            plate_region: Cropped plate region image
            
        Returns:
            Extracted text or None
        """
        try:
            # Check if OCR reader is available
            if self.ocr_reader is None:
                logger.warning("EasyOCR not available, skipping OCR")
                return None
            
            # Preprocess the image for better OCR
            gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
            
            # Try multiple preprocessing techniques
            processed_images = []
            
            # Original image
            processed_images.append(gray)
            
            # Apply threshold to get binary image
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(binary)
            
            # Apply morphological operations to clean up
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            processed_images.append(cleaned)
            
            # Adaptive threshold
            adaptive_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            processed_images.append(adaptive_thresh)
            
            all_texts = []
            
            # Try OCR on each processed image
            for img in processed_images:
                try:
                    results = self.ocr_reader.readtext(img)
                    
                    # Extract text from results
                    for (bbox, text, confidence) in results:
                        if confidence > 0.3:  # Lowered confidence threshold
                            # Clean up text - be more lenient
                            cleaned_text = re.sub(r'[^A-Z0-9]', '', text.upper())
                            if cleaned_text and len(cleaned_text) >= 3:  # Minimum 3 characters
                                all_texts.append({
                                    'text': cleaned_text,
                                    'confidence': confidence,
                                    'original': text
                                })
                except Exception as e:
                    logger.debug(f"OCR failed on one image variant: {e}")
                    continue
            
            # If no texts found, try with even lower confidence
            if not all_texts:
                try:
                    # Try with the original image and very low confidence
                    results = self.ocr_reader.readtext(gray)
                    for (bbox, text, confidence) in results:
                        if confidence > 0.1:  # Very low threshold
                            cleaned_text = re.sub(r'[^A-Z0-9]', '', text.upper())
                            if cleaned_text and len(cleaned_text) >= 2:  # Even shorter minimum
                                all_texts.append({
                                    'text': cleaned_text,
                                    'confidence': confidence,
                                    'original': text
                                })
                except Exception as e:
                    logger.debug(f"Low confidence OCR failed: {e}")
            
            # Return the best result
            if all_texts:
                # Sort by confidence and return the best
                best_result = max(all_texts, key=lambda x: x['confidence'])
                return best_result['text']
            
            return None
            
        except Exception as e:
            logger.error(f"Error in OCR: {e}")
            return None
    
    def is_valid_plate_format(self, plate_text: str) -> bool:
        """
        Check if the detected text matches valid license plate format
        
        Args:
            plate_text: Text to validate
            
        Returns:
            True if valid format, False otherwise
        """
        # Clean the text
        cleaned_text = re.sub(r'[^A-Z0-9]', '', plate_text.upper())
        
        if not cleaned_text or len(cleaned_text) < 5:
            return False
        
        # Check against known patterns
        for pattern in self.plate_patterns:
            if re.match(pattern, cleaned_text):
                return True
        
        # Additional flexible patterns for better detection
        flexible_patterns = [
            r'^[A-Z]{2}[0-9]{1,4}[A-Z]{1,4}[0-9]{1,4}$',  # More flexible
            r'^[A-Z]{1,3}[0-9]{1,4}[A-Z]{1,4}[0-9]{1,4}$',  # Even more flexible
            r'^[A-Z0-9]{6,12}$',  # Any alphanumeric 6-12 chars
        ]
        
        for pattern in flexible_patterns:
            if re.match(pattern, cleaned_text):
                return True
        
        return False
    
    def match_plate_with_user_input(self, detected_plates: List[Dict], user_plate: str) -> Dict:
        """
        Match detected plates with user-provided plate number
        
        Args:
            detected_plates: List of detected plates from video
            user_plate: User-provided plate number
            
        Returns:
            Matching result with details
        """
        if not detected_plates:
            return {
                'match_found': False,
                'message': 'No license plates detected in the video',
                'detected_plates': [],
                'user_plate': user_plate,
                'context': f'Searching for plate: {user_plate}'
            }
        
        # Clean user input
        user_plate_clean = re.sub(r'[^A-Z0-9]', '', user_plate.upper())
        
        best_match = None
        best_confidence = 0
        
        for plate in detected_plates:
            # Ensure plate is a dictionary
            if not isinstance(plate, dict):
                continue
                
            detected_text = plate.get('text', '')
            if not detected_text:
                continue
                
            detected_clean = re.sub(r'[^A-Z0-9]', '', detected_text.upper())
            
            # Exact match
            if detected_clean == user_plate_clean:
                return {
                    'match_found': True,
                    'exact_match': True,
                    'detected_plate': plate,
                    'user_plate': user_plate,
                    'confidence': plate.get('confidence', 1.0),
                    'message': f'Exact match found: {detected_text}',
                    'context': f'Exact match for {user_plate} found in frame {plate.get("frame_number", "Unknown")}'
                }
            
            # Partial match (using similarity)
            similarity = self.calculate_similarity(detected_clean, user_plate_clean)
            if similarity > best_confidence:
                best_confidence = similarity
                best_match = plate
        
        # Return best partial match if confidence is high enough
        if best_confidence > 0.7 and best_match:
            return {
                'match_found': True,
                'exact_match': False,
                'detected_plate': best_match,
                'user_plate': user_plate,
                'confidence': best_confidence,
                'message': f'Partial match found: {best_match.get("text", "Unknown")} (similarity: {best_confidence:.2f})',
                'context': f'Partial match for {user_plate} found in frame {best_match.get("frame_number", "Unknown")}'
            }
        
        # Extract plate texts for the response
        plate_texts = []
        for plate in detected_plates:
            if isinstance(plate, dict):
                plate_texts.append(plate.get('text', 'Unknown'))
            else:
                plate_texts.append(str(plate))
        
        return {
            'match_found': False,
            'message': 'No matching license plate found in the video',
            'detected_plates': plate_texts,
            'user_plate': user_plate,
            'context': f'No match found for {user_plate} in video'
        }
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two strings using Levenshtein distance
        
        Args:
            text1: First string
            text2: Second string
            
        Returns:
            Similarity score (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # Use simple character-based similarity
        common_chars = sum(1 for c in text1 if c in text2)
        max_len = max(len(text1), len(text2))
        
        return common_chars / max_len if max_len > 0 else 0.0
    
    def process_video_for_plates(self, video_path: str, user_plate: str = None) -> Dict:
        """
        Process video to detect and match license plates
        
        Args:
            video_path: Path to video file
            user_plate: User-provided plate number (optional)
            
        Returns:
            Processing results
        """
        logger.info(f"Processing video: {video_path}")
        
        # Extract frames
        frames = self.extract_frames_from_video(video_path)
        if not frames:
            return {
                'success': False,
                'error': 'Could not extract frames from video'
            }
        
        all_detected_plates = []
        debug_info = {
            'total_frames': len(frames),
            'frames_with_detections': 0,
            'total_detections': 0,
            'detection_methods': {}
        }
        
        # Process each frame
        for i, frame in enumerate(frames):
            logger.info(f"Processing frame {i+1}/{len(frames)}")
            
            # Try OpenALPR first
            plates = self.detect_plates_openalpr(frame)
            
            # Fallback to OpenCV if OpenALPR fails
            if not plates:
                plates = self.detect_plates_opencv(frame)
            
            # Track debugging info
            if plates:
                debug_info['frames_with_detections'] += 1
                debug_info['total_detections'] += len(plates)
                
                for plate in plates:
                    if isinstance(plate, dict):
                        method = plate.get('method', 'openalpr')
                        if method not in debug_info['detection_methods']:
                            debug_info['detection_methods'][method] = 0
                        debug_info['detection_methods'][method] += 1
            
            for plate in plates:
                # Ensure plate has frame number
                if isinstance(plate, dict):
                    plate['frame_number'] = i + 1
                all_detected_plates.append(plate)
        
        # Remove duplicates based on text
        unique_plates = []
        seen_texts = set()
        
        for plate in all_detected_plates:
            if isinstance(plate, dict):
                text = plate.get('text', '')
            else:
                text = str(plate)
                
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_plates.append(plate)
        
        result = {
            'success': True,
            'total_frames_processed': len(frames),
            'detected_plates': unique_plates,
            'unique_plate_count': len(unique_plates),
            'debug_info': debug_info
        }
        
        # Match with user input if provided
        if user_plate:
            match_result = self.match_plate_with_user_input(unique_plates, user_plate)
            result.update(match_result)
        
        return result
    
    def process_video_with_multiple_plates(self, video_path: str, vehicle_info: Dict) -> Dict:
        """
        Process video to detect and match multiple license plates from a message
        
        Args:
            video_path: Path to video file
            vehicle_info: Dictionary containing vehicle information from message
                         {'user_vehicle': str, 'other_vehicle': str, 'all_plates': List[str]}
            
        Returns:
            Processing results with multiple plate matching
        """
        logger.info(f"Processing video with multiple plates: {video_path}")
        
        # First, process the video to get all detected plates
        base_result = self.process_video_for_plates(video_path)
        
        if not base_result['success']:
            return base_result
        
        # Initialize results for multiple plate matching
        multi_plate_result = {
            'success': True,
            'video_path': video_path,
            'vehicle_info': vehicle_info,
            'all_detected_plates': base_result['detected_plates'],
            'matches': {},
            'summary': {
                'total_plates_in_message': len(vehicle_info.get('all_plates', [])),
                'plates_found_in_video': 0,
                'exact_matches': 0,
                'partial_matches': 0
            }
        }
        
        # Match each plate from the message
        for plate in vehicle_info.get('all_plates', []):
            match_result = self.match_plate_with_user_input(base_result['detected_plates'], plate)
            multi_plate_result['matches'][plate] = match_result
            
            # Update summary
            if match_result['match_found']:
                multi_plate_result['summary']['plates_found_in_video'] += 1
                if match_result.get('exact_match', False):
                    multi_plate_result['summary']['exact_matches'] += 1
                else:
                    multi_plate_result['summary']['partial_matches'] += 1
        
        # Add context about which vehicle is which
        if vehicle_info.get('user_vehicle'):
            user_plate = vehicle_info['user_vehicle']
            if user_plate in multi_plate_result['matches']:
                match = multi_plate_result['matches'][user_plate]
                if match['match_found']:
                    match['vehicle_type'] = 'user_vehicle'
                    match['context'] = f"User's vehicle ({user_plate}) found in video"
                else:
                    match['vehicle_type'] = 'user_vehicle'
                    match['context'] = f"User's vehicle ({user_plate}) not found in video"
        
        if vehicle_info.get('other_vehicle'):
            other_plate = vehicle_info['other_vehicle']
            if other_plate in multi_plate_result['matches']:
                match = multi_plate_result['matches'][other_plate]
                if match['match_found']:
                    match['vehicle_type'] = 'other_vehicle'
                    match['context'] = f"Other vehicle involved ({other_plate}) found in video"
                else:
                    match['vehicle_type'] = 'other_vehicle'
                    match['context'] = f"Other vehicle involved ({other_plate}) not found in video"
        
        return multi_plate_result 