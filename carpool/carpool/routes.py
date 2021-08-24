from flask import render_template, request, flash, abort, redirect, url_for
from carpool import app, db
from carpool.models import User, Carpool, passengers
from werkzeug.urls import url_parse
from flask_login import login_required, logout_user, current_user, login_user
from carpool.forms import SignupForm, LoginForm, AddCarpoolForm, ChangePassword
from datetime import datetime, timedelta
from pytz import timezone, utc

@app.route("/")
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    carpools = Carpool.get_all().paginate(page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('index', page=carpools.next_num) \
        if carpools.has_next else None
    prev_url = url_for('index', page=carpools.prev_num) \
        if carpools.has_prev else None
    return render_template("index.html", carpools=carpools.items, next_url=next_url, prev_url=prev_url)


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Log in to an account
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    # create form class
    form = LoginForm()
    # if form submits without issues based on validators in class
    if form.validate_on_submit():
        user = User.query.filter_by(name=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password", "error")
            return redirect(url_for("login"))
        login_user(user)
        flash("Login successful", "success")
        return redirect(url_for("index"))
    return render_template("login.html", form=form)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Sign up for an account
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = SignupForm()
    if form.validate_on_submit():
        # check if username exists
        if User.query.filter_by(name=form.name.data).first():
            flash("Username is already taken", "danger")
            return render_template("signup.html", form=form)
        else:
            if User.password_validate(form.password.data):
                # create user object and add it to the DB
                user = User(name=form.name.data, email=form.email.data)
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()
                flash("You have successfully registered!", "success")
                # automatically log-in the user
                login_user(user)
                return redirect(url_for("index"))
            else:
                flash("Password must contain one symbol, one uppercase,\
                      and one digit!", "danger")
                return render_template("signup.html", form=form)
    return render_template("signup.html", form=form)

@login_required
@app.route("/logout", methods=["GET", "POST"])
def logout():
    """
    Log out of an account
    """
    logout_user()
    return redirect(url_for("index"))

@app.route("/carpools/<carpool_id>")
def carpools(carpool_id):
    """
    View a particular carpool by its id
    """
    if current_user.is_authenticated:
        carpool = Carpool.query.filter(Carpool.id == carpool_id).first()
        if not carpool:
            flash("Carpool does not exist", "danger")
            return redirect(url_for("index"))
        return render_template("carpool.html", carpool=carpool)
    return redirect(url_for("login"))

@app.route("/search")
@login_required
def search():
    """
    Search for a user (by username) or carpool (by id)
    """
    if "query" in request.args:
        query = request.args["query"]
    else:
        query = ""
    arrival = Carpool.query.filter(Carpool.from_location.like(f"%{query}%")).all()
    destination = Carpool.query.filter(Carpool.to_location.like(f"%{query}%")).all()
    if len(arrival) == 0 and len(destination) == 0:
        flash("No results found", "danger")
        render_template("search.html")
    return render_template("search.html", query=query, arrival=arrival, destination = destination)

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """
    Add a carpool
    """
    Carpool.check_expired()
    form = AddCarpoolForm()
    if form.validate_on_submit():
        if Carpool.query.filter_by(from_location=form.from_location.data,
                                   to_location = form.to_location.data,
                                   days = ', '.join(form.days.data)).first():
            flash("Carpool already exists", "danger")
            return redirect(url_for("add", form=form))
        else:
            if form.carpool_type.data == 'temporary' and datetime.now() > form.start.data:
                flash("Cannot start a carpool before the current date", "danger")
                return render_template("add.html", form=form)
            startdate = form.start.data
            startdate = startdate.astimezone(utc)
            carpool =  Carpool(name=current_user.name, summary=form.summary.data,
                               from_location=form.from_location.data,
                               to_location=form.to_location.data, creator=current_user,
                               capacity=form.capacity.data, time_created=datetime.utcnow(),
                               start=startdate, carpool_type=form.carpool_type.data,
                               days=', '.join(form.days.data))
            db.session.add(carpool)
            db.session.commit()
            flash("Your carpool has been created!", "success")
            return redirect(url_for("index"))
    return render_template("add.html", form=form)

# TEST CASES
@app.route("/test", methods=["GET", "POST"])
@login_required
def test():
    """
    Add test cases for carpools
    """
    form = AddCarpoolForm()
    if request.method == 'POST':
        Carpool.check_expired()
        # testing manual carpool entries
        startdate = form.start.data
        startdate = startdate.astimezone(utc)
        carpool =  Carpool(name=current_user.name, summary=form.summary.data,
                            from_location=form.from_location.data,
                            to_location=form.to_location.data, creator=current_user,
                            capacity=form.capacity.data, time_created=datetime.utcnow(),
                            start=startdate, carpool_type=form.carpool_type.data,
                            days=', '.join(form.days.data))
        db.session.add(carpool)
        db.session.commit()
        flash("Your carpool has been created!", "success")
        return redirect(url_for("index"))
    return render_template("add.html", form=form)



@app.route("/join/<carpool_id>")
def join(carpool_id):
    """
    Join a carpool
    """
    #check if carpool is expired and delete expired carpools
    deleteFlag, carpoolsExpired, reoccurringExpired = Carpool.check_expired()
    if carpool_id in carpoolsExpired or carpool_id in reoccurringExpired:
        print(f'I am here and the carpool_id was in carpoolsExpired')
        flash("Carpool was expired", 'danger')
        return redirect("/")
    if current_user.is_authenticated:
        carpool = Carpool.query.filter_by(id=carpool_id).first()
        if not carpool:
            flash("Carpool does not exist", "danger")
            return redirect(url_for("index"))
        capacity = carpool.capacity
        quantity = carpool.quantity
        if quantity >= capacity:
            flash("Carpool is full!", "danger")
            return  redirect("/")
        if carpool.creator.id == current_user.id:
            flash("You created this carpool! You cannot join it!", "danger")
            return redirect("/")
        people = db.session.execute("SELECT passengers.user_id FROM passengers\
                                    INNER JOIN Carpool on passengers.carpool_id=:carpool_id",
                                    {"carpool_id":carpool.id})
        for passengers in people:
            if passengers.user_id == current_user.id:
                flash("You are already in this carpool!", "danger")
                return redirect("/")
        current_user.carpools.append(carpool)
        carpool.quantity = int(carpool.quantity) + 1
        db.session.add(current_user)
        db.session.commit()
        flash("You have joined the carpool", "success")
        return redirect("/")
    return redirect(url_for("login"))


@app.route("/delete/<carpool_id>")
def delete(carpool_id):
    """
    Delete a carpool
    """
    if current_user.is_authenticated:
        page = request.referrer
        carpool = Carpool.query.filter_by(id=carpool_id).first()
        if not carpool:
            flash("Carpool does not exist", "danger")
            return redirect(url_for("index"))
        if carpool.creator.id == current_user.id:
            db.session.delete(carpool)
            db.session.commit()
            flash("You have deleted the carpool", "success")
            return redirect(page)
        flash("Cannot delete a carpool you didn't create", "danger")
        return redirect(page)
    return redirect (url_for("login"))


@app.route("/leave/<carpool_id>")
def leave(carpool_id):
    """
    Leave a carpool
    """
    if current_user.is_authenticated:
        carpool = Carpool.query.filter_by(id=carpool_id).first()
        if not carpool:
            flash("Carpool does not exist!", "danger")
            return redirect(url_for("index"))
        people = db.session.execute("SELECT passengers.user_id FROM passengers\
                                    INNER JOIN Carpool on passengers.carpool_id=:carpool_id",
                                    {"carpool_id":carpool.id})
        for passenger in people:
            if passenger.user_id == current_user.id:
                db.session.execute("DELETE FROM passengers WHERE carpool_id=:carpool_id\
                                    AND user_id=:user_id",
                                   {"carpool_id":carpool.id, "user_id":current_user.id})
                carpool.quantity = int(carpool.quantity) - 1
                db.session.commit()
                flash("You have left the carpool", "success")
                return redirect("/")

            else:
                flash("You are not in this carpool!", "danger")
                return redirect("/")
        flash("Unable to leave a carpool you are not currently in", "danger")
        return redirect("/")
    return redirect (url_for("login"))


@app.route("/my_carpools/<user_name>")
def my_carpools(user_name):
    """
    List of created and joined carpools
    """
    if current_user.is_authenticated:
        user_id = db.session.execute("SELECT * FROM User WHERE User.name=:user_name",
                                     {"user_name":user_name}).first()
        if user_id:
            user_id = user_id.id
            # join the carpools and user DB on their many to many relationship table
            carpools = Carpool.query.join(User, Carpool.passengers).filter(User.id==user_id)
            # search all carpools for if the creator id matches the users id
            myCarpools = Carpool.query.filter(Carpool.creator.has(id=user_id)).all()
            return render_template("my_carpools.html", carpools = carpools,
                                   myCarpools = myCarpools, user=user_name)
        flash("User does not exist", "danger")
        return redirect("/")
    return redirect (url_for("login"))


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    """
    Change logged in user's password
    """
    if current_user.is_authenticated:
        form = ChangePassword()
        if form.validate_on_submit():
            user = User.query.filter_by(name=current_user.name).first()
            # check to make sure the user provided their current password
            if user is None or not user.check_password(form.current_password.data):
                flash("Incorrect password", "error")
                return redirect(url_for("change_password"))
            else:
                if password_validate(form.password.data):
                    # set the user's new password and commit it to the DB
                    current_user.set_password(form.password.data)
                    db.session.commit()
                    flash("You have changed your password!", "success")
                    return redirect(url_for("index"))
                else:
                    flash("Password must contain one uppercase, one symbol,\
                          and one digit", "danger")
                    return redirect(url_for("change_password"))
        return render_template("change_password.html", form=form)
    return redirect (url_for("login"))
