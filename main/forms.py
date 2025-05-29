from flask_wtf import FlaskForm
from flask_wtf.file import  FileField, FileAllowed
from flask_login import current_user
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from main.models import User


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email=StringField("Email", validators=[DataRequired(), Email()])
    password=PasswordField('Password', validators=[DataRequired()])
    confirm_password= PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit= SubmitField('Sign Up')

    def validate_username(self, username):
        # Check if the username already exists in the database
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is already taken. Please choose a different one.')

    def validate_email(self, email):
        # Check if the email already exists in the database

        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already taken. Please choose a different one.')

class LoginForm(FlaskForm):
    email=StringField("Email", validators=[DataRequired(), Email()])
    password=PasswordField('Password', validators=[DataRequired()])
    remember=BooleanField('Remember Me')
    submit= SubmitField('Login')


class UpdateAccountForm(FlaskForm):

    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email=StringField("Email", validators=[DataRequired(), Email()])

    submit= SubmitField('Update')

    def validate_username(self, username):

        if username.data != current_user.username:
        # Check if the username already exists in the database
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('That username is already taken. Please choose a different one.')

    def validate_email(self, email):
        # Check if the email already exists in the database
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is already taken. Please choose a different one.')

class RequestRestForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])

    submit = SubmitField("Request Password Rest")

    def validate_email(self, email):
        # Check if the email already exists in the database
            user = User.query.filter_by(email=email.data).first()
            if user is None:
                raise ValidationError('Email not found. You must register first.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField("Reset Password")

class ProfileForm(FlaskForm):
    bio = TextAreaField('About You', validators=[Length(max=500)])
    skills = StringField('Skills (comma-separated)', validators=[Length(max=200)])
    picture = FileField('Update Profile Picture', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    linkedin = StringField('LinkedIn Profile URL')
    github = StringField('GitHub Profile URL')
    location = StringField('Location', validators=[Length(max=100)])
    submit = SubmitField('Update Profile')


