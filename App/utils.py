from itsdangerous import URLSafeTimedSerializer
from flask_socketio import emit
from flask_mail import Message
from flask_login import current_user
from flask import current_app, url_for, render_template

# from App.models import Notification
from App import db, mail

def generate_confirmation_token(email, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-confirm')

def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt='email-confirm',
            max_age=expiration
        )
    except:
        return False
    return email

def send_password_reset_email(user):
    # Sends an email with a link to reset the user's password.
    token = user.get_reset_password_token()
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    msg = Message(
        subject='Rindang User Reset Password',
        recipients=[user.email],
        html=render_template('auth/reset_password_email_template.html', reset_url=reset_url, user=user)
    )
    mail.send(msg)

# def get_unread_notifications():
#     if current_user.is_authenticated:
#         return Notification.query.filter_by(recipient_id=current_user.id, is_read=False).all()
    # return []  # Return an empty list if not logged in

# def get_user_notification_room(user_id):
#     return f"user_{user_id}_notifications"

# def send_notification(recipient_id, message, sender_id=None):
#     """Sends a notification to a user and creates a database record.

#     Args:
#         recipient_id (str): ID of the recipient user.
#         message (str): The notification message.
#         sender_id (str, optional): ID of the sender user. Defaults to None.
#     """

#     room = get_user_notification_room(recipient_id)

#     notification = Notification(
#         recipient_id=recipient_id,
#         message=message,
#         sender_id=sender_id  # Optional
#     )
#     db.session.add(notification)
#     db.session.commit()

#     unread_count = len(get_unread_notifications()) # Function to get unread count

#     # Include unread count in emitted data
#     emit('new_notification', {
#         'message': message, 
#         'room': room,
#         'count': unread_count
#     }, room=room, namespace='/')