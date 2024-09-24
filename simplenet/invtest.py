import sys

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget, QApplication

from simplenet.gui.forms.crud import CRUDWidget
from simplenet.gui.forms.sqltool import SQLQueryWidget


def main():
    app = QApplication(sys.argv)
    main_window = QWidget()
    main_window.setWindowTitle('Tabbed PySimpleNet')
    main_layout = QVBoxLayout()

    tab_widget = QTabWidget()

    crud_widget = CRUDWidget()
    sql_widget = SQLQueryWidget(None)  # Passing None as there might not be a connection initially

    tab_widget.addTab(crud_widget, "CRUD Manager")
    tab_widget.addTab(sql_widget, "SQL Query Tool")

    main_layout.addWidget(tab_widget)
    main_window.setLayout(main_layout)
    main_window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()