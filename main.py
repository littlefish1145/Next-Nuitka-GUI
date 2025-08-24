# nuitka_gui_packer.py
# -*- coding: utf-8 -*-
"""
基于QFluentWidgets和PyQt5的Nuitka可视化打包工具 V5
优化版本：
1. 恢复原UI样式
2. 通过更多标签页分散设置
3. 保留虚拟环境支持
4. 优化界面大小
"""

import sys
import os
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings, QProcess, QProcessEnvironment
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QFileDialog, QTextEdit, QGridLayout, QGroupBox,
                             QSizePolicy, QLabel, QStackedWidget, QTableWidgetItem)
from PyQt5.QtGui import QIcon, QFont, QTextCursor

from qfluentwidgets import (FluentWindow, NavigationInterface, NavigationItemPosition,
                            FluentIcon, PushButton, PrimaryPushButton, SwitchButton,
                            LineEdit, ComboBox, SpinBox, TextEdit, PlainTextEdit,
                            CardWidget, ExpandLayout, SettingCardGroup,
                            SubtitleLabel, BodyLabel, CaptionLabel, StrongBodyLabel,
                            InfoBar, InfoBarPosition, MessageBox, Dialog,
                            TableWidget, CommandBar, Action, ProgressBar,
                            CheckBox, RadioButton, Slider, ToolButton,
                            IconWidget, SearchLineEdit, ToggleButton,
                            setTheme, Theme, setThemeColor, isDarkTheme,
                            Pivot, qconfig, TabBar, TabCloseButtonDisplayMode)


class PackageThread(QThread):
    """打包线程"""
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, command, env=None, cwd=None):
        super().__init__()
        self.command = command
        self.env = env
        self.cwd = cwd
        self.process = None

    def run(self):
        try:
            self.output_signal.emit(f"执行命令：\n{self.command}\n")
            if self.cwd:
                self.output_signal.emit(f"工作目录：{self.cwd}\n")
            self.output_signal.emit("-" * 50 + "\n")

            # 准备环境变量
            env = os.environ.copy()
            if self.env:
                env.update(self.env)

            # 使用subprocess执行命令
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
                cwd=self.cwd
            )

            # 实时读取输出
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self.output_signal.emit(line)

                    # 尝试解析进度
                    if "%" in line:
                        try:
                            percent = int(line.split("%")[0].split()[-1])
                            self.progress_signal.emit(percent)
                        except:
                            pass

            self.process.wait()

            if self.process.returncode == 0:
                self.finished_signal.emit(True, "打包成功完成！")
            else:
                self.finished_signal.emit(False, f"打包失败，返回代码：{self.process.returncode}")

        except Exception as e:
            self.finished_signal.emit(False, f"打包出错：{str(e)}")

    def stop(self):
        if self.process:
            self.process.terminate()


