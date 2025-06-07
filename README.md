# CareerFinder
Group project

# Team Three
Weilan Liang
Dereje Teshager

# About the Project
CareerFinder is a modern application with three main function:
Home: Job search based on job, location, position type.
Resume: with two seclection to build and give AI provided suggestion to user
  -Resume builder: build new resume from scratch, able to review AI suggestion, editing, export & save the resume
  -Upload resume: user could upload their resume, we will provided AI suggestion based on uploaded resume
People: user could update and show their skills, and employers could search interest future employee based on their skillset

# Seamless User Experience
  -Secure Authentication:
    -Traditional Email & Password Registration/Login.
  -Social Logins: Convenient sign-in via Google and GitHub.
  -Profile: Update data profile based on users' need, they could update location, bio, & skill
  -Account Management: Update your profile details with ease.
  -Password Recovery: Secure password reset functionality.
  -Session Management: Persistent login for a smooth experience.

# Build and run the application locally using Docker
  git clone https://github.com/weilan1299/TCSS-506_groupPro.git
  cd career-finder
  ./builder_docker.sh
  ./run_docker.sh
  Open in your browser: http://localhost:5000

# Individual contributions
ALL: Documentation, GitHub, Debugging
Weilan: 
Work on resume builder, API’s and resume templates and resume functions. 
Dereje:
Work on web design, API's, job posting and login and account management.


# Docker image to host on EC2
https://hub.docker.com/repository/docker/weilan1299/career_finder/tags/latest/sha256-235d76fb013bae16bd3833a94ee2e456f8e88105718c99f610af4c910e5c0e71
docker pull weilan1299/career_finder
docker run -d -p 5000:5001 --name careerfinder weilan1299/career_finder

# Currenly Host on EC2
http://ec2-3-145-175-187.us-east-2.compute.amazonaws.com:5000

# Bug pending to fix
Check yml file
Fixed export bug New Docker file add install wkhtmltopdf
Password reset
Other Login
