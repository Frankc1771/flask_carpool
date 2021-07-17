from wtforms import StringField, PasswordField, BooleanField, SubmitField, IntegerField, SelectMultipleField, RadioField, DateTimeField, widgets
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length, NumberRange
from flask_wtf import FlaskForm
from carpool.models import User

class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.
    """

    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

    

class SignupForm(FlaskForm):
    """User Signup Form."""

    name = StringField("Name", validators=[DataRequired(message=('Please enter a username'))])
    email = StringField(
        "Email",
        validators=[
            Length(min=6, message=("Please enter a valid email address.")),
            Email(message=("Please enter a valid email address.")),
            DataRequired(message=("Please enter a valid email address.")),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Please enter a password."),
            Length(min=6, message=("Please select a stronger password."))])
    confirm = PasswordField("Confirm Your Password", validators=[
        EqualTo('password', message="Passwords must match")])
    submit = SubmitField("Register")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError("Please use a different username.")

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError("Please use a different email address.")


class LoginForm(FlaskForm):
    """User Login Form."""

    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField(
        "Password", validators=[DataRequired("Do not forget your password!")])
    submit = SubmitField("Log In")

class AddCarpoolForm(FlaskForm):
    """Carpool creation form."""
    summary = StringField('Please enter a short description about your carpool', validators=[DataRequired(message='Please\
                                                                                enter a short description about your carpool'),
                                                   Length(max=128, message=("Please keep the description under 128 characters."))])
    from_location = StringField("From Location (City, State)", validators=[DataRequired(message='Please enter the from location')])
    to_location = StringField("Destination (City, State)", validators=[DataRequired(message='Please enter the destination')])
    capacity = IntegerField('Max Number of Occupants', validators=[DataRequired(message = 'Please enter the maxium occupancy for the carpool'),
                                                                    NumberRange(min=0, max=8)])
    carpool_type = RadioField('Choose a temporary or reoccurring carpool type', choices=[('temporary', 'Temporary'), ('reoccurring', 'Reoccurring')],
                              validators=[DataRequired(message="Please select a carpool type")])
    start = DateTimeField('Start Date and Pickup Time', format='%Y-%m-%d %H:%M', validators=[DataRequired(message = 'Please enter a start date and time')])
    days = MultiCheckboxField('Choose what days your carpool will avaiable', choices=[('monday', 'Monday'), ('tuesday', 'Tuesday'),
                                                                            ('wednesday', 'Wednesday'), ('thursday', 'Thursday'),
                                                                            ('friday', 'Friday'), ('saturday', 'Saturday'), ('sunday', 'Sunday')],
                                                                            validators=[DataRequired(message = 'Please select the days your carpool will be active')])
    
    
    submit = SubmitField("Add Carpool")
    
class ChangePassword(FlaskForm):
    current_password = PasswordField(
        "Current Password",
        validators=[
            DataRequired(message="Please enter your current password.")])
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Please enter a new password."),
            Length(min=6, message=("Please select a stronger password."))])
    confirm = PasswordField("Confirm Your Password", validators=[
        EqualTo('password', message="Passwords must match")])
    submit = SubmitField("Change Password")
