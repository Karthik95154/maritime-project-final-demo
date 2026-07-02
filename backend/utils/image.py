import cv2
import numpy as np
import requests
import os

def load_image(path_or_url: str):
    """
    Loads an image either from a local file path or a remote HTTP URL.
    Returns a numpy array (cv2 image).
    """
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        response = requests.get(path_or_url)
        if response.status_code == 200:
            image_array = np.asarray(bytearray(response.content), dtype="uint8")
            return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        else:
            raise Exception(f"Failed to download image from {path_or_url}, status code: {response.status_code}")
    else:
        if not os.path.exists(path_or_url):
            raise Exception(f"Local file not found: {path_or_url}")
        return cv2.imread(path_or_url)

