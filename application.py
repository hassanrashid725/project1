import os, re, smtplib, string, secrets

from flask import Flask, session, render_template, request, redirect, url_for
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
    if request.method=="GET":   #Login Page
        if session.get("login_success") == 1:
            return redirect("/home")

        if session.get("invalid_cred") is None:
            error=""
        elif session["invalid_cred"] == 1:
            error = "Invalid Email or Password"
            session["invalid_cred"] = None
        return render_template ("index.html",error=error)

    elif request.method=="POST":    #Security Code Page
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
        if session.get("login_success") is None:
            return redirect("/")
        elif session["login_success"] == 1:
            session["books"]=db.execute("SELECT * FROM books ORDER BY title asc LIMIT 20").fetchall()
            return render_template("home.html",books=session["books"])

    elif request.method=="POST":
        session["email"]=request.form.get("email")
        session["pw"]=request.form.get("password")
        session["user_id"]=db.execute("SELECT id FROM users WHERE email = :email AND password = :pw",
        {"email": session["email"], "pw": session["pw"]}).fetchone()
        if session["user_id"] is None:
            session["invalid_cred"]=1
            return redirect("/")
        else:
            session["login_success"] = 1
            session["books"]=db.execute("SELECT * FROM books ORDER BY title asc LIMIT 20").fetchall()
            return render_template("home.html",books=session["books"])

@app.route("/home/<int:page_num>")
def home_page_num(page_num):
    if session.get("login_success") is None:
        return redirect("/")
    elif session["login_success"] == 1:
        page = 20 * page_num
        session["books"]=db.execute("SELECT * FROM books ORDER BY title asc LIMIT 20 OFFSET :page",
        {"page": page}).fetchall()
        return render_template("home.html",books=session["books"])

@app.route("/search")
def search():
    if session.get("login_success") is None:
        return redirect("/")
    search_word = request.args.get('search')
    search_word = "%" + search_word + "%"
    search_results = db.execute("SELECT * FROM books WHERE UPPER(title) LIKE UPPER(:search_word)"
    " OR UPPER(author) LIKE UPPER(:search_word)"
    " OR UPPER(isbn) LIKE UPPER(:search_word)",
    {"search_word": search_word}).fetchall()
    return render_template("home.html",books=search_results)


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
                s.login("EMAIL@gmail.com", "PW")
                s.sendmail("EMAIL@gmail.com", session["email"], session["keycode"])
                s.quit()
                error="Please enter the Security Code that was sent on your email."
                return render_template ("security_check.html",error=error)
        else:
            error="Email ID already registered"
            return render_template("signup.html",error=error)

@app.route("/book/<string:book_isbn>",methods=["GET","POST"])
def book(book_isbn):
    if session.get("login_success") is None:
        return redirect("/")
    book = db.execute("SELECT * FROM books WHERE isbn = :search_word",
    {"search_word": book_isbn}).fetchone()
    reviews = db.execute("SELECT rating,comment,email FROM reviews JOIN users ON reviews.user_id = users.id "
    "JOIN books ON reviews.book_id = books.id "
    "WHERE books.isbn = :book_isbn",
    {"book_isbn": book_isbn}).fetchall()
    avg_rat = db.execute("SELECT to_char(AVG(rating),'99999999999999999D99') FROM reviews JOIN users ON reviews.user_id = users.id "
    "JOIN books ON reviews.book_id = books.id "
    "WHERE books.isbn = :book_isbn",
    {"book_isbn": book_isbn}).fetchone()
    error=""
    if request.method=="POST":
        session["user_review"] = request.form.get("user_review")
        session["user_rating"] = request.form.get("user_rating")
        if len(session["user_review"]) == 0 or session.get("user_rating") is None:
            error = "Please submit both review and rating."
            return render_template("book.html",book=book,reviews=reviews,avg_rat=avg_rat[0], error=error)
        if ord(session["user_review"][0]) == 32:
            error = "Please submit both review and rating."
            return render_template("book.html",book=book,reviews=reviews,avg_rat=avg_rat[0], error=error)
        check_review = db.execute("SELECT comment FROM reviews JOIN users ON reviews.user_id = users.id "
        "JOIN books ON reviews.book_id = books.id "
        "WHERE books.isbn = :book_isbn AND users.id = :user_id",
        {"book_isbn": book_isbn, "user_id": session["user_id"][0]}).fetchone()
        if check_review is not None:
            error="You have already submitted a review for this book."
            return render_template("book.html",book=book,reviews=reviews,avg_rat=avg_rat[0], error=error)
        elif check_review is None:
            db.execute("INSERT INTO reviews (user_id, book_id, comment, rating) VALUES "
            "(:user_id, :book_id, :comment, :rating)",
            {"user_id": session["user_id"][0], "book_id": book.id,"comment": session["user_review"],"rating": session["user_rating"]})
            db.commit()
            return redirect(url_for('book',book_isbn=book.isbn))

    return render_template("book.html",book=book,reviews=reviews,avg_rat=avg_rat[0], error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
