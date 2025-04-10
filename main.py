# main.py
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon # 可选
from qt_material import apply_stylesheet # 导入 qt_material

# 确保本地导入正常工作
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # NFR-02: 应用 qt_material 主题
    theme_path = os.path.join(os.path.dirname(__file__), "themes", "light_pink_500.xml")
    try:
        if os.path.exists(theme_path):
             apply_stylesheet(app, theme=theme_path)
             print(f"应用主题: {theme_path}")
        else:
             # 如果 XML 丢失，则回退到默认的内置主题
             print(f"警告: 在 {theme_path} 未找到主题文件. 应用默认的 light_blue.")
             apply_stylesheet(app, theme='light_blue.xml')
    except Exception as e:
        print(f"应用主题时出错: {e}. 使用默认样式.")


    # 可选: 设置应用程序图标
    # icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    # if os.path.exists(icon_path):
    #    app.setWindowIcon(QIcon(icon_path))

    # 创建并显示主窗口
    window = MainWindow()
    window.show() # NFR-03: 标准窗口控件是 QMainWindow 的一部分

    # NFR-06: 启动事件循环以实现响应
    sys.exit(app.exec())