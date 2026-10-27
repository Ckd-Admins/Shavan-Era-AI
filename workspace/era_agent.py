
import webbrowser
import urllib.parse

def send_whatsapp_message(contact, message):
    # Formatting the URL for WhatsApp Web
    message_encoded = urllib.parse.quote(message)
    # The current assumption is to use WhatsApp Web; direct app control is complex for a script.
    url = f"https://web.whatsapp.com/send?phone={contact}&text={message_encoded}"
    
    # Opens WhatsApp Web in the default browser
    print(f"Opening WhatsApp for {contact} with message.")
    webbrowser.open(url)

# Usage example:
# send_whatsapp_message('919876543210', 'Hello from Era Agent!')
