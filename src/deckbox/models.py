from dataclasses import dataclass
from typing import List
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QTransform


PAGE_WIDTH_MM = 215.9
PAGE_HEIGHT_MM = 279.4
PRINT_MARGIN_MM = 10.0
DEFAULT_FLAP_SIZE_MM = 10.0
DEFAULT_HOLE_RADIUS_MM = 10.0


@dataclass
class PanelLabel:
    text: str
    rect: QRectF


@dataclass
class BoxDimensions:
    card_width: float
    card_height: float
    box_depth: float
    flap_size: float = DEFAULT_FLAP_SIZE_MM
    hole_radius: float = DEFAULT_HOLE_RADIUS_MM


@dataclass
class PageGeometry:
    cut_path: QPainterPath
    fold_path: QPainterPath
    bounding_rect: QRectF
    labels: List[PanelLabel]


def _build_full_template(
    dims: BoxDimensions,
) -> tuple[QPainterPath, QPainterPath, List[PanelLabel]]:
    cut_path = QPainterPath()
    fold_path = QPainterPath()

    width_val = dims.card_width
    height_val = dims.card_height
    depth_val = dims.box_depth
    flap_val = dims.flap_size
    hole_rad = dims.hole_radius
    chamfer = min(flap_val * 0.4, 4.0)

    # 4 consecutive body panels: RIGHT, BACK, LEFT, FRONT + Glue Flap
    x_right = 0.0
    x_back = depth_val
    x_left = depth_val + width_val
    x_front = (2.0 * depth_val) + width_val
    total_w = (2.0 * depth_val) + (2.0 * width_val)

    # Vertical fold lines
    fold_path.moveTo(x_back, 0.0)
    fold_path.lineTo(x_back, height_val)

    fold_path.moveTo(x_left, 0.0)
    fold_path.lineTo(x_left, height_val)

    fold_path.moveTo(x_front, 0.0)
    fold_path.lineTo(x_front, height_val)

    # Horizontal fold lines
    fold_path.moveTo(0.0, 0.0)
    fold_path.lineTo(x_front, 0.0)

    fold_path.moveTo(0.0, height_val)
    fold_path.lineTo(total_w, height_val)

    # Top Tuck Flap folds on BACK panel
    fold_path.moveTo(x_back, -depth_val)
    fold_path.lineTo(x_back + width_val, -depth_val)

    # Top cuts
    cut_path.moveTo(x_right, 0.0)
    cut_path.lineTo(x_right + chamfer, -flap_val)
    cut_path.lineTo(x_back - chamfer, -flap_val)
    cut_path.lineTo(x_back, 0.0)

    # Top panel & tuck flap attached to BACK
    cut_path.lineTo(x_back, -depth_val)
    cut_path.lineTo(x_back + chamfer, -depth_val - flap_val)
    cut_path.lineTo(x_back + width_val - chamfer, -depth_val - flap_val)
    cut_path.lineTo(x_back + width_val, -depth_val)
    cut_path.lineTo(x_back + width_val, 0.0)

    # LEFT top dust flap
    cut_path.lineTo(x_left + chamfer, -flap_val)
    cut_path.lineTo(x_front - chamfer, -flap_val)
    cut_path.lineTo(x_front, 0.0)

    # FRONT panel thumb notch
    notch_center_x = x_front + (width_val / 2.0)
    effective_notch_rad = min(hole_rad, (width_val / 2.0) - 2.0)
    if effective_notch_rad > 0.0:
        cut_path.lineTo(notch_center_x - effective_notch_rad, 0.0)
        cut_path.arcTo(
            notch_center_x - effective_notch_rad,
            -effective_notch_rad,
            effective_notch_rad * 2.0,
            effective_notch_rad * 2.0,
            180.0,
            180.0,
        )
    cut_path.lineTo(total_w, 0.0)

    # Rightmost glue flap on FRONT
    fold_path.moveTo(total_w, 0.0)
    fold_path.lineTo(total_w, height_val)
    cut_path.lineTo(total_w + flap_val, chamfer)
    cut_path.lineTo(total_w + flap_val, height_val - chamfer)
    cut_path.lineTo(total_w, height_val)

    # Bottom cuts
    # FRONT bottom: attaches BOTTOM panel and tuck flap
    fold_path.moveTo(x_front, height_val + depth_val)
    fold_path.lineTo(total_w, height_val + depth_val)
    cut_path.lineTo(total_w, height_val + depth_val)
    cut_path.lineTo(total_w - chamfer, height_val + depth_val + flap_val)
    cut_path.lineTo(x_front + chamfer, height_val + depth_val + flap_val)
    cut_path.lineTo(x_front, height_val + depth_val)
    cut_path.lineTo(x_front, height_val)

    # LEFT bottom flap
    cut_path.lineTo(x_front - chamfer, height_val + flap_val)
    cut_path.lineTo(x_left + chamfer, height_val + flap_val)
    cut_path.lineTo(x_left, height_val)

    # BACK bottom: flush cut
    cut_path.lineTo(x_back, height_val)

    # RIGHT bottom flap
    cut_path.lineTo(x_back - chamfer, height_val + flap_val)
    cut_path.lineTo(x_right + chamfer, height_val + flap_val)
    cut_path.lineTo(x_right, height_val)
    cut_path.lineTo(x_right, 0.0)

    labels = [
        PanelLabel("RIGHT", QRectF(x_right, 0.0, depth_val, height_val)),
        PanelLabel("BACK", QRectF(x_back, 0.0, width_val, height_val)),
        PanelLabel("TOP", QRectF(x_back, -depth_val, width_val, depth_val)),
        PanelLabel("LEFT", QRectF(x_left, 0.0, depth_val, height_val)),
        PanelLabel("FRONT", QRectF(x_front, 0.0, width_val, height_val)),
        PanelLabel("BOTTOM", QRectF(x_front, height_val, width_val, depth_val)),
    ]

    return cut_path, fold_path, labels


