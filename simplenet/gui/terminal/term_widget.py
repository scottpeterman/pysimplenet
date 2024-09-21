from PyQt6.QtCore import QTimer, QRect, Qt, QEvent, pyqtSignal, QObject
from PyQt6.QtWidgets import QApplication, QWidget, QScrollBar, QHBoxLayout, \
    QSizePolicy, QMenu, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QAction, QFont, QBrush, QColor, QPen, QFontMetrics, QPixmap
import sys
import traceback
# Import the SSHLib or replace it with your own terminal backend
from simplenet.gui.terminal.backend import SSHLib

# Define keymap and align constants as in your original code
keymap = {
    Qt.Key.Key_Backspace: chr(127).encode(),
    Qt.Key.Key_Escape: chr(27).encode(),
    Qt.Key.Key_AsciiTilde: chr(126).encode(),
    Qt.Key.Key_Up: b'\x1b[A',
    Qt.Key.Key_Down: b'\x1b[B',
    Qt.Key.Key_Left: b'\x1b[D',
    Qt.Key.Key_Right: b'\x1b[C',
    Qt.Key.Key_Tab: b'\t',
    Qt.Key.Key_PageUp: "~1".encode(),
    Qt.Key.Key_PageDown: "~2".encode(),
    Qt.Key.Key_Home: "~H".encode(),
    Qt.Key.Key_End: "~F".encode(),
    Qt.Key.Key_Insert: "~3".encode(),
    Qt.Key.Key_Delete: "~4".encode(),
    Qt.Key.Key_F1: "\x1bOP".encode(),
    Qt.Key.Key_F2: "\x1bOQ".encode(),
    Qt.Key.Key_F3: "\x1bOR".encode(),
    Qt.Key.Key_F4: "\x1bOS".encode(),
    Qt.Key.Key_F6: b"\x1b\x5b\x31\x37\x7e",
    Qt.Key.Key_F7: b"\x1b\x5b\x31\x38\x7e",
    Qt.Key.Key_F8: b"\x1b\x5b\x31\x39\x7e",
    Qt.Key.Key_F9: b"\x1b\x5b\x32\x30\x7e",
    Qt.Key.Key_F10: b"^[[21~",
    Qt.Key.Key_F11: b"\x1b\x5b\x32\x33\x7e",
    Qt.Key.Key_F12: b"\x1b\x5b\x32\x34\x7e"
}
align = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft

class AppEventFilter(QObject):  # Subclass QObject
    def __init__(self, parent=None):
        super(AppEventFilter, self).__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab:
                print("Tab key pressed, will send through SSH")
                # Your logic to send the Tab character through SSH
                return True  # event is handled
        return False  # continue event propagation
