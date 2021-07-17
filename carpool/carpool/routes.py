from flask import render_template, request, flash, abort, redirect, url_for
from carpool import app, db
from carpool.models import User, Carpool, passengers
from werkzeug.urls import url_parse
from flask_login import login_required, logout_user, current_user, login_user
from carpool.forms import SignupForm, LoginForm, AddCarpoolForm, ChangePassword
from datetime import datetime
from string import punctuation
from pytz import timezone, utc
import calendar

def password_validate(password):
    """
    Returns true if password(str) has one digit,
    one symbol, one uppercase
    """
    if type(password) == str:
        has_upper = False
        has_symbol = False
        has_digit = False
        for i in password:
            if i.isupper():
                has_upper = True
            elif i.isdigit():
                has_digit = True
            elif i in punctuation:
                has_symbol = True
        if has_upper and has_symbol and has_digit:
            return True
        return False
    return False

def check_expired():
    #expired = Carpool.query.filter(Carpool.start < datetime.utcnow(), Carpool.carpool_type=='temporary').all()
    expired = Carpool.query.all()
    if expired:
        # helper function to find total days to increase date checked for expiration
        def find_dayIncrease(carpool):
                """
                input is carpool db object
                returns total number of days to increase date by checking days of the week selected from carpool.days to check for expiration 
                """
                # hard coded days of week list and weekday value key : string weekday value
                daysOfWeek = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                dayFinder = {0:'monday', 1:'tuesday', 2:'wednesday', 3:'thursday', 4:'friday', 5:'saturday', 6:'sunday'}
                # find currentDay in string format
                currentDay = int(carpool.start.weekday())
                currentDay = dayFinder[currentDay]
                # rearrange daysOfWeek to have carpool start weekday as first day followed by rest of the weekdays in order
                indexValue = daysOfWeek.index(currentDay)
                daysOfWeek = daysOfWeek[indexValue:] + daysOfWeek[:indexValue]
                # create a list of carpool days selected
                days = carpool.days.replace(" ", "").split(',')
                # if carpool start date day of week is selected carpool ends in 7 days otherwise find farthest weekday value to increase date by
                if dayFinder[carpool.start.weekday()] in days:
                    dayIncrease = 7
                else:
                    dayIncrease = 1
                    for day in days:
                        if day == "":
                            dayIncrease = 0
                        elif daysOfWeek.index(day) > dayIncrease:
                            dayIncrease = daysOfWeek.index(day)
                return dayIncrease

        deleteFlag = False
        for carpool in expired:
            month = int(carpool.start.month)
            year = int(carpool.start.year)
            day = int(carpool.start.day)
            dayIncrease = find_dayIncrease(carpool)
            # first exception check if carpool start date is at the end of Decemeber and make adjustments in case carpool extends into the next year
            if int(datetime.utcnow().month) == 1 and month == 12 and int(datetime.utcnow().year) == year + 1:
                if day + dayIncrease > 31:
                    newDay = day + dayIncrease
                    newDay -= 31
                    newMonth = 1
                    newYear = year + 1
                else:
                    newDay = day + dayIncrease
                    newMonth = 12
                    newYear = year
                maxDate = datetime(newYear, newMonth, newDay, carpool.start.hour, carpool.start.minute)
                if maxDate > datetime.utcnow():
                    print(f'first case continue {maxDate}')
                    continue
            # second exception check if carpool start date is at the end of a month and make adjustment to check against next month date
            elif day + dayIncrease > 28 and month != 12:
                rng = calendar.monthrange(year, month)
                if day + dayIncrease > int(rng[1]):
                    newDay = day + dayIncrease
                    newDay -= int(rng[1])
                    maxDate = datetime(year, month + 1, newDay, carpool.start.hour, carpool.start.minute)
                    if maxDate > datetime.utcnow():
                        print(f'second case continue {maxDate}')
                        continue
            # third exception check if carpool is still valid using latest day for the carpool
            elif day + dayIncrease > int(datetime.utcnow().day):
                print(f'testing carpool start date...{carpool.start} {carpool.start.day}')
                print(f'third case continue, days of the week selected {carpool.days} and dayIncease + day is {dayIncrease} + {day}')
                continue
        # expire carpools where date exceeds max date for temporary carpool
            db.session.delete(carpool)
            db.session.commit()
            deleteFlag = True
            print(f'deleted expired {carpool.start}')
        if deleteFlag == True:
            print('returned true because for loop executed and expired carpool didnt meet exceptions')
            return True
        else:
            print('had expired db results, but exceptions were met, so no deletions were made')
            return False
    print('no db results for queue to select expired')
    return False

@app.route("/")
@login_required
def index():
    return render_template("index.html", carpools=Carpool.get_all())


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
            return redirect(url_for("signup"))
        else:
            if password_validate(form.password.data):
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
                return redirect(url_for("signup"))
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
    check_expired()
    form = AddCarpoolForm()
    # testing manual carpool entries
    if form.validate_on_submit():
        if Carpool.query.filter_by(from_location=form.from_location.data,
                                   to_location = form.to_location.data).first():
            flash("Carpool already exists", "danger")
            return redirect(url_for("add", form=form))
        else:
            if form.carpool_type.data == 'temporary' and datetime.now() > form.start.data:
                flash("Cannot start a carpool before the current date", "danger")
                return redirect(url_for("add", form=form))
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

#TEST CASES
@app.route("/test", methods=["GET", "POST"])
@login_required
def test():
    """
    Add test cases for carpools
    """
    form = AddCarpoolForm()
    if request.method == 'POST':
        check_expired()
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
    if check_expired():
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
