import datetime
import jwt

from flask import Flask
from flask import request
from flask import jsonify
from flask import abort

from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_marshmallow import Marshmallow
from flask_bcrypt import Bcrypt
from flasgger import Swagger

# Import the database configurations by creating a db_config.py file and
# adding the configurations in DB_CONFIG variable
from db_config import DB_CONFIG

app = Flask(__name__)

ma = Marshmallow(app)
swagger = Swagger(app)
bcrypt = Bcrypt(app)

app.config['SQLALCHEMY_DATABASE_URI'] = DB_CONFIG
CORS(app)
db = SQLAlchemy(app)

from model.user import User, UserSchema
from model.transaction import Transaction, TransactionSchema
from model.listing import Listing, ListingSchema


SECRET_KEY = "b'|\xe7\xbfU3`\xc4\xec\xa7\xa9zf:}\xb5\xc7\xb9\x139^3@Dv'"

transaction_schema = TransactionSchema()
transactions_schema = TransactionSchema(many=True)
user_schema = UserSchema()
listing_schema = ListingSchema()


#route to add a listing to the database
@app.route('/listing', methods=['POST'])
def add_listing():
    """ Adds a new User-Transaction.
    ---
    parameters:
      - name : user_phone_number
        in : body
        type : string
        required : true
        example : 78554884
        description : The phone number of the user to transact with
      - name: selling_amount
        in: body
        type : number
        example: 10
        required: true
      - name: buying_amount
        in: body
        type : number
        example: 130000
        required: true
      - name : usd_to_lbp
        in : body
        type : boolean
        example : 1
        required : true
        description : True if transaction is USD to LBP. False otherwise.
      - name : token
        in : header
        type : string
        required : true
        description : A token should be passed if the user is signed in. Not passed otherwise.
    responses:
      200:
        description: The User listing as a json.
      403:
        description : The token is expired or invalid.
    """
    auth_token = extract_auth_token(request)
    user_phone_number = request.json['user_phone_number']
    selling_amount = request.json['selling_amount']
    buying_amount = request.json['buying_amount']
    usd_to_lbp = request.json['usd_to_lbp']

    try: 
        listing = Listing(posting_user_id=decode_token(auth_token) if auth_token else None,
                          user_phone_number=user_phone_number,
                          selling_amount=selling_amount,
                          buying_amount=buying_amount,
                          usd_to_lbp=usd_to_lbp,
                          resolved=False,
                          resolved_by_user=None)
        db.session.add(listing)
        db.session.commit()
    
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        abort(403)
    
    return jsonify(listing_schema.dump(listing))


@app.route('/listings', methods=['GET'])
def get_listings():
    """ Returns all User listings registered by the signed in user.
    ---
    parameters:
      - name: token
        in: header
        type : string
        required: true
        description : The token returned by the backend whenever a certain user signs in.
    responses:
      200:
        description: A JSON of all User listings registered by the signed in user that are not resolved.
      403:
        description : The token passed is invalid or expired.
    """
    # get all the listings that are not resolved
    try:
        listings = Listing.query.filter_by(resolved=False).all()
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        abort(403)

    return jsonify(listing_schema.dump(listings, many=True))
    

@app.route('/transaction', methods=['POST'])
def new_transaction():
    """ Adds a new transaction.
    ---
    parameters:
      - name: usd_amount
        in: body
        type : number
        example: 1
        required: true
      - name: lbp_amount
        in: body
        type : number
        example: 25000
        required: true
      - name : usd_to_lbp
        in : body
        type : boolean
        example : 1
        required : true
        description : True if transaction is USD to LBP. False otherwise.
      - name : token
        in : header
        type : string
        required : false
        description : A token should be passed if the user is signed in. Not passed otherwise.
    responses:
      200:
        description: The transaction added as a json.
      403:
        description : The token passed is invalid or expired..
    """
    auth_token = extract_auth_token(request)

    usd_amount = request.json["usd_amount"]
    lbp_amount = request.json["lbp_amount"]
    usd_to_lbp = request.json["usd_to_lbp"]

    try:
        transaction = Transaction(usd_amount=usd_amount,
                                  lbp_amount=lbp_amount,
                                  usd_to_lbp=usd_to_lbp,
                                  user_id=decode_token(auth_token) if auth_token else None,
                                  )
        db.session.add(transaction)
        db.session.commit()
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        abort(403)

    return jsonify(transaction_schema.dump(transaction))


