import os
import sys
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtGui import *
from storage import DEFAULT_DB, ProfileError, Storage

DEFAULT_HOME = 'http://google.com'

#Tabbed browsing
class BrowserTab(QWidget):
    def __init__(self, parent=None):
        super(BrowserTab, self).__init__(parent)
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(window.homepage() if 'window' in globals() else DEFAULT_HOME))
        self.browser.loadProgress.connect(self.update_progress)
        layout = QVBoxLayout()
        layout.addWidget(self.browser)

        self.setLayout(layout)
    
    def navigate_to_url(self, url):
        if '://' not in url:
            url = 'http://' + url
        # History is recorded in SQLite when the page finishes loading (MainWindow.record_visit).
        self.browser.setUrl(QUrl(url))
    def update_progress(self, p):
        window.status.showMessage(f'Loading... {p}%', 2000 if p==100 else 0)
        
class Omnibox(QLineEdit):
    def __init__(self, parent=None):
        super(Omnibox, self).__init__(parent)
        self.history = []

    def update_history(self, url):
        if url not in self.history:
            self.history.append(url)

    def keyPressEvent(self, event):
        super(Omnibox, self).keyPressEvent(event)
        if event.key() == Qt.Key_Down:
            self.show_suggestions()
    def show_suggestions(self):
        completion_model = QStringListModel(self.history, self)
        completer = QCompleter(completion_model, self)
        self.setCompleter(completer)
        completer.complete()
        

class UserProfileDialog(QDialog):
    """Log in to an existing encrypted profile, or create a new one."""

    def __init__(self, storage, parent=None):
        super(UserProfileDialog, self).__init__(parent)
        self.storage = storage
        self.profile = None
        self.setWindowTitle("User Profile")
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.message = QLabel("Profiles are AES-256-GCM encrypted on disk with a key derived from your password.")
        self.message.setWordWrap(True)
        login_button = QPushButton("Log in")
        login_button.clicked.connect(self.log_in)
        create_button = QPushButton("Create profile")
        create_button.clicked.connect(self.create_profile)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Username"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Password"))
        layout.addWidget(self.password_input)
        layout.addWidget(login_button)
        layout.addWidget(create_button)
        layout.addWidget(self.message)
        self.setLayout(layout)

    def _credentials(self):
        return self.username_input.text().strip(), self.password_input.text()

    def log_in(self):
        username, password = self._credentials()
        try:
            self.profile = self.storage.load_profile(username, password)
        except ProfileError as e:
            self.message.setText(str(e))
            return
        self.accept()

    def create_profile(self):
        username, password = self._credentials()
        try:
            self.storage.create_profile(username, password, {"homepage": DEFAULT_HOME})
            self.profile = self.storage.load_profile(username, password)
        except ProfileError as e:
            self.message.setText(str(e))
            return
        self.accept()


