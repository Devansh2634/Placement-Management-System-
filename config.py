# ------------------------------
# DATABASE (MySQL) CONFIGURATION
# ------------------------------
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "Trupu@$2"
MYSQL_DATABASE = "placement_portal"

# ------------------------------
# EMAIL (OTP + REMINDERS)
# ------------------------------
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USE_TLS = True

# Gmail App Password (not Gmail login password)
MAIL_USERNAME = "bhandarivarda@gmail.com"
MAIL_PASSWORD = "vhnfvxbyroyygiiw"

# ------------------------------
# SYSTEM SETTINGS
# ------------------------------

# Allowed email domain for OTP Login
ALLOWED_DOMAIN = "@thapar.edu"

# OTP expiry time (in minutes)
OTP_EXPIRY_MINUTES = 10

# Secret key for session handling
SECRET_KEY = "super-secret-key-change-this"

# Weekly auto-reminder email message (can be edited)
REMINDER_EMAIL_SUBJECT = "Placement Portal Weekly Reminder"
REMINDER_EMAIL_BODY = (
    "Hello Student,\n\n"
    "This is your weekly reminder to update your placement status or internship details "
    "on the Thapar Placement Portal.\n\n"
    "Regards,\nPlacement Cell"
)

# Teacher notification email
TEACHER_REMINDER_SUBJECT = "New Student Registration Alert"
TEACHER_REMINDER_BODY = "A new student has registered on the portal."