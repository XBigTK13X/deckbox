import os
import json
from typing import Dict, Any, List
from .canvas import DeckboxScene, OverlayImageItem


def save_project(
    file_path: str,
    card_width: float,
    card_height: float,
    box_depth: float,
    scenes: List[DeckboxScene],
):
    pages_payload = []
    for scene in scenes:
        page_images = [item.to_dict() for item in scene.get_image_items()]
        pages_payload.append({"images": page_images})

    project_data = {
        "version": 1,
        "dimensions": {
            "card_width": card_width,
            "card_height": card_height,
            "box_depth": box_depth,
        },
        "pages": pages_payload,
    }

    with open(file_path, "w", encoding="utf-8") as file_handle:
        json.dump(project_data, file_handle, indent=2)


def load_project(file_path: str) -> Dict[str, Any]:
    if not os.path.isfile(file_path):
        return {}

    with open(file_path, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def restore_scenes_from_project(
    project_data: Dict[str, Any], scenes: List[DeckboxScene]
):
    pages_data = project_data.get("pages", [])
    for page_idx, page_info in enumerate(pages_data):
        if page_idx >= len(scenes):
            break
        scene = scenes[page_idx]
        scene.clear_images()

        for img_record in page_info.get("images", []):
            img_path = img_record.get("file_path", "")
            if os.path.isfile(img_path):
                from PySide6.QtGui import QPixmap

                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    item = OverlayImageItem(pixmap, file_path=img_path)
                    item.setPos(img_record.get("x", 0.0), img_record.get("y", 0.0))
                    item.setScale(img_record.get("scale", 1.0))
                    item.setRotation(img_record.get("rotation", 0.0))
                    item.setZValue(img_record.get("z_value", 1.0))
                    scene.addItem(item)