class PythonEnvironmentInterface(QWidget):
    """Python环境设置界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # Python环境卡片
        self.pythonCard = CardWidget(self)
        self.pythonLayout = QVBoxLayout(self.pythonCard)
        self.pythonLayout.setSpacing(12)
        self.pythonLayout.setContentsMargins(20, 20, 20, 20)

        self.pythonTitleLabel = SubtitleLabel("Python解释器", self)
        self.pythonLayout.addWidget(self.pythonTitleLabel)

        # Python路径选择
        self.pythonSelectLayout = QHBoxLayout()
        self.pythonEdit = LineEdit(self)
        self.pythonEdit.setPlaceholderText("选择Python解释器（留空使用系统Python）")
        self.pythonButton = PushButton("浏览", self)
        self.pythonButton.clicked.connect(self.selectPython)
        self.detectButton = PushButton("自动检测（Python模式下可用）", self)
        self.detectButton.clicked.connect(self.detectPython)

        self.pythonSelectLayout.addWidget(self.pythonEdit, 1)
        self.pythonSelectLayout.addWidget(self.pythonButton)
        self.pythonSelectLayout.addWidget(self.detectButton)
        self.pythonLayout.addLayout(self.pythonSelectLayout)

        # Python信息
        self.pythonInfoLabel = CaptionLabel("未选择Python解释器", self)
        self.pythonLayout.addWidget(self.pythonInfoLabel)

        self.mainLayout.addWidget(self.pythonCard)

        # Nuitka状态卡片
        self.nuitkaCard = CardWidget(self)
        self.nuitkaLayout = QVBoxLayout(self.nuitkaCard)
        self.nuitkaLayout.setSpacing(12)
        self.nuitkaLayout.setContentsMargins(20, 20, 20, 20)

        self.nuitkaTitleLabel = SubtitleLabel("Nuitka状态", self)
        self.nuitkaLayout.addWidget(self.nuitkaTitleLabel)

        # Nuitka检查
        self.nuitkaCheckLayout = QHBoxLayout()
        self.nuitkaStatusLabel = BodyLabel("状态：未检测", self)
        self.checkNuitkaButton = PushButton("检查Nuitka", self)
        self.checkNuitkaButton.clicked.connect(self.checkNuitka)

        self.nuitkaCheckLayout.addWidget(self.nuitkaStatusLabel, 1)
        self.nuitkaCheckLayout.addWidget(self.checkNuitkaButton)
        self.nuitkaLayout.addLayout(self.nuitkaCheckLayout)

        # Nuitka版本信息
        self.nuitkaVersionLabel = CaptionLabel("", self)
        self.nuitkaLayout.addWidget(self.nuitkaVersionLabel)

        self.mainLayout.addWidget(self.nuitkaCard)

        # 说明卡片
        self.infoCard = CardWidget(self)
        self.infoLayout = QVBoxLayout(self.infoCard)
        self.infoLayout.setContentsMargins(20, 20, 20, 20)

        self.infoTitleLabel = SubtitleLabel("使用说明", self)
        self.infoLayout.addWidget(self.infoTitleLabel)

        self.infoTextLabel = BodyLabel(
            "• 选择虚拟环境中的Python可使用该环境的Nuitka\n"
            "• 留空将使用系统默认Python和Nuitka\n"
            "• 如果Nuitka未安装，请在对应环境中运行：pip install nuitka",
            self
        )
        self.infoLayout.addWidget(self.infoTextLabel)

        self.mainLayout.addWidget(self.infoCard)
        self.mainLayout.addStretch()

    def selectPython(self):
        """选择Python解释器"""
        file, _ = QFileDialog.getOpenFileName(
            self, "选择Python解释器", "",
            "Python (python.exe python);;All Files (*)")
        if file:
            self.pythonEdit.setText(file)
            self.updatePythonInfo()
            self.checkNuitka()

    def detectPython(self):
        """自动检测当前Python"""
        try:
            # 检查是否是打包后的exe文件
            if getattr(sys, 'frozen', False):
                # 如果是打包后的exe，尝试查找系统Python
                import shutil
                python_path = shutil.which('python')
                if not python_path:
                    # 如果找不到python命令，尝试查找python.exe
                    python_path = shutil.which('python.exe')
                if python_path:
                    self.pythonEdit.setText(python_path)
                else:
                    # 如果还是找不到，使用sys.executable并给出警告
                    python_path = sys.executable
                    self.pythonEdit.setText(python_path)
                    InfoBar.warning(
                        title='警告',
                        content='检测到打包后的exe文件，但未找到系统Python。\n可能会导致Nuitka检测失败。',
                        position=InfoBarPosition.TOP_RIGHT,
                        parent=self
                    )
            else:
                # 正常模式下使用sys.executable
                python_path = sys.executable
                self.pythonEdit.setText(python_path)

            self.updatePythonInfo()
            self.checkNuitka()
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'检测Python失败：{str(e)}',
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )

    def updatePythonInfo(self):
        """更新Python信息显示"""
        python_path = self.pythonEdit.text()
        if python_path:
            try:
                # 获取Python版本
                result = subprocess.run(
                    [python_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version_info = result.stdout.strip()
                    self.pythonInfoLabel.setText(f"已选择：{version_info}")
                    self.pythonInfoLabel.setStyleSheet("color: green")
                else:
                    self.pythonInfoLabel.setText("无效的Python解释器")
                    self.pythonInfoLabel.setStyleSheet("color: red")
            except:
                self.pythonInfoLabel.setText("无法获取Python信息")
                self.pythonInfoLabel.setStyleSheet("color: orange")
        else:
            self.pythonInfoLabel.setText("未选择Python解释器")
            self.pythonInfoLabel.setStyleSheet("")

    def checkNuitka(self):
        """检查Nuitka是否安装"""
        python_path = self.pythonEdit.text() or 'python'

        try:
            # 检查Nuitka版本
            result = subprocess.run(
                [python_path, '-m', 'nuitka', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                version_info = result.stdout.strip()
                self.nuitkaStatusLabel.setText("状态：已安装")
                self.nuitkaStatusLabel.setStyleSheet("color: green")

                # 提取版本号
                for line in version_info.split('\n'):
                    if 'Version' in line or 'Nuitka' in line:
                        self.nuitkaVersionLabel.setText(line)
                        break
            else:
                self.nuitkaStatusLabel.setText("状态：未安装")
                self.nuitkaStatusLabel.setStyleSheet("color: red")
                self.nuitkaVersionLabel.setText("请在Python环境中安装Nuitka")

        except subprocess.TimeoutExpired:
            self.nuitkaStatusLabel.setText("状态：检查超时")
            self.nuitkaStatusLabel.setStyleSheet("color: orange")
            self.nuitkaVersionLabel.setText("")
        except Exception as e:
            self.nuitkaStatusLabel.setText(f"状态：检查失败")
            self.nuitkaStatusLabel.setStyleSheet("color: red")
            self.nuitkaVersionLabel.setText(str(e))

    def getNuitkaCommand(self):
        """获取Nuitka命令"""
        python_path = self.pythonEdit.text()
        if python_path:
            # 使用指定的Python运行Nuitka模块
            return f'"{python_path}" -m nuitka'
        else:
            # 使用系统nuitka命令
            return 'nuitka'


class AssetsInterface(QWidget):
    """资源文件管理界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 资源文件卡片
        self.assetsCard = CardWidget(self)
        self.assetsLayout = QVBoxLayout(self.assetsCard)
        self.assetsLayout.setSpacing(12)
        self.assetsLayout.setContentsMargins(20, 20, 20, 20)

        self.assetsTitleLabel = SubtitleLabel("资源文件", self)
        self.assetsLayout.addWidget(self.assetsTitleLabel)

        # 资源文件表格
        self.assetsTable = TableWidget(self)
        self.assetsTable.setColumnCount(4)
        self.assetsTable.setHorizontalHeaderLabels(['包含', '源路径', '目标路径', '类型'])
        self.assetsTable.setColumnWidth(0, 60)
        self.assetsTable.setColumnWidth(1, 300)
        self.assetsTable.setColumnWidth(2, 200)
        self.assetsTable.setColumnWidth(3, 80)
        self.assetsTable.setSelectionBehavior(TableWidget.SelectRows)
        self.assetsTable.setDragDropMode(TableWidget.DragDrop)
        self.assetsTable.setAlternatingRowColors(True)

        # 设置拖拽支持
        self.assetsTable.setAcceptDrops(True)
        self.assetsTable.dragEnterEvent = self.dragEnterEvent
        self.assetsTable.dragMoveEvent = self.dragMoveEvent
        self.assetsTable.dropEvent = self.dropEvent

        self.assetsLayout.addWidget(self.assetsTable)

        # 按钮布局
        self.buttonLayout = QHBoxLayout()

        self.addFileButton = PushButton("添加文件", self)
        self.addFileButton.clicked.connect(self.addFile)

        self.addFolderButton = PushButton("添加文件夹", self)
        self.addFolderButton.clicked.connect(self.addFolder)

        self.removeButton = PushButton("移除选中", self)
        self.removeButton.clicked.connect(self.removeSelected)

        self.clearButton = PushButton("清空全部", self)
        self.clearButton.clicked.connect(self.clearAll)

        self.buttonLayout.addWidget(self.addFileButton)
        self.buttonLayout.addWidget(self.addFolderButton)
        self.buttonLayout.addWidget(self.removeButton)
        self.buttonLayout.addWidget(self.clearButton)
        self.buttonLayout.addStretch()

        self.assetsLayout.addLayout(self.buttonLayout)

        # 说明信息
        self.infoLabel = CaptionLabel(
            "拖拽文件或文件夹到表格中添加资源\n"
            "支持设置相对路径，目标路径留空则使用默认路径",
            self
        )
        self.assetsLayout.addWidget(self.infoLabel)

        self.mainLayout.addWidget(self.assetsCard)
        self.mainLayout.addStretch()

        # 设置右键菜单
        self.assetsTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.assetsTable.customContextMenuRequested.connect(self.showContextMenu)

    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """拖拽放置事件"""
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        for file_path in files:
            if os.path.exists(file_path):
                if os.path.isdir(file_path):
                    # 如果是文件夹，递归添加其中的内容
                    self.addAssetRecursive(file_path)
                else:
                    # 如果是文件，直接添加
                    self.addAsset(file_path)

    def showContextMenu(self, pos):
        """显示右键菜单"""
        menu = RoundMenu(self)

        removeAction = Action(FIF.DELETE, "移除选中", self)
        removeAction.triggered.connect(self.removeSelected)

        clearAction = Action(FIF.CLEAR_SELECTION, "清空全部", self)
        clearAction.triggered.connect(self.clearAll)

        menu.addAction(removeAction)
        menu.addAction(clearAction)
        menu.exec(self.assetsTable.mapToGlobal(pos))

    def addFile(self):
        """添加文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "", "所有文件 (*.*)")
        for file_path in files:
            self.addAsset(file_path)

    def addFolder(self):
        """添加文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.addAssetRecursive(folder)

    def addAssetRecursive(self, path, relative_path=""):
        """递归添加资源文件夹"""
        if not path:
            return

        # 如果是文件夹，递归处理其中的文件和子文件夹
        if os.path.isdir(path):
            # 添加文件夹本身
            self.addAsset(path, relative_path if relative_path else os.path.basename(path))

            # 递归处理子文件和子文件夹
            try:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    new_relative_path = os.path.join(relative_path, item) if relative_path else item
                    self.addAssetRecursive(item_path, new_relative_path)
            except Exception as e:
                print(f"遍历文件夹 {path} 时出错: {e}")
        else:
            # 如果是文件，直接添加
            self.addAsset(path, relative_path if relative_path else os.path.basename(path))

    def addAsset(self, path, target_path=None):
        """添加资源"""
        if not path:
            return

        # 检查是否已存在
        for row in range(self.assetsTable.rowCount()):
            item = self.assetsTable.item(row, 1)
            if item and item.text() == path:
                return

        # 添加新行
        row = self.assetsTable.rowCount()
        self.assetsTable.insertRow(row)

        # 包含复选框
        checkbox = CheckBox(self)
        checkbox.setChecked(True)
        self.assetsTable.setCellWidget(row, 0, checkbox)

        # 源路径
        source_item = QTableWidgetItem(path)
        source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
        self.assetsTable.setItem(row, 1, source_item)

        # 目标路径
        if target_path is None:
            target_name = os.path.basename(path)
        else:
            target_name = target_path
        target_item = QTableWidgetItem(target_name)
        self.assetsTable.setItem(row, 2, target_item)

        # 类型
        type_text = "文件" if os.path.isfile(path) else "文件夹"
        type_item = QTableWidgetItem(type_text)
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        self.assetsTable.setItem(row, 3, type_item)

    def removeSelected(self):
        """移除选中的资源"""
        selected_rows = []
        for item in self.assetsTable.selectedItems():
            if item.row() not in selected_rows:
                selected_rows.append(item.row())

        # 从后往前删除，避免索引问题
        for row in sorted(selected_rows, reverse=True):
            self.assetsTable.removeRow(row)

    def clearAll(self):
        """清空所有资源"""
        self.assetsTable.setRowCount(0)

    def getSelectedAssets(self):
        """获取选中的资源列表"""
        assets = []
        for row in range(self.assetsTable.rowCount()):
            checkbox = self.assetsTable.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                source = self.assetsTable.item(row, 1).text()
                target = self.assetsTable.item(row, 2).text()
                type_text = self.assetsTable.item(row, 3).text()
                assets.append({
                    'source': source,
                    'target': target,
                    'type': type_text
                })
        return assets

    def getAssets(self):
        """获取所有资源列表，用于配置保存"""
        assets = []
        for row in range(self.assetsTable.rowCount()):
            checkbox = self.assetsTable.cellWidget(row, 0)
            source = self.assetsTable.item(row, 1).text()
            target = self.assetsTable.item(row, 2).text()
            type_text = self.assetsTable.item(row, 3).text()

            # 将中文类型转换为英文类型
            asset_type = 'file' if type_text == '文件' else 'folder'

            assets.append({
                'enabled': checkbox.isChecked() if checkbox else True,
                'source': source,
                'target': target,
                'type': asset_type
            })
        return assets

    def setAssets(self, assets):
        """设置资源列表，用于配置加载"""
        self.clearAll()
        for asset in assets:
            if not asset.get('source'):
                continue

            row = self.assetsTable.rowCount()
            self.assetsTable.insertRow(row)

            # 包含复选框
            checkbox = CheckBox(self)
            checkbox.setChecked(asset.get('enabled', True))
            self.assetsTable.setCellWidget(row, 0, checkbox)

            # 源路径
            source = asset.get('source', '')
            source_item = QTableWidgetItem(source)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.assetsTable.setItem(row, 1, source_item)

            # 目标路径
            target = asset.get('target', os.path.basename(source))
            target_item = QTableWidgetItem(target)
            self.assetsTable.setItem(row, 2, target_item)

            # 类型
            asset_type = asset.get('type', 'file')
            type_text = '文件' if asset_type == 'file' else '文件夹'
            type_item = QTableWidgetItem(type_text)
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.assetsTable.setItem(row, 3, type_item)


