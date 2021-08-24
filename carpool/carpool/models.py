from carpool import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from carpool import login_manager
from string import punctuation
from pytz import timezone, utc
from datetime import datetime, timedelta
import calendar


# check these fields with either carpool.passengers or user.carpool
passengers = db.Table(
    "passengers",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("carpool_id", db.Integer, db.ForeignKey("carpool.id")),
)


class Carpool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), index=True)
    summary = db.Column(db.String(128))
    time_created = db.Column(db.DateTime(), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    from_location = db.Column(db.String(32))
    to_location = db.Column(db.String(32))
    quantity = db.Column(db.Integer, default = 0)
    capacity = db.Column(db.Integer)
    start = db.Column(db.DateTime())
    carpool_type = db.Column(db.String(16))
    days = db.Column(db.String(32))

    @staticmethod
    def get_all():
        return Carpool.query.order_by(db.desc(Carpool.time_created))

    @staticmethod
    def check_expired():
        """
        checks to see if any carpools should be deleted
        check reoccurring is a helper function the main function checks temporary carpools
        reoccurring carpools delete after 6 months if no one is in the carpool
        temporary carpools delete after the last valid day for the carpool
        returns status of deletion if a carpool was deleted and 
        carpools_id of deleted carpools to display correct error message
        """
        def check_reoccurring():
            """
            function to check reoccurring carpools and see if they need to be deleted
            returns deleted carpools id
            """
            carpoolsExpired = []
            expired = Carpool.query.filter((Carpool.start + timedelta(days=180)) < datetime.utcnow(), Carpool.carpool_type=='reoccurring', Carpool.quantity==0).all()
            if expired:
                for carpool in expired:
                    carpoolsExpired.append(str(carpool.id))
                    db.session.delete(carpool)
                    db.session.commit()
                    print('deleted reoccurring carpool')
                return (True, carpoolsExpired)
            return (False, carpoolsExpired)
        status, reoccurringExpired = check_reoccurring()
        expired = Carpool.query.filter(Carpool.start < datetime.utcnow(), Carpool.carpool_type=='temporary').all()
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
            carpoolsExpired = []
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
                elif day + dayIncrease > 28 and month != 12 and year == int(datetime.utcnow().year):
                    rng = calendar.monthrange(year, month)
                    if day + dayIncrease > int(rng[1]):
                        newDay = day + dayIncrease
                        newDay -= int(rng[1])
                        maxDate = datetime(year, month + 1, newDay, carpool.start.hour, carpool.start.minute)
                        if maxDate > datetime.utcnow():
                            print(f'second case continue {maxDate}')
                            continue
                # third exception check if carpool is still valid using latest day for the carpool
                elif day + dayIncrease > int(datetime.utcnow().day) and month == int(datetime.utcnow().month) and year == int(datetime.utcnow().year):
                    print(f'testing carpool start date...{carpool.start} {carpool.start.day}')
                    print(f'third case continue, days of the week selected {carpool.days} and dayIncease + day is {dayIncrease} + {day}')
                    continue
            # expire carpools where date exceeds max date for temporary carpool
                print("-----------------------------------")
                print("-----------------------------------")
                print(f'deleted expired {carpool.start}, compared to {datetime.utcnow()}')
                carpoolsExpired.append(str(carpool.id))
                print(f'carpool deletion list is {carpoolsExpired}')
                db.session.delete(carpool)
                db.session.commit()
                deleteFlag = True
            if deleteFlag == True:
                print('returned true because for loop executed and expired carpool didnt meet exceptions')
                return (True, carpoolsExpired, reoccurringExpired)
            else:
                print('had expired db results, but exceptions were met, so exceptions werent deleted')
                return (False, [None], reoccurringExpired)
        print('no db results for queue to select expired')
        return (False, [None], reoccurringExpired)

    def __repr__(self):
        return "<Carpool: {}>".format(self.name)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), index=True, unique=True)
    password = db.Column(
        db.String(200), primary_key=False, unique=False, nullable=False
    )
    email = db.Column(db.String(40), index=True, unique=True, nullable=False)
    carpools = db.relationship(
        "Carpool",
        secondary=passengers,
        primaryjoin=(passengers.c.user_id == id),
        secondaryjoin=(passengers.c.carpool_id == Carpool.id),
        backref=db.backref("passengers", lazy="dynamic"),
        lazy="dynamic",
    )
    # Carpool append users with creator
    created_carpools = db.relationship("Carpool", backref="creator")

    def set_password(self, password):
        """Create hashed password."""
        self.password = generate_password_hash(password, method="sha256")

    @staticmethod
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
        
    
    def check_password(self, password):
        """Check hashed password."""
        return check_password_hash(self.password, password)

    def __repr__(self):
        return "<User: {}>".format(self.name)


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))
