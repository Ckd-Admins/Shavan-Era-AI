
import webbrowser
import urllib.parse

def prepare_whatsapp_message(contact_name, message):
    # This prepares the URL to send a message via WhatsApp Web.
    message_encoded = urllib.parse.quote(message)
    # The URL to attempt direct opening; user must click send.
    # Note: searching by name directly via URL is unreliable.
    print(f"Opening WhatsApp Web to send message to '{contact_name}'.")
    webbrowser.open("https://web.whatsapp.com/")

# Function to facilitate easy calling, boss.
# prepare_whatsapp_message('Contact Name Herer', 'Message Here')
