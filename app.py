from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Required for session management

# ─── DATABASE CONFIGURATION ───────────────────────────────
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://admin:MySecurePass123!@inventory-db.c16okmo081b8.us-west-1.rds.amazonaws.com:3306/inventory"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─── YOUR MODELS GO HERE (example below) ─────────────────
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    quantity = db.Column(db.Integer)

# ─── CREATE TABLES ONCE ───────────────────────────────────
with app.app_context():
    db.create_all()

# ─── TEMPORARY USER STORE ─────────────────────────────────
USERS = {
    "admin@example.com": {"name": "Admin", "password": "letmein"},
}

# ─── ROUTES ───────────────────────────────────────────────
@app.route("/signin", methods=["GET", "POST"])
def signin():
    error = None
    if request.method == 'POST':
        email = request.form["email"].lower()
        pwd = request.form["password"]
        user = USERS.get(email)
        if user and user["password"] == pwd:
            session["email"] = email
            return redirect("/")
        return redirect("/signin")
    return render_template("signin.html", error=error)

@app.route("/logout")
def logout():
    session.pop("email", None)
    return redirect("/signin")

@app.route("/")
def dashboard():
    if "email" not in session:
        return redirect("/signin")
    return f"Hello {session['email']} – inventory dashboard coming soon!"

if __name__ == "__main__":
    app.run(debug=True,host='0.0.0.0')
