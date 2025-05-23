from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Required for session management

# ─── DATABASE CONFIGURATION ───────────────────────────────
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://admin:MySecurePass123!@inventory-db.c16okmo081b8.us-west-1.rds.amazonaws.com:3306/inventory"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─── YOUR MODELS GO HERE ──────────────────────────────────
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
        else:
            error = "Invalid email or password"
    return render_template("signin.html", error=error)

@app.route("/logout")
def logout():
    session.pop("email", None)
    return redirect("/signin")

@app.route("/")
def dashboard():
    if "email" not in session:
        return redirect("/signin")
    return redirect("/inventory")

@app.route("/inventory", methods=["GET", "POST"])
def inventory():
    if "email" not in session:
        return redirect("/signin")

    message = request.args.get("message")

    if request.method == "POST":
        name = request.form["name"]
        quantity = request.form["quantity"]
        new_item = Item(name=name, quantity=int(quantity))
        db.session.add(new_item)
        db.session.commit()
        return redirect("/inventory?message=Item added")

    message = request.args.get("message")
    items = Item.query.all()
    return render_template("inventory.html", items=items, message=message)

@app.route("/edit-item/<int:item_id>", methods=["GET", "POST"])
def edit_item(item_id):
    if "email" not in session:
        return redirect("/signin")
    item = Item.query.get_or_404(item_id)
    if request.method == "POST":
        old_name = item.name
        item.name = request.form["name"]
        item.quantity = int(request.form["quantity"])
        db.session.commit()
        return redirect("/inventory?message=Item updated {old_name} to {item.quantity}")
    return render_template("edit_item.html", item=item)

@app.route("/delete-item/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    if "email" not in session:
        return redirect("/signin")
    item = Item.query.get_or_404(item_id)
    deleted_info = f"Deleted{item.quantity} {item.name}(s)"
    db.session.delete(item)
    db.session.commit()
    return redirect("/inventory?message={deleted_info}")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