@app.route('/transaction', methods=['GET'])
def get_user_transactions():
    """ Returns all transactions registered by the signed in user.
    ---
    parameters:
      - name: token
        in: header
        type : string
        required: true
        description : The token present if the user is signed in.
    responses:
      200:
        description: A JSON of all transactions registered
      403:
        description: The token passed is invalid or expired.
    """
    auth_token = extract_auth_token(request)

    if not auth_token:
        abort(403)

    user_id = decode_token(auth_token)
    all_user_transactions = Transaction.query.filter(Transaction.user_id == user_id).all()

    return jsonify(transactions_schema.dump(all_user_transactions))


@app.route('/exchangeRate', methods=['GET'])
def get_rate():
    """ Returns the exchange rates during last 3 days.
        ---
        responses:
          200:
            description: The exchange rate during the last 3 days. It returns both buy (usd_to_lbp) and sell (lbp_to_usd) rates.
        """
    all_usd_to_lbp = Transaction.query.filter(
        Transaction.added_date.between(datetime.datetime.now() - datetime.timedelta(days=3), datetime.datetime.now()),
        Transaction.usd_to_lbp == True).all()
    all_lbp_to_usd = Transaction.query.filter(
        Transaction.added_date.between(datetime.datetime.now() - datetime.timedelta(days=3), datetime.datetime.now()),
        Transaction.usd_to_lbp == False).all()

    AVERAGE_USD_TO_LBP = find_average(all_usd_to_lbp)
    AVERAGE_LBP_TO_USD = find_average(all_lbp_to_usd)

    rate = {
        "usd_to_lbp": AVERAGE_USD_TO_LBP,
        "lbp_to_usd": AVERAGE_LBP_TO_USD
    }

    return jsonify(rate)


@app.route('/user', methods=['POST'])
def new_user():
    """ Creates a new User
    ---
    parameters:
      - name: user_name
        in: body
        type : string
        example: user123
        required: true
      - name: password
        in: body
        type : string
        example: pass123
        required: true
    responses:
      200:
        description: The user as a JSON
      400:
        description : The input is invalid. Make sure you have passed user_name and password.
    """
    user_name = request.json["user_name"]
    password = request.json["password"]

    user = User(user_name=user_name, password=password)

    db.session.add(user)
    db.session.commit()

    return jsonify(user_schema.dump(user))


@app.route('/authentication', methods=['POST'])
def authenticate():
    """ Authenticates user's credentials. Used when a user wants to sign in.
        ---
        parameters:
          - name: user_name
            in: body
            type : string
            example: user123
            required: true
          - name: password
            in: body
            type : string
            example: pass123
            required: true
        responses:
          200:
            description: A token in JSON format.
          400:
            description : The input is invalid. Make sure you have passed the correct user_name and password.
          403:
            description : The user does not exist or the password is wrong.
        """
    user_name = request.json["user_name"]
    password = request.json["password"]

    if user_name is None or password is None or len(user_name) == 0 or len(password) == 0:
        abort(400)

    user = User.query.filter_by(user_name=user_name).first()
    if user is None:
        abort(403)

    if not bcrypt.check_password_hash(user.hashed_password, password):
        abort(403)

    token = create_token(user.id)

    return jsonify(
        {
            "token": token
        }
    )


