from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os, jwt

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret123")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////app/data/toilet.db"
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
JWT_SECRET = os.environ.get('JWT_SECRET', 'sora-jwt-secret-2026')

@app.before_request
def jwt_auth():
    from flask_login import current_user
    if current_user.is_authenticated:
        return
    token = request.cookies.get('sora_token')
    if not token:
        return
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        user = User.query.filter_by(email=payload['email']).first()
        if user:
            login_user(user)
    except Exception:
        pass

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    name = db.Column(db.String(150))

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(50))
    address = db.Column(db.String(200))

class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(50))
    service_type = db.Column(db.String(50))

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"))
    job_type = db.Column(db.String(50))
    desired_date = db.Column(db.String(100))
    status = db.Column(db.String(50), default="未連絡")
    vendor_reply = db.Column(db.Text)
    fax_sent = db.Column(db.Boolean, default=False)
    site_name = db.Column(db.String(200))
    site_address = db.Column(db.String(200))
    toilet_type = db.Column(db.String(50))
    flush_type = db.Column(db.String(50))
    attachment = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.now)
    client = db.relationship("Client", backref="jobs")
    vendor = db.relationship("Vendor", backref="jobs")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
@login_required
def index():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template("index.html", jobs=jobs)

@app.route("/login")
def login():
    next_url = request.args.get('next', request.url)
    return redirect(f'https://auth.sora-chat.shop/login?next={next_url}')

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = User(
            email=request.form["email"],
            name=request.form["name"],
            password=generate_password_hash(request.form["password"])
        )
        db.session.add(user)
        db.session.commit()
        flash("登録完了しました。ログインしてください。")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    logout_user()
    return redirect('https://auth.sora-chat.shop/logout?next=https://toilet.sora-chat.shop/login')

@app.route("/clients")
@login_required
def clients():
    return render_template("clients.html", clients=Client.query.all())

@app.route("/clients/add", methods=["GET", "POST"])
@login_required
def add_client():
    if request.method == "POST":
        db.session.add(Client(
            name=request.form["name"],
            email=request.form["email"],
            phone=request.form["phone"],
            address=request.form["address"]
        ))
        db.session.commit()
        flash("得意先を追加しました")
        return redirect(url_for("clients"))
    return render_template("add_client.html")

@app.route("/vendors")
@login_required
def vendors():
    return render_template("vendors.html", vendors=Vendor.query.all())

@app.route("/vendors/add", methods=["GET", "POST"])
@login_required
def add_vendor():
    if request.method == "POST":
        db.session.add(Vendor(
            name=request.form["name"],
            email=request.form["email"],
            phone=request.form["phone"],
            service_type=request.form["service_type"]
        ))
        db.session.commit()
        flash("業者を追加しました")
        return redirect(url_for("vendors"))
    return render_template("add_vendor.html")

@app.route("/jobs/add", methods=["GET", "POST"])
@login_required
def add_job():
    if request.method == "POST":
        # ファイルアップロード処理（複数対応）
        attachment_path = None
        files = request.files.getlist("attachments")
        saved_files = []
        for file in files:
            if file and file.filename:
                import uuid
                ext = file.filename.rsplit(".", 1)[-1]
                filename = f"{uuid.uuid4().hex}.{ext}"
                os.makedirs("/app/data/uploads", exist_ok=True)
                filepath = f"/app/data/uploads/{filename}"
                file.save(filepath)
                saved_files.append(filepath)
        attachment_path = "|".join(saved_files) if saved_files else None

        job = Job(
            client_id=request.form["client_id"],
            vendor_id=request.form["vendor_id"],
            job_type=request.form["job_type"],
            desired_date=request.form["desired_date"],
            fax_sent="fax_sent" in request.form,
            site_name=request.form.get("site_name", ""),
            site_address=request.form.get("site_address", ""),
            toilet_type=request.form.get("toilet_type", ""),
            flush_type=request.form.get("flush_type", ""),
            attachment=attachment_path
        )
        db.session.add(job)
        db.session.commit()
        if True:  # 設置も含め全種別メール送信
            vendor = Vendor.query.get(job.vendor_id)
            client = Client.query.get(job.client_id)
            mail_user = get_setting("mail_username")
            mail_pass = get_setting("mail_password")
            mail_server = get_setting("mail_server", "smtp.gmail.com")
            mail_port = int(get_setting("mail_port", "587"))
            app.config["MAIL_USERNAME"] = mail_user
            app.config["MAIL_PASSWORD"] = mail_pass
            app.config["MAIL_SERVER"] = mail_server
            app.config["MAIL_PORT"] = mail_port
            app.config["MAIL_USE_TLS"] = True
            if vendor.email and mail_user:
                try:
                    msg = MIMEMultipart()
                    msg["Subject"] = f"【{job.job_type}依頼】{client.name}様"
                    msg["From"] = mail_user
                    msg["To"] = vendor.email
                    body = f"{vendor.name} 御中\n\nお世話になっております。\n\n■依頼内容：{job.job_type}\n■トイレ種別：{job.toilet_type}\n■排水方式：{job.flush_type}\n■得意先：{client.name}\n■現場名：{job.site_name}\n■現場住所：{job.site_address or client.address}\n■希望日時：{job.desired_date}\n\nご確認の上、返答をお願いいたします。"
                    msg.attach(MIMEText(body, "plain", "utf-8"))
                    if attachment_path:
                        import mimetypes
                        from email.mime.base import MIMEBase
                        from email import encoders
                        for fpath in attachment_path.split("|"):
                            ctype, _ = mimetypes.guess_type(fpath)
                            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
                            with open(fpath, "rb") as f:
                                mime = MIMEBase(maintype, subtype)
                                mime.set_payload(f.read())
                                encoders.encode_base64(mime)
                                mime.add_header("Content-Disposition", "attachment", filename=os.path.basename(fpath))
                                msg.attach(mime)
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.ehlo()
                    server.starttls()
                    server.login(mail_user, mail_pass)
                    server.sendmail(mail_user, [vendor.email], msg.as_string())
                    server.quit()
                    job.status = "返答待ち"
                    db.session.commit()
                    flash("業者へメールを送信しました")
                except Exception as e:
                    flash(f"案件を登録しました（エラー：{e}）")
            else:
                flash("案件を登録しました")
        
        return redirect(url_for("index"))
    return render_template("add_job.html", clients=Client.query.all(), vendors=Vendor.query.all())