class BasicSettingsInterface(QWidget):
    """基础设置界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # Python文件选择卡片
        self.fileCard = CardWidget(self)
        self.fileLayout = QVBoxLayout(self.fileCard)
        self.fileLayout.setSpacing(12)
        self.fileLayout.setContentsMargins(20, 20, 20, 20)

        self.fileTitleLabel = SubtitleLabel("Python文件", self)
        self.fileLayout.addWidget(self.fileTitleLabel)

        self.fileSelectLayout = QHBoxLayout()
        self.fileEdit = LineEdit(self)
        self.fileEdit.setPlaceholderText("请选择要打包的Python文件")
        self.fileButton = PushButton("浏览", self)
        self.fileButton.clicked.connect(self.selectFile)

        self.fileSelectLayout.addWidget(self.fileEdit, 1)
        self.fileSelectLayout.addWidget(self.fileButton)
        self.fileLayout.addLayout(self.fileSelectLayout)

        self.mainLayout.addWidget(self.fileCard)

        # 打包模式卡片
        self.modeCard = CardWidget(self)
        self.modeLayout = QVBoxLayout(self.modeCard)
        self.modeLayout.setSpacing(12)
        self.modeLayout.setContentsMargins(20, 20, 20, 20)

        self.modeTitleLabel = SubtitleLabel("打包模式", self)
        self.modeLayout.addWidget(self.modeTitleLabel)

        self.modeButtonLayout = QHBoxLayout()
        self.standaloneRadio = RadioButton("独立文件夹 (--standalone)", self)
        self.standaloneRadio.setChecked(True)
        self.onefileRadio = RadioButton("单文件 (--onefile)", self)

        self.modeButtonLayout.addWidget(self.standaloneRadio)
        self.modeButtonLayout.addWidget(self.onefileRadio)
        self.modeButtonLayout.addStretch()
        self.modeLayout.addLayout(self.modeButtonLayout)

        self.modeDescLabel = CaptionLabel(
            "独立文件夹：生成包含所有依赖的文件夹，启动速度快\n"
            "单文件：生成单个exe文件，方便分发但启动较慢", self)
        self.modeLayout.addWidget(self.modeDescLabel)

        self.mainLayout.addWidget(self.modeCard)
        self.mainLayout.addStretch()

    def selectFile(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "选择Python文件", "", "Python Files (*.py)")
        if file:
            self.fileEdit.setText(file)


class OutputSettingsInterface(QWidget):
    """输出设置界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 输出设置卡片
        self.outputCard = CardWidget(self)
        self.outputLayout = QVBoxLayout(self.outputCard)
        self.outputLayout.setSpacing(12)
        self.outputLayout.setContentsMargins(20, 20, 20, 20)

        self.outputTitleLabel = SubtitleLabel("输出设置", self)
        self.outputLayout.addWidget(self.outputTitleLabel)

        # 输出目录
        self.outputDirLayout = QHBoxLayout()
        self.outputDirLabel = BodyLabel("输出目录：", self)
        self.outputDirEdit = LineEdit(self)
        self.outputDirEdit.setPlaceholderText("选择输出目录（可选）")
        self.outputDirButton = PushButton("浏览", self)
        self.outputDirButton.clicked.connect(self.selectOutputDir)

        self.outputDirLayout.addWidget(self.outputDirLabel)
        self.outputDirLayout.addWidget(self.outputDirEdit, 1)
        self.outputDirLayout.addWidget(self.outputDirButton)
        self.outputLayout.addLayout(self.outputDirLayout)

        # 应用名称
        self.nameLayout = QHBoxLayout()
        self.nameLabel = BodyLabel("应用名称：", self)
        self.nameEdit = LineEdit(self)
        self.nameEdit.setPlaceholderText("输入应用程序名称（可选）")

        self.nameLayout.addWidget(self.nameLabel)
        self.nameLayout.addWidget(self.nameEdit, 1)
        self.outputLayout.addLayout(self.nameLayout)

        self.mainLayout.addWidget(self.outputCard)

        # 图标设置卡片
        self.iconCard = CardWidget(self)
        self.iconLayout = QVBoxLayout(self.iconCard)
        self.iconLayout.setSpacing(12)
        self.iconLayout.setContentsMargins(20, 20, 20, 20)

        self.iconTitleLabel = SubtitleLabel("应用图标", self)
        self.iconLayout.addWidget(self.iconTitleLabel)

        self.iconSelectLayout = QHBoxLayout()
        self.iconEdit = LineEdit(self)
        self.iconEdit.setPlaceholderText("选择图标文件（.ico）")
        self.iconButton = PushButton("浏览", self)
        self.iconButton.clicked.connect(self.selectIcon)

        self.iconSelectLayout.addWidget(self.iconEdit, 1)
        self.iconSelectLayout.addWidget(self.iconButton)
        self.iconLayout.addLayout(self.iconSelectLayout)

        self.iconInfoLabel = CaptionLabel(
            "建议使用包含多种尺寸的.ico文件，确保在不同场景下显示效果良好", self)
        self.iconLayout.addWidget(self.iconInfoLabel)

        self.mainLayout.addWidget(self.iconCard)
        self.mainLayout.addStretch()

    def selectOutputDir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.outputDirEdit.setText(directory)

    def selectIcon(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "选择图标文件", "", "Icon Files (*.ico)")
        if file:
            self.iconEdit.setText(file)


