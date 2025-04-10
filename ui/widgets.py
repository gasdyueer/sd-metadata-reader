# ui/widgets.py
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent

class DragDropArea(QLabel):
    """ A QLabel that accepts drag and drop for files/folders. """
    dropped = Signal(list) # Emits a list of file/folder paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setText("Drag & Drop Image or Folder Here\nor use 'Open' button")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("color: grey; ") # Basic styling


    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setText("Drop Here!")
            self.setStyleSheet("color: black; font-weight: bold; ")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setText("Drag & Drop Image or Folder Here\nor use 'Open' button")
        self.setStyleSheet("color: grey; ")
        event.accept()


    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if paths:
            self.dropped.emit(paths) # Emit signal with dropped paths
        self.setText("Drag & Drop Image or Folder Here\nor use 'Open' button")
        self.setStyleSheet("color: grey; ")
        event.acceptProposedAction()

from PySide6.QtWidgets import QVBoxLayout # Add missing import at the top if needed