@app.route("/jobs/<int:job_id>")
@login_required
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    notify_text = f"{job.client.name} 様\n\nいつもお世話になっております。\n以下の通り確定いたしましたのでご連絡いたします。\n\n■内容：{job.job_type}\n■確定日時：{job.vendor_reply}\n\nよろしくお願いいたします。"
    return render_template("job_detail.html", job=job, notify_text=notify_text)

@app.route("/jobs/<int:job_id>/reply", methods=["POST"])
@login_required
def update_reply(job_id):
    job = Job.query.get_or_404(job_id)
    job.vendor_reply = request.form["vendor_reply"]
    job.status = "確定"
    db.session.commit()
    flash("返答を記録しました")
    return redirect(url_for("job_detail", job_id=job_id))


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True)
    value = db.Column(db.String(500))

def get_setting(key, default=""):
    s = Setting.query.filter_by(key=key).first()
    return s.value if s else default

def save_setting(key, value):
    s = Setting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        db.session.add(Setting(key=key, value=value))

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        for key in ["mail_server", "mail_port", "mail_username", "mail_password", "mail_use_tls"]:
            save_setting(key, request.form.get(key, ""))
        db.session.commit()
        app.config["MAIL_SERVER"] = request.form.get("mail_server", "smtp.gmail.com")
        app.config["MAIL_PORT"] = int(request.form.get("mail_port", 587))
        app.config["MAIL_USERNAME"] = request.form.get("mail_username", "")
        app.config["MAIL_PASSWORD"] = request.form.get("mail_password", "")
        app.config["MAIL_USE_TLS"] = request.form.get("mail_use_tls", "on") == "on"
        flash("設定を保存しました")
        return redirect(url_for("settings"))
    return render_template("settings.html",
        mail_server=get_setting("mail_server", "smtp.gmail.com"),
        mail_port=get_setting("mail_port", "587"),
        mail_username=get_setting("mail_username", ""),
        mail_password=get_setting("mail_password", ""),
        mail_use_tls=get_setting("mail_use_tls", "on")
    )

if __name__ == "__main__":
    with app.app_context():
        os.makedirs("/app/data", exist_ok=True)
        db.create_all()
    # DBから設定を読み込んでMailに反映
    with app.app_context():
        try:
            s_server = Setting.query.filter_by(key="mail_server").first()
            s_port = Setting.query.filter_by(key="mail_port").first()
            s_user = Setting.query.filter_by(key="mail_username").first()
            s_pass = Setting.query.filter_by(key="mail_password").first()
            if s_user: app.config["MAIL_USERNAME"] = s_user.value
            if s_pass: app.config["MAIL_PASSWORD"] = s_pass.value
            if s_server: app.config["MAIL_SERVER"] = s_server.value
            if s_port: app.config["MAIL_PORT"] = int(s_port.value)
        except:
            pass
    app.run(host="0.0.0.0", port=5000)

import hmac, hashlib, time, base64

AUTO_LOGIN_SECRET = 'sora-autotoken-2026'

@app.route('/auto_login/<path:token>')
@app.route('/auto_login/<path:token>')
def auto_login(token):
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return redirect(url_for('login'))
        email, expiry, sig = parts
        expected = hmac.new(
            AUTO_LOGIN_SECRET.encode(),
            f"{email}.{expiry}".encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        if sig != expected or int(expiry) < int(time.time()):
            flash('リンクが無効または期限切れです')
            return redirect(url_for('login'))
        user = User.query.filter_by(email=email).first()
        if not user:
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('index'))
    except:
        return redirect(url_for('login'))