def _build_half_piece_back(
    dims: BoxDimensions,
) -> tuple[QPainterPath, QPainterPath, List[PanelLabel]]:
    # Piece 1: RIGHT + BACK + TOP panel
    cut_path = QPainterPath()
    fold_path = QPainterPath()

    width_val = dims.card_width
    height_val = dims.card_height
    depth_val = dims.box_depth
    flap_val = dims.flap_size
    chamfer = min(flap_val * 0.4, 4.0)

    x_right = 0.0
    x_back = depth_val
    x_edge = depth_val + width_val

    # Folds
    fold_path.moveTo(x_back, 0.0)
    fold_path.lineTo(x_back, height_val)

    fold_path.moveTo(0.0, 0.0)
    fold_path.lineTo(x_edge, 0.0)

    fold_path.moveTo(0.0, height_val)
    fold_path.lineTo(x_back, height_val)

    fold_path.moveTo(x_back, -depth_val)
    fold_path.lineTo(x_edge, -depth_val)

    # Cuts
    cut_path.moveTo(x_right, 0.0)
    cut_path.lineTo(x_right + chamfer, -flap_val)
    cut_path.lineTo(x_back - chamfer, -flap_val)
    cut_path.lineTo(x_back, 0.0)

    # TOP panel & tuck flap
    cut_path.lineTo(x_back, -depth_val)
    cut_path.lineTo(x_back + chamfer, -depth_val - flap_val)
    cut_path.lineTo(x_edge - chamfer, -depth_val - flap_val)
    cut_path.lineTo(x_edge, -depth_val)
    cut_path.lineTo(x_edge, 0.0)

    # Side glue flap
    fold_path.moveTo(x_edge, 0.0)
    fold_path.lineTo(x_edge, height_val)
    cut_path.lineTo(x_edge + flap_val, chamfer)
    cut_path.lineTo(x_edge + flap_val, height_val - chamfer)
    cut_path.lineTo(x_edge, height_val)

    # Flush bottom cut for BACK
    cut_path.lineTo(x_back, height_val)

    # RIGHT bottom flap
    cut_path.lineTo(x_back - chamfer, height_val + flap_val)
    cut_path.lineTo(x_right + chamfer, height_val + flap_val)
    cut_path.lineTo(x_right, height_val)
    cut_path.lineTo(x_right, 0.0)

    labels = [
        PanelLabel("RIGHT", QRectF(x_right, 0.0, depth_val, height_val)),
        PanelLabel("BACK", QRectF(x_back, 0.0, width_val, height_val)),
        PanelLabel("TOP", QRectF(x_back, -depth_val, width_val, depth_val)),
    ]

    return cut_path, fold_path, labels


