import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTabWidget, QTableView, QPushButton,QFileDialog, QMessageBox, QHBoxLayout, QLineEdit, QLabel, QCheckBox,QSpinBox, QInputDialog)
from PyQt6.QtCore import (QAbstractTableModel, Qt, QSortFilterProxyModel, pyqtSignal, QSettings)
import requests
import sqlite3
from datetime import datetime, timedelta

class CustomTableModel(QAbstractTableModel):
    def __init__(self, data, headers, parent=None):
        super().__init__(parent)
        self._data = data
        self._headers = headers

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self._data[index.row()][index.column()])
        return None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)
        
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return str(self._headers[section])
        return None

def send_message_to_telegram(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.post(url, params=params)
    if response.status_code != 200:
        print("Failed to send message to Telegram.")

class OpenDatabaseTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        layout = QVBoxLayout(self)
        self.conn = None  # Initialize the connection object to None

        # Button to open database file
        self.open_button = QPushButton("Open Database")
        self.open_button.clicked.connect(self.open_database)
        layout.addWidget(self.open_button)

    def open_database(self):
        # Open file dialog to choose the database file
        file_dialog = QFileDialog(self)
        db_path, _ = file_dialog.getOpenFileName(self, "Open Database File", "", "SQLite Database Files (*.db *.sqlite)")
        print("Database Path:", db_path)  # Print the database path
        if db_path:
            try:
                # Connect to SQLite database
                self.conn = sqlite3.connect(db_path)
                cur = self.conn.cursor()
                cur.execute("SELECT Id, Name, Description FROM Product WHERE Description IS NOT NULL")  # Select only rows where Description is not null
                data = cur.fetchall()
                headers = [desc[0] for desc in cur.description]
                headers[2] = "Expiry Date"
                # Add 'Remaining' column header
                headers.append('Remaining')

                # Calculate remaining days and update the data
                for i, row in enumerate(data):
                    expiry_date = datetime.strptime(row[2], "%d/%m/%Y")  # Assuming Expiry date is at index 2
                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # Current date without time
                    remaining_days = (expiry_date - today).days
                    if remaining_days <= 0:
                        remaining_text = 'Expired'
                    elif remaining_days == 1:
                        remaining_text = '1 day'
                    else:
                        remaining_text = f'{remaining_days} days'
                    data[i] = row + (remaining_text,)  # Append the remaining days text or 'Expired' to the row

                # Create table model
                model = CustomTableModel(data, headers, self)
                self.main_window.create_table_tab(model)

                # Send message to Telegram
                self.main_window.table_tab.send_to_telegram()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def refresh_data(self):
        if self.conn:  # Check if the connection object exists
            try:
                cur = self.conn.cursor()
                cur.execute("SELECT Id, Name, Description FROM Product WHERE Description IS NOT NULL")  # Select only rows where Description is not null
                data = cur.fetchall()
                headers = [desc[0] for desc in cur.description]

                # Add 'Remaining' column header
                headers.append('Remaining')

                # Calculate remaining days and update the data
                for i, row in enumerate(data):
                    expiry_date = datetime.strptime(row[2], "%d/%m/%Y")  # Assuming Expiry date is at index 2
                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # Current date without time
                    remaining_days = (expiry_date - today).days
                    if remaining_days <= 0:
                        remaining_text = 'Expired'
                    elif remaining_days == 1:
                        remaining_text = '1 day'
                    else:
                        remaining_text = f'{remaining_days} days'
                    data[i] = row + (remaining_text,)  # Append the remaining days text or 'Expired' to the row

                # Create table model
                model = CustomTableModel(data, headers, self)
                self.main_window.create_table_tab(model)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

class TableTab(QWidget):
    refreshRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Search box and refresh button layout
        search_layout = QHBoxLayout()

        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search...")
        self.search_edit.textChanged.connect(self.filter_data)  # Connect textChanged signal to filter_data method
        search_layout.addWidget(self.search_edit)

        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_data)
        search_layout.addWidget(self.refresh_button)

        # Expired checkbox
        self.expired_checkbox = QCheckBox("Expired")
        self.expired_checkbox.stateChanged.connect(self.filter_data)
        search_layout.addWidget(self.expired_checkbox)
        
        # About to expire checkbox
        self.about_to_expire_checkbox = QCheckBox("About to Expire")
        self.about_to_expire_checkbox.stateChanged.connect(self.filter_data)
        search_layout.addWidget(self.about_to_expire_checkbox)

        layout.addLayout(search_layout)

        # Table view
        self.table_view = QTableView()
        layout.addWidget(self.table_view)

        # Label to display number of products
        self.product_count_label = QLabel()
        layout.addWidget(self.product_count_label)

        self.expired_label = QLabel()
        layout.addWidget(self.expired_label)

        # Send to Telegram button
        self.send_telegram_button = QPushButton("Send to Telegram")
        self.send_telegram_button.clicked.connect(self.send_to_telegram)
        layout.addWidget(self.send_telegram_button)

        # Initialize model and proxy model
        self.model = None
        self.proxy_model = None

    def set_model(self, model):
        self.model = model
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # Filter all columns
        self.table_view.setModel(self.proxy_model)

        # Update product count label
        self.update_product_count()

    def filter_data(self):
        try:
            if self.model is None:
                QMessageBox.warning(self, "No Data", "Please open a database first.")
                return

            text = self.search_edit.text().strip().lower()  # Convert the entered text to lowercase and remove leading/trailing spaces
            
            # Get the notify before value from settings
            settings = QSettings("YourCompany", "YourApp")
            notify_before = settings.value("notify_before", 0, type=int)  # Default value of 0 if setting not found

            # Filter for expired products
            expired_data = []
            for row in range(self.model.rowCount()):
                remaining_index = self.model.index(row, self.model.columnCount() - 1)  # Index of the "Remaining" column
                remaining_value = self.model.data(remaining_index)
                if remaining_value == 'Expired':
                    expired_data.append([self.model.data(self.model.index(row, col)) for col in range(self.model.columnCount())])

            # Filter for products about to expire
            about_to_expire_data = []
            for row in range(self.model.rowCount()):
                remaining_index = self.model.index(row, self.model.columnCount() - 1)  # Index of the "Remaining" column
                remaining_value = self.model.data(remaining_index)
                if remaining_value != 'Expired':
                    remaining_days = int(remaining_value.split()[0])  # Extract remaining days
                    if remaining_days <= notify_before:
                        about_to_expire_data.append([self.model.data(self.model.index(row, col)) for col in range(self.model.columnCount())])

            # Update the model with filtered data based on checkbox states
            if self.expired_checkbox.isChecked() and self.about_to_expire_checkbox.isChecked():
                filtered_data = expired_data + about_to_expire_data
            elif self.expired_checkbox.isChecked():
                filtered_data = expired_data
            elif self.about_to_expire_checkbox.isChecked():
                filtered_data = about_to_expire_data
            else:
                filtered_data = self.model._data

            # Filter data based on search text
            filtered_data = [row for row in filtered_data if any(text in str(cell).lower() for cell in row)]

            self.proxy_model = CustomTableModel(filtered_data, self.model._headers, self)
            self.table_view.setModel(self.proxy_model)

            # Update product count label
            self.update_product_count()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def update_product_count(self):
        if self.proxy_model is not None:
            count = self.proxy_model.rowCount()
            self.product_count_label.setText(f"Number of Products: {count}")

    def refresh_data(self):
        # Emit the refreshRequested signal when the refresh button is clicked
        self.refreshRequested.emit()

    def send_to_telegram(self):
        settings = QSettings("YourCompany", "YourApp")
        bot_token = settings.value("bot_token", "")
        chat_id = settings.value("chat_id", "")
        if not bot_token or not chat_id:
            QMessageBox.warning(self, "Settings Missing", "Bot Token or Chat ID is missing. Please check your settings.")
            return

        # Get expired products
        expired_products = self.get_expired_products()

        # Initialize a list to store expired product names and reminders
        expired_messages = []
        reminder_messages = []

        if expired_products:
            # Generate message for expired products
            expired_messages.append("Expired:\n" + "\n".join([f"{name} has expired" for name in expired_products]))

        # Get reminders for expiring products
        reminders = []
        notify_before = settings.value("notify_before", 0, type=int)  # Default value of 0 if setting not found

        # Access the data from the table model via the proxy model
        if self.proxy_model is not None:
            data_count = self.proxy_model.rowCount()
            for row in range(data_count):
                # Get the index of the row
                name_index = self.proxy_model.index(row, 1)  # Assuming the second column contains the product names
                # Retrieve the product name and remaining days from the model
                product_name = self.proxy_model.data(name_index)
                remaining_days_text = self.proxy_model.data(name_index.siblingAtColumn(self.model.columnCount() - 1))  # Assuming "Remaining" column is the last column
                if remaining_days_text != 'Expired':
                    remaining_days = int(remaining_days_text.split()[0])  # Extract remaining days
                    if remaining_days <= notify_before:
                        # If the product is expiring within the specified number of days, add a reminder to the list
                        reminders.append(f"{product_name} will expire in {remaining_days} days")

        if expired_messages:
            # Send message for expired products to Telegram
            expired_message = "\n\n".join(expired_messages)
            send_message_to_telegram(bot_token, chat_id, expired_message)
            QMessageBox.information(self, "Expired Products Sent", "Expired products have been sent to Telegram.")

        if reminders:
            # Send message for reminders to Telegram
            reminders_message = "Reminder:\n" + "\n".join(reminders)
            send_message_to_telegram(bot_token, chat_id, reminders_message)
            QMessageBox.information(self, "Reminders Sent", "Reminders for expiring products have been sent to Telegram.")

        if not expired_messages and not reminders:
            QMessageBox.information(self, "No Data to Send", "There are no expired or expiring products to send.")

    def get_expired_products(self):
        expired_products = []
        if self.model is not None:
            for row in range(self.model.rowCount()):
                remaining_index = self.model.index(row, self.model.columnCount() - 1)  # Index of the "Remaining" column
                remaining_value = self.model.data(remaining_index)
                if remaining_value == 'Expired':
                    name_index = self.model.index(row, 1)  # Index of the "Name" column
                    name_value = self.model.data(name_index)
                    expired_products.append(name_value)
        return expired_products