class SSHTerminalWidget(QWidget):

    ssh_failed_upwards_signal = pyqtSignal(str)
    # ssh_failed_signal = pyqtSignal(str)
    # ...
    colors = {
        'black': QColor(0x00, 0x00, 0x00),
        'red': QColor(0xaa, 0x00, 0x00),
        'green': QColor(0x00, 0xaa, 0x00),
        'blue': QColor(0x00, 0x00, 0xaa),
        'cyan': QColor(0x00, 0xaa, 0xaa),
        'brown': QColor(0xaa, 0xaa, 0x00),
        'yellow': QColor(0xff, 0xff, 0x44),
        'magenta': QColor(0xaa, 0x00, 0xaa),
        'white': QColor(0xff, 0xff, 0xff)
    }

    def __init__(self, parent=None, host=None, user=None, password=None, port=22, channel=None):
        super(SSHTerminalWidget, self).__init__(parent)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.startTimer(100)
        self.parent=parent
        self.host = host
        self.font_name = "Consolas"  # Use a monospaced font: Monospace, Consolas
        self.font_p_size = 16
        self.font = self.new_font()

        # Handle text selection and clipboard copy
        self.selected_text = ""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # Initialize other variables
        self.fontmanager = QFontMetrics(self.font)
        self._char_height = self.fontmanager.height()
        self._char_width = self.fontmanager.horizontalAdvance("W")
        self._columns, self._rows = self._pixel2pos(self.width(), self.height())

        self.cursor_x = 0
        self.cursor_y = 0
        self._selection = None

        # Cache
        self.pens = {}
        self.brushes = {}
        self.default_brush = QBrush(self.colors['black'])
        self.default_pen = QPen(self.colors['white'])

        # Instantiate the SSHLib here
        # Check if a channel is provided
        if channel:
            self.backend = SSHLib(self._columns, self._rows, channel=channel)  # Use the existing channel
        else:
            # Instantiate the SSHLib with connection parameters
            self.backend = SSHLib(self._columns, self._rows, host, user, password)

        # self.backend = SSHLib(self._columns, self._rows, host, user, password)
        self.backend.ssh_failed_signal.connect(self.handle_ssh_failure)

        # Instantiate a QPixmap for painting
        self.pixmap = QPixmap(self.width(), self.height())

        # Scroll
        self.scroll = None

        # Initialize variables for text selection
        self.selection_start = None
        self.selection_end = None

        # Install an event filter to capture mouse events
        self.installEventFilter(self)

    def handle_ssh_failure(self, error_message):
        self.ssh_failed_upwards_signal.emit(error_message)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab:
                print("Tab key pressed, will send through SSH")
                # Your logic to send the Tab character through SSH
                try:
                    self.send(b"\t")
                except:
                    print(f"tab proces failed")
                return True  # event is handled

        if event.type() == QEvent.Type.MouseButtonPress and event.buttons() & Qt.MouseButton.LeftButton:
            print("[Mouse Press] X:", event.pos().x(), "Y:", event.pos().y())
            self.selection_start = self._pixel2pos(event.pos().x(), event.pos().y())
            self.selection_end = self.selection_start
            print(f"Selection Start: {self.selection_start}, Selection End: {self.selection_end}")
            self.update()

        elif event.type() == QEvent.Type.MouseMove and self.selection_start:
            self.selection_end = self._pixel2pos(event.pos().x(), event.pos().y())
            print(f"Mouse moving: Updating Selection End to {self.selection_end}")
            self.update()


        elif event.type() == QEvent.Type.MouseButtonRelease:
            if self.selection_start and self.selection_end:
                print(
                    f"Mouse Released: Final Selection Start: {self.selection_start}, Selection End: {self.selection_end}")
                self.copy_selected_text_to_clipboard()
                self.clear_selection()
                self.update()

        return super().eventFilter(obj, event)

    def clear_selection(self):
        self.selection_start = None
        self.selection_end = None

    def get_pen(self, color_name):
        pen = self.pens.get(color_name)
        if not pen:
            color = self.colors.get(color_name)
            if not color:
                pen = self.default_pen
            else:
                pen = QPen(color)
            self.pens[color_name] = pen
        return pen

    def show_context_menu(self, pos):
        menu = QMenu(self)
        paste_action = QAction("Paste", self)
        paste_action.triggered.connect(self.paste_text_to_terminal)
        menu.addAction(paste_action)
        menu.exec(self.mapToGlobal(pos))

    def paste_text_to_terminal(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            try:
                self.send(text.encode("utf-8"))
            except Exception as e:
                print(e)


    def new_font(self):
        font = QFont()
        font.setFamily(self.font_name)
        font.setPixelSize(self.font_p_size)
        return font

    def copy_selected_text_to_clipboard(self):
        try:
            clipboard = QApplication.clipboard()
            start_col, start_row = self.selection_start
            end_col, end_row = self.selection_end
            if start_row > end_row or (start_row == end_row and start_col > end_col):
                start_row, end_row = end_row, start_row
                start_col, end_col = end_col, start_col

            selected_text = ""

            # Determine the order of rows (top to bottom or bottom to top)
            if start_row < end_row:
                rows_range = range(start_row, end_row + 1)
            else:
                rows_range = range(end_row, start_row + 1)

            for row in rows_range:
                line = self.backend.screen.buffer.get(row)
                if line:
                    line_text = ""

                    col_start = start_col if row == start_row else 0
                    col_end = end_col if row == end_row else len(line) - 1

                    for col in range(col_start, col_end + 1):
                        char = line[col]
                        line_text += char.data

                    selected_text += line_text
                    if row != end_row:
                        selected_text += '\n'  # Add newline only if not the last line

            clipboard.setText(selected_text)
            self.selected_text = selected_text
            print(selected_text)

        except Exception as e:
            print(e)

    # def copy_selected_text_to_clipboard(self):
    #     try:
    #         print("got to copy_selected_text_to_clipboard")
    #         clipboard = QApplication.clipboard()
    #         if self.selection_start and self.selection_end:
    #             start_col, start_row = self.selection_start
    #             end_col, end_row = self.selection_end
    #
    #             selected_text = ""
    #
    #             # Determine the order of rows (top to bottom or bottom to top)
    #             if start_row < end_row:
    #                 rows_range = range(start_row, end_row + 1)
    #             else:
    #                 rows_range = range(end_row, start_row + 1)
    #
    #             for row in rows_range:
    #                 line = self.backend.screen.buffer.get(row)
    #                 if line:
    #                     line_text = ""
    #                     for col in range(len(line)):
    #                         char = line[col]
    #                         # Check if character is within the selection range
    #                         if (
    #                                 (row == start_row and col >= start_col)
    #                                 or (row == end_row and col <= end_col)
    #                                 or (start_row < row < end_row)
    #                         ):
    #                             line_text += char.data
    #                         else:
    #                             line_text += " "  # Replace non-selected characters with spaces
    #                     selected_text += line_text
    #                     if row != end_row:
    #                         selected_text += '\n'  # Add newline only if not the last line
    #
    #             clipboard.setText(selected_text)
    #             self.selected_text = selected_text
    #             print(selected_text)
    #
    #             # self.show_message("copied selection...")
    #
    #     except Exception as e:
    #         print(e)

    def _pixel2pos(self, x, y):
        # Pixel to coordinate conversion
        col = int(x / self._char_width)
        row = int(y / self._char_height)
        print(f"Pixel ({x}, {y}) -> Position ({col}, {row})")

        return col, row

    def _pos2pixel(self, col, row):
        # Coordinate to pixel conversion
        x = col * self._char_width
        y = row * self._char_height
        print(f"Pixel ({x}, {y}) -> Position ({col}, {row})")

        return x, y

    def resizeEvent(self, event):
        # Triggered when resizing the widget
        try:
            self._columns, self._rows = self._pixel2pos(self.width(), self.height())
            self.backend.resize(self._columns, self._rows)
            self.pixmap = QPixmap(self.width(), self.height())
            self.paint_full_pixmap()
        except:
            traceback.print_exc()

    def timerEvent(self, event):
        try:
            cursor = self.backend.cursor()
            if not self.backend.screen.dirty and self.cursor_x == cursor.x and self.cursor_y == cursor.y:
                return

            self.paint_part_pixmap()
            self.update()
        except:
            traceback.print_exc()

    def draw_text(self, text, start_x, start_y, text_width, fg, bg, painter, align):
        rect = QRect(start_x, start_y, text_width, self._char_height)

        if bg and bg != 'default':
            painter.fillRect(rect, self.get_brush(bg))

        painter.setPen(self.get_pen(fg))
        painter.drawText(rect, align, text)

    def paint_full_text(self, painter):
        painter.setFont(self.font)

        for line_num in range(self._rows):
            self.paint_line_text(painter, line_num, clear=True)

    def paint_dirty_text(self, painter):
        painter.setFont(self.font)
        screen = self.backend.screen

        screen.dirty.add(self.cursor_y)

        for line_num in screen.dirty:
            self.paint_line_text(painter, line_num, clear=True)

        screen.dirty.clear()

    def paint_line_text(self, painter, line_num, clear=False):
        start_x = 0
        start_y = line_num * self._char_height
        screen = self.backend.screen

        if clear:
            clear_rect = QRect(start_x, start_y, self.width(), self._char_height)
            painter.fillRect(clear_rect, self.default_brush)

        line = screen.buffer[line_num]

        same_text = ""
        text_width = 0
        pre_char = None

        for col in range(screen.columns):
            char = line[col]
            if pre_char and char.fg == pre_char.fg and char.bg == pre_char.bg:
                same_text += char.data
                continue
            else:
                if same_text:
                    text_width = self.fontmanager.horizontalAdvance(same_text)
                    self.draw_text(same_text, start_x, start_y, text_width, pre_char.fg, pre_char.bg, painter, align)

                pre_char = char
                same_text = char.data
                start_x = start_x + text_width

        if same_text:
            text_width = self.fontmanager.horizontalAdvance(same_text)
            self.draw_text(same_text, start_x, start_y, text_width, pre_char.fg, pre_char.bg, painter, align)


    def get_brush(self, color_name):
        brush = self.brushes.get(color_name)
        if not brush:
            color = self.colors.get(color_name)
            if not color:
                brush = self.default_brush
            else:
                brush = QBrush(color)
            self.brushes[color_name] = brush
        return brush

    def pain_cursor(self, painter):
        cursor = self.backend.cursor()
        self.cursor_x = cursor.x
        self.cursor_y = cursor.y

        bcol = QColor(0x00, 0xaa, 0x00, 80)
        brush = QBrush(bcol)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(brush)
        painter.drawRect(QRect(self.cursor_x * self._char_width, self.cursor_y * self._char_height, self._char_width,
                               self._char_height))

    def paint_full_pixmap(self):
        painter = QPainter(self.pixmap)
        self.paint_full_text(painter)
        self.pain_cursor(painter)

    def paint_part_pixmap(self):
        painter = QPainter(self.pixmap)
        self.paint_dirty_text(painter)
        self.pain_cursor(painter)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)

        if self.selection_start and self.selection_end:
            # Set a transparent pen to avoid outlines
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0x00, 0x00, 0xFF, 100)))  # Blue background for selection

            start_col, start_row = self.selection_start
            end_col, end_row = self.selection_end

            # Ensure start is always before end
            if start_row > end_row or (start_row == end_row and start_col > end_col):
                start_col, start_row, end_col, end_row = end_col, end_row, start_col, start_row

            # Iterate through rows and columns to highlight characters
            for row in range(start_row, end_row + 1):
                col_start = start_col if row == start_row else 0
                col_end = end_col if row == end_row else self._columns - 1

                for col in range(col_start, col_end + 1):
                    x, y = self._pos2pixel(col, row)
                    painter.drawRect(x, y, self._char_width, self._char_height)

    def send(self, data):
        self.backend.write(data)

    def keyPressEvent(self, event):
        if not self.backend.channel.closed:

            try:
                text = str(event.text())
                key = event.key()
                native_modifiers = event.nativeModifiers()
                if key == Qt.Key.Key_Tab:
                    # Your logic to send the Tab character over SSH
                    event.accept()
                    self.send(b'\t')
                    return
                if text and key != Qt.Key.Key_Backspace:
                    self.send(text.encode("utf-8"))
                else:
                    s = keymap.get(key)
                    if s:
                        self.send(s)
                event.accept()
            except Exception as e:
                print(f"Keypress exception: {e}")
        else:
            print("connection closed")
            self.parent.term.hide()
            self.parent.scroll_bar.hide()
            # self.close()


    def wheelEvent(self, event):
        try:
            y = event.angleDelta().y()
            if y > 0:
                self.backend.screen.prev_page()
            else:
                self.backend.screen.next_page()
            self.update()
        except:
            traceback.print_exc()


