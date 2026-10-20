import os
from typing import List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QCheckBox,
    QLabel,
    QComboBox,
    QSpinBox,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
)
from .canvas import OverlayImageItem


class DeckboxSidebar(QWidget):
    open_project_requested = Signal()
    save_project_requested = Signal()
    export_pdf_requested = Signal()
    prev_page_requested = Signal()
    next_page_requested = Signal()
    dimensions_changed = Signal()
    add_image_requested = Signal()
    layer_selected = Signal(object)
    layers_reordered = Signal()
    layer_removed = Signal(object)
    layer_duplicated = Signal(object)
    labels_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(290)
        self.syncing_selection = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        proj_group = QGroupBox("Project")
        proj_layout = QHBoxLayout(proj_group)
        self.btn_open_proj = QPushButton("Open")
        self.btn_open_proj.clicked.connect(self.open_project_requested.emit)
        self.btn_save_proj = QPushButton("Save")
        self.btn_save_proj.clicked.connect(self.save_project_requested.emit)
        proj_layout.addWidget(self.btn_open_proj)
        proj_layout.addWidget(self.btn_save_proj)
        layout.addWidget(proj_group)

        self.btn_download = QPushButton("Download PDF (300 DPI)")
        self.btn_download.clicked.connect(self.export_pdf_requested.emit)
        layout.addWidget(self.btn_download)

        page_ctrl_layout = QHBoxLayout()
        self.lbl_page_status = QLabel("Page 1 of 1")
        self.btn_prev_page = QPushButton("<")
        self.btn_next_page = QPushButton(">")
        self.btn_prev_page.clicked.connect(self.prev_page_requested.emit)
        self.btn_next_page.clicked.connect(self.next_page_requested.emit)
        page_ctrl_layout.addWidget(self.btn_prev_page)
        page_ctrl_layout.addWidget(self.lbl_page_status)
        page_ctrl_layout.addWidget(self.btn_next_page)
        layout.addLayout(page_ctrl_layout)

        form_layout = QFormLayout()

        self.combo_card_type = QComboBox()
        self.combo_card_type.addItems(
            ["Custom", "Standard (MTG/Pokemon)", "Japanese (Yugioh)"]
        )
        self.combo_card_type.currentIndexChanged.connect(
            self._handle_card_preset_change
        )
        form_layout.addRow("CARD TYPE", self.combo_card_type)

        self.spin_card_height = QSpinBox()
        self.spin_card_height.setRange(20, 300)
        self.spin_card_height.setValue(89)
        self.spin_card_height.setSuffix(" mm")
        self.spin_card_height.valueChanged.connect(
            lambda _: self.dimensions_changed.emit()
        )
        form_layout.addRow("CARD HEIGHT", self.spin_card_height)

        self.spin_card_width = QSpinBox()
        self.spin_card_width.setRange(20, 300)
        self.spin_card_width.setValue(64)
        self.spin_card_width.setSuffix(" mm")
        self.spin_card_width.valueChanged.connect(
            lambda _: self.dimensions_changed.emit()
        )
        form_layout.addRow("CARD WIDTH", self.spin_card_width)

        self.spin_box_depth = QSpinBox()
        self.spin_box_depth.setRange(5, 200)
        self.spin_box_depth.setValue(23)
        self.spin_box_depth.setSuffix(" mm")
        self.spin_box_depth.valueChanged.connect(
            lambda _: self.dimensions_changed.emit()
        )
        form_layout.addRow("BOX DEPTH", self.spin_box_depth)

        layout.addLayout(form_layout)

        self.chk_labels = QCheckBox("Show Panel Labels")
        self.chk_labels.setChecked(True)
        self.chk_labels.toggled.connect(self.labels_toggled.emit)
        layout.addWidget(self.chk_labels)

        img_group = QGroupBox("Artwork Layers")
        img_layout = QVBoxLayout(img_group)

        self.btn_load_image = QPushButton("Add Image Layer")
        self.btn_load_image.clicked.connect(self.add_image_requested.emit)
        img_layout.addWidget(self.btn_load_image)

        self.layer_list = QListWidget()
        self.layer_list.setFixedHeight(140)
        self.layer_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.layer_list.currentRowChanged.connect(self._handle_list_row_changed)
        self.layer_list.model().rowsMoved.connect(lambda: self.layers_reordered.emit())
        img_layout.addWidget(self.layer_list)

        order_btns_layout = QHBoxLayout()
        self.btn_move_up = QPushButton("Up")
        self.btn_move_down = QPushButton("Down")
        self.btn_duplicate = QPushButton("Dup")
        self.btn_delete_layer = QPushButton("Del")

        self.btn_move_up.clicked.connect(self._move_layer_up)
        self.btn_move_down.clicked.connect(self._move_layer_down)
        self.btn_duplicate.clicked.connect(self._duplicate_layer)
        self.btn_delete_layer.clicked.connect(self._remove_layer)

        order_btns_layout.addWidget(self.btn_move_up)
        order_btns_layout.addWidget(self.btn_move_down)
        order_btns_layout.addWidget(self.btn_duplicate)
        order_btns_layout.addWidget(self.btn_delete_layer)
        img_layout.addLayout(order_btns_layout)

        help_label = QLabel(
            "Controls:\n"
            "- Drag & drop images onto canvas\n"
            "- Reorder layers in list (top is front)\n"
            "- Mouse wheel: scale image / zoom\n"
            "- Ctrl + Mouse wheel: smooth rotate\n"
            "- Press 'R': rotate image 90°\n"
            "- Template renders above artwork"
        )
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        img_layout.addWidget(help_label)

        layout.addWidget(img_group)

    def _handle_card_preset_change(self):
        preset = self.combo_card_type.currentText()
        if preset == "Standard (MTG/Pokemon)":
            self.spin_card_width.setValue(66)
            self.spin_card_height.setValue(91)
        elif preset == "Japanese (Yugioh)":
            self.spin_card_width.setValue(62)
            self.spin_card_height.setValue(89)

    def _handle_list_row_changed(self, row: int):
        if self.syncing_selection or row < 0:
            return
        list_item = self.layer_list.item(row)
        if list_item:
            self.layer_selected.emit(list_item.data(Qt.ItemDataRole.UserRole))

    def _move_layer_up(self):
        curr_row = self.layer_list.currentRow()
        if curr_row > 0:
            self.layer_list.blockSignals(True)
            take_item = self.layer_list.takeItem(curr_row)
            self.layer_list.insertItem(curr_row - 1, take_item)
            self.layer_list.setCurrentRow(curr_row - 1)
            self.layer_list.blockSignals(False)
            self.layers_reordered.emit()

    def _move_layer_down(self):
        curr_row = self.layer_list.currentRow()
        if 0 <= curr_row < self.layer_list.count() - 1:
            self.layer_list.blockSignals(True)
            take_item = self.layer_list.takeItem(curr_row)
            self.layer_list.insertItem(curr_row + 1, take_item)
            self.layer_list.setCurrentRow(curr_row + 1)
            self.layer_list.blockSignals(False)
            self.layers_reordered.emit()

    def _duplicate_layer(self):
        curr_row = self.layer_list.currentRow()
        if curr_row < 0 and self.layer_list.selectedItems():
            curr_row = self.layer_list.row(self.layer_list.selectedItems()[0])

        if curr_row >= 0:
            list_item = self.layer_list.item(curr_row)
            target_item = list_item.data(Qt.ItemDataRole.UserRole)
            if target_item:
                self.layer_duplicated.emit(target_item)

    def _remove_layer(self):
        curr_row = self.layer_list.currentRow()
        if curr_row >= 0:
            list_item = self.layer_list.item(curr_row)
            target_item = list_item.data(Qt.ItemDataRole.UserRole)
            self.layer_list.takeItem(curr_row)
            self.layer_removed.emit(target_item)
            self.layers_reordered.emit()

    def update_page_status(self, current_page: int, total_pages: int):
        self.lbl_page_status.setText(f"Page {current_page + 1} of {total_pages}")
        self.btn_prev_page.setEnabled(current_page > 0)
        self.btn_next_page.setEnabled(current_page < total_pages - 1)

    def update_layer_list(self, image_items: List[OverlayImageItem]):
        self.layer_list.blockSignals(True)
        self.layer_list.clear()

        for item in reversed(image_items):
            file_name = (
                os.path.basename(item.file_path) if item.file_path else "Untitled Layer"
            )
            list_item = QListWidgetItem(file_name)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.layer_list.addItem(list_item)
            if item.isSelected():
                list_item.setSelected(True)

        self.layer_list.blockSignals(False)

    def sync_selection(self, selected_items: set):
        self.syncing_selection = True
        self.layer_list.blockSignals(True)
        active_row = -1
        for idx in range(self.layer_list.count()):
            list_item = self.layer_list.item(idx)
            item_ref = list_item.data(Qt.ItemDataRole.UserRole)
            is_selected = item_ref in selected_items
            list_item.setSelected(is_selected)
            if is_selected:
                active_row = idx

        if active_row >= 0:
            self.layer_list.setCurrentRow(active_row)

        self.layer_list.blockSignals(False)
        self.syncing_selection = False

    def get_ordered_layer_items(self) -> List[OverlayImageItem]:
        ordered = []
        for idx in range(self.layer_list.count()):
            list_item = self.layer_list.item(idx)
            item = list_item.data(Qt.ItemDataRole.UserRole)
            if item:
                ordered.append(item)
        return ordered

    def set_dimension_values(self, width: float, height: float, depth: float):
        self.spin_card_width.blockSignals(True)
        self.spin_card_height.blockSignals(True)
        self.spin_box_depth.blockSignals(True)

        self.spin_card_width.setValue(width)
        self.spin_card_height.setValue(height)
        self.spin_box_depth.setValue(depth)

        self.spin_card_width.blockSignals(False)
        self.spin_card_height.blockSignals(False)
        self.spin_box_depth.blockSignals(False)

    def get_dimensions(self) -> tuple[float, float, float]:
        return (
            float(self.spin_card_width.value()),
            float(self.spin_card_height.value()),
            float(self.spin_box_depth.value()),
        )
