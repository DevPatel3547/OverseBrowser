# Overse: A Simple, Feature-rich Web Browser

Overse is a minimal, yet powerful web browser built with Python and PyQt5. It combines simplicity and efficiency, providing a friendly browsing experience.



## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Features

Overse comes packed with essential features that make browsing a pleasure:

- **Tabbed Browsing:** Browse multiple sites at once. Each tab operates independently, allowing for multitasking.
- **Omnibox:** The smart URL box suggests URLs from your history, making navigation faster.
- **Navigation Tools:** Includes the essential navigation tools - back, forward, and reload. Plus, a home button to get you back to your homepage.
- **Bookmarks:** Like a page? Bookmark it! Bookmarks are saved in SQLite and survive restarts.
- **User Profiles (encrypted):** Create and log in to profiles. Each profile (currently its homepage, set with *Set Home*) is encrypted at rest with AES-256-GCM through the `cryptography` package (OpenSSL). The key is derived from the profile password with scrypt and a random per-profile salt, and the password itself is never stored. A wrong password or modified data fails authentication.
- **History:** Every page a tab finishes loading is stored in SQLite and can be reopened from the History menu or the Omnibox.

All state lives in one SQLite file, `~/.overse/overse.db` (override with `OVERSE_DB`). See `storage.py`.
## Installation and Usage

### Requirements

- Python 3
- PyQt5 and PyQtWebEngine
- cryptography

First, clone the repository to your local machine:

git clone https://github.com/DevPatel3547/OverseBrowser.git or you can use ssh, zip etc.

Navigate into the cloned repository:
cd Overse
Install the dependencies using pip:
pip install -r requirements.txt

Run the storage tests (no Qt needed):
pip install cryptography pytest && pytest tests


Once you've installed Overse, you're ready to begin browsing. Here's a quick guide to getting started:

**Launching the Application:**
   Open your terminal/command prompt and navigate to the directory containing `main.py`. Run the command: `python main.py`. 



## Contributing

Contributions to Overse are always welcome. Here's how you can contribute:

1. **Fork the Repository:**
   Click on the 'Fork' button at the top-right corner of the page. This will create a copy of the repository in your GitHub account.

2. **Clone the Repository:**
   Now, clone this forked repository to your machine. Click on the 'Code' button on your forked repository and copy the URL. Open your terminal and run: `git clone url_you_just_copied`.

3. **Create a New Branch:**
   Navigate to the directory of the cloned repository in your machine. Create a new branch using the command: `git checkout -b your-branch-name`.

4. **Make Your Changes:**
   Make the necessary changes in your local copy of the project.

5. **Commit and Push Your Changes:**
   Once you're done making changes, stage them for a commit using: `git add .`. Now, commit those changes using: `git commit -m 'commit message'`. Push your changes to GitHub using: `git push origin your-branch-name`.

6.Open a pull request