class CompileOptionsInterface(QWidget):
    """编译选项界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 编译器选项卡片
        self.compilerCard = CardWidget(self)
        self.compilerLayout = QVBoxLayout(self.compilerCard)
        self.compilerLayout.setSpacing(12)
        self.compilerLayout.setContentsMargins(20, 20, 20, 20)

        self.compilerTitleLabel = SubtitleLabel("编译器设置", self)
        self.compilerLayout.addWidget(self.compilerTitleLabel)

        # 编译器选择
        self.compilerSelectLayout = QHBoxLayout()
        self.compilerLabel = BodyLabel("编译器：", self)
        self.compilerCombo = ComboBox(self)
        self.compilerCombo.addItems(["自动检测", "MSVC", "MinGW64", "Clang", "本地GCC"])
        self.compilerCombo.currentTextChanged.connect(self.onCompilerChanged)

        self.compilerSelectLayout.addWidget(self.compilerLabel)
        self.compilerSelectLayout.addWidget(self.compilerCombo, 1)
        self.compilerLayout.addLayout(self.compilerSelectLayout)

        # GCC路径（仅当选择本地GCC时显示）
        self.gccPathLayout = QHBoxLayout()
        self.gccPathLabel = BodyLabel("GCC路径：", self)
        self.gccPathEdit = LineEdit(self)
        self.gccPathEdit.setPlaceholderText("输入gcc.exe的完整路径")
        self.gccPathButton = PushButton("浏览", self)
        self.gccPathButton.clicked.connect(self.selectGccPath)

        self.gccPathLayout.addWidget(self.gccPathLabel)
        self.gccPathLayout.addWidget(self.gccPathEdit, 1)
        self.gccPathLayout.addWidget(self.gccPathButton)
        self.compilerLayout.addLayout(self.gccPathLayout)

        # 默认隐藏GCC路径选项
        self.gccPathLabel.hide()
        self.gccPathEdit.hide()
        self.gccPathButton.hide()

        # 自动下载
        self.autoDownloadLayout = QHBoxLayout()
        self.autoDownloadLabel = BodyLabel("自动下载依赖：", self)
        self.autoDownloadSwitch = SwitchButton(self)
        self.autoDownloadSwitch.setChecked(True)

        self.autoDownloadLayout.addWidget(self.autoDownloadLabel)
        self.autoDownloadLayout.addWidget(self.autoDownloadSwitch)
        self.autoDownloadLayout.addStretch()
        self.compilerLayout.addLayout(self.autoDownloadLayout)

        self.mainLayout.addWidget(self.compilerCard)

        # 显示选项卡片
        self.displayCard = CardWidget(self)
        self.displayLayout = QVBoxLayout(self.displayCard)
        self.displayLayout.setSpacing(12)
        self.displayLayout.setContentsMargins(20, 20, 20, 20)

        self.displayTitleLabel = SubtitleLabel("显示选项", self)
        self.displayLayout.addWidget(self.displayTitleLabel)

        # 选项网格
        self.optionsGrid = QGridLayout()
        self.optionsGrid.setSpacing(10)

        # 显示控制台
        self.consoleLabel = BodyLabel("显示控制台：", self)
        self.consoleSwitch = SwitchButton(self)
        self.consoleSwitch.setChecked(True)
        self.optionsGrid.addWidget(self.consoleLabel, 0, 0)
        self.optionsGrid.addWidget(self.consoleSwitch, 0, 1)

        # 显示进度
        self.progressLabel = BodyLabel("显示进度：", self)
        self.progressSwitch = SwitchButton(self)
        self.progressSwitch.setChecked(True)
        self.optionsGrid.addWidget(self.progressLabel, 1, 0)
        self.optionsGrid.addWidget(self.progressSwitch, 1, 1)

        # 显示内存
        self.memoryLabel = BodyLabel("显示内存：", self)
        self.memorySwitch = SwitchButton(self)
        self.memorySwitch.setChecked(True)
        self.optionsGrid.addWidget(self.memoryLabel, 2, 0)
        self.optionsGrid.addWidget(self.memorySwitch, 2, 1)

        # 清理临时文件
        self.removeLabel = BodyLabel("清理临时文件：", self)
        self.removeSwitch = SwitchButton(self)
        self.removeSwitch.setChecked(True)
        self.optionsGrid.addWidget(self.removeLabel, 3, 0)
        self.optionsGrid.addWidget(self.removeSwitch, 3, 1)

        self.displayLayout.addLayout(self.optionsGrid)
        self.mainLayout.addWidget(self.displayCard)
        self.mainLayout.addStretch()

    def onCompilerChanged(self, text):
        """编译器选择改变时的处理"""
        if text == "本地GCC":
            self.gccPathLabel.show()
            self.gccPathEdit.show()
            self.gccPathButton.show()
        else:
            self.gccPathLabel.hide()
            self.gccPathEdit.hide()
            self.gccPathButton.hide()

    def selectGccPath(self):
        """选择GCC路径"""
        file, _ = QFileDialog.getOpenFileName(
            self, "选择gcc.exe", "", "Executable Files (gcc.exe)")
        if file:
            self.gccPathEdit.setText(file)


class OptimizationInterface(QWidget):
    """优化选项界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 优化选项卡片
        self.optimizeCard = CardWidget(self)
        self.optimizeLayout = QVBoxLayout(self.optimizeCard)
        self.optimizeLayout.setSpacing(12)
        self.optimizeLayout.setContentsMargins(20, 20, 20, 20)

        self.optimizeTitleLabel = SubtitleLabel("优化选项", self)
        self.optimizeLayout.addWidget(self.optimizeTitleLabel)

        # 使用ccache
        self.ccacheLayout = QHBoxLayout()
        self.ccacheLabel = BodyLabel("使用ccache加速：", self)
        self.ccacheSwitch = SwitchButton(self)
        self.ccacheSwitch.setChecked(False)

        self.ccacheLayout.addWidget(self.ccacheLabel)
        self.ccacheLayout.addWidget(self.ccacheSwitch)
        self.ccacheLayout.addStretch()
        self.optimizeLayout.addLayout(self.ccacheLayout)

        # 低内存模式
        self.lowMemoryLayout = QHBoxLayout()
        self.lowMemoryLabel = BodyLabel("低内存模式：", self)
        self.lowMemorySwitch = SwitchButton(self)

        self.lowMemoryLayout.addWidget(self.lowMemoryLabel)
        self.lowMemoryLayout.addWidget(self.lowMemorySwitch)
        self.lowMemoryLayout.addStretch()
        self.optimizeLayout.addLayout(self.lowMemoryLayout)

        # LTO优化
        self.ltoLayout = QHBoxLayout()
        self.ltoLabel = BodyLabel("启用LTO优化：", self)
        self.ltoSwitch = SwitchButton(self)
        self.ltoSwitch.setChecked(False)

        self.ltoLayout.addWidget(self.ltoLabel)
        self.ltoLayout.addWidget(self.ltoSwitch)
        self.ltoLayout.addStretch()
        self.optimizeLayout.addLayout(self.ltoLayout)

        self.mainLayout.addWidget(self.optimizeCard)

        # 说明卡片
        self.infoCard = CardWidget(self)
        self.infoLayout = QVBoxLayout(self.infoCard)
        self.infoLayout.setContentsMargins(20, 20, 20, 20)

        self.infoTitleLabel = SubtitleLabel("优化说明", self)
        self.infoLayout.addWidget(self.infoTitleLabel)

        self.infoText = BodyLabel(
            "• ccache：缓存编译结果，加速重复编译\n"
            "• 低内存模式：减少编译时的内存占用\n"
            "• LTO优化：链接时优化，提升运行性能但增加编译时间",
            self
        )
        self.infoLayout.addWidget(self.infoText)

        self.mainLayout.addWidget(self.infoCard)
        self.mainLayout.addStretch()


