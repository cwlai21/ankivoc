# library_agent.py
#
# This script is an AI agent that connects to your Gmail, reads emails from
# the Taipei Public Library (臺北市立圖書館), understands them using the Gemini AI model,
# and creates Google Calendar events for book due dates and pickup reminders.

# --- Step 0: Install necessary libraries ---
# pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib llama-index llama-index-readers-gmail llama-index-llms-gemini python-dotenv

import os
import datetime
import json
import logging
import pickle
import sys

from dotenv import load_dotenv
from groq import Groq
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from llama_index.core import Document
from llama_index.llms.gemini import Gemini
from llama_index.readers.google import GmailReader

# # --- Configuration ---
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# # Load environment variables from a .env file (for your Gemini API key)
# load_dotenv()

# # **ACTION REQUIRED**: Set the URL for the library's login page.
# TAIPEI_LIBRARY_LOGIN_URL = "https://webbook.tpml.edu.tw/webpac/login.jsp"

# # Define the scopes for Google APIs. This asks for read-only access to Gmail
# # and write access to your calendar.
# SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/calendar.events']
# CREDENTIALS_FILE = 'credentials.json'
# TOKEN_PICKLE_FILE = 'token.pickle'

# def authenticate_google():
#     """Handles Google OAuth2 authentication and returns service objects for Gmail and Calendar."""
#     creds = None
#     if os.path.exists(TOKEN_PICKLE_FILE):
#         with open(TOKEN_PICKLE_FILE, 'rb') as token:
#             creds = pickle.load(token)

#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(Request())
#         else:
#             flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
#             creds = flow.run_local_server(port=0)
#         with open(TOKEN_PICKLE_FILE, 'wb') as token:
#             pickle.dump(creds, token)

#     try:
#         gmail_service = build('gmail', 'v1', credentials=creds)
#         calendar_service = build('calendar', 'v3', credentials=creds)
#         logging.info("Successfully authenticated with Google services.")
#         return gmail_service, calendar_service
#     except Exception as e:
#         logging.error(f"Failed to build Google services: {e}")
#         return None, None

# def fetch_library_emails(gmail_service):
#     """Fetches unread emails from the Taipei Public Library from the last 2 days."""
#     # We search for unread emails in the last 2 days to be efficient for daily runs.
#     query = "from:(臺北市立圖書館) is:unread in:inbox newer_than:2d"
    
#     # We need a special reader that uses our authenticated service object.
#     gmail_loader = GmailReader(google_api_gmail=gmail_service)
    
#     try:
#         # Load data performs the search
#         documents = gmail_loader.load_data(query=query, use_iterative_parser=True)
        
#         # After fetching, we should mark the emails as read so we don't process them again.
#         response = gmail_service.users().messages().list(userId='me', q=query).execute()
#         messages = response.get('messages', [])
#         if messages:
#             msg_ids = [msg['id'] for msg in messages]
#             gmail_service.users().messages().batchModify(
#                 userId='me',
#                 body={'ids': msg_ids, 'removeLabelIds': ['UNREAD']}
#             ).execute()
#             logging.info(f"Marked {len(msg_ids)} email(s) as read.")
            
#         return documents
#     except Exception as e:
#         logging.error(f"Could not fetch emails: {e}")
#         return []

# def analyze_email_with_gemini(email_content: str) -> dict:
#     """Uses Gemini to analyze email content and extract structured data."""
    
#     # Check for Gemini API Key
#     if not os.getenv("GEMINI_API_KEY"):
#         logging.error("GEMINI_API_KEY not found in .env file.")
#         raise ValueError("Please set your GEMINI_API_KEY in the .env file.")
        
#     llm = Gemini(model_name="models/gemini-1.5-flash-latest")
    
#     prompt = f"""
#     You are an intelligent assistant analyzing emails in Traditional Chinese from the Taipei Public Library (臺北市立圖書館).
#     Based on the following email text, classify the email and extract the specified information in a structured JSON format.

#     The possible email types are: 'EXPIRING_BOOK' (到期通知), 'ARRIVING_BOOK' (預約書到館通知), or 'OTHER'.

#     1. If the email is an 'EXPIRING_BOOK' (到期通知) notice:
#        Extract the following JSON:
#        {{
#          "email_type": "EXPIRING_BOOK",
#          "book_title": "the book title",
#          "due_date": "the due date in YYYY-MM-DD format"
#        }}

#     2. If the email is an 'ARRIVING_BOOK' (預約書到館通知) notice:
#        Extract the following JSON:
#        {{
#          "email_type": "ARRIVING_BOOK",
#          "book_title": "the book title",
#          "pickup_location": "the pickup branch name",
#          "pickup_end_date": "the last day for pickup in YYYY-MM-DD format"
#        }}

