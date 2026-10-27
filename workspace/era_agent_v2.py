
import webbrowser
import urllib.parse

def prepare_whatsapp_message(contact_name, message):
    # This prepares the URL to send a message via WhatsApp Web.
    # The user still needs to click 'send' on WhatsApp Web.
    message_encoded = urllib.parse.quote(message)
    # Note: WhatsApp Web URL works better with phone numbers.
    # Searching by name directly via URL isn't reliably supported.
    # We will formulate it, but success depends on WhatsApp Web's handling.
    url = f"https://web.whatsapp.com/send?text={message_encoded}" # Cannot directly open chat by name easily via URL.
    
    print(f"Opening WhatsApp Web. Please search for '{contact_name}' and paste your message.")
    # More realistically, we open WhatsApp Web and the user handles finding the contact.
    webbrowser.open("https://web.whatsapp.com/")

# Usage Example (Boss, you would replace these):
# prepare_whatsapp_message('Bhaiyya', 'Hello from Ira Agent!')