class PluginsInterface(QWidget):
    """插件设置界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 常用插件卡片
        self.commonCard = CardWidget(self)
        self.commonLayout = QVBoxLayout(self.commonCard)
        self.commonLayout.setSpacing(12)
        self.commonLayout.setContentsMargins(20, 20, 20, 20)

        self.commonTitleLabel = SubtitleLabel("常用插件", self)
        self.commonLayout.addWidget(self.commonTitleLabel)

        # 插件网格 - 分两列显示
        self.pluginsGrid = QGridLayout()
        self.pluginsGrid.setSpacing(10)

        self.plugins = {
            'pyqt5': CheckBox('PyQt5', self),
            'pyside2': CheckBox('PySide2', self),
            'pyside6': CheckBox('PySide6', self),
            'numpy': CheckBox('Numpy', self),
            'torch': CheckBox('PyTorch', self),
            'tensorflow': CheckBox('TensorFlow', self),
            'matplotlib': CheckBox('Matplotlib', self),
            'tk-inter': CheckBox('Tkinter', self),
        }

        row = 0
        col = 0
        for name, checkbox in self.plugins.items():
            self.pluginsGrid.addWidget(checkbox, row, col)
            col += 1
            if col > 1:  # 两列布局
                col = 0
                row += 1

        self.commonLayout.addLayout(self.pluginsGrid)
        self.mainLayout.addWidget(self.commonCard)

        # 自定义插件卡片
        self.customCard = CardWidget(self)
        self.customLayout = QVBoxLayout(self.customCard)
        self.customLayout.setSpacing(12)
        self.customLayout.setContentsMargins(20, 20, 20, 20)

        self.customTitleLabel = SubtitleLabel("自定义插件", self)
        self.customLayout.addWidget(self.customTitleLabel)

        self.customEdit = TextEdit(self)
        self.customEdit.setPlaceholderText("输入自定义插件名称，每行一个")
        self.customEdit.setMaximumHeight(80)

        self.customLayout.addWidget(self.customEdit)
        self.mainLayout.addWidget(self.customCard)

        self.mainLayout.addStretch()


class ModulesInterface(QWidget):
    """模块设置界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 模块设置卡片
        self.moduleCard = CardWidget(self)
        self.moduleLayout = QVBoxLayout(self.moduleCard)
        self.moduleLayout.setSpacing(12)
        self.moduleLayout.setContentsMargins(20, 20, 20, 20)

        self.moduleTitleLabel = SubtitleLabel("模块设置", self)
        self.moduleLayout.addWidget(self.moduleTitleLabel)

        # 跟随导入
        self.followImportsLayout = QHBoxLayout()
        self.followImportsLabel = BodyLabel("跟随导入：", self)
        self.followImportsSwitch = SwitchButton(self)
        self.followImportsSwitch.setChecked(True)

        self.followImportsLayout.addWidget(self.followImportsLabel)
        self.followImportsLayout.addWidget(self.followImportsSwitch)
        self.followImportsLayout.addStretch()
        self.moduleLayout.addLayout(self.followImportsLayout)

        # 包含模块
        self.includeLayout = QVBoxLayout()
        self.includeLabel = BodyLabel("包含模块：", self)
        self.includeEdit = LineEdit(self)
        self.includeEdit.setPlaceholderText("需要编译的模块/文件夹，用逗号分隔")

        self.includeLayout.addWidget(self.includeLabel)
        self.includeLayout.addWidget(self.includeEdit)
        self.moduleLayout.addLayout(self.includeLayout)

        # 排除模块
        self.excludeLayout = QVBoxLayout()
        self.excludeLabel = BodyLabel("排除模块：", self)
        self.excludeEdit = LineEdit(self)
        self.excludeEdit.setPlaceholderText("不需要编译的模块，用逗号分隔")

        self.excludeLayout.addWidget(self.excludeLabel)
        self.excludeLayout.addWidget(self.excludeEdit)
        self.moduleLayout.addLayout(self.excludeLayout)

        self.mainLayout.addWidget(self.moduleCard)

        # 数据文件卡片
        self.dataCard = CardWidget(self)
        self.dataLayout = QVBoxLayout(self.dataCard)
        self.dataLayout.setSpacing(12)
        self.dataLayout.setContentsMargins(20, 20, 20, 20)

        self.dataTitleLabel = SubtitleLabel("数据文件", self)
        self.dataLayout.addWidget(self.dataTitleLabel)

        self.dataEdit = TextEdit(self)
        self.dataEdit.setPlaceholderText(
            "需要包含的数据文件或目录\n"
            "格式：源路径=目标路径\n"
            "例如：data/*.txt=data/"
        )
        self.dataEdit.setMaximumHeight(80)

        self.dataLayout.addWidget(self.dataEdit)
        self.mainLayout.addWidget(self.dataCard)

        self.mainLayout.addStretch()


class WindowsOptionsInterface(QWidget):
    """Windows选项界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 应用信息卡片
        self.appInfoCard = CardWidget(self)
        self.appInfoLayout = QVBoxLayout(self.appInfoCard)
        self.appInfoLayout.setSpacing(12)
        self.appInfoLayout.setContentsMargins(20, 20, 20, 20)

        self.appInfoTitleLabel = SubtitleLabel("应用信息", self)
        self.appInfoLayout.addWidget(self.appInfoTitleLabel)

        # 公司名称
        self.companyLayout = QHBoxLayout()
        self.companyLabel = BodyLabel("公司名称：", self)
        self.companyEdit = LineEdit(self)
        self.companyEdit.setPlaceholderText("输入公司名称")

        self.companyLayout.addWidget(self.companyLabel)
        self.companyLayout.addWidget(self.companyEdit, 1)
        self.appInfoLayout.addLayout(self.companyLayout)

        # 产品名称
        self.productLayout = QHBoxLayout()
        self.productLabel = BodyLabel("产品名称：", self)
        self.productEdit = LineEdit(self)
        self.productEdit.setPlaceholderText("输入产品名称")

        self.productLayout.addWidget(self.productLabel)
        self.productLayout.addWidget(self.productEdit, 1)
        self.appInfoLayout.addLayout(self.productLayout)

        # 文件版本
        self.versionLayout = QHBoxLayout()
        self.versionLabel = BodyLabel("文件版本：", self)
        self.versionEdit = LineEdit(self)
        self.versionEdit.setPlaceholderText("例如：1.0.0.0")

        self.versionLayout.addWidget(self.versionLabel)
        self.versionLayout.addWidget(self.versionEdit, 1)
        self.appInfoLayout.addLayout(self.versionLayout)

        # 文件描述
        self.descLayout = QHBoxLayout()
        self.descLabel = BodyLabel("文件描述：", self)
        self.descEdit = LineEdit(self)
        self.descEdit.setPlaceholderText("输入文件描述")

        self.descLayout.addWidget(self.descLabel)
        self.descLayout.addWidget(self.descEdit, 1)
        self.appInfoLayout.addLayout(self.descLayout)

        self.mainLayout.addWidget(self.appInfoCard)

        # 权限设置卡片
        self.permissionCard = CardWidget(self)
        self.permissionLayout = QVBoxLayout(self.permissionCard)
        self.permissionLayout.setSpacing(12)
        self.permissionLayout.setContentsMargins(20, 20, 20, 20)

        self.permissionTitleLabel = SubtitleLabel("权限设置", self)
        self.permissionLayout.addWidget(self.permissionTitleLabel)

        # UAC权限
        self.uacLayout = QHBoxLayout()
        self.uacLabel = BodyLabel("需要管理员权限：", self)
        self.uacSwitch = SwitchButton(self)

        self.uacLayout.addWidget(self.uacLabel)
        self.uacLayout.addWidget(self.uacSwitch)
        self.uacLayout.addStretch()
        self.permissionLayout.addLayout(self.uacLayout)

        self.permissionInfoLabel = CaptionLabel(
            "启用后，程序运行时将请求管理员权限", self)
        self.permissionLayout.addWidget(self.permissionInfoLabel)

        self.mainLayout.addWidget(self.permissionCard)
        self.mainLayout.addStretch()


class AdvancedInterface(QWidget):
    """高级设置界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 额外参数卡片
        self.extraCard = CardWidget(self)
        self.extraLayout = QVBoxLayout(self.extraCard)
        self.extraLayout.setSpacing(12)
        self.extraLayout.setContentsMargins(20, 20, 20, 20)

        self.extraTitleLabel = SubtitleLabel("额外参数", self)
        self.extraLayout.addWidget(self.extraTitleLabel)

        self.extraEdit = TextEdit(self)
        self.extraEdit.setPlaceholderText("输入其他Nuitka参数，每行一个")
        self.extraEdit.setMaximumHeight(120)

        self.extraLayout.addWidget(self.extraEdit)

        self.extraInfoLabel = CaptionLabel(
            "这里可以添加任何Nuitka支持的命令行参数\n"
            "例如：--include-package=requests", self)
        self.extraLayout.addWidget(self.extraInfoLabel)

        self.mainLayout.addWidget(self.extraCard)

        # 常用参数提示卡片
        self.tipsCard = CardWidget(self)
        self.tipsLayout = QVBoxLayout(self.tipsCard)
        self.tipsLayout.setContentsMargins(20, 20, 20, 20)

        self.tipsTitleLabel = SubtitleLabel("常用参数", self)
        self.tipsLayout.addWidget(self.tipsTitleLabel)

        self.tipsText = BodyLabel(
            "• --include-package=包名：强制包含指定包\n"
            "• --include-module=模块名：强制包含指定模块\n"
            "• --include-plugin-directory=路径：包含插件目录\n"
            "• --python-flag=标志：设置Python标志\n"
            "• --warn-implicit-exceptions：警告隐式异常\n"
            "• --warn-unusual-code：警告异常代码",
            self
        )
        self.tipsLayout.addWidget(self.tipsText)

        self.mainLayout.addWidget(self.tipsCard)
        self.mainLayout.addStretch()