#     3. If you cannot determine the type or find the required information, return an empty JSON object: {{}}.

#     Here is the email text to analyze:
#     ---
#     {email_content}
#     ---
#     """
    
#     try:
#         response = llm.complete(prompt)
#         # Clean up the response to get only the JSON part
#         json_str = response.text.strip().replace("```json", "").replace("```", "").strip()
#         return json.loads(json_str)
#     except Exception as e:
#         logging.error(f"Error analyzing email with Gemini or parsing JSON: {e}")
#         return {}


# def create_calendar_event(calendar_service, summary, description, start_datetime, end_datetime):
#     """Creates a new event on the user's primary Google Calendar."""
#     event = {
#         'summary': summary,
#         'description': description,
#         'start': {
#             'dateTime': start_datetime.isoformat(),
#             'timeZone': 'Asia/Taipei',
#         },
#         'end': {
#             'dateTime': end_datetime.isoformat(),
#             'timeZone': 'Asia/Taipei',
#         },
#         'reminders': {
#             'useDefault': True,
#         },
#     }

#     try:
#         created_event = calendar_service.events().insert(calendarId='primary', body=event).execute()
#         logging.info(f"Event created successfully: {created_event.get('htmlLink')}")
#     except Exception as e:
#         logging.error(f"Failed to create calendar event: {e}")


# def main():
#     """Main function to run the library agent."""
#     logging.info("🚀 Starting Library Agent...")
#     gmail_service, calendar_service = authenticate_google()

#     if not gmail_service or not calendar_service:
#         logging.error("Could not authenticate. Exiting.")
#         return

#     documents = fetch_library_emails(gmail_service)

#     if not documents:
#         logging.info("No new library emails found. All done for today!")
#         return

#     logging.info(f"Found {len(documents)} new email(s) to process.")

#     for doc in documents:
#         analysis = analyze_email_with_gemini(doc.text)

#         if not analysis or "email_type" not in analysis:
#             logging.warning("Could not analyze or classify an email. Skipping.")
#             continue

#         email_type = analysis.get("email_type")
#         book_title = analysis.get("book_title", "Unknown Title")

#         if email_type == 'EXPIRING_BOOK':
#             due_date_str = analysis.get("due_date")
#             if due_date_str:
#                 due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()
#                 event_start = datetime.datetime.combine(due_date, datetime.time(12, 0)) # noon on the due date
#                 event_end = event_start + datetime.timedelta(hours=1)
                
#                 logging.info(f"Creating 'Return Book' event for '{book_title}' on {due_date_str}")
#                 create_calendar_event(
#                     calendar_service=calendar_service,
#                     summary=f"還書/續借提醒: {book_title}", # "Return/Extend Reminder"
#                     description=f"書籍 '{book_title}' 即將到期。\n\n請記得歸還或登入圖書館網站辦理續借。\n登入頁面: {TAIPEI_LIBRARY_LOGIN_URL}",
#                     start_datetime=event_start,
#                     end_datetime=event_end
#                 )

#         elif email_type == 'ARRIVING_BOOK':
#             end_date_str = analysis.get("pickup_end_date")
#             location = analysis.get("pickup_location", "Unknown Location")
#             if end_date_str:
#                 # We'll create an all-day event from today until the pickup end date
#                 start_date = datetime.date.today()
#                 end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
#                 # For an all-day event, the end date must be the day *after* the last day.
#                 event_end_date = end_date + datetime.timedelta(days=1)
                
#                 # Make start/end compatible with API which expects datetime strings
#                 event_start_str = start_date.strftime("%Y-%m-%d")
#                 event_end_str = event_end_date.strftime("%Y-%m-%d")

#                 logging.info(f"Creating 'Pick up Book' event for '{book_title}' until {end_date_str}")

#                 # Re-using the create_calendar_event function for an all-day event
#                 all_day_event = {
#                     'summary': f"領取預約書: {book_title}", # "Pick up Reserved Book"
#                     'location': location,
#                     'description': f"預約的書籍 '{book_title}' 已送達分館: {location}。\n請在 {end_date_str} 前領取。",
#                     'start': {'date': event_start_str},
#                     'end': {'date': event_end_str},
#                     'reminders': {'useDefault': True}
#                 }
                
#                 try:
#                     created_event = calendar_service.events().insert(calendarId='primary', body=all_day_event).execute()
#                     logging.info(f"All-day event created successfully: {created_event.get('htmlLink')}")
#                 except Exception as e:
#                     logging.error(f"Failed to create all-day calendar event: {e}")

#     logging.info("✅ Library Agent finished processing.")

if __name__ == '__main__':
    # main()
    print(sys.version)