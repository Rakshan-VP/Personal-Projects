import sys
import sqlite3
from datetime import datetime
from collections import defaultdict

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QListWidget, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QInputDialog, QListWidgetItem,
    QGroupBox
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QHeaderView

import pyqtgraph as pg

DB_NAME = "expenses.db"


# ---------------- Detailed Window ---------------- #
class DetailWindow(QDialog):
    def __init__(self, parent, rows):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Detailed Expenses")
        self.resize(600, 450)

        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Date", "Category", "Place", "Amount"]
        )
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(row[0])))
            self.table.setItem(r, 1, QTableWidgetItem(str(row[3])))
            self.table.setItem(r, 2, QTableWidgetItem(str(row[1])))
            self.table.setItem(r, 3, QTableWidgetItem(str(row[2])))
            self.table.setItem(r, 4, QTableWidgetItem(str(row[4])))

        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        delete_btn = QPushButton("Delete Selected Expense")
        delete_btn.clicked.connect(self.delete_selected)
        layout.addWidget(delete_btn)

        self.setLayout(layout)

    def delete_selected(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            return

        expense_id = self.table.item(selected_row, 0).text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete this expense?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.parent.cursor.execute(
                "DELETE FROM expenses WHERE id=?",
                (expense_id,)
            )
            self.parent.conn.commit()
            self.parent.refresh_all()
            self.accept()


# ---------------- Main App ---------------- #
class ExpenseTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minimal Smart Expense Tracker")
        self.resize(1200, 750)

        self.current_mode = "category"
        self.selected_category = None

        self.init_db()
        self.init_ui()
        self.apply_dark_theme()
        self.load_categories()
        self.load_months()
        self.refresh_all()

    # ---------------- DATABASE ---------------- #
    def init_db(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.cursor = self.conn.cursor()

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS places(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                category_id INTEGER
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                place TEXT,
                date TEXT,
                amount REAL
            )
        """)

        self.conn.commit()

    # ---------------- UI ---------------- #
    def init_ui(self):
        main_layout = QHBoxLayout()

        left_layout = QVBoxLayout()

        input_group = QGroupBox("Add Expense")
        input_layout = QVBoxLayout()

        input_layout.addWidget(QLabel("Category"))
        self.category_box = QComboBox()
        self.category_box.currentIndexChanged.connect(self.load_places)
        input_layout.addWidget(self.category_box)

        add_cat_btn = QPushButton("+ Add Category")
        add_cat_btn.clicked.connect(self.add_category)
        input_layout.addWidget(add_cat_btn)

        input_layout.addWidget(QLabel("Place"))
        self.place_box = QComboBox()
        input_layout.addWidget(self.place_box)

        add_place_btn = QPushButton("+ Add Place")
        add_place_btn.clicked.connect(self.add_place)
        input_layout.addWidget(add_place_btn)

        input_layout.addWidget(QLabel("Amount"))
        self.amount_input = QLineEdit()
        input_layout.addWidget(self.amount_input)

        input_layout.addWidget(QLabel("Date"))
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        input_layout.addWidget(self.date_input)

        add_btn = QPushButton("Add Expense")
        add_btn.clicked.connect(self.add_expense)
        input_layout.addWidget(add_btn)

        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)

        left_layout.addWidget(QLabel("Month"))
        self.month_box = QComboBox()
        self.month_box.currentIndexChanged.connect(self.month_changed)
        left_layout.addWidget(self.month_box)

        summary_group = QGroupBox("Monthly Category Summary")
        summary_layout = QVBoxLayout()

        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Category", "Expense"])
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.summary_table.verticalHeader().setVisible(False)

        summary_layout.addWidget(self.summary_table)
        summary_group.setLayout(summary_layout)
        left_layout.addWidget(summary_group)

        detail_btn = QPushButton("View Detailed Expenses")
        detail_btn.clicked.connect(self.open_details)
        left_layout.addWidget(detail_btn)

        main_layout.addLayout(left_layout, 1)

        right_layout = QVBoxLayout()

        pie_group = QGroupBox("Expense Distribution")
        pie_layout = QHBoxLayout()

        self.pie_chart = pg.PlotWidget()
        self.pie_chart.setBackground("#121212")
        self.pie_chart.setAspectLocked(True)
        self.pie_chart.setMouseEnabled(False, False)
        self.pie_chart.hideAxis('left')
        self.pie_chart.hideAxis('bottom')
        self.pie_chart.hideAxis('right')
        self.pie_chart.hideAxis('top')
        self.pie_chart.showGrid(x=False, y=False)

        self.legend_list = QListWidget()
        self.legend_list.setMaximumWidth(200)
        self.legend_list.setStyleSheet("""
        QListWidget {
            font-size: 20px;
        }

        QListWidget::item {
            padding: 10px 0px;
        }
        """)

        self.legend_list.setSpacing(8)
        self.legend_list.itemClicked.connect(self.legend_clicked)

        pie_layout.addWidget(self.pie_chart, 3)
        pie_layout.addWidget(self.legend_list, 1)

        pie_group.setLayout(pie_layout)
        right_layout.addWidget(pie_group)

        self.back_btn = QPushButton("Back to Categories")
        self.back_btn.clicked.connect(self.back_to_main)
        self.back_btn.hide()
        right_layout.addWidget(self.back_btn)

        report_group = QGroupBox("Monthly Report")
        report_layout = QVBoxLayout()

        self.report_label = QLabel("")
        self.report_label.setWordWrap(True)
        self.report_label.setFont(QFont("Arial", 10))
        report_layout.addWidget(self.report_label)

        report_group.setLayout(report_layout)
        right_layout.addWidget(report_group)

        main_layout.addLayout(right_layout, 2)
        self.setLayout(main_layout)

    # ---------------- DARK THEME ---------------- #
    def apply_dark_theme(self):
        self.setStyleSheet("""
        QWidget {
            background-color: #121212;
            color: #E0E0E0;
            font-size: 13px;
        }

        QGroupBox {
            border: 1px solid #2C2C2C;
            border-radius: 8px;
            margin-top: 10px;
            padding: 10px;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #BBBBBB;
        }

        QPushButton {
            background-color: #1F1F1F;
            border: 1px solid #333;
            padding: 6px;
            border-radius: 6px;
        }

        QPushButton:hover {
            background-color: #2A2A2A;
        }

        QLineEdit, QComboBox, QDateEdit {
            background-color: #1E1E1E;
            border: 1px solid #333;
            padding: 4px;
            border-radius: 4px;
        }

        QTableWidget {
            background-color: #1A1A1A;
            gridline-color: #2C2C2C;
            border: none;
        }

        QHeaderView::section {
            background-color: #1A1A1A;
            color: #E0E0E0;
            border: 1px solid #2C2C2C;
            padding: 4px;
        }

        QTableCornerButton::section {
            background-color: #1A1A1A;
            border: 1px solid #2C2C2C;
        }

        QListWidget {
            background-color: #1A1A1A;
            border: 1px solid #2C2C2C;
        }
        """)

    # ---------------- CATEGORY / PLACE ---------------- #
    def add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category name:")
        if ok and name.strip():
            try:
                self.cursor.execute(
                    "INSERT INTO categories(name) VALUES(?)",
                    (name.strip(),)
                )
                self.conn.commit()
                self.load_categories()
            except:
                QMessageBox.information(self, "Info", "Category already exists.")

    def add_place(self):
        cat = self.category_box.currentText()
        if not cat:
            QMessageBox.information(self, "Info", "Select a category first.")
            return

        name, ok = QInputDialog.getText(self, "Add Place", "Place name:")
        if ok and name.strip():
            self.cursor.execute("SELECT id FROM categories WHERE name=?", (cat,))
            cat_id = self.cursor.fetchone()

            if cat_id:
                self.cursor.execute(
                    "INSERT INTO places(name, category_id) VALUES(?, ?)",
                    (name.strip(), cat_id[0])
                )
                self.conn.commit()
                self.load_places()

    def load_categories(self):
        self.category_box.clear()
        self.cursor.execute("SELECT name FROM categories")
        for row in self.cursor.fetchall():
            self.category_box.addItem(row[0])
        self.load_places()

    def load_places(self):
        self.place_box.clear()
        cat = self.category_box.currentText()
        if not cat:
            return
        self.cursor.execute("SELECT id FROM categories WHERE name=?", (cat,))
        cat_id = self.cursor.fetchone()
        if cat_id:
            self.cursor.execute("SELECT name FROM places WHERE category_id=?", (cat_id[0],))
            for row in self.cursor.fetchall():
                self.place_box.addItem(row[0])

    def load_months(self):
        self.month_box.clear()
        self.cursor.execute(
            "SELECT DISTINCT substr(date,1,7) FROM expenses ORDER BY date"
        )
        for row in self.cursor.fetchall():
            self.month_box.addItem(row[0])

    # ---------------- ADD EXPENSE ---------------- #
    def add_expense(self):
        try:
            amount = float(self.amount_input.text())
        except:
            return

        self.cursor.execute(
            "INSERT INTO expenses(category,place,date,amount) VALUES(?,?,?,?)",
            (
                self.category_box.currentText(),
                self.place_box.currentText(),
                self.date_input.date().toString("yyyy-MM-dd"),
                amount
            )
        )
        self.conn.commit()

        self.amount_input.clear()
        self.load_months()
        self.refresh_all()

    # ---------------- REFRESH ---------------- #
    def month_changed(self):
        self.current_mode = "category"
        self.selected_category = None
        self.back_btn.hide()
        self.refresh_all()

    def refresh_all(self):
        month = self.month_box.currentText()
        if not month:
            return

        self.cursor.execute(
            "SELECT id,category,place,date,amount FROM expenses WHERE substr(date,1,7)=?",
            (month,)
        )
        rows = self.cursor.fetchall()
        self.rows = rows

        category_totals = defaultdict(float)
        place_totals = defaultdict(float)
        total = 0

        for row in rows:
            category_totals[row[1]] += row[4]
            place_totals[row[2]] += row[4]
            total += row[4]

        # ✅ Updated Summary Table
        self.summary_table.setRowCount(len(category_totals) + 1)

        row_index = 0
        for cat, val in category_totals.items():
            self.summary_table.setItem(row_index, 0, QTableWidgetItem(cat))
            self.summary_table.setItem(row_index, 1, QTableWidgetItem(f"₹{val:.2f}"))
            row_index += 1

        # Total Row
        total_item = QTableWidgetItem("Total")
        total_item.setFont(QFont("Arial", 10, QFont.Bold))
        amount_item = QTableWidgetItem(f"₹{total:.2f}")
        amount_item.setFont(QFont("Arial", 10, QFont.Bold))

        self.summary_table.setItem(row_index, 0, total_item)
        self.summary_table.setItem(row_index, 1, amount_item)

        if self.current_mode == "category":
            self.draw_pie(category_totals, total)
        else:
            self.draw_place_pie()

        self.generate_report(rows, category_totals, place_totals, total)

    # ---------------- PIE ---------------- #
    def draw_pie(self, data, total):
        self.pie_chart.clear()
        self.legend_list.clear()

        start = 0
        radius = 100

        for key, val in data.items():
            angle = 360 * (val / total) if total else 0

            color = pg.intColor(hash(key))
            qcolor = pg.mkColor(color)

            slice_item = pg.QtWidgets.QGraphicsEllipseItem(
                -radius, -radius, radius * 2, radius * 2
            )
            slice_item.setStartAngle(int(start * 16))
            slice_item.setSpanAngle(int(angle * 16))
            slice_item.setBrush(qcolor)
            self.pie_chart.addItem(slice_item)

            start += angle

            legend_item = QListWidgetItem(key)
            legend_item.setForeground(QColor(qcolor))
            self.legend_list.addItem(legend_item)

    def legend_clicked(self, item):
        self.current_mode = "place"
        self.selected_category = item.text()
        self.back_btn.show()
        self.draw_place_pie()

    def draw_place_pie(self):
        month = self.month_box.currentText()
        self.cursor.execute(
            "SELECT place, amount FROM expenses WHERE category=? AND substr(date,1,7)=?",
            (self.selected_category, month)
        )
        rows = self.cursor.fetchall()

        data = defaultdict(float)
        total = 0
        for row in rows:
            data[row[0]] += row[1]
            total += row[1]

        self.draw_pie(data, total)

    def back_to_main(self):
        self.current_mode = "category"
        self.selected_category = None
        self.back_btn.hide()
        self.refresh_all()

    # ---------------- REPORT ---------------- #
    def generate_report(self, rows, cat_totals, place_totals, total):
        if total == 0:
            self.report_label.setText("No data for this month.")
            return

        days = len(set([r[3] for r in rows]))
        avg = total / days if days else 0

        top_cat = max(cat_totals, key=cat_totals.get)
        top_place = max(place_totals, key=place_totals.get)

        percent = (cat_totals[top_cat] / total) * 100

        report = f"""
Total spent: ₹{total:.2f}
Average per active day: ₹{avg:.2f}

Highest category: {top_cat} ({percent:.1f}%)
Highest place: {top_place}

Active days this month: {days}
"""
        self.report_label.setText(report)

    # ---------------- DETAILS ---------------- #
    def open_details(self):
        if hasattr(self, "rows"):
            dialog = DetailWindow(self, self.rows)
            dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ExpenseTracker()
    window.showMaximized()
    sys.exit(app.exec_())