class MainInterface(QWidget):
    """主界面 - 使用标签页组织"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mainInterface")
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 10, 20, 20)

        # 标题
        self.titleLabel = SubtitleLabel("Nuitka可视化打包工具", self)
        self.mainLayout.addWidget(self.titleLabel)

        # 创建标签页
        self.pivot = Pivot(self)

        # 创建各个界面
        self.pythonInterface = PythonEnvironmentInterface(self)
        self.basicInterface = BasicSettingsInterface(self)
        self.outputInterface = OutputSettingsInterface(self)
        self.compileInterface = CompileOptionsInterface(self)
        self.optimizeInterface = OptimizationInterface(self)
        self.pluginsInterface = PluginsInterface(self)
        self.modulesInterface = ModulesInterface(self)
        self.windowsInterface = WindowsOptionsInterface(self)
        self.advancedInterface = AdvancedInterface(self)
        self.assetsInterface = AssetsInterface(self)

        # 创建堆叠窗口
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.addWidget(self.pythonInterface)
        self.stackedWidget.addWidget(self.basicInterface)
        self.stackedWidget.addWidget(self.outputInterface)
        self.stackedWidget.addWidget(self.compileInterface)
        self.stackedWidget.addWidget(self.optimizeInterface)
        self.stackedWidget.addWidget(self.pluginsInterface)
        self.stackedWidget.addWidget(self.modulesInterface)
        self.stackedWidget.addWidget(self.assetsInterface)
        self.stackedWidget.addWidget(self.windowsInterface)
        self.stackedWidget.addWidget(self.advancedInterface)

        # 添加标签
        self.pivot.addItem(
            routeKey="python",
            text="环境",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.pythonInterface)
        )
        self.pivot.addItem(
            routeKey="basic",
            text="基础",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.basicInterface)
        )
        self.pivot.addItem(
            routeKey="output",
            text="输出",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.outputInterface)
        )
        self.pivot.addItem(
            routeKey="compile",
            text="编译",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.compileInterface)
        )
        self.pivot.addItem(
            routeKey="optimize",
            text="优化",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.optimizeInterface)
        )
        self.pivot.addItem(
            routeKey="plugins",
            text="插件",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.pluginsInterface)
        )
        self.pivot.addItem(
            routeKey="modules",
            text="模块",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.modulesInterface)
        )
        self.pivot.addItem(
            routeKey="assets",
            text="资源",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.assetsInterface)
        )
        self.pivot.addItem(
            routeKey="windows",
            text="Windows",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.windowsInterface)
        )
        self.pivot.addItem(
            routeKey="advanced",
            text="高级",
            onClick=lambda: self.stackedWidget.setCurrentWidget(self.advancedInterface)
        )

        self.pivot.setCurrentItem("python")

        self.mainLayout.addWidget(self.pivot)
        self.mainLayout.addWidget(self.stackedWidget, 1)

        # 按钮区域
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setSpacing(10)

        self.saveConfigButton = PushButton("保存配置", self)
        self.saveConfigButton.clicked.connect(self.saveConfig)

        self.loadConfigButton = PushButton("加载配置", self)
        self.loadConfigButton.clicked.connect(self.loadConfig)

        self.previewButton = PushButton("预览命令", self)
        self.previewButton.clicked.connect(self.previewCommand)

        self.packageButton = PrimaryPushButton("开始打包", self)
        self.packageButton.clicked.connect(self.startPackage)

        self.buttonLayout.addWidget(self.saveConfigButton)
        self.buttonLayout.addWidget(self.loadConfigButton)
        self.buttonLayout.addStretch()
        self.buttonLayout.addWidget(self.previewButton)
        self.buttonLayout.addWidget(self.packageButton)

        self.mainLayout.addLayout(self.buttonLayout)

    def buildCommand(self):
        """构建Nuitka命令"""
        if not self.basicInterface.fileEdit.text():
            InfoBar.error(
                title='错误',
                content='请选择要打包的Python文件！',
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
            return None

        # 获取Python解释器路径
        python_path = self.pythonInterface.pythonEdit.text() or 'python'
        cmd_parts = [python_path, '-m', 'nuitka']

        # 打包模式
        if self.basicInterface.standaloneRadio.isChecked():
            cmd_parts.append('--standalone')
        else:
            cmd_parts.append('--onefile')

        # 自动确认下载
        if self.compileInterface.autoDownloadSwitch.isChecked():
            cmd_parts.append('--assume-yes-for-downloads')

        # 编译器选择
        compiler = self.compileInterface.compilerCombo.currentText()
        if compiler == "MinGW64":
            cmd_parts.append('--mingw64')
        elif compiler == "Clang":
            cmd_parts.append('--clang')
        elif compiler == "MSVC":
            cmd_parts.append('--msvc=latest')

            # 控制台
        if not self.compileInterface.consoleSwitch.isChecked():
            cmd_parts.append('--windows-disable-console')

        # 显示选项
        if self.compileInterface.progressSwitch.isChecked():
            cmd_parts.append('--show-progress')
        if self.compileInterface.memorySwitch.isChecked():
            cmd_parts.append('--show-memory')
        if self.compileInterface.removeSwitch.isChecked():
            cmd_parts.append('--remove-output')

        # 优化选项
        if self.optimizeInterface.lowMemorySwitch.isChecked():
            cmd_parts.append('--low-memory')
        if self.optimizeInterface.ltoSwitch.isChecked():
            cmd_parts.append('--lto=yes')

        # 输出设置
        if self.outputInterface.outputDirEdit.text():
            cmd_parts.append(f'--output-dir={self.outputInterface.outputDirEdit.text()}')
        if self.outputInterface.nameEdit.text():
            cmd_parts.append(f'--output-filename={self.outputInterface.nameEdit.text()}')
        if self.outputInterface.iconEdit.text():
            cmd_parts.append(f'--windows-icon-from-ico={self.outputInterface.iconEdit.text()}')

        # 插件
        enabled_plugins = []
        for name, checkbox in self.pluginsInterface.plugins.items():
            if checkbox.isChecked():
                enabled_plugins.append(name)
        if enabled_plugins:
            cmd_parts.append(f'--enable-plugin={",".join(enabled_plugins)}')

        # 自定义插件
        custom_text = self.pluginsInterface.customEdit.toPlainText().strip()
        if custom_text:
            custom_plugins = [p.strip() for p in custom_text.split('\n') if p.strip()]
            if custom_plugins:
                cmd_parts.append(f'--enable-plugin={",".join(custom_plugins)}')

        # 模块设置
        if self.modulesInterface.followImportsSwitch.isChecked():
            if self.modulesInterface.includeEdit.text():
                includes = self.modulesInterface.includeEdit.text().replace(' ', '')
                cmd_parts.append(f'--follow-import-to={includes}')
            else:
                cmd_parts.append('--follow-imports')
        else:
            cmd_parts.append('--nofollow-imports')

        # 排除模块
        if self.modulesInterface.excludeEdit.text():
            excludes = self.modulesInterface.excludeEdit.text().split(',')
            for exclude in excludes:
                cmd_parts.append(f'--nofollow-import-to={exclude.strip()}')

        # 数据文件
        data_text = self.modulesInterface.dataEdit.toPlainText().strip()
        if data_text:
            data_lines = [line.strip() for line in data_text.split('\n') if line.strip()]
            for data_line in data_lines:
                if '=' in data_line:
                    cmd_parts.append(f'--include-data-files={data_line}')
                else:
                    cmd_parts.append(f'--include-data-dir={data_line}')

        # 资源文件
        assets = self.assetsInterface.getAssets()
        for asset in assets:
            if asset['enabled']:
                source_path = asset['source']
                target_path = asset['target']
                asset_type = asset['type']

                if asset_type == 'file':
                    cmd_parts.append(f'--include-data-files={source_path}={target_path}')
                elif asset_type == 'folder':
                    cmd_parts.append(f'--include-data-dir={source_path}={target_path}')

        # Windows选项
        if self.windowsInterface.companyEdit.text():
            cmd_parts.append(f'--windows-company-name={self.windowsInterface.companyEdit.text()}')
        if self.windowsInterface.productEdit.text():
            cmd_parts.append(f'--windows-product-name={self.windowsInterface.productEdit.text()}')
        if self.windowsInterface.versionEdit.text():
            cmd_parts.append(f'--windows-file-version={self.windowsInterface.versionEdit.text()}')
        if self.windowsInterface.descEdit.text():
            cmd_parts.append(f'--windows-file-description={self.windowsInterface.descEdit.text()}')
        if self.windowsInterface.uacSwitch.isChecked():
            cmd_parts.append('--windows-uac-admin')

        # 额外参数
        extra_text = self.advancedInterface.extraEdit.toPlainText().strip()
        if extra_text:
            extra_args = [arg.strip() for arg in extra_text.split('\n') if arg.strip()]
            cmd_parts.extend(extra_args)

        # Python文件
        cmd_parts.append(self.basicInterface.fileEdit.text())

        return ' '.join(cmd_parts)

    def getEnvironment(self):
        """获取环境变量"""
        env = {}

        # 如果选择了本地GCC，设置CC环境变量
        if (self.compileInterface.compilerCombo.currentText() == "本地GCC" and
                self.compileInterface.gccPathEdit.text()):
            env['CC'] = self.compileInterface.gccPathEdit.text()

        # 如果使用ccache
        if self.optimizeInterface.ccacheSwitch.isChecked():
            # 检查系统中是否有ccache
            ccache_path = self.findCCache()
            if ccache_path:
                env['NUITKA_CCACHE_BINARY'] = ccache_path

        return env

    def findCCache(self):
        """查找ccache路径"""
        # Windows
        if sys.platform == 'win32':
            paths = [
                r'C:\ProgramData\chocolatey\bin\ccache.exe',
                r'C:\msys64\usr\bin\ccache.exe',
                r'C:\msys64\mingw64\bin\ccache.exe',
                r'C:\tools\ccache\ccache.exe',
            ]
            # 从PATH中查找
            for path in os.environ.get('PATH', '').split(';'):
                ccache = os.path.join(path, 'ccache.exe')
                if os.path.exists(ccache):
                    return ccache
            # 检查预定义路径
            for path in paths:
                if os.path.exists(path):
                    return path
        else:
            # Linux/Mac
            import shutil
            return shutil.which('ccache')

        return None

    def previewCommand(self):
        """预览命令"""
        command = self.buildCommand()
        if command:
            env_info = ""
            env = self.getEnvironment()
            if env:
                env_info = "\n\n环境变量：\n"
                for key, value in env.items():
                    env_info += f"{key}={value}\n"

            cwd_info = ""
            if self.basicInterface.fileEdit.text():
                cwd = os.path.dirname(self.basicInterface.fileEdit.text())
                cwd_info = f"\n工作目录：{cwd}\n"

            dialog = Dialog("命令预览", command + cwd_info + env_info, self)
            dialog.exec()

    def startPackage(self):
        """开始打包"""
        command = self.buildCommand()
        if command:
            # 切换到日志界面
            parent = self.parent().parent().parent()  # 获取主窗口
            parent.switchTo(parent.logInterface)

            # 获取环境变量
            env = self.getEnvironment()

            # 获取工作目录（Python文件所在目录）
            cwd = None
            if self.basicInterface.fileEdit.text():
                cwd = os.path.dirname(self.basicInterface.fileEdit.text())

            # 开始打包
            parent.logInterface.startPackage(command, env, cwd)

    def saveConfig(self):
        """保存配置"""
        file, _ = QFileDialog.getSaveFileName(
            self, "保存配置", "", "JSON Files (*.json)")
        if file:
            config = self.getConfig()
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            InfoBar.success(
                title='成功',
                content='配置已保存！',
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )

    def loadConfig(self):
        """加载配置"""
        file, _ = QFileDialog.getOpenFileName(
            self, "加载配置", "", "JSON Files (*.json)")
        if file:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.setConfig(config)
                InfoBar.success(
                    title='成功',
                    content='配置已加载！',
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self
                )
            except Exception as e:
                InfoBar.error(
                    title='错误',
                    content=f'加载配置失败：{str(e)}',
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self
                )

    def getConfig(self):
        """获取当前配置"""
        config = {
            'python': self.pythonInterface.pythonEdit.text(),
            'basic': {
                'file': self.basicInterface.fileEdit.text(),
                'mode': 'standalone' if self.basicInterface.standaloneRadio.isChecked() else 'onefile',
            },
            'output': {
                'dir': self.outputInterface.outputDirEdit.text(),
                'name': self.outputInterface.nameEdit.text(),
                'icon': self.outputInterface.iconEdit.text(),
            },
            'compile': {
                'compiler': self.compileInterface.compilerCombo.currentText(),
                'gcc_path': self.compileInterface.gccPathEdit.text(),
                'auto_download': self.compileInterface.autoDownloadSwitch.isChecked(),
                'console': self.compileInterface.consoleSwitch.isChecked(),
                'progress': self.compileInterface.progressSwitch.isChecked(),
                'memory': self.compileInterface.memorySwitch.isChecked(),
                'remove': self.compileInterface.removeSwitch.isChecked(),
            },
            'optimize': {
                'ccache': self.optimizeInterface.ccacheSwitch.isChecked(),
                'low_memory': self.optimizeInterface.lowMemorySwitch.isChecked(),
                'lto': self.optimizeInterface.ltoSwitch.isChecked(),
            },
            'plugins': {
                name: checkbox.isChecked()
                for name, checkbox in self.pluginsInterface.plugins.items()
            },
            'custom_plugins': self.pluginsInterface.customEdit.toPlainText(),
            'modules': {
                'follow_imports': self.modulesInterface.followImportsSwitch.isChecked(),
                'include': self.modulesInterface.includeEdit.text(),
                'exclude': self.modulesInterface.excludeEdit.text(),
                'data': self.modulesInterface.dataEdit.toPlainText(),
            },
            'assets': self.assetsInterface.getAssets(),
            'windows': {
                'company': self.windowsInterface.companyEdit.text(),
                'product': self.windowsInterface.productEdit.text(),
                'version': self.windowsInterface.versionEdit.text(),
                'description': self.windowsInterface.descEdit.text(),
                'uac': self.windowsInterface.uacSwitch.isChecked(),
            },
            'advanced': {
                'extra': self.advancedInterface.extraEdit.toPlainText(),
            }
        }
        return config

    def setConfig(self, config):
        """设置配置"""
        # Python环境
        self.pythonInterface.pythonEdit.setText(config.get('python', ''))
        self.pythonInterface.updatePythonInfo()
        self.pythonInterface.checkNuitka()

        # 基础设置
        basic = config.get('basic', {})
        self.basicInterface.fileEdit.setText(basic.get('file', ''))
        if basic.get('mode') == 'onefile':
            self.basicInterface.onefileRadio.setChecked(True)
        else:
            self.basicInterface.standaloneRadio.setChecked(True)

        # 输出设置
        output = config.get('output', {})
        self.outputInterface.outputDirEdit.setText(output.get('dir', ''))
        self.outputInterface.nameEdit.setText(output.get('name', ''))
        self.outputInterface.iconEdit.setText(output.get('icon', ''))

        # 资源文件
        assets = config.get('assets', [])
        self.assetsInterface.setAssets(assets)

        # 编译选项
        compile_opt = config.get('compile', {})
        self.compileInterface.compilerCombo.setCurrentText(compile_opt.get('compiler', '自动检测'))
        self.compileInterface.gccPathEdit.setText(compile_opt.get('gcc_path', ''))
        self.compileInterface.autoDownloadSwitch.setChecked(compile_opt.get('auto_download', True))
        self.compileInterface.consoleSwitch.setChecked(compile_opt.get('console', True))
        self.compileInterface.progressSwitch.setChecked(compile_opt.get('progress', True))
        self.compileInterface.memorySwitch.setChecked(compile_opt.get('memory', True))
        self.compileInterface.removeSwitch.setChecked(compile_opt.get('remove', True))
        self.compileInterface.onCompilerChanged(self.compileInterface.compilerCombo.currentText())

        # 优化选项
        optimize = config.get('optimize', {})
        self.optimizeInterface.ccacheSwitch.setChecked(optimize.get('ccache', False))
        self.optimizeInterface.lowMemorySwitch.setChecked(optimize.get('low_memory', False))
        self.optimizeInterface.ltoSwitch.setChecked(optimize.get('lto', False))

        # 插件
        plugins = config.get('plugins', {})
        for name, checkbox in self.pluginsInterface.plugins.items():
            checkbox.setChecked(plugins.get(name, False))
        self.pluginsInterface.customEdit.setPlainText(config.get('custom_plugins', ''))

        # 模块设置
        modules = config.get('modules', {})
        self.modulesInterface.followImportsSwitch.setChecked(modules.get('follow_imports', True))
        self.modulesInterface.includeEdit.setText(modules.get('include', ''))
        self.modulesInterface.excludeEdit.setText(modules.get('exclude', ''))
        self.modulesInterface.dataEdit.setPlainText(modules.get('data', ''))

        # Windows选项
        windows = config.get('windows', {})
        self.windowsInterface.companyEdit.setText(windows.get('company', ''))
        self.windowsInterface.productEdit.setText(windows.get('product', ''))
        self.windowsInterface.versionEdit.setText(windows.get('version', ''))
        self.windowsInterface.descEdit.setText(windows.get('description', ''))
        self.windowsInterface.uacSwitch.setChecked(windows.get('uac', False))

        # 高级设置
        advanced = config.get('advanced', {})
        self.advancedInterface.extraEdit.setPlainText(advanced.get('extra', ''))


class LogInterface(QWidget):
    """日志界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logInterface")
        self.packageThread = None
        self.setupUI()

    def setupUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)

        # 标题和进度
        self.headerLayout = QHBoxLayout()
        self.titleLabel = SubtitleLabel("打包日志", self)
        self.progressBar = ProgressBar(self)
        self.progressBar.setRange(0, 100)
        self.progressBar.hide()

        self.headerLayout.addWidget(self.titleLabel)
        self.headerLayout.addStretch()
        self.headerLayout.addWidget(self.progressBar)
        self.mainLayout.addLayout(self.headerLayout)

        # 日志显示
        self.logCard = CardWidget(self)
        self.logLayout = QVBoxLayout(self.logCard)
        self.logLayout.setContentsMargins(20, 20, 20, 20)

        self.logEdit = PlainTextEdit(self)
        self.logEdit.setReadOnly(True)
        font = QFont("Consolas", 9)
        self.logEdit.setFont(font)

        self.logLayout.addWidget(self.logEdit)
        self.mainLayout.addWidget(self.logCard, 1)

        # 按钮
        self.buttonLayout = QHBoxLayout()

        self.clearButton = PushButton("清空日志", self)
        self.clearButton.clicked.connect(self.clearLog)

        self.saveButton = PushButton("保存日志", self)
        self.saveButton.clicked.connect(self.saveLog)

        self.stopButton = PushButton("停止打包", self)
        self.stopButton.clicked.connect(self.stopPackage)
        self.stopButton.setEnabled(False)

        self.buttonLayout.addWidget(self.clearButton)
        self.buttonLayout.addWidget(self.saveButton)
        self.buttonLayout.addStretch()
        self.buttonLayout.addWidget(self.stopButton)

        self.mainLayout.addLayout(self.buttonLayout)

    def startPackage(self, command, env=None, cwd=None):
        """开始打包"""
        self.clearLog()
        self.progressBar.show()
        self.progressBar.setValue(0)
        self.stopButton.setEnabled(True)

        self.logEdit.appendPlainText(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if env:
            self.logEdit.appendPlainText("环境变量设置：")
            for key, value in env.items():
                self.logEdit.appendPlainText(f"  {key}={value}")
            self.logEdit.appendPlainText("")

        self.packageThread = PackageThread(command, env, cwd)
        self.packageThread.output_signal.connect(self.appendLog)
        self.packageThread.progress_signal.connect(self.updateProgress)
        self.packageThread.finished_signal.connect(self.packageFinished)
        self.packageThread.start()

    def stopPackage(self):
        """停止打包"""
        if self.packageThread and self.packageThread.isRunning():
            self.packageThread.stop()
            self.appendLog("\n用户取消了打包操作\n")

    def appendLog(self, text):
        """添加日志"""
        self.logEdit.moveCursor(QTextCursor.End)
        self.logEdit.insertPlainText(text)
        self.logEdit.moveCursor(QTextCursor.End)

    def updateProgress(self, value):
        """更新进度"""
        self.progressBar.setValue(value)

    def packageFinished(self, success, message):
        """打包完成"""
        self.stopButton.setEnabled(False)
        self.appendLog(f"\n结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.appendLog(f"打包结果：{message}\n")

        if success:
            InfoBar.success(
                title='成功',
                content=message,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
            self.progressBar.setValue(100)
        else:
            InfoBar.error(
                title='失败',
                content=message,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )

    def clearLog(self):
        """清空日志"""
        self.logEdit.clear()

    def saveLog(self):
        """保存日志"""
        file, _ = QFileDialog.getSaveFileName(
            self, "保存日志", f"nuitka_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)")
        if file:
            with open(file, 'w', encoding='utf-8') as f:
                f.write(self.logEdit.toPlainText())
            InfoBar.success(
                title='成功',
                content='日志已保存！',
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )


class MainWindow(FluentWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nuitka可视化打包工具")

        # 设置固定最小尺寸
        self.setMinimumSize(900, 800)
        self.resize(900, 800)

        # 创建界面
        self.mainInterface = MainInterface(self)
        self.logInterface = LogInterface(self)

        # 初始化导航
        self.initNavigation()

        # 设置样式
        self.setStyleSheet("""
            QWidget {
                font-family: 'Microsoft YaHei', 'Segoe UI', 'Arial';
            }
        """)

    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.mainInterface, FluentIcon.HOME, '主页')
        self.addSubInterface(self.logInterface, FluentIcon.DOCUMENT, '日志')

        # 添加设置按钮
        self.navigationInterface.addItem(
            routeKey='settings',
            icon=FluentIcon.SETTING,
            text='设置',
            onClick=self.showSettings,
            position=NavigationItemPosition.BOTTOM
        )

    def showSettings(self):
        """显示设置对话框"""
        InfoBar.info(
            title='提示',
            content='设置功能正在开发中...',
            position=InfoBarPosition.TOP_RIGHT,
            parent=self
        )


def main():
    # 启用高DPI缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # 设置主题
    setTheme(Theme.AUTO)

    # 创建主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()