@app.route('/graph', methods=['GET'])
def get_daily_rate():
    """ Returns the exchange rates during last 10 days.
        ---
        responses:
          200:
            description: The exchange rate during the last 10 days to be plotted in a graph.
        """
    transactions = Transaction.query.all()

    usd_to_lbp_dict = {}
    lbp_to_usd_dict = {}

    # today's date
    today = datetime.datetime.now()
    # adding today and last 10 days to each dictionary
    for i in range(10):
        usd_to_lbp_dict[today.strftime("%Y-%m-%d")] = 0
        lbp_to_usd_dict[today.strftime("%Y-%m-%d")] = 0
        today = today - datetime.timedelta(days=1)

    # function to get the rate of usd_to_lbp transactions of certain day # def get_usd_to_lbp_rate(date):

    # function to get the rate of lbp_to_usd transactions of certain day # def get_lbp_to_usd_rate(date):

    # loop over each key of usd_to_lbp_dict and get the rate of usd_to_lbp transactions of that day
    for key in usd_to_lbp_dict:
        usd_to_lbp_dict[key] = get_usd_to_lbp_rate(key, transactions)

    # loop over each key of lbp_to_usd_dict and get the rate of lbp_to_usd transactions of that day
    for key in lbp_to_usd_dict:
        lbp_to_usd_dict[key] = get_lbp_to_usd_rate(key, transactions)

    return jsonify({'sell': usd_to_lbp_dict, 'buy': lbp_to_usd_dict})


@app.route('/insights', methods=['GET'])  # average, open, close, volume
def get_insights():
    """ Returns insights for the past 14 days.
        ---
        responses:
          200:
            description: Returns dictionaries of the average, open, close, volume (in USD and in Number of Trxs) in JSON format.
        """
    usd_to_lbp_avg = {}  # average sell
    lbp_to_usd_avg = {}  # average buy
    numb = 10

    usd_to_lbp_open = {}  # open sell
    lbp_to_usd_open = {}  # open buy
    usd_to_lbp_close = {}  # close sell
    lbp_to_usd_close = {}  # close buy
    volume_in_trxs = {}  # number of transactions per day in last 2 weeks
    volume_in_usd = {}  # amount of USD transacted with per day in last 2 weeks

    today = datetime.datetime.now()

    transactions = Transaction.query.filter(
        Transaction.added_date.between(datetime.datetime.now() - datetime.timedelta(days=numb),
                                       datetime.datetime.now())).all()
    buy_transactions = Transaction.query.filter(
        Transaction.added_date.between(datetime.datetime.now() - datetime.timedelta(days=numb),datetime.datetime.now()),
        Transaction.usd_to_lbp == 1).all()

    sell_transactions = Transaction.query.filter(
        Transaction.added_date.between(datetime.datetime.now() - datetime.timedelta(days=numb),datetime.datetime.now()),
        Transaction.usd_to_lbp == 0).all()

    for trx in range(len(transactions)):
        usd_to_lbp_avg[today.strftime("%Y-%m-%d")] = 0
        lbp_to_usd_avg[today.strftime("%Y-%m-%d")] = 0

        # usd_to_lbp_open[today.strftime("%Y-%m-%d")] = 0
        # lbp_to_usd_open[today.strftime("%Y-%m-%d")] = 0

        today = today - datetime.timedelta(days=1)

    for trx in range(len(buy_transactions)):
        if trx == 1:
            usd_to_lbp_open[buy_transactions[trx-1].added_date.strftime("%Y-%m-%d")] = buy_transactions[trx-1].lbp_amount / buy_transactions[trx-1].usd_amount
        if buy_transactions[trx].added_date.strftime("%Y-%m-%d") != buy_transactions[trx - 1].added_date.strftime("%Y-%m-%d"):
            usd_to_lbp_open[buy_transactions[trx].added_date.strftime("%Y-%m-%d")] = buy_transactions[trx].lbp_amount / buy_transactions[trx].usd_amount

        if trx == len(buy_transactions) - 1:
            usd_to_lbp_close[buy_transactions[trx].added_date.strftime("%Y-%m-%d")] = buy_transactions[trx].lbp_amount / buy_transactions[trx].usd_amount
            break
        if buy_transactions[trx].added_date.strftime("%Y-%m-%d") != buy_transactions[trx + 1].added_date.strftime("%Y-%m-%d"):
            usd_to_lbp_close[buy_transactions[trx].added_date.strftime("%Y-%m-%d")] = buy_transactions[trx].lbp_amount / buy_transactions[trx].usd_amount

    for trx in range(len(sell_transactions)):
        if trx == 1:
            lbp_to_usd_open[sell_transactions[trx-1].added_date.strftime("%Y-%m-%d")] = sell_transactions[trx-1].lbp_amount / sell_transactions[trx-1].usd_amount
        if sell_transactions[trx].added_date.strftime("%Y-%m-%d") != sell_transactions[trx - 1].added_date.strftime("%Y-%m-%d"):
            lbp_to_usd_open[sell_transactions[trx].added_date.strftime("%Y-%m-%d")] = sell_transactions[trx].lbp_amount / sell_transactions[trx].usd_amount

        if trx == len(sell_transactions) - 1:
            lbp_to_usd_close[sell_transactions[trx].added_date.strftime("%Y-%m-%d")] = sell_transactions[trx].lbp_amount / sell_transactions[trx].usd_amount
            break
        if sell_transactions[trx].added_date.strftime("%Y-%m-%d") != sell_transactions[trx + 1].added_date.strftime("%Y-%m-%d"):
            lbp_to_usd_close[sell_transactions[trx].added_date.strftime("%Y-%m-%d")] = sell_transactions[trx].lbp_amount / sell_transactions[trx].usd_amount

    # loop over each key of usd_to_lbp_dict and get the rate of usd_to_lbp transactions of that day
    for key in usd_to_lbp_avg:
        usd_to_lbp_avg[key] = get_usd_to_lbp_rate(key, transactions)
    for key in lbp_to_usd_avg:
        lbp_to_usd_avg[key] = get_lbp_to_usd_rate(key, transactions)

    today = datetime.datetime.now()

    for i in range(14):  # date in form of "2022-04-24"
        date_to_check = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        trx_on_day = Transaction.query.filter(Transaction.added_date.between(today - datetime.timedelta(days=1), today)).all()

        volume_in_trxs[date_to_check] = len(trx_on_day)

        usd_sum = 0
        for j in trx_on_day:
            usd_sum += j.usd_amount

        volume_in_usd[date_to_check] = usd_sum

        # print(trx_on_day, file=sys.stderr)
        today = today - datetime.timedelta(days=1)

    return jsonify({"usd_to_lbp_avg": usd_to_lbp_avg,
                    "lbp_to_usd_avg": lbp_to_usd_avg,
                    "usd_to_lbp_open": usd_to_lbp_open,
                    "lbp_to_usd_open": lbp_to_usd_open,
                    "usd_to_lbp_close": usd_to_lbp_close,
                    "lbp_to_usd_close": lbp_to_usd_close,
                    "volume_in_trxs": volume_in_trxs,
                    "volume_in_usd": volume_in_usd})