class SSHTerminal(QWidget):
    def __init__(self, host=None, user=None, password=None, port=22):
        super(SSHTerminal, self).__init__()
        self.resize(800, 600)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.event_filter = AppEventFilter()  # Create an instance of your event filter class
        self.installEventFilter(self.event_filter)
        # Create a QVBoxLayout for the main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.host = host
        # Create a QHBoxLayout for the terminal widget and scrollbar
        terminal_layout = QHBoxLayout()
        terminal_layout.setContentsMargins(0, 0, 0, 0)

        self.term = SSHTerminalWidget(self, host=host, user=user, password=password, port=port)
        self.term.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.term.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.term.installEventFilter(self.event_filter)
        # Add the SSHTerminalWidget to the QHBoxLayout
        terminal_layout.addWidget(self.term)

        self.scroll_bar = QScrollBar(Qt.Orientation.Vertical, self.term)

        # Add the QScrollBar to the QHBoxLayout
        terminal_layout.addWidget(self.scroll_bar)

        self.term.scroll = self.scroll_bar

        # Create a QLabel for displaying messages
        self.message_label = QLabel()
        self.message_label.setText("")
        self.message_label.setMaximumHeight(20)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)


        # Add the QHBoxLayout and QLabel to the main QVBoxLayout
        main_layout.addLayout(terminal_layout)
        main_layout.addWidget(self.message_label)

        # Set the main_layout as the layout for this widget
        self.setLayout(main_layout)

        # Create a QTimer for hiding the message after 2 seconds
        self.message_timer = QTimer(self)
        self.message_timer.timeout.connect(self.hide_message)

    def show_message(self, message):
        # Display the message in the label and start the timer to hide it
        self.message_label.setText(message)
        self.message_label.setVisible(True)
        self.message_label.show()
        self.message_timer.start(2000)

    def hide_message(self):
        # Clear the message and stop the timer
        self.message_label.setText("")
        self.message_timer.stop()

    def closeEvent(self, event):
        if not self.term.backend.channel.closed:
            self.term.backend.close()
        else:

            self.term.close()
            # self.close()


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        win = SSHTerminal("10.0.0.108", "speterman", "letme1n")
        win.show()

        sys.exit(app.exec())
    except:
        traceback.print_exc()
