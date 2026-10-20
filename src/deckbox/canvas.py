import os
from typing import Dict, Any, List
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QPixmap,
    QWheelEvent,
    QKeyEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsItemGroup,
    QGraphicsSimpleTextItem,
    QGraphicsItem,
)
from .models import PageGeometry, PAGE_WIDTH_MM, PAGE_HEIGHT_MM

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


class OverlayImageItem(QGraphicsPixmapItem):
    def __init__(self, pixmap: QPixmap, file_path: str = ""):
        super().__init__(pixmap)
        self.file_path = file_path
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setZValue(1.0)
        pixmap_bounds = self.boundingRect()
        self.setTransformOriginPoint(pixmap_bounds.center())

    def adjust_scale(self, factor: float):
        self.setScale(max(0.01, self.scale() * factor))

    def adjust_rotation(self, angle_degrees: float):
        self.setRotation(self.rotation() + angle_degrees)

    def to_dict(self) -> Dict[str, Any]:
        pos = self.pos()
        return {
            "file_path": self.file_path,
            "x": pos.x(),
            "y": pos.y(),
            "scale": self.scale(),
            "rotation": self.rotation(),
            "z_value": self.zValue(),
        }


class DeckboxScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_rect = QRectF(0.0, 0.0, PAGE_WIDTH_MM, PAGE_HEIGHT_MM)

        # Give the canvas a margin so the paper floats centered inside the workspace
        margin = 35.0
        self.setSceneRect(
            -margin,
            -margin,
            PAGE_WIDTH_MM + (2.0 * margin),
            PAGE_HEIGHT_MM + (2.0 * margin),
        )

        self.cut_item = QGraphicsPathItem()
        self.fold_item = QGraphicsPathItem()
        self.label_group = QGraphicsItemGroup()
        self.labels_visible = True

        self.setup_template_layers()

    def setup_template_layers(self):
        cut_pen = QPen(QColor(220, 40, 40))
        cut_pen.setWidthF(0.6)
        cut_pen.setCosmetic(False)
        self.cut_item.setPen(cut_pen)
        self.cut_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.cut_item.setZValue(100.0)

        fold_pen = QPen(QColor(30, 160, 50))
        fold_pen.setWidthF(0.6)
        fold_pen.setCosmetic(False)
        self.fold_item.setPen(fold_pen)
        self.fold_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.fold_item.setZValue(100.0)

        self.label_group.setZValue(120.0)

        self.addItem(self.cut_item)
        self.addItem(self.fold_item)
        self.addItem(self.label_group)

    def update_template(self, geometry: PageGeometry):
        self.cut_item.setPath(geometry.cut_path)
        self.fold_item.setPath(geometry.fold_path)

        for child in list(self.label_group.childItems()):
            self.label_group.removeFromGroup(child)
            self.removeItem(child)

        label_font = QFont("Sans", 6, QFont.Weight.Bold)
        label_brush = QBrush(QColor(70, 70, 70, 160))

        for label_data in geometry.labels:
            text_item = QGraphicsSimpleTextItem(label_data.text)
            text_item.setFont(label_font)
            text_item.setBrush(label_brush)

            text_bounds = text_item.boundingRect()
            center_x = label_data.rect.center().x() - (text_bounds.width() / 2.0)
            center_y = label_data.rect.center().y() - (text_bounds.height() / 2.0)
            text_item.setPos(center_x, center_y)

            self.label_group.addToGroup(text_item)

        self.label_group.setVisible(self.labels_visible)

    def set_labels_visible(self, visible: bool):
        self.labels_visible = visible
        self.label_group.setVisible(visible)

    def get_image_items(self) -> List[OverlayImageItem]:
        image_items = [
            item for item in self.items() if isinstance(item, OverlayImageItem)
        ]
        image_items.sort(key=lambda item: item.zValue())
        return image_items

    def clear_images(self):
        for item in self.get_image_items():
            self.removeItem(item)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        # 1. Fill entire visible canvas area with dark gray
        painter.fillRect(rect, QColor(35, 35, 38))

        # 2. Fill the actual paper sheet area with solid white
        painter.fillRect(self.page_rect, QColor(255, 255, 255))

        # 3. Draw a subtle edge border around the paper
        page_border_pen = QPen(QColor(60, 60, 65))
        page_border_pen.setWidthF(0.4)
        painter.setPen(page_border_pen)
        painter.drawRect(self.page_rect)


class DeckboxView(QGraphicsView):
    files_dropped = Signal(list, QPointF)

    def __init__(self, scene=None, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(
            self.renderHints()
            | QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        # Style the surrounding widget viewport dark
        self.setStyleSheet("background-color: #232326; border: none;")

    def drawBackground(self, painter: QPainter, rect: QRectF):
        # 1. Fill surrounding workspace canvas with dark gray
        painter.fillRect(rect, QColor(35, 35, 38))

        # 2. Fill the actual paper sheet with solid white
        current_scene = self.scene()
        if current_scene and hasattr(current_scene, "page_rect"):
            painter.fillRect(current_scene.page_rect, QColor(255, 255, 255))

            # 3. Subtle page outline
            page_border_pen = QPen(QColor(60, 60, 65))
            page_border_pen.setWidthF(0.4)
            painter.setPen(page_border_pen)
            painter.drawRect(current_scene.page_rect)

    def _extract_image_paths(self, mime_data) -> List[str]:
        image_paths = []
        if mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile():
                    local_path = url.toLocalFile()
                    _, ext = os.path.splitext(local_path)
                    if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                        image_paths.append(local_path)
        return image_paths

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self._extract_image_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        if self._extract_image_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        paths = self._extract_image_paths(event.mimeData())
        if paths:
            self.files_dropped.emit(paths, None)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_R:
            current_scene = self.scene()
            if current_scene:
                selected_items = current_scene.selectedItems()
                target_images = [
                    item
                    for item in selected_items
                    if isinstance(item, OverlayImageItem)
                ]
                if target_images:
                    for target_item in target_images:
                        target_item.adjust_rotation(90.0)
                else:
                    self.rotate(90.0)
            else:
                self.rotate(90.0)
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        current_scene = self.scene()
        if not current_scene:
            event.ignore()
            return

        selected_items = current_scene.selectedItems()
        target_images = [
            item for item in selected_items if isinstance(item, OverlayImageItem)
        ]

        if target_images:
            num_degrees = event.angleDelta().y() / 8.0
            num_steps = num_degrees / 15.0
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                rotation_step = 5.0 if num_steps > 0 else -5.0
                for target_item in target_images:
                    target_item.adjust_rotation(rotation_step)
            else:
                scale_factor = 1.05 if num_steps > 0 else 0.95
                for target_item in target_images:
                    target_item.adjust_scale(scale_factor)
            event.accept()
        else:
            zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
            self.scale(zoom_factor, zoom_factor)
            event.accept()
