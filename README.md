
# Medical Pre-diagnosis Bot

**PrediagnosisAI Bot** is an interactive chatbot that offers general health advice based on reported symptoms. Developed using Python and the `python-telegram-bot` library, this bot allows users to receive preliminary diagnoses and suggestions on whether to seek medical attention. It also stores user interactions in a Snowflake database for future improvements.

[!IMPORTANT]
You can find and interact with the bot on Telegram: [@PrediagnosisAI_bot](https://t.me/PrediagnosisAI_bot).
Botdata: https://medicai-oeeczwkzpw623bofysnsp4.streamlit.app/

---

## Requirements

Ensure that your environment has the following:

- Python 3.7 or higher
- Required libraries:
  - `streamlit`
  - `pandas`
  - `python-telegram-bot==21.10`
  - `snowflake-connector-python`
  - `translations`
  - `python-dotenv`

To install the necessary libraries, run:

```bash
pip install -r requirements.txt
```

---

## Snowflake Configuration

This bot connects to a **Snowflake** database to store user interaction data. You’ll need to configure the following credentials:

- Username
- Password
- Account
- Warehouse
- Database
- Schema

These credentials are used in the `save_interaction_data` and `get_diagnosis` functions within the code.

[!IMPORTANT]
CREATE THE TABLES
```
CREATE TABLE bot_interactions (
    interaction_id BIGINT AUTOINCREMENT PRIMARY KEY,
    user_id STRING,
    chat_id STRING,
    interaction_start TIMESTAMP,
    interaction_end TIMESTAMP,
    symptoms_reported STRING,
    diagnosis_provided STRING,
    confirmation_status STRING, -- Valores posibles: 'Correcto', 'Incorrecto'
    satisfaction_status STRING, -- Valores posibles: 'Satisfecho', 'No Satisfecho'
    messages_exchanged INT,
    session_duration_seconds INT,
    inactivity_flag BOOLEAN,
    error_details STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
---

## Features

- **Login and Language Selection**  
  Start the bot by using the `/start` command and select your preferred language (Spanish or English).
  
- **Symptom Registration**  
  The bot asks the user to report their symptoms through a guided conversation. The information is collected and stored for diagnostic purposes.
  
- **Preliminary Diagnosis**  
  Based on the reported symptoms, the bot queries a diagnostic model in Snowflake to generate preliminary diagnoses, home remedies, and advice on when to seek professional medical care.
  
- **User Satisfaction Survey**  
  At the end of each session, the bot asks users if they are satisfied with the experience, and this feedback is stored in the database.
  
- **Inactivity Timeout**  
  If the user remains inactive for more than 30 minutes, the bot deletes the session data automatically.

---

## Project File Structure

```
/chatbot
├── chatbot.py            # Main bot code
├── translations.py       # Translation files for different languages
└── requirements.txt      # Python dependencies file
└── streamlit.py          # Data Visualization
```

---

## Usage

1. **Start the bot** on Telegram by sending the `/start` command.
2. **Select a language** (Spanish or English).
3. **Report your symptoms** by following the bot's instructions.
4. **Receive a preliminary diagnosis** along with advice on home treatments and when to seek medical attention.
5. **Provide feedback** on your experience at the end of the session.

---

## Contributing

We welcome contributions to improve this project! If you'd like to contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b new-feature`).
3. Make your changes.
4. Commit your changes (`git commit -am 'Add new functionality'`).
5. Push to your branch (`git push origin new-feature`).
6. Create a new Pull Request.

---

## License

This project is licensed under the **MIT License**. See the LICENSE file for details.

---

### Author
Daniela Moreno
