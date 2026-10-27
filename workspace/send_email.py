
import smtplib
from email.mime.text import MIMEText

# Email configuration
sender_email = "shavanvashishth@gmail.com"
receiver_email = "sakshisolanki8449@gmail.com"
# Note: Using an App Password is required for Gmail SMTP
password = "your_app_password" # Placeholder for security

# Create the message
msg = MIMEText("Hey")
msg["Subject"] = "Hello"
msg["From"] = sender_email
msg["To"] = receiver_email

try:
    # Connect to Gmail SMTP server
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        # server.login(sender_email, password) # Commented out as password is placeholder
        # server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Successfully created email draft. (Actual sending requires authentication)")
except Exception as e:
    print(f"Error: {e}")
