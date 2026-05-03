"""
MRZ Reader - Standalone Machine Readable Zone parser for passports and ID cards.
Ported from tesseract_ocr_service to run locally.

Supports ICAO 9303 standard:
- TD3 (Passports): 2 lines x 44 characters
- TD1 (ID Cards): 3 lines x 30 characters
- TD2 (Travel Docs): 2 lines x 36 characters
- MRVA/MRVB (Visas)

Features:
- ONNX segmentation model for MRZ region detection
- Multi-rotation detection (0/90/180/270 degrees)
- ICAO 9303 check digit validation
- Multiple extraction strategies with fallback
- Tesseract OCR with MRZ language support
"""
import base64
import io
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Try imports
try:
    import pytesseract
    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    TESSERACT_AVAILABLE = True
    try:
        _langs = pytesseract.get_languages()
        MRZ_LANG_AVAILABLE = 'mrz' in _langs
    except Exception:
        MRZ_LANG_AVAILABLE = False
except ImportError:
    TESSERACT_AVAILABLE = False
    MRZ_LANG_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Try ONNX runtime
try:
    import onnxruntime
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False


class MRZReader:
    """
    Standalone MRZ parser with ONNX segmentation model support.
    Detects and extracts MRZ from passport/ID images with rotation handling.
    """

    # MRZ model path - look in app/parsers/models/ first, then tesseract_ocr_service
    ONNX_MODEL_PATHS = [
        Path(__file__).parent / "models" / "mrz_seg.onnx",
        Path(__file__).parent.parent.parent / "tesseract_ocr_service" / "mrz_extractor" / "model" / "mrz_seg.onnx",
    ]

    def __init__(self, onnx_model_path: str = None):
        self.onnx_net = None
        self._load_onnx_model(onnx_model_path)

    def _load_onnx_model(self, custom_path: str = None):
        """Load the ONNX segmentation model for MRZ region detection."""
        if not CV2_AVAILABLE:
            logger.info("[MRZ] OpenCV not available, ONNX model disabled")
            return

        paths_to_try = []
        if custom_path:
            paths_to_try.append(Path(custom_path))
        paths_to_try.extend(self.ONNX_MODEL_PATHS)

        for path in paths_to_try:
            if path.exists():
                try:
                    self.onnx_net = cv2.dnn.readNetFromONNX(str(path))
                    logger.info(f"[MRZ] ONNX model loaded from: {path}")
                    return
                except Exception as e:
                    logger.warning(f"[MRZ] Failed to load ONNX from {path}: {e}")

        logger.info("[MRZ] ONNX model not found, using Tesseract-only MRZ detection")

    # =========================================================================
    #  MRZ LINE VALIDATION
    # =========================================================================

    def validate_mrz_line(self, line: str) -> dict:
        """
        Validate if a line is a valid MRZ line with strict checks.
        Returns: {"valid": bool, "score": int, "type": str, "line": str}
        """
        cleaned = re.sub(r'[^A-Z0-9<]', '', line.upper())
        result = {"valid": False, "score": 0, "type": None, "line": cleaned}

        length = len(cleaned)
        if length < 28 or length > 46:
            return result

        filler_count = cleaned.count('<')
        if filler_count < 3:
            return result

        if '<<' not in cleaned:
            return result

        # TD3 Line 1 (Passport): P<COUNTRY_CODE + NAME
        if re.match(r'^P<[A-Z]{3}[A-Z]+<<[A-Z<]+$', cleaned) and 42 <= length <= 46:
            if filler_count >= 5:
                result.update({"valid": True, "score": 100, "type": "TD3_L1"})
                return result

        # TD3 Line 2: Doc number + checks
        if 42 <= length <= 46:
            if re.match(r'^[A-Z0-9<]{9}[0-9][A-Z]{3}[0-9]{6}[0-9][MF<][0-9]{6}[0-9]', cleaned):
                result.update({"valid": True, "score": 100, "type": "TD3_L2"})
                return result

        # TD1 Line 1 (ID Card)
        if re.match(r'^[IAC][A-Z<][A-Z]{3}[A-Z0-9<]{24}$', cleaned) and 28 <= length <= 32:
            result.update({"valid": True, "score": 90, "type": "TD1_L1"})
            return result

        # TD1 Line 2
        if re.match(r'^[0-9]{6}[0-9][MF<][0-9]{6}[0-9][A-Z]{3}', cleaned) and 28 <= length <= 32:
            result.update({"valid": True, "score": 90, "type": "TD1_L2"})
            return result

        # TD1 Line 3 (Name)
        if re.match(r'^[A-Z]+<<[A-Z<]+$', cleaned) and 28 <= length <= 32 and filler_count >= 5:
            result.update({"valid": True, "score": 85, "type": "TD1_L3"})
            return result

        # TD2 patterns (36 chars)
        if 34 <= length <= 38:
            if re.match(r'^[PVIAC][A-Z<][A-Z]{3}[A-Z]+<<[A-Z<]+$', cleaned) and filler_count >= 5:
                result.update({"valid": True, "score": 80, "type": "TD2_L1"})
                return result
            if re.match(r'^[A-Z0-9<]{9}[0-9][A-Z]{3}[0-9]{6}[0-9][MF<][0-9]{6}[0-9]', cleaned):
                result.update({"valid": True, "score": 80, "type": "TD2_L2"})
                return result

        # Visa patterns
        if re.match(r'^V<[A-Z]{3}[A-Z]+<<[A-Z<]+$', cleaned) and length >= 36 and filler_count >= 5:
            result.update({"valid": True, "score": 90, "type": "VISA_L1"})
            return result

        return result

    # =========================================================================
    #  MRZ DETECTION WITH ROTATION
    # =========================================================================

    def detect_mrz(self, image: Image.Image) -> dict:
        """
        Detect MRZ with smart rotation handling.
        Tries OSD-suggested rotation first, then all 4 orientations.
        Checks full image and bottom portions where MRZ typically appears.

        Returns:
            dict with has_mrz, best_rotation, score, mrz_lines, mrz_type
        """
        if not TESSERACT_AVAILABLE:
            return {"has_mrz": False, "best_rotation": 0, "score": 0,
                    "mrz_lines": [], "mrz_type": None}

        gray = image.convert('L') if image.mode != 'L' else image.copy()
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.5)

        best_result = {
            "has_mrz": False, "best_rotation": 0, "score": 0,
            "mrz_lines": [], "mrz_type": None
        }

        # OSD orientation detection
        osd_rotation, osd_confidence = self._detect_orientation_osd(enhanced)

        if osd_confidence > 2.0:
            rotations_to_try = [osd_rotation]
            for r in [0, 90, 180, 270]:
                if r not in rotations_to_try:
                    rotations_to_try.append(r)
        else:
            rotations_to_try = [0, 90, 180, 270]

        lang = 'mrz' if MRZ_LANG_AVAILABLE else 'eng'

        for angle in rotations_to_try:
            test_img = enhanced.rotate(angle, expand=True) if angle != 0 else enhanced
            width, height = test_img.size

            regions = [
                ("full", test_img),
                ("bottom_50", test_img.crop((0, int(height * 0.5), width, height))),
                ("bottom_30", test_img.crop((0, int(height * 0.7), width, height))),
                ("bottom_20", test_img.crop((0, int(height * 0.8), width, height))),
            ]

            for region_name, region_img in regions:
                for psm in [6, 3, 4, 11, 12]:
                    try:
                        config = f'--psm {psm} --oem 3'
                        text = pytesseract.image_to_string(region_img, lang=lang, config=config)
                        text_upper = text.upper()

                        has_hint = ('P<' in text_upper or 'V<' in text_upper or
                                    'I<' in text_upper or '<<<' in text_upper)
                        if not has_hint and region_name != "full":
                            continue

                        lines = text.split('\n')
                        valid_lines = []
                        total_score = 0

                        for line in lines:
                            validation = self.validate_mrz_line(line)
                            if validation["valid"]:
                                valid_lines.append(validation)
                                total_score += validation["score"]

                        has_l1 = any(v["type"] and v["type"].endswith("_L1") for v in valid_lines)
                        has_l2 = any(v["type"] and v["type"].endswith("_L2") for v in valid_lines)

                        if len(valid_lines) >= 2 and has_l1 and has_l2:
                            if has_l1:
                                total_score += 50

                            if total_score > best_result["score"]:
                                mrz_type = "UNKNOWN"
                                for v in valid_lines:
                                    if v["type"]:
                                        if v["type"].startswith("TD3"):
                                            mrz_type = "TD3_PASSPORT"
                                        elif v["type"].startswith("TD1"):
                                            mrz_type = "TD1_ID"
                                        elif v["type"].startswith("TD2"):
                                            mrz_type = "TD2_ID"
                                        elif v["type"].startswith("VISA"):
                                            mrz_type = "VISA"
                                        break

                                best_result = {
                                    "has_mrz": True,
                                    "best_rotation": angle,
                                    "score": total_score,
                                    "mrz_lines": valid_lines,
                                    "mrz_type": mrz_type,
                                }
                                logger.info(
                                    f"[MRZ] Found at {angle} deg ({region_name}, PSM {psm}): "
                                    f"score={total_score}, type={mrz_type}"
                                )

                                if total_score >= 200:
                                    return best_result

                    except Exception:
                        continue

        if not best_result["has_mrz"]:
            logger.debug("[MRZ] No valid MRZ found after checking all rotations")

        return best_result

    def _detect_orientation_osd(self, image: Image.Image) -> Tuple[int, float]:
        """Detect image orientation using Tesseract OSD."""
        try:
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
            rotation = osd.get('rotate', 0)
            confidence = osd.get('orientation_conf', 0)
            return (rotation, confidence)
        except Exception:
            return (0, 0)

    # =========================================================================
    #  MRZ DATA EXTRACTION
    # =========================================================================

    def extract_mrz_data(self, image: Image.Image, rotation: int = 0,
                         detected_lines: list = None) -> dict:
        """
        Extract structured MRZ data using multiple strategies:
        1. ONNX model text parsing on detected lines
        2. ONNX model image-based extraction
        3. Tesseract with MRZ language fallback
        """
        if rotation != 0:
            image = image.rotate(rotation, expand=True)

        # Strategy 1: Parse detected MRZ text with ONNX extractor
        if self.onnx_net is not None and detected_lines:
            mrz_text = '\n'.join([l.get('line', '') for l in detected_lines if l.get('line')])
            if mrz_text and len(mrz_text) > 50:
                logger.info("[MRZ] Strategy 1: parsing detected MRZ text...")
                result = self._parse_mrz_text(mrz_text)
                if result.get('status') == 'SUCCESS':
                    result['extraction_method'] = 'onnx_text'
                    result['rotation_applied'] = rotation
                    return result

        # Strategy 2: ONNX model image-based extraction
        if self.onnx_net is not None and CV2_AVAILABLE:
            logger.info("[MRZ] Strategy 2: ONNX image extraction...")
            width, height = image.size
            crops = [
                ("bottom_20", image.crop((0, int(height * 0.8), width, height))),
                ("bottom_30", image.crop((0, int(height * 0.7), width, height))),
                ("bottom_40", image.crop((0, int(height * 0.6), width, height))),
                ("full", image),
            ]
            for crop_name, crop_img in crops:
                try:
                    result = self._extract_with_onnx(crop_img)
                    if result.get('status') == 'SUCCESS':
                        result['extraction_method'] = f'onnx_image_{crop_name}'
                        result['rotation_applied'] = rotation
                        logger.info(f"[MRZ] ONNX extraction successful on {crop_name}")
                        return result
                except Exception as e:
                    logger.debug(f"[MRZ] ONNX extraction failed on {crop_name}: {e}")

        # Strategy 3: Tesseract MRZ language fallback
        logger.info("[MRZ] Strategy 3: Tesseract MRZ fallback...")
        return self._extract_with_tesseract(image, rotation)

    def _extract_with_onnx(self, image: Image.Image) -> dict:
        """Extract MRZ using ONNX segmentation model + Tesseract."""
        img_array = np.array(image.convert('RGB'))
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Process through ONNX model
        processed = cv2.resize(img_bgr, (256, 256), interpolation=cv2.INTER_NEAREST)
        processed = np.asarray(np.float32(processed / 255))
        if len(processed.shape) >= 3:
            processed = processed[:, :, :3]
        processed = np.reshape(processed, (1, 256, 256, 3))

        self.onnx_net.setInput(processed)
        output = self.onnx_net.forward()

        # Get ROI from segmentation output
        mask = (output[0, :, :, 0] > 0.25) * 1
        mask = np.uint8(mask * 255)
        mask_resized = cv2.resize(mask, (img_bgr.shape[1], img_bgr.shape[0]))

        kernel = np.ones((5, 5), dtype=np.float32)
        mask_resized = cv2.erode(mask_resized, kernel, iterations=1)

        contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if len(contours) == 0:
            return {"status": "FAILURE", "status_message": "No MRZ region detected"}

        areas = [cv2.contourArea(c) for c in contours]
        x, y, w, h = cv2.boundingRect(contours[np.argmax(areas)])

        padding = 10
        x_start = max(0, x - padding)
        y_start = max(0, y - padding)
        x_end = min(img_bgr.shape[1], x + w + padding)
        y_end = min(img_bgr.shape[0], y + h + padding)

        roi = img_bgr[y_start:y_end, x_start:x_end].copy()
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        roi_binary = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        lang = 'mrz' if MRZ_LANG_AVAILABLE else 'eng'
        config = '--oem 3 --psm 6'
        mrz_text = pytesseract.image_to_string(roi_binary, lang=lang, config=config)

        # Clean and parse
        cleaned = self._cleanse_mrz_text(mrz_text)
        if not cleaned:
            return {"status": "FAILURE", "status_message": "No valid MRZ text in ROI"}

        return self._parse_mrz_text(cleaned)

    def _extract_with_tesseract(self, image: Image.Image, rotation: int = 0) -> dict:
        """Extract MRZ using Tesseract with MRZ language data."""
        if not TESSERACT_AVAILABLE:
            return {"status": "FAILED", "error": "Tesseract not available"}

        gray = image.convert('L') if image.mode != 'L' else image.copy()
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)

        width, height = enhanced.size
        bottom = enhanced.crop((0, int(height * 0.6), width, height))

        best_mrz_lines = []
        best_score = 0

        for img_name, img in [("full", enhanced), ("bottom", bottom)]:
            for psm in [6, 4, 3, 11]:
                try:
                    lang = 'mrz' if MRZ_LANG_AVAILABLE else 'eng'
                    config = f'--psm {psm} --oem 3'
                    text = pytesseract.image_to_string(img, lang=lang, config=config)

                    lines = text.split('\n')
                    mrz_lines = []
                    score = 0

                    for line in lines:
                        validation = self.validate_mrz_line(line)
                        if validation["valid"]:
                            mrz_lines.append(validation["line"])
                            score += validation["score"]

                    if score > best_score and len(mrz_lines) >= 2:
                        best_score = score
                        best_mrz_lines = mrz_lines

                except Exception:
                    continue

        if len(best_mrz_lines) >= 2:
            # Final validation
            has_l1 = any(re.match(r'^[PVIAC]<[A-Z]{3}', line) for line in best_mrz_lines)
            has_l2 = any(
                re.match(r'^[A-Z0-9<]{9}[0-9][A-Z]{3}[0-9]{6}[0-9][MF]', line) or
                re.match(r'^[0-9]{6}[0-9][MF]', line)
                for line in best_mrz_lines
            )

            if not (has_l1 or has_l2):
                return {"status": "FAILED", "error": "Detected text is not valid MRZ"}

            result = self.parse_mrz_lines('\n'.join(best_mrz_lines))
            result['extraction_method'] = 'tesseract_mrz'
            result['rotation_applied'] = rotation
            return result

        return {"status": "FAILED", "error": "Could not extract MRZ lines"}

    # =========================================================================
    #  MRZ TEXT PARSING
    # =========================================================================

    def _cleanse_mrz_text(self, mrz_text: str) -> str:
        """Clean raw OCR output to extract valid MRZ lines."""
        input_list = mrz_text.replace(" ", "").split("\n")
        selection_length = next(
            (len(item) for item in input_list
             if "<" in item and len(item) in {30, 36, 44}),
            None,
        )
        if selection_length is None:
            return ""
        new_list = [item for item in input_list
                     if len(item) >= selection_length and "<" in item]
        return "\n".join(new_list)

    def _parse_mrz_text(self, mrz_text: str, include_checkdigit: bool = False) -> dict:
        """Parse MRZ text into structured data with ICAO 9303 validation."""
        if not mrz_text:
            return {"status": "FAILURE", "status_message": "No MRZ detected"}

        mrz_lines = mrz_text.strip().split("\n")
        if len(mrz_lines) not in [2, 3]:
            return {"status": "FAILURE", "status_message": "Invalid MRZ format"}

        result = {}

        if len(mrz_lines) == 2:
            # TD3, TD2, MRVA, MRVB
            line1, line2 = mrz_lines

            if line2[-1] == "<":
                result["mrz_type"] = "MRVA" if line1[0] == "V" else "TD2"
            else:
                result["mrz_type"] = "MRVB" if line1[0] == "V" else "TD3"

            result["document_code"] = line1[:2].strip("<")
            result["issuer_code"] = line1[2:5]

            if not result["issuer_code"].isalpha():
                result["status"] = "FAILURE"
                result["status_message"] = "Invalid MRZ format"

            names = line1[5:].split("<<")
            result["surname"] = names[0].replace("<", " ").strip()
            result["given_name"] = names[1].replace("<", " ").strip() if len(names) > 1 else ""

            result["document_number"] = line2[:9].strip("<")
            doc_check = self._get_checkdigit(result["document_number"])
            if doc_check != line2[9]:
                result.setdefault("status", "WARNING")
                result.setdefault("status_message", "Document number checksum mismatch")
            if include_checkdigit:
                result["document_number_checkdigit"] = doc_check

            result["nationality_code"] = line2[10:13]

            result["birth_date"] = line2[13:19]
            bd_check = self._get_checkdigit(result["birth_date"])
            if include_checkdigit:
                result["birth_date_checkdigit"] = bd_check
            try:
                result["birth_date"] = self._format_date(result["birth_date"])
            except Exception:
                pass

            result["sex"] = line2[20]

            result["expiry_date"] = line2[21:27]
            exp_check = self._get_checkdigit(result["expiry_date"])
            if include_checkdigit:
                result["expiry_date_checkdigit"] = exp_check
            try:
                result["expiry_date"] = self._format_date(result["expiry_date"])
            except Exception:
                pass

            # Adjust birth date if needed
            if result.get("birth_date") and result.get("expiry_date"):
                result["birth_date"] = self._adjust_birth_date(
                    result["birth_date"], result["expiry_date"]
                )

            if result["mrz_type"] == "TD2":
                result["optional_data"] = line2[28:35].strip("<")
            elif result["mrz_type"] == "TD3":
                result["optional_data"] = line2[28:42].strip("<")
            elif result["mrz_type"] == "MRVA":
                result["optional_data"] = line2[28:44].strip("<")
            else:
                result["optional_data"] = line2[28:36].strip("<")

        elif len(mrz_lines) == 3:
            # TD1
            line1, line2, line3 = mrz_lines
            result["mrz_type"] = "TD1"
            result["document_code"] = line1[:2].strip("<")
            result["issuer_code"] = line1[2:5]
            result["document_number"] = line1[5:14].strip("<")

            doc_check = self._get_checkdigit(line1[5:14])
            if include_checkdigit:
                result["document_number_checkdigit"] = doc_check

            result["optional_data_1"] = line1[15:].strip("<")

            result["birth_date"] = line2[:6]
            if include_checkdigit:
                result["birth_date_checkdigit"] = self._get_checkdigit(result["birth_date"])
            try:
                result["birth_date"] = self._format_date(result["birth_date"])
            except Exception:
                pass

            result["sex"] = line2[7]

            result["expiry_date"] = line2[8:14]
            if include_checkdigit:
                result["expiry_date_checkdigit"] = self._get_checkdigit(result["expiry_date"])
            try:
                result["expiry_date"] = self._format_date(result["expiry_date"])
            except Exception:
                pass

            if result.get("birth_date") and result.get("expiry_date"):
                result["birth_date"] = self._adjust_birth_date(
                    result["birth_date"], result["expiry_date"]
                )

            result["nationality_code"] = line2[15:18]

            names = line3.split("<<")
            result["surname"] = names[0].replace("<", " ").strip()
            result["given_name"] = names[1].replace("<", " ").strip() if len(names) > 1 else ""

        result["mrz_text"] = mrz_text

        if result.get("status") != "FAILURE":
            result["status"] = "SUCCESS"

        return result

    def parse_mrz_lines(self, mrz_text: str) -> dict:
        """
        Parse raw MRZ lines into structured data.
        Public interface for parsing from Tesseract output.
        """
        lines = [l.strip() for l in mrz_text.split('\n') if l.strip() and len(l.strip()) >= 28]
        if not lines:
            return {"status": "FAILED", "error": "No MRZ lines found"}

        result = {"status": "SUCCESS", "raw_mrz": mrz_text}

        try:
            if len(lines) >= 2:
                line1, line2 = lines[0], lines[1]

                # TD3 (Passport): 2 lines of 44 characters
                if len(line1) >= 42:
                    result["mrz_type"] = "TD3"
                    result["document_type"] = line1[0] if line1 else ""
                    result["country"] = line1[2:5] if len(line1) >= 5 else ""

                    name_part = line1[5:44] if len(line1) >= 44 else line1[5:]
                    if '<<' in name_part:
                        surname, given = name_part.split('<<', 1)
                        result["surname"] = surname.replace('<', ' ').strip()
                        result["given_name"] = given.replace('<', ' ').strip()

                    if len(line2) >= 28:
                        result["document_number"] = line2[0:9].replace('<', '').strip()
                        result["nationality"] = line2[10:13] if len(line2) >= 13 else ""

                        dob = line2[13:19] if len(line2) >= 19 else ""
                        if dob and dob.isdigit():
                            year = int(dob[0:2])
                            year = 1900 + year if year > 30 else 2000 + year
                            result["date_of_birth"] = f"{year}-{dob[2:4]}-{dob[4:6]}"

                        result["sex"] = line2[20] if len(line2) >= 21 else ""

                        exp = line2[21:27] if len(line2) >= 27 else ""
                        if exp and exp.isdigit():
                            year = 2000 + int(exp[0:2])
                            result["expiry_date"] = f"{year}-{exp[2:4]}-{exp[4:6]}"

                # TD1 (ID Card): 3 lines of 30 characters
                elif len(lines) >= 3 and len(line1) == 30:
                    result["mrz_type"] = "TD1"
                    result["document_type"] = line1[0:2].replace('<', '').strip()
                    result["country"] = line1[2:5]
                    result["document_number"] = line1[5:14].replace('<', '').strip()

                    line3 = lines[2]
                    if '<<' in line3:
                        surname, given = line3.split('<<', 1)
                        result["surname"] = surname.replace('<', ' ').strip()
                        result["given_name"] = given.replace('<', ' ').strip()

                    if len(line2) >= 20:
                        dob = line2[0:6]
                        if dob.isdigit():
                            year = int(dob[0:2])
                            year = 1900 + year if year > 30 else 2000 + year
                            result["date_of_birth"] = f"{year}-{dob[2:4]}-{dob[4:6]}"
                        result["sex"] = line2[7] if len(line2) >= 8 else ""
                        exp = line2[8:14] if len(line2) >= 14 else ""
                        if exp.isdigit():
                            year = 2000 + int(exp[0:2])
                            result["expiry_date"] = f"{year}-{exp[2:4]}-{exp[4:6]}"
                        result["nationality"] = line2[15:18] if len(line2) >= 18 else ""

                # TD2
                elif len(line1) >= 34:
                    result["mrz_type"] = "TD2"
                    result["document_type"] = line1[0:2].replace('<', '').strip()
                    result["country"] = line1[2:5]

                    name_part = line1[5:36] if len(line1) >= 36 else line1[5:]
                    if '<<' in name_part:
                        surname, given = name_part.split('<<', 1)
                        result["surname"] = surname.replace('<', ' ').strip()
                        result["given_name"] = given.replace('<', ' ').strip()

                    if len(line2) >= 28:
                        result["document_number"] = line2[0:9].replace('<', '').strip()
                        result["nationality"] = line2[10:13] if len(line2) >= 13 else ""

        except Exception as e:
            result["parse_error"] = str(e)

        return result

    # =========================================================================
    #  UTILITIES
    # =========================================================================

    def _get_checkdigit(self, input_string: str) -> str:
        """Calculate ICAO 9303 check digit using 7-3-1 weighting."""
        weights = [7, 3, 1]
        total = 0
        for i, char in enumerate(input_string):
            if char.isdigit():
                value = int(char)
            elif char.isalpha():
                value = ord(char.upper()) - ord("A") + 10
            else:
                value = 0
            total += value * weights[i % len(weights)]
        return str(total % 10)

    def _format_date(self, date_str: str) -> str:
        """Convert YYMMDD to YYYY-MM-DD."""
        return str(datetime.strptime(date_str, "%y%m%d").date())

    def _adjust_birth_date(self, birth_date: str, expiry_date: str) -> str:
        """Adjust birth year if it's after expiry year (2-digit year ambiguity)."""
        try:
            birth_year = int(birth_date[:4])
            expiry_year = int(expiry_date[:4])
            if birth_year > expiry_year:
                return f"{birth_year - 100}-{birth_date[5:]}"
        except (ValueError, IndexError):
            pass
        return birth_date

    def mrz_to_text(self, mrz_data: dict) -> str:
        """Convert structured MRZ data to readable text for RAG indexing."""
        if mrz_data.get('status') not in ('SUCCESS', 'WARNING'):
            return ""

        lines = ["[Passport/ID Document]"]

        field_mapping = [
            ('Document Type', ['document_type', 'document_code']),
            ('Country', ['country', 'issuer_code']),
            ('Surname', ['surname']),
            ('Given Name', ['given_name']),
            ('Document Number', ['document_number']),
            ('Nationality', ['nationality', 'nationality_code']),
            ('Date of Birth', ['date_of_birth', 'birth_date']),
            ('Sex', ['sex']),
            ('Expiry Date', ['expiry_date']),
            ('Optional Data', ['optional_data']),
        ]

        for label, keys in field_mapping:
            for key in keys:
                value = mrz_data.get(key)
                if value and str(value).strip() and str(value) != 'None':
                    lines.append(f"{label}: {value}")
                    break

        raw_mrz = mrz_data.get('mrz_text') or mrz_data.get('raw_mrz')
        if raw_mrz:
            lines.append(f"\nRaw MRZ:\n{raw_mrz}")

        return '\n'.join(lines)

    def extract(self, image_data: bytes, filename: str = "image") -> dict:
        """
        Main extraction method. Detects MRZ, extracts data, returns structured result.

        Returns:
            dict with text, has_mrz, mrz_data, rotation_applied, mode
        """
        result = {
            "text": "", "has_mrz": False, "mrz_data": None,
            "rotation_applied": 0, "mode": "none"
        }

        try:
            image = Image.open(io.BytesIO(image_data))
        except Exception as e:
            logger.error(f"[MRZ] Cannot open image: {e}")
            return result

        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')

        # Detect MRZ
        detection = self.detect_mrz(image)
        result["has_mrz"] = detection["has_mrz"]

        if detection["has_mrz"]:
            mrz_data = self.extract_mrz_data(
                image, detection["best_rotation"],
                detected_lines=detection.get("mrz_lines")
            )

            if mrz_data.get('status') in ('SUCCESS', 'WARNING'):
                result["mode"] = "mrz"
                result["mrz_data"] = mrz_data
                result["text"] = self.mrz_to_text(mrz_data)
                result["rotation_applied"] = detection["best_rotation"]
                return result

        # Try ONNX extractor directly as fallback
        if self.onnx_net is not None:
            for rotation in [0, 90, 180, 270]:
                mrz_data = self.extract_mrz_data(image, rotation)
                if mrz_data.get('status') in ('SUCCESS', 'WARNING'):
                    result["mode"] = "mrz"
                    result["has_mrz"] = True
                    result["mrz_data"] = mrz_data
                    result["text"] = self.mrz_to_text(mrz_data)
                    result["rotation_applied"] = rotation
                    return result

        return result
