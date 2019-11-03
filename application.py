import os, re, smtplib, string, secrets

from flask import Flask, session, render_template, request, redirect
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/",methods=["POST","GET"])
def index():
    if request.method=="GET":
        error=""
        return render_template ("index.html",error=error)

    elif request.method=="POST":
        session["keycode2"] = request.form.get("securitykey")
        while session["keycode"] != session["keycode2"]:
            error="Security Code is incorrect. Please try again."
            return render_template ("security_check.html",error=error)
        db.execute("INSERT INTO users (email, password) VALUES (:email, :password)",
                    {"email": session["new_email"], "password": session["new_pw"]})
        db.commit()
        error="Account Created! Please sign in using your Email and Password"
        return render_template("index.html",error=error)


@app.route("/home",methods=["POST","GET"])
def home():
    if request.method=="GET":
        return redirect("/")

    elif request.method=="POST":
        session["email"]=request.form.get("email")
        session["pw"]=request.form.get("password")
        cred=db.execute("SELECT id FROM users WHERE email = :email AND password = :pw",
        {"email": session["email"], "pw": session["pw"]}).fetchone()
        if cred is None:
            return redirect("/")
        else:
            return f"<h1>Hello!</h1>"

@app.route("/signup",methods=["POST","GET"])
def new_user():
    if request.method=="GET":
        error=""
        return render_template("signup.html",error=error)

    elif request.method=="POST":
        session["new_email"]=request.form.get("email")
        session["new_pw"]=request.form.get("password1")
        session["pw2"]=request.form.get("password2")
        cred=db.execute("SELECT id FROM users WHERE email = :email",
        {"email": session["new_email"]}).fetchone()
        if cred is None:
            if session["new_pw"]!=session["pw2"]:
                error="Passwords do not match"
                return render_template("signup.html",error=error)
            length_error = len(session["new_pw"]) < 8
            digit_error = re.search(r"\d", session["new_pw"]) is None
            uppercase_error = re.search(r"[A-Z]", session["new_pw"]) is None
            lowercase_error = re.search(r"[a-z]", session["new_pw"]) is None
            symbol_error = re.search(r"\W", session["new_pw"]) is None
            password_ok = not ( length_error or digit_error or uppercase_error or lowercase_error or symbol_error )
            if password_ok is False:
                error="Weak Password. Password must have"
                return render_template("signup.html",error=error)
            elif password_ok is True:
                alphabet = string.ascii_letters + string.digits
                session["keycode"] = ''.join(secrets.choice(alphabet) for i in range(8))
                s = smtplib.SMTP('smtp.gmail.com', 587)
                s.starttls()
                s.login("EMAIL@gmail.com", "PASSWORD")
                s.sendmail("EMAIL@gmail.com", session["email"], session["keycode"])
                s.quit()
                error="Please enter the Security Code that was sent on your email."
                return render_template ("security_check.html",error=error)
        else:
            error="Email ID already registered"
            return render_template("signup.html",error=error)
