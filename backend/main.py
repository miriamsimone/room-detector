"""
FastAPI backend for Room Detection Service
Wraps Tanner's Mask R-CNN inference code
"""

import io
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torchvision
from torchvision.models.detection import maskrcnn_resnet50_fpn, MaskRCNN_ResNet50_FPN_Weights
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection.mask_rcnn import MaskRCNNPredictor

app = FastAPI(title="Room Detection API", version="1.0.0")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model (loaded once at startup)
MODEL = None
DEVICE = None
MODEL_PATH = Path(__file__).parent / "maskrcnn_best.pth"


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Room(BaseModel):
    id: str
    bounding_box: list[float]  # [x_min, y_min, x_max, y_max] normalized 0-1000
    bbox_pixels: BoundingBox
    vertices: list[list[float]]
    confidence: float
    name_hint: Optional[str] = None


class DetectionResult(BaseModel):
    image_size: dict
    total_rooms: int
    rooms: list[Room]


def get_maskrcnn_model(num_classes: int = 2):
    """Get Mask R-CNN model architecture."""
    model = maskrcnn_resnet50_fpn(weights=MaskRCNN_ResNet50_FPN_Weights.DEFAULT)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
    model.roi_heads.mask_predictor = MaskRCNNPredictor(in_features_mask, 256, num_classes)
    return model


def compute_iou(box1: dict, box2: dict) -> float:
    """Compute IoU between two bounding boxes."""
    x1 = max(box1['x1'], box2['x1'])
    y1 = max(box1['y1'], box2['y1'])
    x2 = min(box1['x2'], box2['x2'])
    y2 = min(box1['y2'], box2['y2'])
    
    if x2 <= x1 or y2 <= y1:
        return 0.0
    
    intersection = (x2 - x1) * (y2 - y1)
    area1 = (box1['x2'] - box1['x1']) * (box1['y2'] - box1['y1'])
    area2 = (box2['x2'] - box2['x1']) * (box2['y2'] - box2['y1'])
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0.0


def remove_overlapping_rooms(rooms: list, iou_threshold: float = 0.3) -> list:
    """Remove overlapping room detections."""
    if not rooms:
        return rooms
    
    rooms_sorted = sorted(rooms, key=lambda x: x['confidence'], reverse=True)
    kept_rooms = []
    
    for room in rooms_sorted:
        overlaps = False
        for kept in kept_rooms:
            iou = compute_iou(room['bbox_pixels'], kept['bbox_pixels'])
            if iou > iou_threshold:
                overlaps = True
                break
        if not overlaps:
            kept_rooms.append(room)
    
    return kept_rooms


@app.on_event("startup")
async def load_model():
    """Load model at startup."""
    global MODEL, DEVICE
    
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {DEVICE}")
    
    if not MODEL_PATH.exists():
        print(f"WARNING: Model not found at {MODEL_PATH}")
        print("Place maskrcnn_best.pth in the backend directory")
        return
    
    MODEL = get_maskrcnn_model(num_classes=2)
    checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)
    MODEL.load_state_dict(checkpoint['model_state_dict'])
    MODEL.to(DEVICE)
    MODEL.eval()
    print("Model loaded successfully!")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": MODEL is not None,
        "device": str(DEVICE) if DEVICE else None
    }


@app.post("/detect", response_model=DetectionResult)
async def detect_rooms(
    file: UploadFile = File(...),
    threshold: float = 0.7,
    overlap_threshold: float = 0.3
):
    """
    Detect rooms in a blueprint image.
    Returns normalized coordinates (0-1000 range) as per PRD spec.
    """
    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Place maskrcnn_best.pth in backend directory.")
    
    # Read image
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image")
    
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    
    # To tensor
    img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).float() / 255.0
    img_tensor = img_tensor.unsqueeze(0).to(DEVICE)
    
    # Inference
    with torch.no_grad():
        outputs = MODEL(img_tensor)[0]
    
    # Process results
    rooms = []
    for i in range(len(outputs['boxes'])):
        score = outputs['scores'][i].item()
        if score < threshold:
            continue
        
        box = outputs['boxes'][i].cpu().numpy()
        mask = outputs['masks'][i, 0].cpu().numpy()
        
        # Get polygon from mask
        mask_binary = (mask > 0.5).astype(np.uint8)
        contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        vertices = []
        if contours:
            contour = max(contours, key=cv2.contourArea)
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            vertices = approx.reshape(-1, 2).tolist()
        
        # Normalize to 0-1000 range as per PRD
        x_min_norm = float(box[0]) / w * 1000
        y_min_norm = float(box[1]) / h * 1000
        x_max_norm = float(box[2]) / w * 1000
        y_max_norm = float(box[3]) / h * 1000
        
        rooms.append({
            'id': f"room_{uuid.uuid4().hex[:8]}",
            'bounding_box': [
                round(x_min_norm, 1),
                round(y_min_norm, 1),
                round(x_max_norm, 1),
                round(y_max_norm, 1)
            ],
            'bbox_pixels': {
                'x1': float(box[0]),
                'y1': float(box[1]),
                'x2': float(box[2]),
                'y2': float(box[3]),
            },
            'vertices': vertices,
            'confidence': round(score, 3),
            'name_hint': None
        })
    
    # Remove overlapping rooms
    rooms = remove_overlapping_rooms(rooms, iou_threshold=overlap_threshold)
    
    # Re-assign IDs after filtering
    for i, room in enumerate(rooms):
        room['id'] = f"room_{i+1:03d}"
    
    return {
        'image_size': {'width': w, 'height': h},
        'total_rooms': len(rooms),
        'rooms': rooms
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
