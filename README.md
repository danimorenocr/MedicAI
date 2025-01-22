Pre-Diagnostic medic in Telegram

This is an interactive chatbot developed in Python, using the `python-telegram-bot` library to interact with users on Telegram. The bot specializes in collecting symptoms, providing preliminary diagnoses, and suggesting treatments, all while recording interactions in a Snowflake database.

## Requirements

- Python 3.7 or higher
- Necessary libraries:
  - `python-telegram-bot`
  - `snowflake-connector-python`
  - `json`
  - `asyncio`
  - `datetime`
  - `translations` (local file with translations)

Install the required libraries using `pip`:

```bash
pip install python-telegram-bot snowflake-connector-python
```

Snowflake Configuration
The bot connects to a Snowflake database to store interaction data with users. Ensure that you have the necessary credentials (username, password, account, warehouse, database, and schema). These credentials are configured in the code of the `save_interaction_data` and `get_diagnosis` functions.

Features
Login and language selection
The bot allows users to start a conversation using the `/start` command and select their preferred language (Spanish or English).
Symptom registration
The bot guides the user through a series of questions to gather information about their symptoms. The symptoms are stored and used to generate a preliminary diagnosis.
Diagnosis
Based on the symptoms reported by the user, the bot queries a diagnostic model (using Snowflake) and provides recommendations on preliminary diagnoses, home treatments, and when to seek medical attention.
User satisfaction
At the end of the session, the bot asks the user if they are satisfied with the experience and stores this information in the database.
Inactivity
If the user remains inactive for more than 30 minutes, the bot will delete their session data.

Project files and structure

/chatbot
├── bot.py                # Main bot code
├── translations.py       # Translations for different languages
└── requirements.txt      # File for Python dependencies

Usage
Start the bot on Telegram by sending the `/start` command.
Select your preferred language (Spanish or English).
The bot will guide you to report your symptoms.
After submitting the symptoms, the bot will provide a preliminary diagnosis and suggestions.
Finally, the bot will ask you if you are satisfied with the experience.
Contributing
Fork the repository.
Create a new branch (git checkout -b new-feature).
Make your changes.
Commit your changes (git commit -am 'Add new functionality').
Push to your branch (git push origin new-feature).
Create a new Pull Request.

License
This project is licensed under the MIT License - see the LICENSE file for details.

Daniela Moreno 