db.create_all()


def find_average(transactions):
    average = 0
    if len(transactions) == 0:
        return None
    else:
        for transaction in transactions:
            average += (transaction.lbp_amount / transaction.usd_amount)
        average /= len(transactions)
    return average


def create_token(user_id):
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=4),
        'iat': datetime.datetime.utcnow(),
        'sub': user_id
    }
    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm='HS256'
    )


def extract_auth_token(authenticated_request):
    auth_header = authenticated_request.headers.get('Authorization')
    if auth_header:
        return auth_header.split(" ")[1]
    else:
        return None


def decode_token(token):
    payload = jwt.decode(token, SECRET_KEY, 'HS256')
    return payload['sub']

def get_usd_to_lbp_rate(date, transactions):
    # returns an array containing the average sell rate for the transactions list passed.
    daily_rate = []
    for i in transactions:
        if i.usd_to_lbp == True and i.added_date.strftime("%Y-%m-%d") == date:
            daily_rate.append(i.lbp_amount / i.usd_amount)
    if len(daily_rate) == 0:
        return 0
    return sum(daily_rate) / len(daily_rate)

def get_lbp_to_usd_rate(date, transactions):
    # returns an array containing the average buy rate for the transactions list passed.
    daily_rate = []
    for i in transactions:
        if i.usd_to_lbp == False and i.added_date.strftime("%Y-%m-%d") == date:
            daily_rate.append(i.lbp_amount / i.usd_amount)
    if len(daily_rate) == 0:
        return 0
    return sum(daily_rate) / len(daily_rate)