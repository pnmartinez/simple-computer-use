import cv2
import numpy as np
import matplotlib.pyplot as plt
import tempfile
import logging

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def visualize_detections(image_path, detections, output_path=None):
    """Visualize detections on image"""
    if isinstance(image_path, str):
        image = cv2.imread(image_path)
    else:
        image = image_path
    
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    plt.figure(figsize=(16, 10))
    plt.imshow(image_rgb)
    
    # Draw bounding boxes for all detections
    for det in detections:
        bbox = det['bbox']
        label = det.get('text', det.get('type', 'unknown'))
        confidence = det.get('confidence', 0)
        
        x_min, y_min, x_max, y_max = bbox
        
        # Different colors for different types
        if 'type' in det:
            if det['type'] == 'button':
                color = 'red'
            elif det['type'] == 'input_field':
                color = 'blue'
            elif det['type'] == 'menu_item':
                color = 'green'
            else:
                color = 'yellow'
        else:
            color = 'white'
        
        # Draw rectangle
        plt.gca().add_patch(plt.Rectangle((x_min, y_min), x_max - x_min, y_max - y_min, 
                                         fill=False, edgecolor=color, linewidth=2))
        
        # Draw label
        plt.text(x_min, y_min - 5, f"{label} ({confidence:.2f})", 
                 bbox={'facecolor': color, 'alpha': 0.5, 'pad': 2})
    
    plt.axis('off')
    
    if output_path:
        plt.savefig(output_path, bbox_inches='tight')
        return output_path
    else:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            plt.savefig(tmp.name, bbox_inches='tight')
            plt.close()
            return tmp.name