class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.locked = True  # Start locked initially
        layout = QVBoxLayout(self)
        self.settings = QSettings("YourCompany", "YourApp")  # Create QSettings object
        self.passkey = self.settings.value("passkey", "123")  # Default passkey is "123"

        # Bot Token
        bot_token_layout = QHBoxLayout()
        bot_token_label = QLabel("Bot Token:")
        self.bot_token_edit = QLineEdit()
        bot_token_layout.addWidget(bot_token_label)
        bot_token_layout.addWidget(self.bot_token_edit)
        layout.addLayout(bot_token_layout)

        # Chat ID
        chat_id_layout = QHBoxLayout()
        chat_id_label = QLabel("Chat ID:")
        self.chat_id_edit = QLineEdit()
        chat_id_layout.addWidget(chat_id_label)
        chat_id_layout.addWidget(self.chat_id_edit)
        layout.addLayout(chat_id_layout)

        # Notify Before
        notify_layout = QHBoxLayout()
        self.notify_checkbox = QCheckBox("Notify me before")
        self.notify_spinbox = QSpinBox()
        self.notify_spinbox.setMinimum(1)
        self.notify_spinbox.setMaximum(365)
        self.notify_spinbox.setEnabled(False)
        self.notify_checkbox.stateChanged.connect(self.notify_spinbox.setEnabled)
        notify_layout.addWidget(self.notify_checkbox)
        notify_layout.addWidget(self.notify_spinbox)
        notify_layout.addWidget(QLabel("days"))
        layout.addLayout(notify_layout)

        # Unlock/Lock button
        self.unlock_button = QPushButton("Unlock Settings")
        self.unlock_button.clicked.connect(self.toggle_lock)
        layout.addWidget(self.unlock_button)

        # Change Passkey button
        self.change_passkey_button = QPushButton("Change Passkey")
        self.change_passkey_button.clicked.connect(self.change_passkey)
        layout.addWidget(self.change_passkey_button)

        # Save button
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

        layout.addStretch()  # Add stretch to push the widgets to the top

        self.load_settings()
        self.lock()  # Lock the settings at startup

    def set_enabled(self, enabled):
        self.bot_token_edit.setEnabled(enabled)
        self.chat_id_edit.setEnabled(enabled)
        self.notify_checkbox.setEnabled(enabled)
        self.notify_spinbox.setEnabled(enabled)

        if not enabled:  # If settings are disabled (locked)
            self.bot_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.chat_id_edit.setEchoMode(QLineEdit.EchoMode.Password)
        else:  # If settings are enabled (unlocked)
            self.bot_token_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.chat_id_edit.setEchoMode(QLineEdit.EchoMode.Normal)

    def lock(self):
        self.set_enabled(False)
        self.locked = True
        self.update_button_text()  # Update button text after locking

    def unlock(self):
        passkey, ok = QInputDialog.getText(self, 'Enter Passkey', 'Enter passkey:')
        if ok:
            if self.check_passkey(passkey):
                self.set_enabled(True)
                self.locked = False
                self.update_button_text()  # Update button text after unlocking
            else:
                QMessageBox.warning(self, 'Incorrect Passkey', 'Incorrect passkey. Settings remain locked.')

    def change_passkey(self):
        passkey, ok = QInputDialog.getText(self, 'Change Passkey', 'Enter current passkey:')
        if ok:
            if self.check_passkey(passkey):
                new_passkey, ok = QInputDialog.getText(self, 'Change Passkey', 'Enter new passkey:')
                if ok:
                    confirm_passkey, ok = QInputDialog.getText(self, 'Change Passkey', 'Confirm new passkey:')
                    if ok:
                        if new_passkey == confirm_passkey:
                            self.passkey = new_passkey  # Update the stored passkey
                            self.settings.setValue("passkey", self.passkey)  # Save new passkey using QSettings
                            QMessageBox.information(self, 'Passkey Changed', 'Passkey has been changed successfully.')
                        else:
                            QMessageBox.warning(self, 'Passkey Mismatch', 'New passkey and confirm passkey do not match. Passkey remains unchanged.')
            else:
                QMessageBox.warning(self, 'Incorrect Passkey', 'Incorrect passkey. Passkey remains unchanged.')

    def toggle_lock(self):
        if self.locked:
            self.unlock()
        else:
            self.lock()

    def save_settings(self):
        if self.locked:
            QMessageBox.warning(self, 'Settings Locked', 'Settings are locked. Please unlock them to save changes.')
        else:  # Save settings only if the tab is unlocked
            settings = QSettings("YourCompany", "YourApp")
            settings.setValue("bot_token", self.bot_token_edit.text())
            settings.setValue("chat_id", self.chat_id_edit.text())
            settings.setValue("notify_before", self.notify_spinbox.value() if self.notify_checkbox.isChecked() else None)
            settings.setValue("notify_checked", self.notify_checkbox.isChecked())
            QMessageBox.information(self, 'Settings Saved', 'Settings have been saved successfully.')

    def save_settings_quietly(self):
        if not self.locked:  # Save settings only if the tab is unlocked
            settings = QSettings("YourCompany", "YourApp")
            settings.setValue("bot_token", self.bot_token_edit.text())
            settings.setValue("chat_id", self.chat_id_edit.text())
            settings.setValue("notify_before", self.notify_spinbox.value() if self.notify_checkbox.isChecked() else None)
            settings.setValue("notify_checked", self.notify_checkbox.isChecked())

    def load_settings(self):
        settings = QSettings("YourCompany", "YourApp")
        self.bot_token_edit.setText(settings.value("bot_token", ""))
        self.chat_id_edit.setText(settings.value("chat_id", ""))
        notify_before = settings.value("notify_before", None)
        notify_checked = settings.value("notify_checked", False, type=bool)
        self.notify_checkbox.setChecked(notify_checked)
        if notify_before is not None:
            self.notify_spinbox.setValue(int(notify_before))
            self.notify_spinbox.setEnabled(notify_checked)
        else:
            self.notify_checkbox.setChecked(False)
            self.notify_spinbox.setEnabled(False)

    def check_passkey(self, passkey):
        return passkey == self.passkey

    def update_button_text(self):
        if self.locked:
            self.unlock_button.setText("Unlock Settings")
        else:
            self.unlock_button.setText("Lock Settings")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Expiry Date Checker")
        self.setGeometry(100, 100, 800, 500)

        layout = QVBoxLayout(self)
        tab_widget = QTabWidget()

        # Create tabs
        self.open_database_tab = OpenDatabaseTab(self)
        tab_widget.addTab(self.open_database_tab, "Open Database")

        self.table_tab = TableTab(self)
        tab_widget.addTab(self.table_tab, "Table")

        self.settings_tab = SettingsTab(self)
        tab_widget.addTab(self.settings_tab, "Settings")

        layout.addWidget(tab_widget)

        # Connect the refreshRequested signal of TableTab to the refresh_data method of OpenDatabaseTab
        self.table_tab.refreshRequested.connect(self.open_database_tab.refresh_data)

    def create_table_tab(self, model):
        self.table_tab.set_model(model)

    def closeEvent(self, event):
        self.settings_tab.save_settings_quietly()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())



