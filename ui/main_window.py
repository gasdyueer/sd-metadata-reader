# ui/main_window.py
import os
import pprint # 用于美化打印字典
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QTextEdit, QLineEdit, QLabel,
    QSplitter, QFileDialog, QCheckBox, QListWidgetItem, QScrollArea,
    QMessageBox
)
from PySide6.QtCore import Qt, Slot, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage



# Import from sibling modules/packages
from .widgets import DragDropArea
from core import metadata_parser
from core import file_handler

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SD图像元数据阅读器")
        # self.setWindowIcon(QIcon("assets/icon.png")) # Optional icon
        self.setGeometry(100, 100, 1200, 700) # 设置初始窗口大小
        self.current_search_pattern = None

        self.current_folder_path = None
        self.current_file_list = [] # 已加载文件夹中的文件列表
        self.current_single_file = None
        self.current_metadata_cache = {} # 缓存文件夹视图的元数据{文件路径:元数据}
        self.last_selected_folder = "" # 记住对话框最后选择的文件夹
        self.previous_state = None # 记录返回按钮的先前状态
        self.original_file_list = []  # 保存原始文件列表
        self.current_search_pattern = None

        self.setup_ui()
        self.connect_signals()


    def setup_ui(self):
        # --- Main Layout: Splitter ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5,5,5,5)

        # Top part: Buttons and Options
        left_top_layout = QHBoxLayout()
        self.open_button = QPushButton("打开文件/文件夹")
        self.clear_button = QPushButton("清空")
        self.back_button = QPushButton("返回")
        self.recursive_checkbox = QCheckBox("递归")
        self.recursive_checkbox.setToolTip("搜索子文件夹")
        left_top_layout.addWidget(self.open_button)
        left_top_layout.addWidget(self.clear_button)
        left_top_layout.addWidget(self.back_button)
        left_top_layout.addWidget(self.recursive_checkbox)
        left_top_layout.addStretch()
        left_layout.addLayout(left_top_layout)


        # Drag and Drop Area / File List / Preview
        # Using a container widget to swap between preview and list
        self.left_content_area = QWidget()
        self.left_content_layout = QVBoxLayout(self.left_content_area)
        self.left_content_layout.setContentsMargins(0,0,0,0)

        # Drag/Drop Prompt (initially visible)
        self.drag_drop_widget = DragDropArea()

        # File List (for folders)
        self.file_list_widget = QListWidget()
        self.file_list_widget.setVisible(False) # Initially hidden
        self.file_list_widget.setAlternatingRowColors(True)

        # Image Preview (for single files)
        self.image_preview_label = QLabel("未选择图片")
        self.image_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_label.setMinimumSize(200, 200) # Min preview size
        self.image_preview_scroll = QScrollArea() # 如果图片过大则使预览可滚动
        self.image_preview_scroll.setWidgetResizable(True)
        self.image_preview_scroll.setWidget(self.image_preview_label)
        self.image_preview_scroll.setVisible(False) # Initially hidden


        # Add widgets to the content layout (only one visible at a time usually)
        self.left_content_layout.addWidget(self.drag_drop_widget)
        self.left_content_layout.addWidget(self.file_list_widget)
        self.left_content_layout.addWidget(self.image_preview_scroll)

        left_layout.addWidget(self.left_content_area, stretch=1) # Make content area expand
        main_splitter.addWidget(left_panel)


        # --- Right Panel ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5,5,5,5)

        # Top: Feedback Area (FR-22)
        self.feedback_label = QLabel("日志 & 状态:")
        self.feedback_text = QTextEdit()
        self.feedback_text.setReadOnly(True)
        self.feedback_text.setMaximumHeight(200) # Limit height
        right_layout.addWidget(self.feedback_label)
        right_layout.addWidget(self.feedback_text)


        # Middle: Metadata Display Splitter
        middle_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Middle Left: Metadata Text (FR-12)
        metadata_widget = QWidget()
        metadata_layout = QVBoxLayout(metadata_widget)
        metadata_layout.setContentsMargins(0,0,0,0)
        self.metadata_label = QLabel("元数据:")
        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap) # 允许水平滚动
        metadata_layout.addWidget(self.metadata_label)
        metadata_layout.addWidget(self.metadata_text)
        middle_splitter.addWidget(metadata_widget)


        # Middle Right: ComfyUI Node List (FR-14)
        node_list_widget = QWidget()
        node_list_layout = QVBoxLayout(node_list_widget)
        node_list_layout.setContentsMargins(0,0,0,0)
        self.node_list_label = QLabel("ComfyUI 节点:")
        self.node_list = QListWidget()
        self.node_list.setVisible(False) # 初始隐藏，仅对ComfyUI显示
        self.node_list_label.setVisible(False)
        node_list_layout.addWidget(self.node_list_label)
        node_list_layout.addWidget(self.node_list)
        middle_splitter.addWidget(node_list_widget)

        middle_splitter.setSizes([600, 200]) # Initial sizes for metadata/node list


        # Bottom: Search Area (FR-16, FR-17)
        search_layout = QHBoxLayout()
        self.search_label = QLabel("正则搜索:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入正则表达式...");
        self.search_button = QPushButton("搜索")
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input, stretch=1)
        search_layout.addWidget(self.search_button)

        right_layout.addWidget(middle_splitter, stretch=1) # Make middle area expand
        right_layout.addLayout(search_layout)

        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([300, 900]) # Initial sizes for left/right panels


    def connect_signals(self):
        self.open_button.clicked.connect(self.handle_open)
        self.drag_drop_widget.dropped.connect(self.handle_drop)
        self.file_list_widget.currentItemChanged.connect(self.handle_list_selection_changed)
        self.node_list.currentItemChanged.connect(self.handle_node_selection_changed)
        self.search_button.clicked.connect(self.handle_search)
        self.search_input.returnPressed.connect(self.handle_search) # Allow Enter key for search
        self.clear_button.clicked.connect(self.handle_clear)
        self.back_button.clicked.connect(self.handle_back)


    @Slot()
    def handle_back(self):
        """Handles the Back button click."""
        if self.current_search_pattern:
            if self.previous_state == "folder_view":
                # Restore folder view
                if hasattr(self, 'search_results'):
                    self.update_file_list_widget(list(self.search_results))
                else:
                    self.update_file_list_widget(self.current_file_list)
                self.show_file_list()
                self.clear_displays()  # 返回操作后清除元数据
            elif self.previous_state == "single_file_view":
                # Restore single file view
                if self.current_single_file and self.current_metadata_cache.get(self.current_single_file):
                    self.display_metadata(self.current_metadata_cache[self.current_single_file])
                    self.display_image_preview(self.current_single_file)
            self.current_search_pattern = None
        elif self.current_folder_path:
            self.update_file_list_widget(self.current_file_list)
            self.show_file_list()
            self.clear_displays()  # 返回操作后清除元数据
        else:
            self.show_drag_drop_prompt()


    @Slot()
    def handle_clear(self):
        """Clears the current file/folder and resets the UI."""
        self.log_message("Clearing current file/folder.")
        self.current_folder_path = None
        self.current_single_file = None
        self.current_file_list = []
        self.current_metadata_cache = {}
        self.clear_displays()
        self.show_drag_drop_prompt()

    # --- UI Update Functions ---

    def log_message(self, message):
        self.feedback_text.append(message)
        print(message) # Also print to console for debugging

    def clear_displays(self):
        """Clear all data display areas."""
        self.metadata_text.clear()
        self.node_list.clear()
        self.node_list.setVisible(False)
        self.node_list_label.setVisible(False)
        self.image_preview_label.clear()
        self.image_preview_label.setText("未选择图片") # Changed
        # Don't clear file list here, handled separately

    def show_drag_drop_prompt(self):
        self.drag_drop_widget.setVisible(True)
        self.file_list_widget.setVisible(False)
        self.image_preview_scroll.setVisible(False)

    def show_file_list(self):
        self.drag_drop_widget.setVisible(False)
        self.file_list_widget.setVisible(True)
        self.image_preview_scroll.setVisible(False)

    def show_image_preview(self):
        self.drag_drop_widget.setVisible(False)
        self.file_list_widget.setVisible(False)
        self.image_preview_scroll.setVisible(True)


    def display_metadata(self, metadata: dict):
        """Displays the processed metadata in the UI."""
        self.clear_displays() # Clear previous data first

        if not metadata or metadata.get('error'):
            error_msg = metadata.get('error', 'Unknown error loading metadata.')
            self.metadata_text.setText(f"Error:\n{error_msg}")
            self.log_message(f"Error loading {metadata.get('file_path', 'file')}: {error_msg}")
            return

        # Display Basic Info
        basic_info_str = "Basic Info:\n" + pprint.pformat(metadata.get('basic_info', {}), indent=2)
        # Display Source Type
        source_type = metadata.get('source_type', 'Unknown')
        source_str = f"\n\nSource Type: {source_type}"

        # Display Parsed Data (main content)
        parsed_data = metadata.get('parsed_data', {})
        parsed_str = "\n\nParsed Data:\n"

        # Pretty print parsed data, excluding internal/raw fields for main view
        display_dict = {}
        comfy_nodes_extracted = {}
        for key, value in parsed_data.items():
             if key == '_raw_info_dict': continue
             if key == '_comfy_nodes_extracted':
                 comfy_nodes_extracted = value # Keep nodes for list view
                 continue # Don't print the whole node structure here
             if key == '_Parsing_Errors' and not value: continue # Hide empty error list
             display_dict[key] = value

        parsed_str += pprint.pformat(display_dict, width=1145)
        # 替换部分字符以符合所需格式
        parsed_str = parsed_str.replace("'", "").replace(":", ": ").replace(", ", ",").replace("\\\\", "\\")
        
        # 这段代码用于格式化元数据字符串的显示格式
        # 主要处理两种情况:
        # 1. 包含"Prompt (raw JSON):"的字符串需要特殊处理,保留JSON部分的格式
        # 2. 普通元数据字符串的格式化
        try:
            if "Prompt (raw JSON):" in parsed_str:
                # 按"Prompt (raw JSON):"分割字符串
                parts = parsed_str.split("Prompt (raw JSON):")
                if len(parts) >= 2:
                    # 日志记录
                    # self.log_message(f"Found 'Prompt (raw JSON):' in metadata for {metadata.get('file_path')}")
                    # 处理第一部分(非JSON部分)
                    # 去除首尾行,每行去除空格,用换行符连接
                    parsed_str1 = '{\n' + '\n'.join([line.strip() for line in parts[0].split('\n')[1:-1]]) + '\n}'
                    # 格式化处理:添加换行,替换转义字符
                    parsed_str1 = parsed_str1.replace("{", "{\n").replace("}", "\n}").replace("\\\\n", "\n")
                    # 移除多余的空行
                    parsed_str1 = parsed_str1.replace("\n\n", "\n")
                    
                    # 重新组合两部分
                    parsed_str = parsed_str1 + "Prompt (raw JSON):" + parts[1]
                else:
                    # 处理格式异常的情况,使用通用格式化
                    pass
            else:
                # 处理不包含JSON的普通元数据字符串
                parsed_str = '{\n' + '\n'.join([line.strip() for line in parsed_str.split('\n')[1:-1]]) + '\n}'
                parsed_str = parsed_str.replace("{", "{\n").replace("}", "\n}").replace("\\\\n", "\n")
                parsed_str = parsed_str.replace("\n\n", "\n")
            # 检查字符串中的连续大括号并修复格式
            while "{\n{" in parsed_str1 and "}\n}" in parsed_str1:
                parsed_str1 = parsed_str1.replace("{\n{", "{\n").replace("}\n}", "}\n")
            # positive-prompt的换行处理
            parsed_str = parsed_str.replace("\\n", "\n")
        except Exception as e:
            self.log_message(f"格式化元数据时出错: {e}")
            parsed_str = pprint.pformat(display_dict, width=1145)


        self.metadata_text.setText(basic_info_str + source_str + parsed_str)
        self.log_message(f"已显示元数据: {metadata.get('file_path')}")

        # Populate ComfyUI Node List if available (FR-14)
        # nodes = metadata.get('comfy_nodes', {})
        if comfy_nodes_extracted:
            self.node_list.clear()
            self.node_list_label.setVisible(True)
            self.node_list.setVisible(True)
            for node_title_id, node_data in comfy_nodes_extracted.items():
                 item = QListWidgetItem(node_title_id)
                 # Store the full node data with the item for later retrieval
                 item.setData(Qt.ItemDataRole.UserRole, node_data)
                 self.node_list.addItem(item)
            self.log_message(f"已填充ComfyUI节点列表(共{len(comfy_nodes_extracted)}个节点).")


    def display_image_preview(self, file_path: str):
        """Loads and displays the image preview (FR-03)."""
        try:
            img = QImage(file_path)
            if img.isNull():
                self.image_preview_label.setText("Cannot display preview")
                self.log_message(f"Warning: Could not load QImage for preview: {file_path}")
                return

            pixmap = QPixmap.fromImage(img)
            # Scale pixmap to fit the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.image_preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_preview_label.setPixmap(scaled_pixmap)
            self.show_image_preview()
            self.log_message(f"成功选择并显示图片: {os.path.basename(file_path)}")
            return True

        except Exception as e:
            self.image_preview_label.setText(f"Preview Error:\n{e}")
            self.log_message(f"Error creating preview for {file_path}: {e}")
            self.show_image_preview()


    def update_file_list_widget(self, file_paths: list[str]):
        """Populates the left list widget with file paths."""
        self.file_list_widget.clear()
        self.current_file_list = file_paths # Update internal list
        self.current_metadata_cache = {} # Clear cache when list changes

        if not file_paths:
             self.show_drag_drop_prompt()
             return

        for path in file_paths:
             item = QListWidgetItem(os.path.basename(path))
             item.setData(Qt.ItemDataRole.UserRole, path) # Store full path
             item.setToolTip(path) # Show full path on hover
             self.file_list_widget.addItem(item)

        self.show_file_list()
        # 不再自动选择第一项，让用户自行选择


    # --- Event Handlers / Slots ---

    @Slot()
    def handle_open(self):
        """处理'打开文件/文件夹'按钮点击事件 (FR-02)."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles) # Allow selecting files or a dir
        # Start in the last selected directory or home
        start_dir = self.last_selected_folder if os.path.isdir(self.last_selected_folder) else os.path.expanduser("~")
        dialog.setDirectory(start_dir)

        # Offer image file filters
        image_extensions = "*.png *.jpg *.jpeg *.webp"
        dialog.setNameFilter(f"Images ({image_extensions});;All Files (*)")

        # We need to check if the user selected a directory.
        # PySide doesn't directly support FileDialog.DirectoryOnly *and* FileDialog.ExistingFiles
        # So we allow ExistingFiles and check the result. A simpler alternative is two buttons.
        # Let's try asking the user first.
        
        # 弹出对话框询问用户打开类型
        choice = QMessageBox.question(
            self, 
            "选择打开方式", 
            "请选择打开方式:\n\n是 - 打开单个或多个文件\n否 - 打开文件夹",
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No | 
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )

        # 用户选择打开文件
        if choice == QMessageBox.StandardButton.Yes:
            dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
            if dialog.exec():
                paths = dialog.selectedFiles()
                if paths:
                    # 单文件处理
                    if len(paths) == 1:
                        self.process_single_file(paths[0])
                    # 多文件处理
                    else:
                        self.process_folder(paths, is_explicit_list=True)

        # 用户选择打开文件夹
        elif choice == QMessageBox.StandardButton.No:
            folder_path = QFileDialog.getExistingDirectory(
                self,
                "选择文件夹",
                start_dir
            )
            if folder_path:
                # 记住最后选择的文件夹路径
                self.last_selected_folder = folder_path
                self.process_folder(folder_path)
                
        # 用户取消操作
        else:
            return

    @Slot(list)
    def handle_drop(self, paths: list):
        """Handles files/folders dropped onto the DragDropArea (FR-01)."""
        if not paths:
            return
        self.log_message(f"Dropped: {paths}")

        # Check if it's a single file or folder(s)
        if len(paths) == 1:
            path = paths[0]
            if os.path.isfile(path):
                # Check extension
                 ext = os.path.splitext(path)[1].lower()
                 if ext in file_handler.SUPPORTED_EXTENSIONS:
                     self.process_single_file(path)
                 else:
                     self.log_message(f"Dropped file is not a supported image type: {path}")
                     QMessageBox.warning(self, "不支持的文件类型", f"拖放的文件不是支持的图像类型:\n{os.path.basename(path)}")
            elif os.path.isdir(path):
                self.process_folder(path)
            else:
                 self.log_message(f"Dropped path is neither file nor directory: {path}")

        else: # Multiple items dropped - treat as a folder list
             # Filter only supported files and existing dirs
             valid_paths = []
             folders_to_scan = []
             for p in paths:
                 if os.path.isfile(p) and os.path.splitext(p)[1].lower() in file_handler.SUPPORTED_EXTENSIONS:
                     valid_paths.append(p)
                 elif os.path.isdir(p):
                     folders_to_scan.append(p)

             # If folders were dropped, scan them
             if folders_to_scan:
                  recursive = self.recursive_checkbox.isChecked()
                  for folder in folders_to_scan:
                      valid_paths.extend(file_handler.get_image_files(folder, recursive))
                  self.current_folder_path = folders_to_scan[0] # Use first folder as "context"
             else:
                 self.current_folder_path = None # No real folder context

             self.update_file_list_widget(sorted(list(set(valid_paths)))) # Use set to remove duplicates



    @Slot(QListWidgetItem, QListWidgetItem)
    def handle_list_selection_changed(self, current_item: QListWidgetItem, previous_item: QListWidgetItem = None):
        """Handles selection change in the file list widget (triggers metadata load)."""
        if current_item is None:
            self.clear_displays()
            return

        file_path = current_item.data(Qt.ItemDataRole.UserRole)
        if not file_path or not os.path.isfile(file_path):
            self.log_message(f"Invalid item selected or file not found: {file_path}")
            return

        # 设置状态
        if self.file_list_widget.isVisible():
            self.previous_state = "folder_view" if not self.current_search_pattern else "search_view"

        # Check cache first
        if file_path in self.current_metadata_cache:
             metadata = self.current_metadata_cache[file_path]
        else:
            # Parse metadata (FR-03 automatic trigger)
            self.log_message(f"Parsing metadata for selected file: {os.path.basename(file_path)}")
            metadata = metadata_parser.get_image_metadata(file_path)
            self.current_metadata_cache[file_path] = metadata # Cache the result

        if metadata:
            # 先显示元数据，再显示预览
            self.display_metadata(metadata)
            # 确保预览显示
            self.display_image_preview(file_path)
        else:
             self.clear_displays()
             self.log_message(f"Failed to get metadata for {file_path}")
             # 即使没有元数据，也尝试显示图片预览
             self.display_image_preview(file_path)


    @Slot(QListWidgetItem, QListWidgetItem)
    def handle_node_selection_changed(self, current_item: QListWidgetItem, previous_item: QListWidgetItem = None):
        """Displays details of the selected ComfyUI node (FR-15)."""
        if current_item is None:
            # Optional: Clear metadata text or show generic message?
            # Keep the main metadata visible, maybe just clear node details?
            return

        node_data = current_item.data(Qt.ItemDataRole.UserRole)
        if node_data and isinstance(node_data, dict):
             # Display node details in the main text area (FR-13 option)
             node_details_str = f"Selected Node: {current_item.text()}\n\n"
             node_details_str += pprint.pformat(node_data, indent=2, width=120)
             self.metadata_text.setText(node_details_str) # Overwrite main text area
             self.log_message(f"Displayed details for node: {current_item.text()}")


    @Slot()
    def handle_search(self):
        """Handles the Search button click or Enter key in search input."""
        pattern = self.search_input.text()
        if not pattern:
            self.log_message("搜索取消：未输入搜索模式")
            if self.current_folder_path or self.file_list_widget.count() > 0:
                self.update_file_list_widget(self.current_file_list)
            return

        self.log_message(f"开始搜索，模式: {pattern}")
        matching_files = set()
        total_matches = 0
        files_searched = 0

        # 获取需要搜索的文件列表
        if self.current_folder_path:
            folder_path = self.current_folder_path
            recursive = self.recursive_checkbox.isChecked()
            image_files = file_handler.get_image_files(folder_path, recursive)
        elif self.current_single_file:
            image_files = [self.current_single_file]
        else:
            image_files = [self.file_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.file_list_widget.count())]

        # 搜索所有文件的元数据
        result_str = "搜索结果:\n"
        for file_path in image_files:
            if not file_path:
                continue

            files_searched += 1
            # 获取元数据
            if file_path in self.current_metadata_cache:
                metadata = self.current_metadata_cache[file_path]
            else:
                self.log_message(f"正在解析文件元数据: {os.path.basename(file_path)}")
                metadata = metadata_parser.get_image_metadata(file_path)
                self.current_metadata_cache[file_path] = metadata

            if metadata:
                if metadata.get('error'):
                    self.log_message(f"解析元数据出错: {os.path.basename(file_path)} - {metadata.get('error')}")
                else:
                    search_results = metadata_parser.search_metadata(metadata, pattern)
                    if search_results:
                        matching_files.add(file_path)
                        matches_count = sum([len(x[1]) for x in search_results])
                        total_matches += matches_count
                        result_str += f"\n文件: {os.path.basename(file_path)}"  # 添加匹配的文件名
                        for path, match in search_results:
                            result_str += f"\n  - 在 {path} 中找到: {match}"
                        result_str += "\n"

        # 更新界面显示
        self.log_message(f"搜索完成。在 {len(matching_files)} 个文件中找到 {total_matches} 个匹配项（共搜索 {files_searched} 个文件）。")

        if not matching_files:
            QMessageBox.information(self, "搜索结果", f"未找到包含以下模式的文件:\n{pattern}")
            result_str += "\n未找到匹配项"
        else:
            # 更新文件列表和搜索结果显示
            self.search_results = matching_files  # 保存搜索结果
            self.update_file_list_widget(sorted(list(matching_files)))
            self.show_file_list()  # 确保显示文件列表而不是图片预览

        # 在右侧文本框显示搜索结果
        self.metadata_text.setText(result_str)
        self.current_search_pattern = pattern

        if not self.current_single_file and not self.current_folder_path:
            self.log_message("Search ignored: No single file or folder loaded.")


    # --- File/Folder Processing Logic ---

    def process_single_file(self, file_path: str):
        """Loads and displays a single image file."""
        self.log_message(f"Processing single file: {file_path}")
        self.current_single_file = file_path
        self.current_folder_path = None
        self.current_file_list = []
        self.current_metadata_cache = {} # Reset cache for single file view

        # Parse metadata (FR-03)
        metadata = metadata_parser.get_image_metadata(file_path)
        self.current_metadata_cache[file_path] = metadata  # Store in cache
        self.original_file_list = self.current_file_list  # 保存原始文件列表

        if metadata:
            self.display_metadata(metadata)
            self.display_image_preview(file_path)  # Also show preview
        else:
            self.clear_displays()
            self.show_image_preview()  # Show preview area with error potentially
            self.log_message(f"Failed to process single file: {file_path}")


    def process_folder(self, path_or_list, is_explicit_list=False):
        """Loads and displays the contents of a folder or a list of files."""
        self.current_single_file = None # Clear single file context
        self.clear_displays() # Clear right panel

        if is_explicit_list and isinstance(path_or_list, list):
             self.log_message(f"Processing explicit list of {len(path_or_list)} files.")
             image_files = sorted([p for p in path_or_list if os.path.isfile(p) and os.path.splitext(p)[1].lower() in file_handler.SUPPORTED_EXTENSIONS])
             self.current_folder_path = None # No single base folder
        elif isinstance(path_or_list, str) and os.path.isdir(path_or_list):
             folder_path = path_or_list
             self.log_message(f"Processing folder: {folder_path}")
             self.current_folder_path = folder_path
             recursive = self.recursive_checkbox.isChecked() # FR-04a
             self.log_message(f"Recursive search: {'Enabled' if recursive else 'Disabled'}")
             # FR-04b: Get files using file_handler
             # TODO: Consider background thread for large folders (NFR-07)
             image_files = file_handler.get_image_files(folder_path, recursive)
             self.log_message(f"Found {len(image_files)} image files.")
        else:
             self.log_message(f"Invalid path provided to process_folder: {path_or_list}")
             self.show_drag_drop_prompt()
             return


        # FR-04c: Update list view
        self.update_file_list_widget(image_files)
        self.original_file_list = image_files  # 保存原始文件列表
        if not image_files:
            # FR-04d: Handle empty folder or no supported images
            self.log_message("在指定位置未找到支持的图像文件.")
            self.show_drag_drop_prompt() # Show drag/drop if list is empty
            QMessageBox.information(self, "空", "在选定位置未找到支持的图像文件.")
        self.show_file_list() # 确保文件列表可见
