from typing import List
from PySide6.QtCore import QRectF, QMarginsF
from PySide6.QtGui import QPageSize, QPageLayout, QPdfWriter, QPainter
from .models import PAGE_WIDTH_MM, PAGE_HEIGHT_MM
from .canvas import DeckboxScene


def export_scenes_to_pdf(scenes: List[DeckboxScene], target_path: str):
    if not scenes or not target_path:
        return

    pdf_writer = QPdfWriter(target_path)
    pdf_writer.setResolution(300)

    page_layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.Letter),
        QPageLayout.Orientation.Portrait,
        QMarginsF(0.0, 0.0, 0.0, 0.0),
        QPageLayout.Unit.Millimeter,
    )
    pdf_writer.setPageLayout(page_layout)

    painter = QPainter(pdf_writer)
    scale_ratio = 300.0 / 25.4
    painter.scale(scale_ratio, scale_ratio)

    page_rect = QRectF(0.0, 0.0, PAGE_WIDTH_MM, PAGE_HEIGHT_MM)

    # Hide label overlays prior to printing and restore their state afterward
    prior_visibilities = [scene.labels_visible for scene in scenes]
    for scene in scenes:
        scene.label_group.setVisible(False)

    for idx, scene in enumerate(scenes):
        if idx > 0:
            pdf_writer.newPage()
        scene.render(painter, page_rect, page_rect)

    painter.end()

    for idx, scene in enumerate(scenes):
        scene.label_group.setVisible(prior_visibilities[idx])