class MainWindow(QMainWindow):
    
    def __init__(self):
        super(MainWindow, self).__init__()

        # History, bookmarks and encrypted profiles live in one SQLite file.
        self.storage = Storage(os.environ.get('OVERSE_DB', DEFAULT_DB))

        # Logged-in profile (decrypted in memory only)
        self.user = None
        self.password = None
        self.profile = {}

        history_action = QAction(QIcon('./images/history.png'), 'History', self)
        history_action.triggered.connect(self.show_history)

        #navbar 
        navbar = QToolBar()
        self.addToolBar(navbar)
        
        navbar.addAction(history_action)        
        #backbutton
        backbutton = QAction(QIcon('./images/back.png'), '<-', self)
        backbutton.triggered.connect(self.navigate_back)
        navbar.addAction(backbutton)

        #frontbutton
        frontbutton = QAction(QIcon('./images/forward.png'), '->', self)
        frontbutton.triggered.connect(self.navigate_forward)
        navbar.addAction(frontbutton)

        #reloadbutton
        reloadbutton = QAction(QIcon('./images/reload.png'), 'Reload', self)
        reloadbutton.triggered.connect(self.navigate_reload)
        navbar.addAction(reloadbutton)

        #homebutton
        homebutton = QAction(QIcon('./images/home.png'), 'Home', self)
        homebutton.triggered.connect(self.navigate_home)
        navbar.addAction(homebutton)
                
        #urlbar
        self.url_bar = Omnibox()
        self.url_bar.history = self.storage.history()
        self.url_bar.returnPressed.connect(self.navigatetourl)
        navbar.addWidget(self.url_bar)

        # User profile button
        user_button = QAction(QIcon('./images/user.png'), 'User', self)
        user_button.triggered.connect(self.show_user_profile)
        navbar.addAction(user_button)

        # Adding actions to the navigation bar
        add_tab_action = QAction(QIcon('./images/addtab.png'), 'Add Tab', self)
        add_tab_action.triggered.connect(self.add_tab)
        navbar.addAction(add_tab_action)

        bookmark_action = QAction(QIcon('./images/bookmark.png'), 'Bookmark', self)
        bookmark_action.triggered.connect(self.bookmark_page)
        navbar.addAction(bookmark_action)
                
        select_bookmark_action = QAction(QIcon('./images/selectbookmark.png'), 'Select Bookmark', self)
        select_bookmark_action.triggered.connect(self.select_bookmark)
        navbar.addAction(select_bookmark_action)

        set_home_action = QAction('Set Home', self)
        set_home_action.triggered.connect(self.set_homepage)
        navbar.addAction(set_home_action)
        
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Tabbed browsing
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        self.showMaximized()



        self.add_tab()
        
        
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #333;
            }


            QToolBar {
                background-color: #555;
            }

            QLineEdit {
                height: 30px;
                background-color: #fff;
                color: #000;
                border: 1px solid #000;
                border-radius: 5px;
                padding: 1px;
                font-size: 16px;
            }

            QPushButton {
                background-color: #007BFF;
                color: #fff;
                height: 30px;
                border: none;
                border-radius: 5px;
                padding: 5px;
            }

            QPushButton:hover {
                background-color: #0056b3;
            }

            QTabWidget::tab-bar {
                alignment: center;
            }

            QTabWidget::pane {
                border: none;
            }

            QTabBar::tab {
                background-color: #555;
                color: #fff;
                padding: 10px;
                border-radius: 5px;
                margin: 2px;
            }

            QTabBar::tab:selected {
                background-color: #007BFF;
            }
        """)



    def show_user_profile(self):
        dialog = UserProfileDialog(self.storage, self)
        if dialog.exec_():
            self.user = dialog.username_input.text().strip()
            self.password = dialog.password_input.text()
            self.profile = dialog.profile or {}
            self.status.showMessage(f'Logged in as {self.user}', 3000)

    def homepage(self):
        return self.profile.get('homepage', DEFAULT_HOME)

    def set_homepage(self):
        if not self.user:
            self.status.showMessage('Log in to a profile to save a homepage', 3000)
            return
        self.profile['homepage'] = self.tabs.currentWidget().browser.url().toString()
        self.storage.save_profile(self.user, self.password, self.profile)
        self.status.showMessage('Homepage saved to your encrypted profile', 3000)

    def record_visit(self, tab, ok):
        if not ok:
            return
        url = tab.browser.url().toString()
        self.storage.add_history(url, tab.browser.title())
        self.url_bar.update_history(url)

    def updateurl(self, q):
        self.url_bar.setText(q.toString())
        self.url_bar.update_history(q.toString())        
        
    def navigate_home(self):
        current_tab = self.tabs.currentWidget()
        current_tab.navigate_to_url(self.homepage())

    def navigatetourl(self):
        url = self.url_bar.text()
        current_tab = self.tabs.currentWidget()
        current_tab.navigate_to_url(url)

    def updateurl(self, q):
        current_tab = self.tabs.currentWidget()
        current_url = current_tab.browser.url().toString()
        self.url_bar.setText(current_url)

        
    def add_tab(self):
        tab = BrowserTab()
        i = self.tabs.addTab(tab, "New Tab")
        tab.browser.urlChanged.connect(self.updateurl)  # add this line
        tab.browser.loadFinished.connect(lambda ok, t=tab: self.record_visit(t, ok))
        self.tabs.setCurrentIndex(i)


    def select_bookmark(self):
        bookmark, ok = QInputDialog.getItem(self, "Select bookmark", "Select bookmark", self.storage.bookmarks(), 0, False)
        if ok and bookmark:
            self.navigate_to_bookmark(bookmark)


    def close_tab(self, i):
        if self.tabs.count() > 1:
            self.tabs.removeTab(i)

    def bookmark_page(self):
        current_tab = self.tabs.currentWidget()
        current_url = current_tab.browser.url().toString()
        self.storage.add_bookmark(current_url, current_tab.browser.title())
        self.status.showMessage(f'Bookmarked {current_url}', 3000)

    def navigate_to_bookmark(self, url):
        # Instead of adding a tab, just set the current tab's URL to the bookmarked one
        current_tab = self.tabs.currentWidget()
        current_tab.navigate_to_url(url)
        
    def navigate_back(self):
        current_tab = self.tabs.currentWidget()
        current_tab.browser.back()

    def navigate_forward(self):
        current_tab = self.tabs.currentWidget()
        current_tab.browser.forward()

    def navigate_reload(self):
        current_tab = self.tabs.currentWidget()
        current_tab.browser.reload()
        
    def show_history(self):
        history, ok = QInputDialog.getItem(self, "History", "Select history", self.storage.history(), 0, False)
        if ok and history:
            current_tab = self.tabs.currentWidget()
            current_tab.navigate_to_url(history)     
       
        
app = QApplication(sys.argv)
QApplication.setApplicationName("Overse")
window = MainWindow()
app.exec_()