def _build_half_piece_front(
    dims: BoxDimensions,
) -> tuple[QPainterPath, QPainterPath, List[PanelLabel]]:
    # Piece 2: LEFT + FRONT + BOTTOM panel + thumb notch
    cut_path = QPainterPath()
    fold_path = QPainterPath()

    width_val = dims.card_width
    height_val = dims.card_height
    depth_val = dims.box_depth
    flap_val = dims.flap_size
    hole_rad = dims.hole_radius
    chamfer = min(flap_val * 0.4, 4.0)

    x_left = 0.0
    x_front = depth_val
    x_edge = depth_val + width_val

    # Folds
    fold_path.moveTo(x_front, 0.0)
    fold_path.lineTo(x_front, height_val)

    fold_path.moveTo(0.0, 0.0)
    fold_path.lineTo(x_front, 0.0)

    fold_path.moveTo(0.0, height_val)
    fold_path.lineTo(x_edge, height_val)

    # Cuts
    cut_path.moveTo(x_left, 0.0)
    cut_path.lineTo(x_left + chamfer, -flap_val)
    cut_path.lineTo(x_front - chamfer, -flap_val)
    cut_path.lineTo(x_front, 0.0)

    # FRONT thumb notch
    notch_center_x = x_front + (width_val / 2.0)
    effective_notch_rad = min(hole_rad, (width_val / 2.0) - 2.0)
    if effective_notch_rad > 0.0:
        cut_path.lineTo(notch_center_x - effective_notch_rad, 0.0)
        cut_path.arcTo(
            notch_center_x - effective_notch_rad,
            -effective_notch_rad,
            effective_notch_rad * 2.0,
            effective_notch_rad * 2.0,
            180.0,
            180.0,
        )
    cut_path.lineTo(x_edge, 0.0)

    # Side glue flap
    fold_path.moveTo(x_edge, 0.0)
    fold_path.lineTo(x_edge, height_val)
    cut_path.lineTo(x_edge + flap_val, chamfer)
    cut_path.lineTo(x_edge + flap_val, height_val - chamfer)
    cut_path.lineTo(x_edge, height_val)

    # BOTTOM panel & tuck flap attached to FRONT
    fold_path.moveTo(x_front, height_val + depth_val)
    fold_path.lineTo(x_edge, height_val + depth_val)
    cut_path.lineTo(x_edge, height_val + depth_val)
    cut_path.lineTo(x_edge - chamfer, height_val + depth_val + flap_val)
    cut_path.lineTo(x_front + chamfer, height_val + depth_val + flap_val)
    cut_path.lineTo(x_front, height_val + depth_val)
    cut_path.lineTo(x_front, height_val)

    # LEFT bottom flap
    cut_path.lineTo(x_front - chamfer, height_val + flap_val)
    cut_path.lineTo(x_left + chamfer, height_val + flap_val)
    cut_path.lineTo(x_left, height_val)
    cut_path.lineTo(x_left, 0.0)

    labels = [
        PanelLabel("LEFT", QRectF(x_left, 0.0, depth_val, height_val)),
        PanelLabel("FRONT", QRectF(x_front, 0.0, width_val, height_val)),
        PanelLabel("BOTTOM", QRectF(x_front, height_val, width_val, depth_val)),
    ]

    return cut_path, fold_path, labels


def _center_path_on_page(
    cut_path: QPainterPath,
    fold_path: QPainterPath,
    labels: List[PanelLabel],
    rotation_deg: float = 0.0,
) -> PageGeometry:
    bounds = cut_path.boundingRect().united(fold_path.boundingRect())
    target_x = (PAGE_WIDTH_MM - bounds.width()) / 2.0 - bounds.left()
    target_y = (PAGE_HEIGHT_MM - bounds.height()) / 2.0 - bounds.top()

    centered_cut = cut_path.translated(target_x, target_y)
    centered_fold = fold_path.translated(target_x, target_y)

    transform = QTransform()
    if rotation_deg != 0.0:
        transform.rotate(rotation_deg)
    transform.translate(target_x, target_y)

    transformed_labels = []
    for label in labels:
        mapped_rect = transform.mapRect(label.rect)
        transformed_labels.append(PanelLabel(text=label.text, rect=mapped_rect))

    return PageGeometry(
        cut_path=centered_cut,
        fold_path=centered_fold,
        bounding_rect=centered_cut.boundingRect().united(centered_fold.boundingRect()),
        labels=transformed_labels,
    )


def calculate_pages(dims: BoxDimensions) -> List[PageGeometry]:
    max_w = PAGE_WIDTH_MM - (2.0 * PRINT_MARGIN_MM)
    max_h = PAGE_HEIGHT_MM - (2.0 * PRINT_MARGIN_MM)

    full_cut, full_fold, full_labels = _build_full_template(dims)
    full_bounds = full_cut.boundingRect().united(full_fold.boundingRect())

    if full_bounds.width() <= max_w and full_bounds.height() <= max_h:
        return [_center_path_on_page(full_cut, full_fold, full_labels)]

    rotation_transform = QTransform().rotate(90.0)
    rot_cut = rotation_transform.map(full_cut)
    rot_fold = rotation_transform.map(full_fold)
    rot_bounds = rot_cut.boundingRect().united(rot_fold.boundingRect())

    if rot_bounds.width() <= max_w and rot_bounds.height() <= max_h:
        return [_center_path_on_page(rot_cut, rot_fold, full_labels, rotation_deg=90.0)]

    cut_back, fold_back, labels_back = _build_half_piece_back(dims)
    cut_front, fold_front, labels_front = _build_half_piece_front(dims)

    return [
        _center_path_on_page(cut_back, fold_back, labels_back),
        _center_path_on_page(cut_front, fold_front, labels_front),
    ]
