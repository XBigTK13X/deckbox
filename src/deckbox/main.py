import sys
import signal
from typing import List, Optional
from PySide6.QtCore import QTimer, QPointF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QFileDialog,
)
from .models import (
    BoxDimensions,
    PageGeometry,
    calculate_pages,
    PAGE_WIDTH_MM,
    PAGE_HEIGHT_MM,
)
from .canvas import DeckboxScene, DeckboxView, OverlayImageItem
from .sidebar import DeckboxSidebar
from .project import save_project, load_project, restore_scenes_from_project
from .exporter import export_scenes_to_pdf


class DeckboxGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Deckbox Generator")
        self.resize(1240, 900)

        self.current_page_index = 0
        self.pages_data: List[PageGeometry] = []
        self.page_scenes: List[DeckboxScene] = []
        self.current_project_path = ""
        self.show_labels = True

        self.view = DeckboxView(None, self)
        self.sidebar = DeckboxSidebar(self)

        self._setup_layout()
        self._connect_signals()
        self.refresh_geometry()

    def _setup_layout(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.view, stretch=1)

    def _connect_signals(self):
        self.view.files_dropped.connect(self.add_images_to_active_scene)

        self.sidebar.open_project_requested.connect(self.open_project_dialog)
        self.sidebar.save_project_requested.connect(self.save_project_dialog)
        self.sidebar.export_pdf_requested.connect(self.export_pdf)
        self.sidebar.prev_page_requested.connect(self.prev_page)
        self.sidebar.next_page_requested.connect(self.next_page)
        self.sidebar.dimensions_changed.connect(self.refresh_geometry)
        self.sidebar.labels_toggled.connect(self.handle_labels_toggled)
        self.sidebar.add_image_requested.connect(self.load_image_dialog)
        self.sidebar.layer_selected.connect(self.handle_layer_selected)
        self.sidebar.layers_reordered.connect(self.sync_z_values_from_sidebar)
        self.sidebar.layer_removed.connect(self.handle_layer_removed)
        self.sidebar.layer_duplicated.connect(self.handle_layer_duplicated)

    def handle_labels_toggled(self, checked: bool):
        self.show_labels = checked
        for scene in self.page_scenes:
            scene.set_labels_visible(checked)

    def refresh_geometry(self):
        card_w, card_h, box_d = self.sidebar.get_dimensions()
        dims = BoxDimensions(card_width=card_w, card_height=card_h, box_depth=box_d)
        self.pages_data = calculate_pages(dims)
        num_pages = len(self.pages_data)

        while len(self.page_scenes) < num_pages:
            new_scene = DeckboxScene(self)
            new_scene.set_labels_visible(self.show_labels)
            new_scene.selectionChanged.connect(self.handle_scene_selection_changed)
            self.page_scenes.append(new_scene)
        while len(self.page_scenes) > num_pages:
            self.page_scenes.pop()

        for idx, page_geom in enumerate(self.pages_data):
            self.page_scenes[idx].update_template(page_geom)
            self.page_scenes[idx].set_labels_visible(self.show_labels)

        if self.current_page_index >= num_pages:
            self.current_page_index = 0

        self.switch_to_page(self.current_page_index)

    def switch_to_page(self, index: int):
        self.current_page_index = index
        self.view.setScene(self.page_scenes[index])
        self.sidebar.update_page_status(index, len(self.page_scenes))
        self.sidebar.update_layer_list(self.page_scenes[index].get_image_items())

    def prev_page(self):
        if self.current_page_index > 0:
            self.switch_to_page(self.current_page_index - 1)

    def next_page(self):
        if self.current_page_index < len(self.page_scenes) - 1:
            self.switch_to_page(self.current_page_index + 1)

    def handle_scene_selection_changed(self):
        active_scene = self.page_scenes[self.current_page_index]
        self.sidebar.sync_selection(set(active_scene.selectedItems()))

    def handle_layer_selected(self, target_item):
        active_scene = self.page_scenes[self.current_page_index]
        active_scene.clearSelection()
        if target_item:
            target_item.setSelected(True)

    def handle_layer_removed(self, target_item):
        if target_item:
            active_scene = self.page_scenes[self.current_page_index]
            active_scene.removeItem(target_item)

    def handle_layer_duplicated(self, source_item: OverlayImageItem):
        if not source_item:
            return

        active_scene = self.page_scenes[self.current_page_index]
        existing_images = active_scene.get_image_items()
        max_z = max([item.zValue() for item in existing_images], default=0.0)

        cloned_item = OverlayImageItem(
            source_item.pixmap(), file_path=source_item.file_path
        )
        cloned_item.setScale(source_item.scale())
        cloned_item.setRotation(source_item.rotation())
        cloned_item.setZValue(max_z + 1.0)

        orig_pos = source_item.pos()
        cloned_item.setPos(orig_pos.x() + 10.0, orig_pos.y() + 10.0)

        active_scene.clearSelection()
        active_scene.addItem(cloned_item)
        cloned_item.setSelected(True)

        self.sidebar.update_layer_list(active_scene.get_image_items())

    def sync_z_values_from_sidebar(self):
        ordered_items = self.sidebar.get_ordered_layer_items()
        total_items = len(ordered_items)
        for idx, item in enumerate(ordered_items):
            item.setZValue(float(total_items - idx))

    def add_images_to_active_scene(self, file_paths: List[str]):
        if not file_paths or not self.page_scenes:
            return

        active_scene = self.page_scenes[self.current_page_index]
        existing_images = active_scene.get_image_items()
        max_z = max([item.zValue() for item in existing_images], default=0.0)
        base_z = max_z + 1.0

        center_pt = active_scene.page_rect.center()

        active_scene.clearSelection()

        for idx, file_path in enumerate(file_paths):
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                item = OverlayImageItem(pixmap, file_path=file_path)
                item.setZValue(base_z + idx)

                base_scale = 100.0 / max(pixmap.width(), pixmap.height())
                item.setScale(base_scale)

                raw_center = item.boundingRect().center()
                item.setPos(
                    center_pt.x() - raw_center.x() + (idx * 5.0),
                    center_pt.y() - raw_center.y() + (idx * 5.0),
                )

                active_scene.addItem(item)
                item.setSelected(True)

        self.sidebar.update_layer_list(active_scene.get_image_items())
        self.view.setFocus()

    def load_image_dialog(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Artwork", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_paths:
            self.add_images_to_active_scene(file_paths)

    def save_project_dialog(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            self.current_project_path or "deckbox_project.json",
            "Project Files (*.json)",
        )
        if not file_path:
            return

        card_w, card_h, box_d = self.sidebar.get_dimensions()
        save_project(file_path, card_w, card_h, box_d, self.page_scenes)
        self.current_project_path = file_path

    def open_project_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "Project Files (*.json)"
        )
        if not file_path:
            return

        project_data = load_project(file_path)
        if not project_data:
            return

        dims = project_data.get("dimensions", {})
        self.sidebar.set_dimension_values(
            dims.get("card_width", 64),
            dims.get("card_height", 89),
            dims.get("box_depth", 23),
        )
        self.refresh_geometry()

        restore_scenes_from_project(project_data, self.page_scenes)
        self.sidebar.update_layer_list(
            self.page_scenes[self.current_page_index].get_image_items()
        )
        self.current_project_path = file_path

    def export_pdf(self):
        target_path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "deckbox_letter_300dpi.pdf", "PDF Files (*.pdf)"
        )
        if target_path:
            export_scenes_to_pdf(self.page_scenes, target_path)


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)

    sigint_timer = QTimer()
    sigint_timer.timeout.connect(lambda: None)
    sigint_timer.start(250)

    window = DeckboxGeneratorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
