import sys
from PyQt6.QtWidgets import QApplication
from simplenet.gui.main_gui import DriverEditor

def main():
    app = QApplication(sys.argv)
    editor = DriverEditor()

    # Retrieve the primary screen
    screen = app.primaryScreen()
    if screen is not None:
        # Get the screen size
        screen_size = screen.size()
        screen_width = screen_size.width()
        screen_height = screen_size.height()

        # Calculate 80% width and 70% height
        desired_width = int(screen_width * 0.8)
        desired_height = int(screen_height * 0.8)

        # Set the window size
        editor.resize(desired_width, desired_height)

        # Optional: Center the window on the screen
        # Calculate top-left coordinates for centering
        x = (screen_width - desired_width) // 2
        y = (screen_height - desired_height) // 2
        editor.move(x, y - 50)
    else:
        # Fallback size if screen information is unavailable
        editor.resize(800, 600)

    editor.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
