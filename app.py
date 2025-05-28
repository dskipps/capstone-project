from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
import csv
import boto3
import io
from io import StringIO
import datetime
import os
import json

def get_db_secret():
    secret_name = "prod/capstone/mysql"
    region_name = "us-west-1"        

    client = boto3.client("secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
     print("Full secret content:", secret)  # Add this debug print
    return secret

app = Flask(__name__)
app.secret_key = "your-secret-key" 

# ─── S3 CONFIGURATION ───────────────────────────
S3_BUCKET_NAME = "my-capstone-bucket"
S3_REGION = "us-west-1"              

s3 = boto3.client('s3', region_name=S3_REGION)

# ─── DATABASE CONFIGURATION ───────────────────────────
#app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://admin:MySecurePass123!@inventory-db.c16okmo081b8.us-west-1.rds.amazonaws.com:3306/inventory"

db_secret = get_db_secret()
db_user = db_secret["username"]
db_pass = db_secret["password"]
db_host = db_secret["host"]
db_name = db_secret["dbname"]
app.config['SQLALCHEMY_DATABASE_URI'] = (f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:3306/{db_name}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

item_tags = db.Table('item_tags',
    db.Column('item_id', db.Integer, db.ForeignKey('item.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

# ─── MODELS ─────────────────────────
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    tags = db.relationship('Tag', secondary=item_tags, backref=db.backref('items', lazy='dynamic'))

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

# ─── CREATE TABLES ONCE ──────────────────────────
with app.app_context():
    db.create_all()

# ─── TEMPORARY USER STORE ───────────────────────
USERS = {
    "admin@example.com": {"name": "Admin", "password": "letmein"},
}

# ─── ROUTES ───────────────────────────────────
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
    search_query = request.args.get("search", "").strip().lower()
    page = request.args.get("page", 1, type=int)
    per_page = 10

    if request.method == "POST":
        name = request.form["name"].strip()
        quantity = request.form["quantity"]
        tags_str = request.form.get("tags", "").strip()  # Get tags from form

        # Duplicate check
        existing_item = Item.query.filter(db.func.lower(Item.name) == name.lower()).first()
        if existing_item:
            return redirect("/inventory?message=Item already exists.")

        new_item = Item(name=name.capitalize(), quantity=int(quantity))

        # Process tags
        if tags_str:
            tag_names = [t.strip().lower() for t in tags_str.split(",") if t.strip()]
            tags = []
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                tags.append(tag)
            new_item.tags = tags

        db.session.add(new_item)
        db.session.commit()
        return redirect("/inventory?message=Item added")

    query = Item.query.join(Item.tags, isouter=True)
    if search_query:
        query = query.filter(db.or_(Item.name.ilike(f"%{search_query}%"), Tag.name.ilike(f"%{search_query}%"))).distinct()

    pagination = query.order_by(Item.id.desc()).paginate(page=page, per_page=per_page)

    return render_template("inventory.html", items=pagination.items, message=message, pagination=pagination, request=request)

@app.route("/export-csv")
def export_csv():
    if "email" not in session:
        return redirect("/signin")

    items = Item.query.order_by(Item.id).all()

    # Build CSV in-memory
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["ID", "Name", "Quantity", "Tags"])

    for item in items:
        tag_names = ", ".join(tag.name for tag in item.tags)
        writer.writerow([item.id, item.name, item.quantity, tag_names])

    # Generate unique filename
    filename = f"inventory_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    s3.upload_fileobj(
        io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
        S3_BUCKET_NAME,
        filename,
        ExtraArgs={"ContentType": "text/csv"}
    )

    return redirect(f"/inventory?message=CSV exported to S3 as {filename}")


@app.route("/edit-item/<int:item_id>", methods=["GET", "POST"])
def edit_item(item_id):
    if "email" not in session:
        return redirect("/signin")

    item = Item.query.get_or_404(item_id)

    if request.method == "POST":
        new_name = request.form["name"].strip().lower()
        new_quantity = int(request.form["quantity"])

        # Check for duplicate name in other items
        duplicate = Item.query.filter(
            db.func.lower(Item.name) == new_name,
            Item.id != item.id
        ).first()
        if duplicate:
            return redirect(f"/inventory?message=Another item with name '{new_name.capitalize()}' already exists.")

        # Update fields
        item.name = new_name.capitalize()
        item.quantity = new_quantity

        # --- NEW: Handle tags ---
        tags_str = request.form.get("tags", "").strip()
        if tags_str:
            tag_names = [t.strip().lower() for t in tags_str.split(",") if t.strip()]
            new_tags = []
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                new_tags.append(tag)
            item.tags = new_tags
        else:
            item.tags = []  # Clear tags if empty

        db.session.commit()
        return redirect(f"/inventory?message=Item '{item.name}' updated.")

    return render_template("edit_item.html", item=item)

@app.route("/delete-item/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    if "email" not in session:
        return redirect("/signin")
    item = Item.query.get_or_404(item_id)
    deleted_info = f"Deleted {item.quantity} {item.name}(s)"
    db.session.delete(item)
    db.session.commit()
    return redirect(f"/inventory?message={deleted_info}")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
