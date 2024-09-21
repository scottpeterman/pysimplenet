from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QStyleFactory, QTextEdit
from simplenet.gui.uglyplugin_parsers.parser_examples import p_examples
from ttp import ttp
from jinja2 import Template
from ruamel.yaml import YAML as yaml
import json
import jmespath
from simplenet.gui.uglyplugin_parsers.HighlighterTEWidget import SyntaxHighlighter


class PlainTextOnlyTextEdit(QTextEdit):
    def insertFromMimeData(self, mime_data):
        # Get the plain text from mime_data and insert it.
        plain_text = mime_data.text()
        self.textCursor().insertText(plain_text)


class HighlightedTextEdit(PlainTextOnlyTextEdit):
    selection_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.highlighted_ranges = []

    def show_context_menu(self, pos):
        cursor = self.cursorForPosition(pos)
        if self.textCursor().hasSelection():
            menu = QtWidgets.QMenu(self)
            assign_action = QtGui.QAction("Assign Variable", self)
            assign_action.triggered.connect(self.assign_variable)
            menu.addAction(assign_action)
            menu.exec(self.mapToGlobal(pos))
        else:
            menu = self.createStandardContextMenu()
            menu.exec(self.mapToGlobal(pos))

    def assign_variable(self):
        cursor = self.textCursor()
        selected_text = cursor.selectedText()
        if not selected_text:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select some text to assign a variable.")
            return

        # Ask for variable name
        var_name, ok = QtWidgets.QInputDialog.getText(self, "Variable Name", "Enter variable name:")
        if not ok or not var_name.strip():
            return

        # Ask for match variable type
        match_types = [
            "None", "WORD", "PHRASE", "ORPHRASE", "_line_", "ROW",
            "DIGIT", "IP", "PREFIX", "IPV6", "PREFIXV6", "MAC", "re"
        ]
        match_type, ok = QtWidgets.QInputDialog.getItem(
            self, "Select Match Type", "Choose a TTP match variable type:", match_types, 0, False
        )
        if not ok:
            return

        if match_type.lower() == 're':
            regex, ok = QtWidgets.QInputDialog.getText(self, "Enter Regular Expression", "Enter regex for the variable:")
            if not ok or not regex.strip():
                return
            match_type = f're("{regex.strip()}")'
        else:
            match_type = match_type.upper() if match_type != "None" else None

        # Store the variable assignment
        start = min(cursor.position(), cursor.anchor())
        end = max(cursor.position(), cursor.anchor())
        self.highlighted_ranges.append({
            'start': start,
            'end': end,
            'var_name': var_name.strip(),
            'match_type': match_type
        })

        # Update highlights
        self.update_highlights()
        self.selection_changed.emit()

    def update_highlights(self):
        extra_selections = []
        for rng in self.highlighted_ranges:
            selection = QtWidgets.QTextEdit.ExtraSelection()
            cursor = self.textCursor()
            cursor.setPosition(rng['start'])
            cursor.setPosition(rng['end'], QtGui.QTextCursor.MoveMode.KeepAnchor)
            selection.cursor = cursor
            selection.format.setBackground(QtGui.QColor("#C1E1C1"))  # Light green background
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def clear_highlights(self):
        self.highlighted_ranges = []
        self.setExtraSelections([])
        self.selection_changed.emit()


class UglyParsingWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(UglyParsingWidget, self).__init__(parent)
        self.setupUi()

    def setupUi(self):
        self.mode = "Mode"

        self.resize(1000, 600)
        self.setObjectName("parsers")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self)
        self.splitter = QtWidgets.QSplitter(self)
        self.splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.verticalLayout_5.addWidget(self.splitter)

        self.verticalLayoutWidget = QtWidgets.QWidget(self.splitter)
        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)

        self.label = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)

        # Initialize teSource with PlainTextOnlyTextEdit; will replace in modeComboBoxChanged if needed
        self.teSource = PlainTextOnlyTextEdit(self.verticalLayoutWidget)
        self.teSource.setObjectName("teSource")
        self.verticalLayout.addWidget(self.teSource)

        self.label_2 = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.label_2.setObjectName("label_2")
        self.verticalLayout.addWidget(self.label_2)

        self.teTemplate = PlainTextOnlyTextEdit(self.verticalLayoutWidget)
        self.teTemplate.setObjectName("teTemplate")
        self.verticalLayout.addWidget(self.teTemplate)

        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.pbRender = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.pbRender.setObjectName("pbRender")
        self.pbRender.setStyleSheet("background-color: #006400; color: white;")
        self.pbRender.clicked.connect(lambda: self.render(self.mode))

        self.horizontalLayout.addWidget(self.pbRender)

        self.pbClear = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.pbClear.setObjectName("pbClear")
        self.pbClear.setStyleSheet("background-color: #8B6508; color: white;")
        self.pbClear.clicked.connect(lambda: self.clear())
        self.horizontalLayout.addWidget(self.pbClear)

        self.pbExample = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.pbExample.clicked.connect(lambda: self.loadExample(self.mode))
        self.pbExample.setObjectName("pbExample")
        self.horizontalLayout.addWidget(self.pbExample)

        self.modeComboBox = QtWidgets.QComboBox(self.verticalLayoutWidget)
        self.modeComboBox.setObjectName("comboBox")
        self.modeComboBox.addItem("Mode")
        self.modeComboBox.addItem("TTP")
        self.modeComboBox.addItem("Jinja2")
        self.modeComboBox.addItem("JMesPath")
        self.modeComboBox.addItem("TTP Assisted")  # Added TTP Assisted mode
        self.modeComboBox.currentIndexChanged.connect(self.modeComboBoxChanged)
        self.horizontalLayout.addWidget(self.modeComboBox)

        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout.addLayout(self.horizontalLayout_2)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.verticalLayoutWidget_2 = QtWidgets.QWidget(self.splitter)
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_2)
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)

        self.label_3 = QtWidgets.QLabel(self.verticalLayoutWidget_2)
        self.label_3.setObjectName("label_3")
        self.verticalLayout_4.addWidget(self.label_3)

        self.teResult = QtWidgets.QTextEdit(self.verticalLayoutWidget_2)
        self.teResult.setObjectName("teResult")
        self.verticalLayout_4.addWidget(self.teResult)

        self.highlighterComboBox = QtWidgets.QComboBox(self.verticalLayoutWidget)
        self.highlighterComboBox.setObjectName("highlighterComboBox")
        self.highlighterComboBox.addItem("No Highlighter")
        self.highlighterComboBox.addItem("JSON Highlighter")
        self.highlighterComboBox.addItem("Cisco Highlighter")
        self.highlighterComboBox.addItem("Ansible Highlighter")
        self.highlighterComboBox.currentIndexChanged.connect(self.highlighterComboBoxChanged)
        self.highlighterComboBox.setVisible(False)
        self.verticalLayout_4.addWidget(self.highlighterComboBox)

        self.modeComboBox.setCurrentIndex(0)
        self.source_highlighter = SyntaxHighlighter(self.teSource.document())
        self.template_highlighter = SyntaxHighlighter(self.teTemplate.document())
        self.result_highlighter = SyntaxHighlighter(self.teResult.document())

        self.modeComboBox.currentIndexChanged.connect(self.modeComboBoxChanged)
        QtCore.QMetaObject.connectSlotsByName(self)

        _translate = QtCore.QCoreApplication.translate
        self.label.setText(_translate("parsers", "Source"))
        self.label_2.setText(_translate("parsers", "Template"))
        self.pbRender.setText(_translate("parsers", "Render"))
        self.pbClear.setText(_translate("parsers", "Clear"))
        self.pbExample.setText(_translate("parsers", "Example"))
        self.modeComboBox.setItemText(0, _translate("parsers", "Mode"))
        self.modeComboBox.setItemText(1, _translate("parsers", "TTP"))
        self.modeComboBox.setItemText(2, _translate("parsers", "Jinja2"))
        self.modeComboBox.setItemText(3, _translate("parsers", "JMesPath"))
        self.modeComboBox.setItemText(4, _translate("parsers", "TTP Assisted"))
        self.label_3.setText(_translate("parsers", "Result"))

    def highlighterComboBoxChanged(self, index):
        # Remove any existing highlighter
        if hasattr(self, "highlighter"):
            self.highlighter.setDocument(None)
            del self.highlighter

        # Add the selected highlighter
        self.highlighter = SyntaxHighlighter(self.teResult.document())
        if index == 1:  # JSON Highlighter
            self.highlighter.set_syntax_type("json")
        elif index == 2:  # Cisco Highlighter
            self.highlighter.set_syntax_type("keyword")
            self.highlighter.load_keywords_from_file("./keywords/cisco_keywords.txt")
        elif index == 3:  # Ansible Highlighter
            self.highlighter.set_syntax_type("keyword")
            self.highlighter.load_keywords_from_file("./keywords/ansible_keywords.txt")

    def clear(self):
        self.teResult.clear()
        self.teSource.clear()
        self.teTemplate.clear()
        if hasattr(self.teSource, 'clear_highlights'):
            self.teSource.clear_highlights()

    def modeComboBoxChanged(self, index):
        self.mode = self.modeComboBox.currentText()

        # Disconnect signals to prevent multiple connections
        try:
            self.teSource.textChanged.disconnect()
            self.teTemplate.textChanged.disconnect()
        except:
            pass

        if hasattr(self.teSource, 'selection_changed'):
            self.teSource.selection_changed.disconnect()

        # Replace teSource if needed
        self.verticalLayout.removeWidget(self.teSource)
        if self.mode == "TTP Assisted":
            self.teSource = HighlightedTextEdit(self.verticalLayoutWidget)
        else:
            self.teSource = PlainTextOnlyTextEdit(self.verticalLayoutWidget)
        self.verticalLayout.insertWidget(1, self.teSource)
        self.source_highlighter = SyntaxHighlighter(self.teSource.document())

        self.source_highlighter.setDocument(self.teSource.document())
        self.template_highlighter.setDocument(self.teTemplate.document())
        self.result_highlighter.setDocument(self.teResult.document())

        if self.mode == "TTP":
            # Existing code for TTP mode
            self.source_highlighter.set_syntax_type("jinja")
            self.template_highlighter.set_syntax_type("jinja")
            self.result_highlighter.set_syntax_type("json")
            self.pbRender.setEnabled(True)
            self.pbRender.setVisible(True)
            self.highlighterComboBox.setVisible(True)
        elif self.mode == "Jinja2":
            # Existing code for Jinja2 mode
            self.source_highlighter.set_syntax_type("yaml")
            self.template_highlighter.set_syntax_type("jinja")
            self.result_highlighter.set_syntax_type("json")
            self.pbRender.setEnabled(True)
            self.pbRender.setVisible(True)
            self.highlighterComboBox.setVisible(True)
        elif self.mode == "JMesPath":
            # Existing code for JMesPath mode
            self.source_highlighter.set_syntax_type("json")
            self.template_highlighter.set_syntax_type("json")
            self.result_highlighter.set_syntax_type("json")
            self.pbRender.setEnabled(True)
            self.pbRender.setVisible(True)
            self.highlighterComboBox.setVisible(True)
        elif self.mode == "TTP Assisted":
            self.source_highlighter.set_syntax_type("plain")
            self.template_highlighter.set_syntax_type("jinja")
            self.result_highlighter.set_syntax_type("json")
            self.pbRender.setEnabled(False)
            self.pbRender.setVisible(False)
            self.highlighterComboBox.setVisible(False)
            self.teSource.selection_changed.connect(self.update_ttp_assisted_template)
            self.teSource.textChanged.connect(self.on_text_changed)
            self.teTemplate.setReadOnly(True)

            # **Clear the text boxes when switching to TTP Assisted**
            self.teSource.clear()
            self.teTemplate.clear()
            self.teResult.clear()
            if hasattr(self.teSource, 'clear_highlights'):
                self.teSource.clear_highlights()
        else:
            # Default case
            self.pbRender.setEnabled(True)
            self.pbRender.setVisible(True)
            self.highlighterComboBox.setVisible(True)

    def loadExample(self, mode):
        if mode != "Mode":
            if mode != "TTP Assisted":
                self.teTemplate.setText(p_examples[mode]['teTemplate'])
                self.teSource.setText(p_examples[mode]['teSource'])
            else:
                # self.teTemplate.clear()
                self.teSource.setText(p_examples['TTP']['teSource'])
        else:
            self.notify("Select Mode", "Please select a mode first ... TTP, Jinja etc")

    def notify(self, message, info):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(info)
        msg.setWindowTitle(message)
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        retval = msg.exec()

    def render(self, mode):
        if mode == "Mode":
            self.notify("Select Mode", "Please select a mode first ... TTP, Jinja etc")
            return
        if mode == "TTP":
            self.render_ttp()
        elif mode == "Jinja2":
            self.render_jinja()
        elif mode == "JMesPath":
            self.render_jpath()
        elif mode == "TTP Assisted":
            # Do nothing; rendering is on-the-fly
            pass

    def render_jpath(self):
        parsed_output = ""
        try:
            parsed_output = json.loads(self.teSource.toPlainText())  # Load into dictionary
        except Exception as e:
            self.teResult.setText(f"Error loading json source")

        jp_qry = self.teTemplate.toPlainText()  # example query
        outputdict = {}
        try:
            outputdict = jmespath.search(jp_qry, parsed_output)  # run the query, output is a dictionary
            result = json.dumps(outputdict, indent=2)  # Strip the outer list object
            self.teResult.setText(result)
        except Exception as e:
            self.teResult.setText(f"Error Rendering JMesPath: {e}")

    def render_jinja(self):
        try:
            config_dict = yaml.safe_load(self.teSource.toPlainText())
            template_text = self.teTemplate.toPlainText()
            jinja_template = Template(template_text)

            result = jinja_template.render(config_dict)
            self.teResult.setPlainText(result)
        except yaml.parser.ParserError as err:
            self.teResult.setPlainText(f"YAML Error: Parsing Error: {err}")
        except Exception as e:
            self.teResult.setPlainText(str(e))

    def render_ttp(self):
        data_to_parse = self.teSource.toPlainText()
        ttp_template = self.teTemplate.toPlainText()

        try:
            parser = ttp(data=data_to_parse, template=ttp_template)
            parser.parse()
            result = parser.result(format='json')[0]
            self.teResult.setPlainText(result)

        except Exception as e:
            if "index out of range" in str(e):
                e = str(e) + " ... No Data?"
            self.teResult.setPlainText(f"Error Parsing Via TTP: {e}")

    # Methods for TTP Assisted mode
    def on_text_changed(self):
        # Clear highlights and variables when text changes
        if hasattr(self.teSource, 'clear_highlights'):
            self.teSource.clear_highlights()
            self.teTemplate.clear()
            self.teResult.clear()

    def update_ttp_assisted_template(self):
        template_text = self.generate_ttp_assisted_template()
        self.teTemplate.setPlainText(template_text)
        self.update_ttp_assisted()

    def generate_ttp_assisted_template(self):
        sample_text = self.teSource.toPlainText()
        lines = sample_text.splitlines(keepends=True)
        line_positions = []
        current_pos = 0
        for line in lines:
            line_length = len(line)
            line_start = current_pos
            line_end = current_pos + line_length
            line_positions.append({'index': len(line_positions), 'start': line_start, 'end': line_end, 'text': line})
            current_pos += line_length

        line_variables = {}
        for rng in self.teSource.highlighted_ranges:
            for line_info in line_positions:
                line_start = line_info['start']
                line_end = line_info['end']
                if rng['start'] >= line_start and rng['end'] <= line_end:
                    idx = line_info['index']
                    if idx not in line_variables:
                        line_variables[idx] = []
                    line_variables[idx].append(rng)
                    break

        template_lines = []
        for line_info in line_positions:
            idx = line_info['index']
            line_text = line_info['text']
            if idx in line_variables:
                vars_in_line = line_variables[idx]
                vars_in_line.sort(key=lambda x: x['start'])
                line_start = line_info['start']
                new_line = ''
                last_pos = line_start
                for var in vars_in_line:
                    var_start = var['start']
                    var_end = var['end']
                    rel_start = var_start - line_start
                    rel_end = var_end - line_start

                    new_line += line_text[last_pos - line_start:rel_start]

                    if var['match_type']:
                        var_string = f"{{{{ {var['var_name']} | {var['match_type']} }}}}"
                    else:
                        var_string = f"{{{{ {var['var_name']} }}}}"

                    new_line += var_string
                    last_pos = var_end

                new_line += line_text[last_pos - line_start:]
                template_lines.append(new_line)
            else:
                # Include lines without variables if needed
                # template_lines.append(line_text)
                pass  # Skip lines without variables

        return ''.join(template_lines)

    def update_ttp_assisted(self):
        data_to_parse = self.teSource.toPlainText()
        ttp_template = self.teTemplate.toPlainText()

        if not data_to_parse.strip() or not ttp_template.strip():
            self.teResult.clear()
            return

        try:
            parser = ttp(data=data_to_parse, template=ttp_template)
            parser.parse()
            result = parser.result(format='json')[0]
            self.teResult.setPlainText(result)
        except Exception as e:
            self.teResult.setPlainText(f"Error Parsing Via TTP Assisted: {e}")


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    MainWindow = QtWidgets.QMainWindow()
    ui = UglyParsingWidget()
    MainWindow.setCentralWidget(ui)  # Set the widget as the central widget
    MainWindow.show()
    sys.exit(app.exec())
